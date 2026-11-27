"""System resource and hardware readiness telemetry via psutil and WinMM."""

from __future__ import annotations

import ctypes
import os
import sys
import time
from typing import Any

import psutil


def probe_audio_devices() -> dict[str, Any]:
    """Check audio input/output device counts without activating microphone capture."""
    if sys.platform != "win32":
        return {"mic_available": False, "speaker_available": False, "mic_count": 0, "speaker_count": 0}
    try:
        winmm = ctypes.windll.winmm
        mic_count = int(winmm.waveInGetNumDevs())
        spk_count = int(winmm.waveOutGetNumDevs())
        return {
            "mic_available": mic_count > 0,
            "speaker_available": spk_count > 0,
            "mic_count": mic_count,
            "speaker_count": spk_count,
        }
    except Exception:
        return {"mic_available": False, "speaker_available": False, "mic_count": 0, "speaker_count": 0}


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
