"""What this computer can run: its graphics cards and memory, read locally.

Used to suggest a cover letter model that fits. Nothing is sent anywhere, and a
part that can't be read is left out rather than guessed.
"""
from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import sys

GIB = 1024 ** 3
# Windows lists every display adapter here; HardwareInformation.qwMemorySize is its own graphics memory.
DISPLAY_ADAPTERS = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)   # no console flash from the windowed app


def scan() -> dict:
    """{'gpus': [{'name', 'vram', 'usable'}], 'ram': bytes, 'unified': bool}."""
    found = (_windows_adapters() or _nvidia()) if sys.platform == "win32" else _nvidia()
    gpus = [{**gpu, "usable": usable(gpu["name"])} for gpu in found if gpu["vram"] >= GIB]   # drops virtual monitors
    return {"gpus": gpus, "ram": _ram(), "unified": sys.platform == "darwin" and platform.machine() == "arm64"}


def usable(name: str) -> bool:
    """Ollama runs models on NVIDIA and AMD cards; Intel and the rest leave the work to the processor."""
    return any(word in name.lower() for word in ("nvidia", "geforce", "quadro", "tesla", "rtx", "amd", "radeon"))


def parse_nvidia(text: str) -> list[dict]:
    """nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits → one card per line, MiB."""
    gpus = []
    for line in text.splitlines():
        name, _, mib = line.rpartition(",")
        if name.strip() and mib.strip().isdigit():
            gpus.append({"name": name.strip(), "vram": int(mib) * 1024 ** 2})
    return gpus


def _nvidia() -> list[dict]:
    try:
        done = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_nvidia(done.stdout)


def _windows_adapters() -> list[dict]:
    import winreg
    gpus = []
    try:
        adapters = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, DISPLAY_ADAPTERS)
    except OSError:
        return []
    with adapters:
        for index in range(100):
            try:
                sub = winreg.EnumKey(adapters, index)
            except OSError:
                break
            try:
                with winreg.OpenKey(adapters, sub) as key:
                    name = winreg.QueryValueEx(key, "DriverDesc")[0]
                    vram = memory_size(winreg.QueryValueEx(key, "HardwareInformation.qwMemorySize")[0])
            except OSError:         # 'Properties' is locked; a basic display driver has no size
                continue
            gpus.append({"name": str(name), "vram": vram})
    return gpus


def memory_size(value) -> int:
    """The registry keeps it as a QWORD, or as raw little-endian bytes on some drivers."""
    return int.from_bytes(value[:8], "little") if isinstance(value, bytes) else int(value)


def _ram() -> int:
    if sys.platform == "win32":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in ("total", "free", "page_total", "page_free",
                                                        "virtual_total", "virtual_free", "extended_free")]
        status = MemoryStatus(length=ctypes.sizeof(MemoryStatus))
        return status.total if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else 0
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, OSError, ValueError):
        return 0
