"""Automatic microphone testing, audio device diagnostics, classification, and automatic recovery."""

from __future__ import annotations

from datetime import datetime, timezone
import math
import re
import sys
import threading
from typing import Any


_VIRTUAL_KEYWORDS = (
    "voicemeeter",
    "virtual",
    "vb-audio",
    "vb-cable",
    "cable output",
    "cable input",
    "loopback",
    "wasapi mix",
    "stereo mix",
    "what u hear",
    "wave out mix",
    "microsoft sound mapper",
    "primary sound capture",
    "pc speaker",
    "obs ",
    "krisp",
    "nvidia broadcast",
    "sonar",
    "steam streaming",
)
_BLUETOOTH_KEYWORDS = (
    "bluetooth",
    "bthhfenum",
    "hands-free",
    "handsfree",
    "hf audio",
    "hfp",
    "a2dp",
    "bt ",
    "airpods",
    "galaxy buds",
    "headset",
    "wireless",
)
_USB_KEYWORDS = (
    "usb",
    "usb-audio",
    "usb mic",
    "usb microphone",
    "usb pnp",
    "yeti",
    "shure",
    "fifine",
    "hyperx",
    "rode",
    "elgato",
    "webcam",
    "cam mic",
    "focusrite",
    "scarlett",
)
_INTEGRATED_KEYWORDS = (
    "microphone array",
    "digital mic",
    "smart sound",
    "intel",
    "realtek",
    "conexant",
    "amd audio",
    "high definition audio",
    "internal",
    "built-in",
    "integrated",
    "laptop",
    "array",
)

_TYPE_PRIORITY = {
    "usb": 0,
    "bluetooth": 1,
    "integrated": 2,
    "unknown": 3,
    "virtual": 4,
}

_HOSTAPI_PRIORITY = {
    "Windows WASAPI": 0,
    "MME": 1,
    "Windows DirectSound": 2,
    "ASIO": 3,
    "Windows WDM-KS": 5,
}

_BTH_MODEL_RE = re.compile(r";\(([^)]+)\)\)?\s*$")


def clean_device_display_name(raw_name: str, hostapi_name: str = "") -> str:
    """Turn raw PortAudio / Windows driver strings into concise, readable names."""
    cleaned = " ".join(str(raw_name).replace("\r", " ").replace("\n", " ").split()).strip()
    if "bthhfenum.sys" in cleaned.lower():
        m = _BTH_MODEL_RE.search(cleaned)
        model = m.group(1).strip() if m else "Bluetooth Headset"
        cleaned = f"{model} (Bluetooth Hands-Free)"
    if hostapi_name:
        short_api = hostapi_name.replace("Windows ", "")
        return f"{cleaned} ({short_api})"
    return cleaned


def classify_device_type(name: str, hostapi_name: str = "") -> str:
    """Return one of: 'usb', 'bluetooth', 'virtual', 'integrated', 'unknown'."""
    lower = f"{name} {hostapi_name}".lower()
    if any(k in lower for k in _VIRTUAL_KEYWORDS):
        return "virtual"
    if any(k in lower for k in _USB_KEYWORDS):
        return "usb"
    if any(k in lower for k in _BLUETOOTH_KEYWORDS):
        return "bluetooth"
    if any(k in lower for k in _INTEGRATED_KEYWORDS):
        return "integrated"
    return "unknown"


