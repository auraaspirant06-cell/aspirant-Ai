"""System resource and hardware readiness telemetry via psutil, WinMM, and sounddevice."""

from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
from typing import Any

import psutil

from aspirant.voice.diagnostics import get_diagnostics_manager


_CACHE_LOCK = threading.Lock()
_AUDIO_CACHE: dict[str, Any] = {}
_AUDIO_CACHE_AT: float = 0.0
_AUDIO_CACHE_TTL_SEC = 4.0


def invalidate_audio_cache() -> None:
    """Force the next telemetry probe to refresh microphone/speaker hardware metadata."""
    global _AUDIO_CACHE_AT
    with _CACHE_LOCK:
        _AUDIO_CACHE_AT = 0.0


def probe_audio_devices(*, force_refresh: bool = False) -> dict[str, Any]:
    """Check audio input/output devices & active mic without activating microphone capture."""
    global _AUDIO_CACHE, _AUDIO_CACHE_AT
    now = time.monotonic()
    with _CACHE_LOCK:
        if not force_refresh and _AUDIO_CACHE and (now - _AUDIO_CACHE_AT) < _AUDIO_CACHE_TTL_SEC:
            return dict(_AUDIO_CACHE)

    mgr = get_diagnostics_manager()
    try:
        diag = mgr.discover()
        active = diag.get("active_device") or diag.get("best_device") or {}
        payload: dict[str, Any] = {
            "mic_available": bool(diag.get("mic_available", False)),
            "speaker_available": bool(diag.get("speaker_available", False)),
            "mic_count": int(diag.get("mic_count", 0)),
            "speaker_count": int(diag.get("speaker_count", 0)),
            "mic_status": diag.get("mic_status", "NOT FOUND"),
            "active_device_index": diag.get("active_device_index"),
            "active_device_name": active.get("display_name") or active.get("name") or "None",
            "active_device_type": active.get("device_type", "unknown"),
            "driver_status": active.get("driver_status", "Unavailable"),
            "sample_rate": int(active.get("default_samplerate", 16000)) if active else 0,
            "permission_granted": bool(diag.get("permission", {}).get("granted", True)),
            "issues_detected": diag.get("issues_detected", []),
        }
    except Exception:
        if sys.platform == "win32":
            try:
                winmm = ctypes.windll.winmm
                mic_count = int(winmm.waveInGetNumDevs())
                spk_count = int(winmm.waveOutGetNumDevs())
            except Exception:
                mic_count, spk_count = 0, 0
        else:
            mic_count, spk_count = 0, 0
        payload = {
            "mic_available": mic_count > 0,
            "speaker_available": spk_count > 0,
            "mic_count": mic_count,
            "speaker_count": spk_count,
            "mic_status": "CONNECTED" if mic_count > 0 else "NOT FOUND",
            "active_device_index": None,
            "active_device_name": "Windows Default" if mic_count > 0 else "None",
            "active_device_type": "unknown",
            "driver_status": "WinMM fallback",
            "sample_rate": 16000 if mic_count > 0 else 0,
            "permission_granted": True,
            "issues_detected": [],
        }

    with _CACHE_LOCK:
        _AUDIO_CACHE = payload
        _AUDIO_CACHE_AT = time.monotonic()
    return dict(payload)


class TelemetryCollector:
    """Samples CPU, RAM, disk, network throughput, and Aspirant process footprint."""

    def __init__(self, drive_root: str = "C:\\") -> None:
        self._drive_root = drive_root
        self._process = psutil.Process(os.getpid())
        self._last_net = psutil.net_io_counters()
        self._last_time = time.monotonic()
        # Prime non-blocking CPU percent baseline
        psutil.cpu_percent(interval=None)

    def snapshot(self) -> dict[str, Any]:
        """Collect a fast, non-blocking snapshot of host and app metrics."""
        now = time.monotonic()
        elapsed = max(0.1, now - self._last_time)
        net = psutil.net_io_counters()
        rx_kbps = max(0.0, (net.bytes_recv - self._last_net.bytes_recv) / elapsed / 1024.0)
        tx_kbps = max(0.0, (net.bytes_sent - self._last_net.bytes_sent) / elapsed / 1024.0)
        self._last_net = net
        self._last_time = now

        vm = psutil.virtual_memory()
        disk = psutil.disk_usage(self._drive_root)
        proc_mem_mb = round(self._process.memory_info().rss / (1024 * 1024), 1)
        audio = probe_audio_devices()

        return {
            "cpu_percent": round(psutil.cpu_percent(interval=None), 1),
            "cpu_cores": psutil.cpu_count(logical=False) or 0,
            "cpu_threads": psutil.cpu_count(logical=True) or 0,
            "ram_percent": round(vm.percent, 1),
            "ram_used_mb": round(vm.used / (1024 * 1024), 0),
            "ram_available_mb": round(vm.available / (1024 * 1024), 0),
            "ram_total_mb": round(vm.total / (1024 * 1024), 0),
            "app_ram_mb": proc_mem_mb,
            "disk_free_gb": round(disk.free / (1024 ** 3), 2),
            "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            "disk_percent": round(disk.percent, 1),
            "net_rx_kbps": round(rx_kbps, 1),
            "net_tx_kbps": round(tx_kbps, 1),
            "audio": audio,
        }