def check_windows_mic_permission() -> dict[str, Any]:
    """Read Windows CapabilityAccessManager microphone consent status safely."""
    if sys.platform != "win32":
        return {
            "granted": True,
            "status": "allowed",
            "desktop_apps_allowed": True,
            "settings_uri": "ms-settings:privacy-microphone",
            "detail": "Non-Windows host assumed permitted.",
        }
    try:
        import winreg  # noqa: PLC0415

        global_val = "Allow"
        non_packaged_val = "Allow"
        base = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as key:
            val, _ = winreg.QueryValueEx(key, "Value")
            global_val = str(val)
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{base}\\NonPackaged") as np_key:
                np_val, _ = winreg.QueryValueEx(np_key, "Value")
                non_packaged_val = str(np_val)
        except OSError:
            non_packaged_val = global_val

        granted = global_val.lower() == "allow" and non_packaged_val.lower() == "allow"
        return {
            "granted": granted,
            "status": "allowed" if granted else "denied",
            "desktop_apps_allowed": non_packaged_val.lower() == "allow",
            "settings_uri": "ms-settings:privacy-microphone",
            "detail": (
                "Windows Microphone permission is enabled for desktop apps."
                if granted
                else "Windows Microphone privacy toggle is Deny. Enable in Settings -> Privacy -> Microphone."
            ),
        }
    except Exception as exc:
        return {
            "granted": True,
            "status": "unknown",
            "desktop_apps_allowed": True,
            "settings_uri": "ms-settings:privacy-microphone",
            "detail": f"Registry permission lookup skipped: {exc}",
        }


def _is_usable_hostapi(hostapi_name: str) -> bool:
    return "WDM-KS" not in hostapi_name


def _device_selection_key(device: dict[str, Any]) -> tuple[int, int, int, int, int]:
    usable = bool(device.get("usable", True))
    dev_type = str(device.get("device_type", "unknown"))
    hostapi = str(device.get("hostapi", ""))
    is_default = bool(device.get("is_default", False))
    idx = int(device.get("index", 999))
    return (
        0 if usable else 1,
        _TYPE_PRIORITY.get(dev_type, 3),
        _HOSTAPI_PRIORITY.get(hostapi, 4),
        0 if is_default else 1,
        idx,
    )


def auto_select_best_microphone(devices: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select the highest-priority input device (Usable HostAPI first, then USB > BT > Integrated > Virtual)."""
    if not devices:
        return None
    return min(devices, key=_device_selection_key)


def _rms_to_db_and_percent(rms: float, peak: float) -> tuple[float, int]:
    if rms <= 1e-6 and peak <= 1e-6:
        return -90.0, 0
    db = max(-90.0, min(0.0, 20.0 * math.log10(max(rms, 1e-6))))
    pct = max(0, min(100, int(round(((db + 75.0) / 75.0) * 100.0))))
    if peak > 1e-5 and pct == 0:
        pct = 2
    return round(db, 1), pct


def _classify_signal_quality(rms: float, peak: float, device_opened: bool = True) -> str:
    if not device_opened:
        return "unavailable"
    if rms > 0.92 or peak >= 0.995:
        return "clipping"
    if rms >= 0.0015 or peak >= 0.01:
        return "ok"
    if peak > 1e-6:
        return "quiet_ready"
    return "muted"


def probe_device_sample_rate(device_index: int) -> int:
    """Return the default sample rate for *device_index*."""
    try:
        import sounddevice as sd  # noqa: PLC0415

        return int(sd.query_devices(device_index).get("default_samplerate", 16000))
    except Exception:
        return 16000


def probe_device_capture(
    device_index: int,
    duration_sec: float = 0.35,
    preferred_sample_rate: int | None = None,
) -> dict[str, Any]:
    """Safely capture a short burst via InputStream (discarding warmup block) and measure RMS/Peak."""
    try:
        import numpy as np  # noqa: PLC0415
        import sounddevice as sd  # noqa: PLC0415

        dev = sd.query_devices(device_index)
        hostapis = list(sd.query_hostapis())
        host_idx = int(dev.get("hostapi", 0))
        hostapi_name = hostapis[host_idx]["name"] if 0 <= host_idx < len(hostapis) else ""
        if not _is_usable_hostapi(hostapi_name):
            return {
                "device_opened": False,
                "rms_level": 0.0,
                "peak_level": 0.0,
                "db_level": -90.0,
                "volume_percent": 0,
                "used_sample_rate": int(dev.get("default_samplerate", 16000)),
                "error": f"{hostapi_name} blocking capture not supported; select WASAPI/MME device.",
            }

        max_ch = max(1, int(dev.get("max_input_channels", 1)))
        def_sr = int(dev.get("default_samplerate", 16000))
        rates = [r for r in (preferred_sample_rate, def_sr, 48000, 44100, 16000) if r and r > 0]
        last_err = "Could not open input stream."

        for sr in dict.fromkeys(rates):
            blocksize = max(256, min(2048, int(sr * 0.04)))
            n_reads = max(4, int(math.ceil((sr * duration_sec) / blocksize)) + 1)
            for ch in (1, min(2, max_ch)):
                for dtype in ("float32", "int16"):
                    try:
                        frames: list[Any] = []
                        with sd.InputStream(
                            device=device_index,
                            channels=ch,
                            samplerate=sr,
                            dtype=dtype,
                            blocksize=blocksize,
                        ) as stream:
                            for _ in range(n_reads):
                                data, _overflow = stream.read(blocksize)
                                frames.append(data.copy())
                        usable_frames = frames[1:] if len(frames) > 1 else frames
                        arr = np.concatenate(usable_frames).astype(np.float32)
                        if dtype == "int16":
                            arr = arr / 32768.0
                        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
                        rms = round(float(np.sqrt(np.mean(np.square(arr)))), 6)
                        peak = round(float(np.max(np.abs(arr))), 6)
                        db, pct = _rms_to_db_and_percent(rms, peak)
                        return {
                            "device_opened": True,
                            "rms_level": rms,
                            "peak_level": peak,
                            "db_level": db,
                            "volume_percent": pct,
                            "used_sample_rate": int(sr),
                            "error": None,
                        }
                    except Exception as exc:
                        last_err = str(exc)
        return {
            "device_opened": False,
            "rms_level": 0.0,
            "peak_level": 0.0,
            "db_level": -90.0,
            "volume_percent": 0,
            "used_sample_rate": def_sr,
            "error": last_err,
        }
    except Exception as exc:
        return {
            "device_opened": False,
            "rms_level": 0.0,
            "peak_level": 0.0,
            "db_level": -90.0,
            "volume_percent": 0,
            "used_sample_rate": 16000,
            "error": str(exc),
        }


def probe_device_rms(device_index: int, duration_sec: float = 0.35, sample_rate: int | None = None) -> float:
    """Record a short burst from the device and return the RMS amplitude level."""
    return float(
        probe_device_capture(
            device_index=device_index,
            duration_sec=duration_sec,
            preferred_sample_rate=sample_rate,
        )["rms_level"]
    )


def _probe_supported_rates(device_index: int, default_sr: int, channels: int) -> tuple[bool, list[int]]:
    supported: list[int] = []
    candidates = list(dict.fromkeys([r for r in (int(default_sr), 48000, 44100, 16000, 8000) if r > 0]))
    try:
        import sounddevice as sd  # noqa: PLC0415

        for rate in candidates:
            for ch in (1, min(2, max(1, channels))):
                try:
                    sd.check_input_settings(device=device_index, channels=ch, samplerate=rate)
                    supported.append(rate)
                    break
                except Exception:
                    continue
        if not supported:
            return False, [int(default_sr)]
        return True, supported
    except Exception:
        return True, [int(default_sr) or 16000]


def _enumerate_devices() -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    try:
        import sounddevice as sd  # noqa: PLC0415

        hostapis = list(sd.query_hostapis())
        default_in = None
        default_out = None
        try:
            default_in = sd.default.device[0]
            default_out = sd.default.device[1]
        except Exception:
            pass

        for idx, dev in enumerate(sd.query_devices()):
            name = str(dev.get("name", f"Device {idx}"))
            sample_rate = int(dev.get("default_samplerate", 16000))
            host_idx = int(dev.get("hostapi", 0))
            hostapi_name = hostapis[host_idx]["name"] if 0 <= host_idx < len(hostapis) else "Unknown"
            max_in = int(dev.get("max_input_channels", 0))
            max_out = int(dev.get("max_output_channels", 0))

            if max_in > 0:
                dev_type = classify_device_type(name, hostapi_name)
                usable_api = _is_usable_hostapi(hostapi_name)
                chk_ok, sup_rates = (
                    _probe_supported_rates(idx, sample_rate, max_in)
                    if usable_api
                    else (False, [sample_rate])
                )
                usable = usable_api and chk_ok
                inputs.append(
                    {
                        "index": idx,
                        "name": name,
                        "display_name": clean_device_display_name(name, hostapi_name),
                        "device_type": dev_type,
                        "hostapi": hostapi_name,
                        "default_samplerate": sample_rate,
                        "supported_sample_rates": sup_rates,
                        "driver_status": f"Available ({hostapi_name})" if usable else f"Standby ({hostapi_name})",
                        "usable": usable,
                        "is_default": idx == default_in,
                        "is_selected": False,
                    }
                )
            if max_out > 0:
                outputs.append(
                    {
                        "index": idx,
                        "name": name,
                        "display_name": clean_device_display_name(name, hostapi_name),
                        "default_samplerate": sample_rate,
                    }
                )
        inputs.sort(key=_device_selection_key)
        return inputs, outputs, None
    except Exception as exc:
        return [], [], str(exc)


class AudioDiagnosticsManager:
    """Thread-safe stateful microphone diagnostics & recovery coordinator for ecosystem backend."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.selected_device_index: int | None = None
        self.selected_device_name: str | None = None
        self.manual_selection: bool = False
        self.last_test_result: dict[str, Any] | None = None

    def discover(self, *, test_samples: list[float] | None = None) -> dict[str, Any]:
        with self._lock:
            inputs, outputs, sub_err = _enumerate_devices()
            perm = check_windows_mic_permission()
            issues: list[str] = []
            guidance: list[str] = []

            if sub_err:
                issues.append(f"Audio subsystem probe unavailable: {sub_err}")
                guidance.append(
                    "Verify Windows Audio service (`Audiosrv`) and microphone driver installation."
                )
            if not perm.get("granted", True):
                issues.append(perm["detail"])
                guidance.append(
                    "Enable Microphone access under Windows Settings -> Privacy & security -> Microphone."
                )
            if not inputs:
                issues.append("No active microphone input devices detected.")
                guidance.append(
                    "Enable Microphone access under Windows Settings -> Privacy & security -> Microphone, "
                    "and plug in or unmute your mic."
                )
            if not outputs:
                issues.append("No speaker or audio output devices detected.")
                guidance.append("Verify default playback device in Windows Sound settings.")

            active: dict[str, Any] | None = None
            if self.selected_device_index is not None:
                active = next((d for d in inputs if d["index"] == self.selected_device_index), None)
                if active is None and self.selected_device_name:
                    active = next((d for d in inputs if d["name"] == self.selected_device_name), None)
            if active is None or (not self.manual_selection and not active.get("usable", True)):
                active = auto_select_best_microphone(inputs)
                if active is not None:
                    self.selected_device_index = active["index"]
                    self.selected_device_name = active["name"]
                    self.manual_selection = False
            elif active is not None:
                self.selected_device_index = active["index"]

            for d in inputs:
                d["is_selected"] = active is not None and d["index"] == active["index"]

            best_device = auto_select_best_microphone(inputs)

            rms_level: float | None = None
            if test_samples:
                rms_level = round(
                    math.sqrt(sum(float(x) * float(x) for x in test_samples) / len(test_samples)),
                    6,
                )
                peak = max(abs(float(x)) for x in test_samples)
                db, pct = _rms_to_db_and_percent(rms_level, peak)
                qual = _classify_signal_quality(rms_level, peak, device_opened=True)
                self.last_test_result = {
                    "rms_level": rms_level,
                    "peak_level": round(peak, 6),
                    "db_level": db,
                    "volume_percent": pct,
                    "signal_quality": qual,
                    "tested_at": datetime.now(timezone.utc).isoformat(),
                }
                if rms_level < 0.005:
                    issues.append(
                        "Captured microphone level is near zero (possible mute or wrong input gain)."
                    )
                    guidance.append(
                        "Increase Windows microphone input volume above 65% and verify hardware mute switch."
                    )
                elif rms_level > 0.96:
                    issues.append("Microphone signal clipping detected.")
                    guidance.append("Reduce mic boost or speak further from the microphone.")

            if not issues:
                guidance.append("Microphone and output devices look healthy for continuous listening.")

            usable_inputs = [d for d in inputs if d.get("usable", True)]
            mic_available = bool(inputs) and (bool(usable_inputs) or active is not None)
            return {
                "mic_available": mic_available,
                "mic_status": "CONNECTED" if mic_available else "NOT FOUND",
                "speaker_available": bool(outputs),
                "mic_count": len(inputs),
                "speaker_count": len(outputs),
                "permission": perm,
                "input_devices": inputs[:24],
                "output_devices": outputs[:12],
                "best_device": active or best_device,
                "active_device": active,
                "active_device_index": active["index"] if active else None,
                "active_device_name": active["display_name"] if active else "None",
                "rms_level": rms_level,
                "last_test_result": self.last_test_result,
                "health_status": "healthy" if not issues else "attention_needed",
                "issues_detected": issues,
                "repair_guidance": guidance,
            }

    def change_microphone(self, device_index: int) -> dict[str, Any]:
        with self._lock:
            inputs, _outputs, err = _enumerate_devices()
            if err:
                return {"status": "error", "active_device_index": device_index, "error": err}
            target = next((d for d in inputs if d["index"] == device_index), None)
            if target is None:
                return {
                    "status": "error",
                    "active_device_index": device_index,
                    "error": f"Device index {device_index} not found or not an input device.",
                }
            self.selected_device_index = target["index"]
            self.selected_device_name = target["name"]
            self.manual_selection = True
        snap = self.discover()
        return {
            **snap,
            "status": "changed",
            "active_device_index": target["index"],
            "active_device_name": target["display_name"],
            "device_type": target["device_type"],
        }

    def test_microphone(
        self,
        *,
        device_index: int | None = None,
        samples: list[float] | None = None,
    ) -> dict[str, Any]:
        if samples:
            snap = self.discover(test_samples=samples)
            last = snap.get("last_test_result") or {}
            return {
                "rms_level": last.get("rms_level", 0.0),
                "peak_level": last.get("peak_level", 0.0),
                "db_level": last.get("db_level", -90.0),
                "volume_percent": last.get("volume_percent", 0),
                "signal_quality": last.get("signal_quality", "ok"),
                "device_opened": True,
                "mic_available": snap["mic_available"],
                "best_device": snap.get("active_device") or snap.get("best_device"),
                "issues": snap.get("issues_detected", []),
                "guidance": snap.get("repair_guidance", []),
            }

        snap = self.discover()
        target = (
            next((d for d in snap["input_devices"] if d["index"] == device_index), None)
            if device_index is not None
            else (snap.get("active_device") or snap.get("best_device"))
        )
        if target is None:
            return {
                "rms_level": 0.0,
                "peak_level": 0.0,
                "db_level": -90.0,
                "volume_percent": 0,
                "signal_quality": "unavailable",
                "device_opened": False,
                "mic_available": False,
                "best_device": None,
                "issues": snap.get("issues_detected", ["No active microphone detected."]),
                "guidance": snap.get("repair_guidance", []),
            }

        cap = probe_device_capture(
            device_index=target["index"],
            duration_sec=0.35,
            preferred_sample_rate=target.get("default_samplerate"),
        )
        rms = float(cap["rms_level"])
        peak = float(cap["peak_level"])
        opened = bool(cap["device_opened"])
        qual = _classify_signal_quality(rms, peak, device_opened=opened)
        with self._lock:
            self.last_test_result = {
                "rms_level": rms,
                "peak_level": peak,
                "db_level": cap["db_level"],
                "volume_percent": cap["volume_percent"],
                "used_sample_rate": cap["used_sample_rate"],
                "signal_quality": qual,
                "device_opened": opened,
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }

        issues = list(snap.get("issues_detected", []))
        guidance = list(snap.get("repair_guidance", []))
        if cap.get("error"):
            issues.append(str(cap["error"]))
        elif qual == "muted":
            issues.append("Microphone signal is zero (hardware mute or disabled input).")

        return {
            "rms_level": rms,
            "peak_level": peak,
            "db_level": cap["db_level"],
            "volume_percent": cap["volume_percent"],
            "used_sample_rate": cap["used_sample_rate"],
            "signal_quality": qual,
            "device_opened": opened,
            "mic_available": snap["mic_available"] and opened,
            "best_device": target,
            "issues": issues,
            "guidance": guidance,
        }

    def recover(self) -> dict[str, Any]:
        """Automatic recovery: rescan -> reinitialize PortAudio -> try alternates -> reconnect default."""
        steps: list[str] = ["1. Rescanning audio endpoints..."]
        try:
            import sounddevice as sd  # noqa: PLC0415

            steps.append("2. Reinitializing audio subsystem...")
            try:
                sd._terminate()  # noqa: SLF001  # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                sd._initialize()  # noqa: SLF001  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception as exc:
            return {
                "status": "no_devices",
                "mic_status": "MIC: NOT FOUND",
                "device": None,
                "steps_attempted": steps,
                "error": str(exc),
            }

        with self._lock:
            self.manual_selection = False
            self.selected_device_index = None

        inputs, _outputs, err = _enumerate_devices()
        if err or not inputs:
            return {
                "status": "no_devices",
                "mic_status": "MIC: NOT FOUND",
                "device": None,
                "steps_attempted": steps + ["No input devices detected after rescan."],
                "error": err or "No input devices found after rescan.",
            }

        steps.append(f"3. Trying alternate microphones ({len(inputs)} found)...")
        usable_candidates = [d for d in inputs if d.get("usable", True)]
        chosen: dict[str, Any] | None = None
        for cand in usable_candidates:
            cap = probe_device_capture(
                device_index=cand["index"],
                duration_sec=0.18,
                preferred_sample_rate=cand.get("default_samplerate"),
            )
            if cap["device_opened"]:
                chosen = cand
                steps.append(f"4. Connected '{cand['display_name']}' ({cap['used_sample_rate']} Hz).")
                break

        if chosen is None:
            chosen = auto_select_best_microphone(inputs)
            if chosen is None or not chosen.get("usable", False):
                return {
                    "status": "no_devices",
                    "mic_status": "MIC: NOT FOUND",
                    "device": None,
                    "steps_attempted": steps + ["No openable microphone responded."],
                    "error": "No openable microphone found.",
                }
            steps.append(f"4. Reconnected default device '{chosen['display_name']}'.")

        with self._lock:
            self.selected_device_index = chosen["index"]
            self.selected_device_name = chosen["name"]
            self.manual_selection = True
        return {
            "status": "recovered",
            "mic_status": "MIC: CONNECTED",
            "device": chosen,
            "steps_attempted": steps,
        }


_DEFAULT_MANAGER = AudioDiagnosticsManager()


def get_diagnostics_manager() -> AudioDiagnosticsManager:
    return _DEFAULT_MANAGER


def reinitialize_audio_subsystem() -> dict[str, Any]:
    """Rescan audio devices, try alternates, and return recovery status."""
    return _DEFAULT_MANAGER.recover()


def diagnose_audio_devices(test_samples: list[float] | None = None) -> dict[str, Any]:
    """Inspect available audio input/output devices and optionally test live mic frame levels."""
    return _DEFAULT_MANAGER.discover(test_samples=test_samples)
