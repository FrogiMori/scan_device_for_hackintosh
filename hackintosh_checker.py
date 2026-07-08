#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║         HACKINTOSH COMPATIBILITY CHECKER                     ║
║    macOS 10.0 (Cheetah) → 26.0 (Tahoe) Rating Engine        ║
╚══════════════════════════════════════════════════════════════╝

Detects your hardware and scores compatibility for every macOS
version from 10.0 to 26.0 for Hackintosh use.

Usage:
    python3 hackintosh_checker.py [--json] [--version VER] [--no-color]
"""

import os
import re
import sys
import json
import shutil
import platform
import argparse
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

# ──────────────────────────────────────────────────────────────
# Optional rich import — fall back to plain ANSI if unavailable
# ──────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import track
    from rich import box
    from rich.columns import Columns
    from rich.rule import Rule
    from rich.style import Style
    RICH = True
except ImportError:
    RICH = False


# ═══════════════════════════════════════════════════════════════
#  DATA MODELS
# ═══════════════════════════════════════════════════════════════

@dataclass
class CPUInfo:
    vendor: str = "Unknown"          # Intel / AMD / Apple
    brand: str = "Unknown"
    family: int = 0
    model_num: int = 0
    generation: int = 0              # Intel gen (1-13+)
    cores: int = 0
    threads: int = 0
    max_mhz: float = 0.0
    flags: list = field(default_factory=list)
    has_avx: bool = False
    has_avx2: bool = False
    has_sse4_2: bool = False
    has_aes: bool = False
    vt_x: bool = False


@dataclass
class GPUInfo:
    vendor: str = "Unknown"          # Intel / NVIDIA / AMD / Apple
    name: str = "Unknown"
    pci_id: str = ""
    is_igpu: bool = False
    generation: str = ""             # e.g. "Tiger Lake", "Navi", "Turing"


@dataclass
class NetworkInfo:
    name: str = "Unknown"
    vendor: str = "Unknown"
    pci_id: str = ""
    is_wifi: bool = False
    chipset_family: str = ""         # e.g. "Intel", "Broadcom", "Realtek"


@dataclass
class AudioInfo:
    name: str = "Unknown"
    codec: str = "Unknown"
    is_hda: bool = False


@dataclass
class StorageInfo:
    drives: list = field(default_factory=list)
    has_nvme: bool = False
    has_sata: bool = False


@dataclass
class SystemInfo:
    cpu: CPUInfo = field(default_factory=CPUInfo)
    gpus: list = field(default_factory=list)       # list[GPUInfo]
    network: list = field(default_factory=list)    # list[NetworkInfo]
    audio: list = field(default_factory=list)      # list[AudioInfo]
    storage: StorageInfo = field(default_factory=StorageInfo)
    ram_gb: float = 0.0
    ram_slots: int = 0
    motherboard: str = "Unknown"
    bios_vendor: str = "Unknown"
    uefi: bool = False
    secure_boot: bool = False
    os_name: str = ""
    hostname: str = ""


@dataclass
class MacOSVersion:
    major: int
    minor: int
    name: str
    codename: str
    year: int
    min_cpu_gen: int           # minimum Intel gen required (0 = any)
    max_cpu_gen: int           # -1 = no upper limit
    supports_amd: bool
    supports_intel: bool
    requires_avx2: bool
    requires_avx: bool
    requires_sse4_2: bool
    min_ram_gb: float
    opencore_support: str      # "full" / "partial" / "none" / "legacy"
    clover_support: str
    notes: str
    eol: bool = False
    recommended: bool = False


# ═══════════════════════════════════════════════════════════════
#  macOS VERSION DATABASE
# ═══════════════════════════════════════════════════════════════

MACOS_VERSIONS: list[MacOSVersion] = [
    # ── Legacy (10.0–10.6) ─────────────────────────────────────
    MacOSVersion(10,  0, "Mac OS X 10.0",  "Cheetah",         2001,
                 min_cpu_gen=0, max_cpu_gen=2, supports_amd=False, supports_intel=True,
                 requires_avx2=False, requires_avx=False, requires_sse4_2=False,
                 min_ram_gb=0.128, opencore_support="none", clover_support="none",
                 notes="PPC/early Intel only. Near-impossible Hackintosh.", eol=True),

    MacOSVersion(10,  1, "Mac OS X 10.1",  "Puma",            2001,
                 min_cpu_gen=0, max_cpu_gen=2, supports_amd=False, supports_intel=True,
                 requires_avx2=False, requires_avx=False, requires_sse4_2=False,
                 min_ram_gb=0.128, opencore_support="none", clover_support="none",
                 notes="PPC era. No practical Hackintosh support.", eol=True),

    MacOSVersion(10,  2, "Mac OS X 10.2",  "Jaguar",          2002,
                 min_cpu_gen=0, max_cpu_gen=2, supports_amd=False, supports_intel=True,
                 requires_avx2=False, requires_avx=False, requires_sse4_2=False,
                 min_ram_gb=0.128, opencore_support="none", clover_support="none",
                 notes="PPC era. No practical Hackintosh support.", eol=True),

    MacOSVersion(10,  3, "Mac OS X 10.3",  "Panther",         2003,
                 min_cpu_gen=0, max_cpu_gen=2, supports_amd=False, supports_intel=True,
                 requires_avx2=False, requires_avx=False, requires_sse4_2=False,
                 min_ram_gb=0.128, opencore_support="none", clover_support="none",
                 notes="PPC era. No practical Hackintosh support.", eol=True),

    MacOSVersion(10,  4, "Mac OS X 10.4",  "Tiger",           2005,
                 min_cpu_gen=0, max_cpu_gen=3, supports_amd=False, supports_intel=True,
                 requires_avx2=False, requires_avx=False, requires_sse4_2=False,
                 min_ram_gb=0.256, opencore_support="legacy", clover_support="legacy",
                 notes="First Intel Mac support in 10.4.4. Very limited Hackintosh.", eol=True),

    MacOSVersion(10,  5, "Mac OS X 10.5",  "Leopard",         2007,
                 min_cpu_gen=0, max_cpu_gen=4, supports_amd=False, supports_intel=True,
                 requires_avx2=False, requires_avx=False, requires_sse4_2=False,
                 min_ram_gb=0.512, opencore_support="legacy", clover_support="legacy",
                 notes="Early Intel Core 2. Hackintosh possible with legacy tools.", eol=True),

    MacOSVersion(10,  6, "Mac OS X 10.6",  "Snow Leopard",    2009,
                 min_cpu_gen=1, max_cpu_gen=5, supports_amd=False, supports_intel=True,
                 requires_avx2=False, requires_avx=False, requires_sse4_2=False,
                 min_ram_gb=1.0, opencore_support="legacy", clover_support="partial",
                 notes="32/64-bit Intel only. Solid Hackintosh foundation.", eol=True),

    # ── Classic Intel era (10.7–10.12) ─────────────────────────
    MacOSVersion(10,  7, "OS X 10.7",      "Lion",            2011,
                 min_cpu_gen=1, max_cpu_gen=6, supports_amd=False, supports_intel=True,
                 requires_avx2=False, requires_avx=False, requires_sse4_2=True,
                 min_ram_gb=2.0, opencore_support="legacy", clover_support="partial",
                 notes="Requires SSE4.2. Dropped Rosetta.", eol=True),

    MacOSVersion(10,  8, "OS X 10.8",      "Mountain Lion",   2012,
                 min_cpu_gen=1, max_cpu_gen=7, supports_amd=False, supports_intel=True,
                 requires_avx2=False, requires_avx=False, requires_sse4_2=True,
                 min_ram_gb=2.0, opencore_support="legacy", clover_support="full",
                 notes="Good Hackintosh support via Clover.", eol=True),

    MacOSVersion(10,  9, "OS X 10.9",      "Mavericks",       2013,
                 min_cpu_gen=1, max_cpu_gen=8, supports_amd=False, supports_intel=True,
                 requires_avx2=False, requires_avx=False, requires_sse4_2=True,
                 min_ram_gb=2.0, opencore_support="legacy", clover_support="full",
                 notes="Excellent Hackintosh support. USB kernel extension needed.", eol=True),

    MacOSVersion(10, 10, "OS X 10.10",     "Yosemite",        2014,
                 min_cpu_gen=1, max_cpu_gen=9, supports_amd=False, supports_intel=True,
                 requires_avx2=False, requires_avx=False, requires_sse4_2=True,
                 min_ram_gb=2.0, opencore_support="legacy", clover_support="full",
                 notes="Very good Hackintosh support.", eol=True),

    MacOSVersion(10, 11, "OS X 10.11",     "El Capitan",      2015,
                 min_cpu_gen=1, max_cpu_gen=9, supports_amd=False, supports_intel=True,
                 requires_avx2=False, requires_avx=False, requires_sse4_2=True,
                 min_ram_gb=2.0, opencore_support="partial", clover_support="full",
                 notes="SIP introduced. USB 15-port limit patch needed.", eol=True),

    MacOSVersion(10, 12, "macOS 10.12",    "Sierra",          2016,
                 min_cpu_gen=1, max_cpu_gen=10, supports_amd=False, supports_intel=True,
                 requires_avx2=False, requires_avx=False, requires_sse4_2=True,
                 min_ram_gb=2.0, opencore_support="partial", clover_support="full",
                 notes="Dropped Nvidia Web Drivers later. Good Intel support.", eol=True),

    # ── Modern era (10.13–10.15) ────────────────────────────────
    MacOSVersion(10, 13, "macOS 10.13",    "High Sierra",     2017,
                 min_cpu_gen=1, max_cpu_gen=10, supports_amd=True, supports_intel=True,
                 requires_avx2=False, requires_avx=False, requires_sse4_2=True,
                 min_ram_gb=4.0, opencore_support="partial", clover_support="full",
                 notes="Last Nvidia Web Driver support. HEVC + Metal req.", eol=True),

    MacOSVersion(10, 14, "macOS 10.14",    "Mojave",          2018,
                 min_cpu_gen=1, max_cpu_gen=10, supports_amd=True, supports_intel=True,
                 requires_avx2=False, requires_avx=False, requires_sse4_2=True,
                 min_ram_gb=4.0, opencore_support="partial", clover_support="full",
                 notes="Metal GPU required. Dark Mode. Dropped many GPUs.", eol=True),

    MacOSVersion(10, 15, "macOS 10.15",    "Catalina",        2019,
                 min_cpu_gen=1, max_cpu_gen=10, supports_amd=True, supports_intel=True,
                 requires_avx2=False, requires_avx=True, requires_sse4_2=True,
                 min_ram_gb=4.0, opencore_support="full", clover_support="full",
                 notes="Dropped 32-bit app support. AVX required.", eol=True),

    # ── Big Sur / Monterey / Ventura era ───────────────────────
    MacOSVersion(11,  0, "macOS 11",        "Big Sur",         2020,
                 min_cpu_gen=3, max_cpu_gen=13, supports_amd=True, supports_intel=True,
                 requires_avx2=True, requires_avx=True, requires_sse4_2=True,
                 min_ram_gb=4.0, opencore_support="full", clover_support="partial",
                 notes="AVX2 req. Signed kexts. OC 0.6+ recommended.",
                 recommended=True, eol=True),

    MacOSVersion(12,  0, "macOS 12",        "Monterey",        2021,
                 min_cpu_gen=4, max_cpu_gen=13, supports_amd=True, supports_intel=True,
                 requires_avx2=True, requires_avx=True, requires_sse4_2=True,
                 min_ram_gb=4.0, opencore_support="full", clover_support="partial",
                 notes="Dropped Intel HD 4000 / Nvidia Kepler iGPU. AirPlay to Mac.",
                 recommended=True, eol=True),

    MacOSVersion(13,  0, "macOS 13",        "Ventura",         2022,
                 min_cpu_gen=6, max_cpu_gen=13, supports_amd=True, supports_intel=True,
                 requires_avx2=True, requires_avx=True, requires_sse4_2=True,
                 min_ram_gb=4.0, opencore_support="full", clover_support="none",
                 notes="6th+ gen Intel required. Metal 3. OpenCore only.",
                 recommended=True, eol=False),

    MacOSVersion(14,  0, "macOS 14",        "Sonoma",          2023,
                 min_cpu_gen=7, max_cpu_gen=14, supports_amd=True, supports_intel=True,
                 requires_avx2=True, requires_avx=True, requires_sse4_2=True,
                 min_ram_gb=4.0, opencore_support="full", clover_support="none",
                 notes="7th+ gen Intel required. Widgets on desktop.",
                 recommended=True, eol=False),

    MacOSVersion(15,  0, "macOS 15",        "Sequoia",         2024,
                 min_cpu_gen=8, max_cpu_gen=14, supports_amd=True, supports_intel=True,
                 requires_avx2=True, requires_avx=True, requires_sse4_2=True,
                 min_ram_gb=8.0, opencore_support="full", clover_support="none",
                 notes="8th+ gen Intel (Coffee Lake) required. iPhone mirroring.",
                 recommended=True, eol=False),

    MacOSVersion(26,  0, "macOS 26",        "Tahoe",           2025,
                 min_cpu_gen=9, max_cpu_gen=14, supports_amd=True, supports_intel=True,
                 requires_avx2=True, requires_avx=True, requires_sse4_2=True,
                 min_ram_gb=8.0, opencore_support="full", clover_support="none",
                 notes="9th+ gen Intel recommended. Apple Intelligence features.",
                 recommended=True, eol=False),
]


# ═══════════════════════════════════════════════════════════════
#  HARDWARE DETECTION
# ═══════════════════════════════════════════════════════════════

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS   = platform.system() == "Darwin"
# Attribute only exists on Windows; define a safe fallback for other platforms
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run(cmd: str, default: str = "") -> str:
    """Run a shell command and return stdout, or default on error."""
    try:
        kwargs: dict = dict(shell=True, capture_output=True, text=True, timeout=10)
        if IS_WINDOWS:
            kwargs["creationflags"] = _CREATE_NO_WINDOW
        result = subprocess.run(cmd, **kwargs)
        return result.stdout.strip()
    except Exception:
        return default


def _run_lines(cmd: str) -> list[str]:
    return [l for l in _run(cmd).splitlines() if l.strip()]


def _cim(wmi_class: str, properties: str) -> list[dict]:
    """
    Query a WMI/CIM class via PowerShell Get-CimInstance and return a list of
    property dicts.  This works on all Windows versions including Windows 11
    24H2+ where `wmic` has been removed.
    """
    import base64
    props = ", ".join(f'"{p}"' for p in properties.split(","))
    script = (
        f"Get-CimInstance -ClassName {wmi_class} | "
        f"Select-Object -Property {props} | "
        "ConvertTo-Json -Compress -Depth 2"
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    out = _run(
        f"powershell -NoProfile -NonInteractive -EncodedCommand {encoded}"
    )
    if not out:
        return []
    try:
        data = json.loads(out)
        # ConvertTo-Json returns a single object (not array) when only 1 result
        if isinstance(data, dict):
            data = [data]
        return [{k: (str(v) if v is not None else "") for k, v in row.items()}
                for row in data if isinstance(row, dict)]
    except (json.JSONDecodeError, ValueError):
        return []


_WMIC_ALIAS_TO_CIM: dict = {
    # wmic short alias  →  CIM/WMI class name
    "cpu":               "Win32_Processor",
    "computersystem":    "Win32_ComputerSystem",
    "baseboard":         "Win32_BaseBoard",
    "bios":              "Win32_BIOS",
    "diskdrive":         "Win32_DiskDrive",
    "memorychip":        "Win32_PhysicalMemory",
    "physicalmemory":    "Win32_PhysicalMemory",
    "sounddevice":       "Win32_SoundDevice",
    "networkadapter":    "Win32_NetworkAdapter",
    "videocontroller":   "Win32_VideoController",
    # full Win32_* names pass through unchanged
}


def _wmic(query: str) -> list[dict]:
    """
    Run a WMIC query and return list of dicts.
    Tries Get-CimInstance (PowerShell) first since wmic is deprecated/removed
    on Windows 11 24H2+; falls back to raw wmic for older systems.

    The `query` format expected here is:  <class_path> get <prop1,prop2,...>
    e.g. "cpu get Name,Manufacturer,NumberOfCores"
         "path Win32_VideoController get Name,AdapterCompatibility"
    """
    # Parse legacy wmic query string into class + properties
    # Pattern:  [path ][class] get [props]
    q = query.strip()
    # Strip optional leading 'path '
    if q.lower().startswith("path "):
        q = q[5:].strip()
    get_idx = q.lower().find(" get ")
    if get_idx != -1:
        raw_class  = q[:get_idx].strip()
        properties = q[get_idx + 5:].strip()
        # Resolve short wmic alias → full CIM class name
        cim_class = _WMIC_ALIAS_TO_CIM.get(
            raw_class.lower(),
            raw_class  # already a full Win32_* name
        )
        rows = _cim(cim_class, properties)
        if rows:  # CIM succeeded
            return rows
    # Fall back to legacy wmic (Windows 10 / older)
    out = _run(f'wmic {query} /format:list')
    records, current = [], {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            if current:
                records.append(current)
                current = {}
        elif '=' in line:
            k, _, v = line.partition('=')
            current[k.strip()] = v.strip()
    if current:
        records.append(current)
    return records


def _ps(expression: str) -> str:
    """Run a PowerShell one-liner and return stdout."""
    import base64
    encoded = base64.b64encode(expression.encode("utf-16-le")).decode("ascii")
    return _run(
        f"powershell -NoProfile -NonInteractive -EncodedCommand {encoded}"
    )


def _sp_json(datatype: str) -> dict:
    """Run system_profiler in JSON mode (macOS only) and return parsed dict."""
    out = _run(f"system_profiler {datatype} -json 2>/dev/null")
    try:
        return json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return {}


def _infer_cpu_flags_from_gen(cpu: "CPUInfo") -> None:
    """
    On Windows we can't easily read CPUID flags the way Linux exposes them in
    /proc/cpuinfo, so we infer common Hackintosh-relevant flags from the CPU
    generation.  These are conservative lower-bounds (all real CPUs of these
    generations support these instruction sets).
    """
    gen = cpu.generation
    vendor = cpu.vendor
    if vendor == "Intel":
        if gen >= 1:   cpu.has_sse4_2 = True   # Nehalem+
        if gen >= 2:   cpu.has_avx    = True    # Sandy Bridge+
        if gen >= 4:   cpu.has_avx2   = True    # Haswell+
        if gen >= 2:   cpu.has_aes    = True    # Sandy Bridge+
        if gen >= 1:   cpu.vt_x       = True    # nearly universal
    elif vendor == "AMD":
        # Zen = Ryzen 1000+
        if gen >= 1:   cpu.has_sse4_2 = True
        if gen >= 1:   cpu.has_avx    = True
        if gen >= 2:   cpu.has_avx2   = True    # Zen 2 (Ryzen 3000)+
        if gen >= 1:   cpu.has_aes    = True
        if gen >= 1:   cpu.vt_x       = True


def _detect_cpu_windows() -> "CPUInfo":
    cpu = CPUInfo()
    rows = _wmic("cpu get Name,Manufacturer,NumberOfCores,NumberOfLogicalProcessors,"
                 "MaxClockSpeed,Description,Architecture")
    if rows:
        r = rows[0]
        cpu.brand  = r.get("Name", "Unknown")
        mfr        = r.get("Manufacturer", "")
        cpu.vendor = ("Intel" if "Intel" in mfr or "GenuineIntel" in mfr else
                      "AMD"   if "AMD"   in mfr or "AuthenticAMD" in mfr else mfr)
        try: cpu.cores   = int(r.get("NumberOfCores", 0))
        except ValueError: pass
        try: cpu.threads = int(r.get("NumberOfLogicalProcessors", 0))
        except ValueError: pass
        try: cpu.max_mhz = float(r.get("MaxClockSpeed", 0))
        except ValueError: pass

    # Detect generation, then infer flags
    if cpu.vendor == "Intel":
        cpu.generation = _detect_intel_gen(cpu.brand, cpu.family, cpu.model_num)
    elif cpu.vendor == "AMD":
        cpu.generation = _detect_amd_gen(cpu.brand)

    # Try reading flags from PowerShell (Win 10/11 supports Get-CimInstance)
    ps_flags = _ps(
        "(Get-CimInstance Win32_Processor).Description"
    ).lower()
    if "avx2" in ps_flags:   cpu.has_avx2   = True
    if "avx"  in ps_flags:   cpu.has_avx    = True
    if "sse4" in ps_flags:   cpu.has_sse4_2 = True
    if "aes"  in ps_flags:   cpu.has_aes    = True

    # Fall back to generation-based inference for any still-unknown flags
    _infer_cpu_flags_from_gen(cpu)
    return cpu


def _detect_cpu_linux() -> "CPUInfo":
    cpu = CPUInfo()
    lscpu_out = _run("lscpu 2>/dev/null")
    for line in lscpu_out.splitlines():
        kv = line.split(":", 1)
        if len(kv) < 2:
            continue
        key, val = kv[0].strip(), kv[1].strip()
        if key == "Vendor ID":
            cpu.vendor = "Intel" if "Intel" in val else "AMD" if "AMD" in val else val
        elif key == "Model name":
            cpu.brand = val
        elif key == "CPU family":
            try: cpu.family = int(val)
            except ValueError: pass
        elif key == "Model":
            try: cpu.model_num = int(val)
            except ValueError: pass
        elif key == "CPU(s)":
            try: cpu.threads = int(val)
            except ValueError: pass
        elif key == "Core(s) per socket":
            try: cpu.cores = int(val)
            except ValueError: pass
        elif key == "CPU max MHz":
            try: cpu.max_mhz = float(val)
            except ValueError: pass
        elif key == "Virtualization":
            cpu.vt_x = "VT-x" in val or "AMD-V" in val
        elif key == "Flags":
            cpu.flags = val.split()

    cpu.has_avx    = "avx"    in cpu.flags
    cpu.has_avx2   = "avx2"   in cpu.flags
    cpu.has_sse4_2 = "sse4_2" in cpu.flags
    cpu.has_aes    = "aes"    in cpu.flags
    if cpu.vendor == "Intel":
        cpu.generation = _detect_intel_gen(cpu.brand, cpu.family, cpu.model_num)
    elif cpu.vendor == "AMD":
        cpu.generation = _detect_amd_gen(cpu.brand)
    return cpu


def _detect_cpu_macos() -> "CPUInfo":
    cpu = CPUInfo()

    # Brand / model string
    cpu.brand = _run("sysctl -n machdep.cpu.brand_string 2>/dev/null").strip()
    if not cpu.brand:
        cpu.brand = _run("sysctl -n hw.model 2>/dev/null").strip() or "Unknown"

    brand_l = cpu.brand.lower()
    if "intel" in brand_l:
        cpu.vendor = "Intel"
    elif "amd" in brand_l:
        cpu.vendor = "AMD"
    elif "apple" in brand_l:
        cpu.vendor = "Apple Silicon"
    else:
        cpu.vendor = _run("sysctl -n machdep.cpu.vendor 2>/dev/null").strip() or "Unknown"

    # Core / thread counts
    try: cpu.cores   = int(_run("sysctl -n hw.physicalcpu 2>/dev/null") or 0)
    except ValueError: pass
    try: cpu.threads = int(_run("sysctl -n hw.logicalcpu 2>/dev/null") or 0)
    except ValueError: pass

    # Max frequency (sysctl reports Hz; Apple Silicon may return 0 — skip gracefully)
    try:
        freq_hz = int(_run("sysctl -n hw.cpufrequency_max 2>/dev/null") or 0)
        if freq_hz:
            cpu.max_mhz = freq_hz / 1_000_000
    except ValueError:
        pass

    # VT-x / Hypervisor support
    hv = _run("sysctl -n kern.hv_support 2>/dev/null").strip()
    cpu.vt_x = hv == "1"

    # CPU instruction set flags via sysctl
    flags_str  = _run("sysctl -n machdep.cpu.features 2>/dev/null").upper()
    leaf7_str  = _run("sysctl -n machdep.cpu.leaf7_features 2>/dev/null").upper()
    all_flags  = flags_str + " " + leaf7_str
    cpu.has_sse4_2 = "SSE4.2" in all_flags
    cpu.has_avx    = "AVX1.0" in all_flags or " AVX " in all_flags
    cpu.has_avx2   = "AVX2" in all_flags
    cpu.has_aes    = "AES" in all_flags

    if cpu.vendor == "Intel":
        cpu.generation = _detect_intel_gen(cpu.brand, cpu.family, cpu.model_num)
    elif cpu.vendor == "AMD":
        cpu.generation = _detect_amd_gen(cpu.brand)
    # Apple Silicon has no Intel generation

    # Infer any still-unknown flags from generation
    _infer_cpu_flags_from_gen(cpu)
    return cpu


def detect_cpu() -> CPUInfo:
    if IS_WINDOWS: return _detect_cpu_windows()
    if IS_MACOS:   return _detect_cpu_macos()
    return _detect_cpu_linux()


def _detect_intel_gen(brand: str, family: int, model: int) -> int:
    """Estimate Intel Core generation from model name and CPUID model number."""
    brand_lower = brand.lower()

    # Try explicit generation from brand string (e.g., "11th Gen")
    m = re.search(r'(\d+)(?:st|nd|rd|th)\s+gen', brand_lower)
    if m:
        return int(m.group(1))

    # Core generation from specific model number (Intel CPUID model)
    # Family 6 (0x6) mapping:
    intel_model_to_gen = {
        # 1st gen (Nehalem/Westmere) – models 26,30,37,44
        range(26, 32): 1,
        # 2nd gen Sandy Bridge – 42, 45
        range(42, 46): 2,
        # 3rd gen Ivy Bridge – 58, 62
        range(58, 63): 3,
        # 4th gen Haswell – 60, 63, 69, 70
        range(60, 64): 4,
        range(69, 72): 4,
        # 5th gen Broadwell – 61, 71, 86
        range(71, 72): 5,
        range(61, 62): 5,
        # 6th gen Skylake – 78, 94
        range(78, 79): 6,
        range(94, 95): 6,
        # 7th gen Kaby Lake – 142 (stepping <=9), 158
        range(142, 143): 7,
        range(158, 159): 7,
        # 8th gen Coffee Lake – 142 (stepping >9), 158 (stepping >9)
        # Handled specially below
        # 9th gen Coffee Lake Refresh – same die
        # 10th gen Ice Lake – 126
        range(126, 127): 10,
        # 10th gen Comet Lake – 165, 166
        range(165, 167): 10,
        # 11th gen Tiger Lake – 140, 141
        range(140, 142): 11,
        # 11th gen Rocket Lake – 167
        range(167, 168): 11,
        # 12th gen Alder Lake – 151, 154
        range(151, 155): 12,
        # 13th gen Raptor Lake – 183, 186
        range(183, 187): 13,
        # 14th gen Raptor Lake Refresh – same die as 13th
        range(182, 183): 14,
    }

    if family == 6:
        for r, gen in intel_model_to_gen.items():
            if model in r:
                # Distinguish 7th / 8th / 9th gen on same model
                if model == 142 or model == 158:
                    # Check brand string
                    if "8th" in brand_lower or "coffee" in brand_lower:
                        return 8
                    if "9th" in brand_lower:
                        return 9
                    return gen
                return gen

    # Fallback: parse i3/i5/i7/i9 + year suffix in brand
    series_map = {
        "i3-10": 10, "i5-10": 10, "i7-10": 10, "i9-10": 10,
        "i3-11": 11, "i5-11": 11, "i7-11": 11, "i9-11": 11,
        "i3-12": 12, "i5-12": 12, "i7-12": 12, "i9-12": 12,
        "i3-13": 13, "i5-13": 13, "i7-13": 13, "i9-13": 13,
        "i3-14": 14, "i5-14": 14, "i7-14": 14, "i9-14": 14,
    }
    for prefix, gen in series_map.items():
        if prefix in brand_lower:
            return gen

    return 0   # unknown


def _detect_amd_gen(brand: str) -> int:
    """Rough AMD generation estimate for Hackintosh context."""
    b = brand.lower()
    if "ryzen 9000" in b or "zen 5" in b:
        return 5
    if "ryzen 7000" in b or "zen 4" in b:
        return 4
    if "ryzen 5000" in b or "zen 3" in b:
        return 3
    if "ryzen 3000" in b or "zen 2" in b:
        return 2
    if "ryzen 2000" in b or "zen+" in b:
        return 1
    if "ryzen 1000" in b or "zen" in b:
        return 1
    if "fx" in b or "bulldozer" in b or "piledriver" in b:
        return 0
    return 0


def _detect_gpus_windows() -> list[GPUInfo]:
    gpus = []
    rows = _wmic("path Win32_VideoController get Name,AdapterCompatibility,"
                 "VideoProcessor,AdapterRAM")
    for r in rows:
        name = r.get("Name", "").strip()
        if not name or name.lower() in ("microsoft basic display adapter", ""):
            continue
        g = GPUInfo()
        g.name = name
        compat = r.get("AdapterCompatibility", "")
        g.vendor = (
            "Intel"  if "Intel"   in compat or "Intel"  in name else
            "NVIDIA" if "NVIDIA"  in compat or "NVIDIA" in name or "nVidia" in name else
            "AMD"    if "AMD"     in compat or "AMD"    in name
                     or "Radeon"  in name    or "Advanced Micro" in compat else
            compat or "Unknown"
        )
        g.is_igpu = g.vendor == "Intel" and any(
            k in name for k in ("Iris", "UHD", "HD Graphics", "GMA")
        )
        g.generation = _gpu_generation(g.vendor, g.name)
        gpus.append(g)
    return gpus


def _detect_gpus_linux() -> list[GPUInfo]:
    gpus = []
    lspci = _run("lspci -vmm 2>/dev/null")
    current: dict = {}
    for line in lspci.splitlines():
        if line.strip() == "":
            if current.get("Class", "").lower() in ("vga compatible controller",
                                                      "3d controller",
                                                      "display controller"):
                g = GPUInfo()
                vendor_str = current.get("Vendor", "")
                g.name   = current.get("Device", "Unknown")
                g.pci_id = current.get("SDevice", "")
                g.vendor = (
                    "Intel"  if "Intel" in vendor_str else
                    "NVIDIA" if "NVIDIA" in vendor_str or "nVidia" in vendor_str else
                    "AMD"    if "AMD" in vendor_str or "Advanced Micro" in vendor_str else
                    vendor_str
                )
                g.is_igpu = "Intel" in vendor_str and (
                    "Iris" in g.name or "UHD" in g.name or "HD Graphics" in g.name
                    or "GMA" in g.name
                )
                g.generation = _gpu_generation(g.vendor, g.name)
                gpus.append(g)
            current = {}
        else:
            kv = line.split(":", 1)
            if len(kv) == 2:
                current[kv[0].strip()] = kv[1].strip()

    if not gpus:  # Fallback: simple grep
        for line in _run_lines("lspci 2>/dev/null | grep -iE 'vga|3d|display'"):
            g = GPUInfo()
            g.name   = line.split(":", 1)[-1].strip()
            g.vendor = (
                "Intel"  if "Intel"  in g.name else
                "NVIDIA" if "NVIDIA" in g.name or "nVidia" in g.name else
                "AMD"    if "AMD"    in g.name or "Radeon" in g.name else
                "Unknown"
            )
            g.is_igpu      = "Intel" in g.name and ("Iris" in g.name or "HD" in g.name)
            g.generation   = _gpu_generation(g.vendor, g.name)
            gpus.append(g)
    return gpus


def _detect_gpus_macos() -> list[GPUInfo]:
    gpus = []
    data = _sp_json("SPDisplaysDataType")
    for entry in data.get("SPDisplaysDataType", []):
        g = GPUInfo()
        g.name   = entry.get("sppci_model") or entry.get("_name", "Unknown")
        vendor_s = entry.get("spdisplays_vendor", "").lower()
        g.vendor = (
            "Intel"  if "intel"  in vendor_s or "intel"  in g.name.lower() else
            "AMD"    if "amd"    in vendor_s or "radeon" in g.name.lower() else
            "NVIDIA" if "nvidia" in vendor_s or "nvidia" in g.name.lower() else
            "Apple"  if "apple"  in vendor_s or "apple"  in g.name.lower() else
            vendor_s.title() or "Unknown"
        )
        g.is_igpu = (
            g.vendor in ("Intel", "Apple") or
            any(k in g.name for k in ("Iris", "UHD", "HD Graphics", "M1", "M2", "M3", "M4"))
        )
        g.generation = _gpu_generation(g.vendor, g.name)
        gpus.append(g)
    return gpus


def detect_gpus() -> list[GPUInfo]:
    if IS_WINDOWS: return _detect_gpus_windows()
    if IS_MACOS:   return _detect_gpus_macos()
    return _detect_gpus_linux()


def _gpu_generation(vendor: str, name: str) -> str:
    name_l = name.lower()
    if vendor == "Intel":
        if "arc" in name_l:           return "Arc (Alchemist)"
        if "xe" in name_l:            return "Iris Xe (Tiger Lake)"
        if "iris plus" in name_l:     return "Iris Plus (Ice Lake)"
        if "uhd 630" in name_l:       return "UHD 630 (Coffee Lake)"
        if "uhd 620" in name_l:       return "UHD 620 (Kaby Lake-R)"
        if "hd 630" in name_l:        return "HD 630 (Kaby Lake)"
        if "hd 530" in name_l:        return "HD 530 (Skylake)"
        if "hd 520" in name_l:        return "HD 520 (Skylake)"
        if "hd 4600" in name_l:       return "HD 4600 (Haswell)"
        if "hd 4000" in name_l:       return "HD 4000 (Ivy Bridge)"
        if "hd 3000" in name_l:       return "HD 3000 (Sandy Bridge)"
        return "Intel iGPU"
    if vendor == "NVIDIA":
        if "40" in name_l or "rtx 40" in name_l:   return "Ada Lovelace (RTX 40)"
        if "30" in name_l or "rtx 30" in name_l:   return "Ampere (RTX 30)"
        if "20" in name_l or "rtx 20" in name_l:   return "Turing (RTX 20)"
        if "gtx 16" in name_l:                     return "Turing (GTX 16)"
        if "gtx 10" in name_l or "1080" in name_l: return "Pascal (GTX 10)"
        if "gtx 9" in name_l or "980" in name_l or "970" in name_l: return "Maxwell (GTX 9)"
        if "gtx 7" in name_l or "770" in name_l or "780" in name_l: return "Kepler (GTX 7)"
        return "NVIDIA GPU"
    if vendor == "AMD":
        if "rx 7" in name_l or "rdna3" in name_l:  return "RDNA 3 (RX 7xxx)"
        if "rx 6" in name_l or "rdna2" in name_l:  return "RDNA 2 (RX 6xxx)"
        if "rx 5" in name_l or "rdna" in name_l:   return "RDNA (RX 5xxx)"
        if "rx 5" in name_l or "vega" in name_l:   return "Vega"
        if "rx 4" in name_l or "polaris" in name_l: return "Polaris (RX 4xx/5xx)"
        if "r9" in name_l or "r7" in name_l:       return "GCN (R9/R7)"
        return "AMD GPU"
    return "Unknown"


def _net_chipset(vendor: str, name: str) -> str:
    name_l = name.lower()
    if vendor == "Intel":
        if "ax" in name_l or "wi-fi 6" in name_l:        return "Intel Wi-Fi 6 (itlwm)"
        if "wireless" in name_l or "wifi" in name_l:      return "Intel Wi-Fi (itlwm)"
        if "i219" in name_l:                               return "Intel I219 Ethernet"
        if "i211" in name_l:                               return "Intel I211 Ethernet"
        if "i225" in name_l:                               return "Intel I225 Ethernet"
        return "Intel Network"
    if vendor == "Realtek":
        if "8125" in name_l:                               return "Realtek 8125 (2.5GbE)"
        if "811" in name_l or "8111" in name_l:           return "Realtek 8111 Ethernet"
        return "Realtek Ethernet"
    if vendor == "Broadcom":
        if "bcm94360" in name_l or "bcm943602" in name_l: return "Broadcom (natively OOB)"
        return "Broadcom"
    if vendor == "Qualcomm":                               return "Qualcomm Atheros"
    return vendor


def _detect_network_windows() -> list[NetworkInfo]:
    nets = []
    # Use Win32_NetworkAdapter (physical adapters only, skip virtual/loopback)
    rows = _wmic("path Win32_NetworkAdapter get Name,Manufacturer,AdapterType,"
                 "NetConnectionID,PhysicalAdapter")
    for r in rows:
        if r.get("PhysicalAdapter", "").lower() != "true":
            continue
        name = r.get("Name", "").strip()
        if not name:
            continue
        n = NetworkInfo()
        n.name = name
        mfr = r.get("Manufacturer", "")
        n.vendor = (
            "Intel"    if "Intel"    in mfr or "Intel"    in name else
            "Realtek"  if "Realtek"  in mfr or "Realtek"  in name else
            "Broadcom" if "Broadcom" in mfr or "Broadcom" in name else
            "Qualcomm" if "Qualcomm" in mfr or "Qualcomm" in name or
                          "Atheros"  in name else
            mfr or "Unknown"
        )
        adapter_type = r.get("AdapterType", "").lower()
        n.is_wifi = ("wireless" in adapter_type or "802.11" in adapter_type
                     or "wi-fi" in name.lower() or "wireless" in name.lower()
                     or " ax" in name.lower())
        n.chipset_family = _net_chipset(n.vendor, n.name)
        nets.append(n)
    return nets


def _detect_network_linux() -> list[NetworkInfo]:
    nets = []
    lspci_out = _run("lspci -vmm 2>/dev/null")
    current: dict = {}
    for line in lspci_out.splitlines():
        if line.strip() == "":
            cls = current.get("Class", "").lower()
            if "network" in cls or "ethernet" in cls:
                n = NetworkInfo()
                vendor_str = current.get("Vendor", "")
                n.name     = current.get("Device", "Unknown")
                n.vendor   = (
                    "Intel"    if "Intel"    in vendor_str else
                    "Realtek"  if "Realtek"  in vendor_str else
                    "Broadcom" if "Broadcom" in vendor_str else
                    "Qualcomm" if "Qualcomm" in vendor_str else
                    vendor_str
                )
                n.is_wifi  = ("wireless" in cls or "wifi" in n.name.lower() or
                               "wi-fi" in n.name.lower() or " ax" in n.name.lower())
                n.chipset_family = _net_chipset(n.vendor, n.name)
                nets.append(n)
            current = {}
        else:
            kv = line.split(":", 1)
            if len(kv) == 2:
                current[kv[0].strip()] = kv[1].strip()
    if not nets:  # Fallback
        for line in _run_lines("lspci 2>/dev/null | grep -iE 'network|ethernet'"):
            n = NetworkInfo()
            n.name   = line.split(":", 1)[-1].strip()
            n.vendor = (
                "Intel"    if "Intel"    in n.name else
                "Realtek"  if "Realtek"  in n.name else
                "Broadcom" if "Broadcom" in n.name else
                "Unknown"
            )
            n.is_wifi        = "wireless" in n.name.lower() or "wi-fi" in n.name.lower()
            n.chipset_family = _net_chipset(n.vendor, n.name)
            nets.append(n)
    return nets


def _detect_network_macos() -> list[NetworkInfo]:
    nets = []
    data = _sp_json("SPNetworkDataType")
    for entry in data.get("SPNetworkDataType", []):
        iface_type = entry.get("spnetworkinterface_type", "").lower()
        hw_addr    = entry.get("Ethernet", {}).get("MACAddress", "")
        name       = entry.get("_name", entry.get("interface", "Unknown"))
        # Skip loopback / virtual
        if "loopback" in iface_type or name.startswith("lo"):
            continue
        n = NetworkInfo()
        n.name    = name
        n.is_wifi = "wi-fi" in iface_type or "airport" in iface_type or name.lower() == "wi-fi"
        # Detect vendor from interface name and hardware info
        hw_info   = entry.get("IPv4", {}).get("InterfaceName", "") or name
        sp_hw     = _run(f"system_profiler SPNetworkDataType 2>/dev/null | grep -A5 '{name}'")
        n.vendor  = (
            "Intel"    if "Intel"    in sp_hw else
            "Broadcom" if "Broadcom" in sp_hw else
            "Realtek"  if "Realtek"  in sp_hw else
            "Qualcomm" if "Qualcomm" in sp_hw or "Atheros" in sp_hw else
            "Apple"    if "Apple"    in sp_hw else
            "Unknown"
        )
        n.chipset_family = _net_chipset(n.vendor, n.name)
        nets.append(n)
    # Fallback: use networksetup
    if not nets:
        for line in _run_lines("networksetup -listallnetworkservices 2>/dev/null"):
            if line.startswith("*") or not line.strip():
                continue
            n = NetworkInfo()
            n.name    = line.strip()
            n.is_wifi = "wi-fi" in line.lower() or "airport" in line.lower()
            n.vendor  = "Unknown"
            n.chipset_family = "Unknown"
            nets.append(n)
    return nets


def detect_network() -> list[NetworkInfo]:
    if IS_WINDOWS: return _detect_network_windows()
    if IS_MACOS:   return _detect_network_macos()
    return _detect_network_linux()


def _detect_audio_codec(name: str) -> str:
    name_l = name.lower()
    if "smart sound" in name_l or "sst" in name_l: return "Intel SST (AppleALC)"
    if "hda" in name_l or "high def" in name_l:    return "HDA (AppleALC)"
    if "alc" in name_l:                            return "Realtek ALC (AppleALC)"
    return "Unknown"


def _detect_audio_windows() -> list[AudioInfo]:
    audios = []
    rows = _wmic("path Win32_SoundDevice get Name,Manufacturer")
    for r in rows:
        name = r.get("Name", "").strip()
        if not name:
            continue
        a = AudioInfo()
        a.name   = name
        a.is_hda = any(k in name.lower() for k in
                       ("high definition audio", "hda", "smart sound", "realtek audio"))
        a.codec  = _detect_audio_codec(name)
        audios.append(a)
    return audios


def _detect_audio_linux() -> list[AudioInfo]:
    audios = []
    lspci_out = _run("lspci -vmm 2>/dev/null")
    current: dict = {}
    for line in lspci_out.splitlines():
        if line.strip() == "":
            cls = current.get("Class", "").lower()
            if "audio" in cls or "sound" in cls or "multimedia" in cls:
                a = AudioInfo()
                a.name   = current.get("Device", "Unknown")
                a.is_hda = ("hda" in a.name.lower() or
                            "high definition audio" in a.name.lower() or
                            "smart sound" in a.name.lower())
                a.codec  = _detect_audio_codec(a.name)
                audios.append(a)
            current = {}
        else:
            kv = line.split(":", 1)
            if len(kv) == 2:
                current[kv[0].strip()] = kv[1].strip()
    return audios


def _detect_audio_macos() -> list[AudioInfo]:
    audios = []
    data   = _sp_json("SPAudioDataType")
    for entry in data.get("SPAudioDataType", []):
        a        = AudioInfo()
        a.name   = entry.get("_name", "Unknown")
        a.is_hda = any(k in a.name.lower() for k in
                       ("high definition audio", "hda", "realtek", "cirrus"))
        a.codec  = _detect_audio_codec(a.name)
        audios.append(a)
    return audios


def detect_audio() -> list[AudioInfo]:
    if IS_WINDOWS: return _detect_audio_windows()
    if IS_MACOS:   return _detect_audio_macos()
    return _detect_audio_linux()


def _detect_storage_windows() -> StorageInfo:
    s = StorageInfo()
    rows = _wmic("diskdrive get Name,MediaType,Model,Size")
    for r in rows:
        model      = r.get("Model", "").strip()
        media_type = r.get("MediaType", "").lower()
        if not model:
            continue
        s.drives.append(model)
        if "nvme" in model.lower() or "nvme" in media_type:
            s.has_nvme = True
        elif "ssd" in model.lower() or "solid" in media_type:
            s.has_sata = True
        else:
            s.has_sata = True   # HDD also counts as SATA for our purposes
    # PowerShell fallback for NVMe
    if not s.has_nvme:
        nvme_check = _ps(
            "Get-PhysicalDisk | Where-Object { $_.BusType -eq 'NVMe' } | Measure-Object | "
            "Select-Object -ExpandProperty Count"
        ).strip()
        if nvme_check.isdigit() and int(nvme_check) > 0:
            s.has_nvme = True
    return s


def _detect_storage_linux() -> StorageInfo:
    s = StorageInfo()
    lsblk_out = _run("lsblk -d -o NAME,ROTA,TYPE 2>/dev/null")
    nvme_list  = _run("ls /dev/nvme* 2>/dev/null")
    s.has_nvme = bool(nvme_list)
    for line in lsblk_out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1] == "disk":
            s.drives.append(parts[0])
            if "0" in parts[1]:   # ROTA=0 → SSD/NVMe
                if parts[0].startswith("nvme"):
                    s.has_nvme = True
                else:
                    s.has_sata = True
            else:
                s.has_sata = True
    return s


def _detect_storage_macos() -> StorageInfo:
    s    = StorageInfo()
    data = _sp_json("SPStorageDataType")
    for vol in data.get("SPStorageDataType", []):
        bsd  = vol.get("bsd_name", "")
        name = vol.get("_name", bsd)
        if name and name not in s.drives:
            s.drives.append(name)
        medium = vol.get("spstorage_solid_state", "").lower()
        if "yes" in medium or "true" in medium:
            if bsd.startswith("disk") and "nvme" in _run(
                    f"diskutil info {bsd} 2>/dev/null").lower():
                s.has_nvme = True
            else:
                s.has_sata = True
        else:
            s.has_sata = True
    # Quick NVMe check via diskutil list
    if not s.has_nvme:
        disk_list = _run("diskutil list 2>/dev/null").lower()
        s.has_nvme = "apple ssd" in disk_list or "nvme" in disk_list
    return s


def detect_storage() -> StorageInfo:
    if IS_WINDOWS: return _detect_storage_windows()
    if IS_MACOS:   return _detect_storage_macos()
    return _detect_storage_linux()


def _detect_system_info_windows(info: SystemInfo) -> None:
    """Fill in Windows-specific system fields (RAM, MB, BIOS, UEFI, Secure Boot)."""
    # RAM
    rows = _wmic("computersystem get TotalPhysicalMemory")
    if rows:
        try:
            info.ram_gb = int(rows[0].get("TotalPhysicalMemory", 0)) / 1024 ** 3
        except (ValueError, TypeError):
            pass

    # Motherboard
    mb_rows = _wmic("baseboard get Manufacturer,Product")
    if mb_rows:
        r = mb_rows[0]
        mb_vendor = r.get("Manufacturer", "").strip()
        mb_name   = r.get("Product", "").strip()
        info.motherboard = f"{mb_vendor} {mb_name}".strip() or "Unknown"

    # BIOS
    bios_rows = _wmic("bios get Manufacturer")
    if bios_rows:
        info.bios_vendor = bios_rows[0].get("Manufacturer", "Unknown").strip()

    # UEFI — check firmware type via bcdedit or PowerShell
    fw = _ps("(Get-ComputerInfo).BiosFirmwareType").strip().lower()
    if fw:
        info.uefi = "uefi" in fw
    else:
        # Fallback: bcdedit /enum firmware (requires admin)
        bc = _run("bcdedit /enum firmware 2>nul").lower()
        info.uefi = "uefi" in bc or not bc  # assume UEFI if bcdedit not accessible

    # Secure Boot
    sb = _ps("Confirm-SecureBootUEFI 2>$null").strip().lower()
    info.secure_boot = sb == "true"


def _detect_system_info_linux(info: SystemInfo) -> None:
    """Fill in Linux-specific system fields (RAM, MB, BIOS, UEFI, Secure Boot)."""
    mem_info = _run("grep MemTotal /proc/meminfo 2>/dev/null")
    m = re.search(r"(\d+)\s*kB", mem_info)
    if m:
        info.ram_gb = int(m.group(1)) / 1024 / 1024

    mb        = _run("cat /sys/class/dmi/id/board_name 2>/dev/null")
    mb_vendor = _run("cat /sys/class/dmi/id/board_vendor 2>/dev/null")
    info.motherboard = f"{mb_vendor} {mb}".strip() if mb else "Unknown"
    info.bios_vendor = _run("cat /sys/class/dmi/id/bios_vendor 2>/dev/null") or "Unknown"
    info.uefi        = os.path.exists("/sys/firmware/efi")
    sb               = _run("mokutil --sb-state 2>/dev/null")
    info.secure_boot = "enabled" in sb.lower()


def _detect_system_info_macos(info: SystemInfo) -> None:
    """Fill in macOS-specific system fields using system_profiler and sysctl."""
    # RAM
    try:
        mem_bytes     = int(_run("sysctl -n hw.memsize 2>/dev/null") or 0)
        info.ram_gb   = mem_bytes / 1024 ** 3
    except ValueError:
        pass

    # Motherboard / machine model from system_profiler
    hw_data = _sp_json("SPHardwareDataType")
    hw      = hw_data.get("SPHardwareDataType", [{}])[0]
    model   = hw.get("machine_model", "")          # e.g. MacBookPro18,1
    cpu_s   = hw.get("cpu_type", "")               # e.g. Apple M2 Pro
    info.motherboard = hw.get("_name", model) or model or "Unknown"
    info.bios_vendor = "Apple EFI"                 # Macs always use Apple EFI
    info.uefi        = True                        # All modern Macs are UEFI (EFI)

    # Secure Boot (only relevant on Apple Silicon / T2 Macs)
    sb = _run("nvram 94b73556-2197-4702-82a8-3e1337dafbfb:AppleSecureBootPolicy 2>/dev/null")
    # AppleSecureBootPolicy %01 = full, %00 = off; absence = Intel without T2 (no SB)
    info.secure_boot = "%01" in sb or "%02" in sb


def detect_system_info() -> SystemInfo:
    info = SystemInfo()
    info.cpu     = detect_cpu()
    info.gpus    = detect_gpus()
    info.network = detect_network()
    info.audio   = detect_audio()
    info.storage = detect_storage()

    if IS_WINDOWS:
        _detect_system_info_windows(info)
    elif IS_MACOS:
        _detect_system_info_macos(info)
    else:
        _detect_system_info_linux(info)

    info.os_name  = platform.version()
    info.hostname = platform.node()
    return info


# ═══════════════════════════════════════════════════════════════
#  COMPATIBILITY SCORING ENGINE
# ═══════════════════════════════════════════════════════════════

@dataclass
class CompatScore:
    version: MacOSVersion
    total: int = 0          # 0-100
    cpu_score: int = 0
    gpu_score: int = 0
    net_score: int = 0
    ram_score: int = 0
    platform_score: int = 0
    grade: str = "F"
    verdict: str = ""
    issues: list = field(default_factory=list)
    highlights: list = field(default_factory=list)


def score_version(info: SystemInfo, ver: MacOSVersion) -> CompatScore:
    cs = CompatScore(version=ver)
    cpu = info.cpu
    v = ver

    # ── CPU score (40 pts) ──────────────────────────────────────
    cpu_pts = 0
    if cpu.vendor == "Intel" and not v.supports_intel:
        cs.issues.append("Intel CPU not supported on this version")
    elif cpu.vendor == "AMD" and not v.supports_amd:
        cs.issues.append("AMD CPU not supported (or very limited patches needed)")
    else:
        # Instruction set
        if v.requires_avx2 and not cpu.has_avx2:
            cs.issues.append("AVX2 required but not present")
        elif v.requires_avx and not cpu.has_avx:
            cs.issues.append("AVX required but not present")
        elif v.requires_sse4_2 and not cpu.has_sse4_2:
            cs.issues.append("SSE4.2 required but not present")
        else:
            cpu_pts += 15  # base instruction set ok

        # Generation check
        if cpu.vendor == "Intel" and cpu.generation > 0:
            if v.min_cpu_gen > 0 and cpu.generation < v.min_cpu_gen:
                cs.issues.append(
                    f"CPU gen {cpu.generation} below minimum ({v.min_cpu_gen}th gen required)"
                )
            elif v.max_cpu_gen != -1 and cpu.generation > v.max_cpu_gen:
                cs.issues.append(
                    f"CPU gen {cpu.generation} exceeds max tested ({v.max_cpu_gen})"
                )
                cpu_pts += 10  # might still work
            else:
                # In the sweet spot
                cpu_pts += 25
                if 4 <= cpu.generation <= 14:
                    cs.highlights.append(f"CPU gen {cpu.generation} is in the ideal range")
        elif cpu.vendor == "AMD":
            # AMD Hackintosh is possible on 10.13–15 with patches
            if v.major in range(10, 16):
                cpu_pts += 20
                cs.highlights.append("AMD patched kernel supported")
            else:
                cpu_pts += 10

    cs.cpu_score = min(cpu_pts, 40)

    # ── GPU score (25 pts) ──────────────────────────────────────
    gpu_pts = 0
    best_gpu = None
    for g in info.gpus:
        pts = 0
        if g.vendor == "Intel" and g.is_igpu:
            gen = cpu.generation
            if v.major <= 10 and v.minor <= 12:
                pts = 20   # early macOS loves Intel iGPU
            elif v.major == 10 and 13 <= v.minor <= 15:
                if gen >= 4:
                    pts = 22
                elif gen >= 2:
                    pts = 15
            elif v.major in (11, 12):
                if gen >= 7:
                    pts = 20
                elif gen >= 4:
                    pts = 10
            elif v.major == 13:
                if gen >= 7:
                    pts = 18
                elif gen >= 4:
                    pts = 8
            elif v.major >= 14:
                if gen >= 8:
                    pts = 15
                else:
                    pts = 5

        elif g.vendor == "AMD":
            gen_str = g.generation.lower()
            if v.major >= 11:
                if "rdna 2" in gen_str or "rdna2" in gen_str:
                    pts = 25
                    cs.highlights.append(f"AMD RDNA2 GPU fully supported OOB")
                elif "rdna" in gen_str:
                    pts = 22
                elif "polaris" in gen_str or "vega" in gen_str:
                    pts = 18
                elif "gcn" in gen_str:
                    pts = 12
            else:
                pts = 15

        elif g.vendor == "NVIDIA":
            gen_str = g.generation.lower()
            if "kepler" in gen_str:
                if v.major <= 10 and v.minor <= 12:
                    pts = 20
                elif v.major <= 10 and v.minor <= 15:
                    pts = 10
                else:
                    pts = 0
                    cs.issues.append("NVIDIA Kepler dropped after macOS 10.15")
            elif "pascal" in gen_str or "maxwell" in gen_str:
                if v.major <= 10 and v.minor <= 13:
                    pts = 18
                else:
                    pts = 0
                    cs.issues.append("NVIDIA Pascal/Maxwell: no WebDrivers for 10.14+")
            elif "turing" in gen_str or "ampere" in gen_str or "ada" in gen_str:
                pts = 0
                cs.issues.append("NVIDIA Turing/Ampere/Ada: no macOS driver support")
            else:
                pts = 5

        if pts > gpu_pts:
            gpu_pts = pts
            best_gpu = g

    cs.gpu_score = min(gpu_pts, 25)

    # ── Network score (15 pts) ──────────────────────────────────
    net_pts = 0
    for n in info.network:
        pts = 0
        if n.vendor == "Intel":
            if n.is_wifi:
                if v.major >= 11:
                    pts = 12  # itlwm / AirportItlwm works great
                    cs.highlights.append("Intel Wi-Fi: AirportItlwm supported")
                else:
                    pts = 8
            else:
                pts = 14  # Intel Ethernet (e1000e/IntelMausi) very well supported
                cs.highlights.append("Intel Ethernet natively supported")
        elif "Realtek" in n.vendor:
            pts = 10  # RealtekRTL8111 kext
        elif "Broadcom" in n.vendor:
            if "OOB" in n.chipset_family:
                pts = 15
                cs.highlights.append("Broadcom Wi-Fi native OOB support!")
            else:
                pts = 8
        elif "Qualcomm" in n.vendor:
            pts = 5
        if pts > net_pts:
            net_pts = pts

    cs.net_score = min(net_pts, 15)

    # ── RAM score (10 pts) ──────────────────────────────────────
    if info.ram_gb >= v.min_ram_gb * 2:
        cs.ram_score = 10
    elif info.ram_gb >= v.min_ram_gb:
        cs.ram_score = 7
    elif info.ram_gb >= v.min_ram_gb * 0.5:
        cs.ram_score = 3
        cs.issues.append(f"RAM {info.ram_gb:.1f} GB may be tight (min {v.min_ram_gb:.0f} GB)")
    else:
        cs.ram_score = 0
        cs.issues.append(f"Insufficient RAM: {info.ram_gb:.1f} GB (min {v.min_ram_gb:.0f} GB)")

    # ── Platform / bootloader score (10 pts) ───────────────────
    plat = 0
    if v.opencore_support == "full":
        plat += 8
        cs.highlights.append("Full OpenCore support")
    elif v.opencore_support == "partial":
        plat += 5
    elif v.opencore_support == "legacy":
        plat += 3
    if v.clover_support == "full":
        plat = max(plat, 7)
    if info.uefi:
        plat += 2
        cs.highlights.append("UEFI firmware detected")
    if info.secure_boot:
        plat -= 3
        cs.issues.append("Secure Boot enabled — disable in BIOS for Hackintosh")
    cs.platform_score = max(0, min(plat, 10))

    # ── Total ────────────────────────────────────────────────────
    cs.total = cs.cpu_score + cs.gpu_score + cs.net_score + cs.ram_score + cs.platform_score

    # ── Grade ───────────────────────────────────────────────────
    t = cs.total
    if t >= 90:
        cs.grade = "S"
        cs.verdict = "Perfect Hackintosh candidate"
    elif t >= 80:
        cs.grade = "A"
        cs.verdict = "Excellent compatibility"
    elif t >= 70:
        cs.grade = "B"
        cs.verdict = "Good, minor patches needed"
    elif t >= 55:
        cs.grade = "C"
        cs.verdict = "Fair, some issues expected"
    elif t >= 40:
        cs.grade = "D"
        cs.verdict = "Difficult, significant work required"
    elif t >= 20:
        cs.grade = "E"
        cs.verdict = "Very poor, not recommended"
    else:
        cs.grade = "F"
        cs.verdict = "Not compatible"

    return cs


# ═══════════════════════════════════════════════════════════════
#  DISPLAY ENGINE
# ═══════════════════════════════════════════════════════════════

GRADE_COLOR = {
    "S": "bold bright_yellow",
    "A": "bold bright_green",
    "B": "bold green",
    "C": "bold yellow",
    "D": "bold red",
    "E": "bold red",
    "F": "bold bright_red",
}

GRADE_SYMBOL = {
    "S": "★",
    "A": "●",
    "B": "●",
    "C": "◑",
    "D": "○",
    "E": "○",
    "F": "✗",
}

SCORE_BAR_WIDTH = 20


def make_bar(score: int, max_score: int = 100, width: int = SCORE_BAR_WIDTH) -> tuple[str, str]:
    """Return (bar_string, color) for a score/max."""
    pct = score / max_score if max_score > 0 else 0
    filled = round(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    color = (
        "bright_green" if pct >= 0.85 else
        "green" if pct >= 0.70 else
        "yellow" if pct >= 0.55 else
        "orange1" if pct >= 0.35 else
        "red"
    )
    return bar, color


def display_system_info(info: SystemInfo, console: "Console") -> None:
    console.print()
    console.print(Rule("[bold cyan]  SYSTEM INFORMATION  [/bold cyan]", style="cyan"))
    console.print()

    # CPU Panel
    cpu = info.cpu
    cpu_text = Text()
    cpu_text.append(f"  Model   : ", style="dim")
    cpu_text.append(f"{cpu.brand}\n", style="bold white")
    cpu_text.append(f"  Vendor  : ", style="dim")
    cpu_text.append(f"{cpu.vendor}  ", style="cyan")
    if cpu.generation:
        cpu_text.append(f"Gen {cpu.generation}", style="bold cyan")
    cpu_text.append(f"\n  Cores   : ", style="dim")
    cpu_text.append(f"{cpu.cores}C / {cpu.threads}T  @ {cpu.max_mhz/1000:.2f} GHz\n", style="white")
    cpu_text.append(f"  VT-x    : ", style="dim")
    cpu_text.append("Yes ✓" if cpu.vt_x else "No ✗", style="green" if cpu.vt_x else "red")
    cpu_text.append(f"\n  AVX2    : ", style="dim")
    cpu_text.append("Yes ✓" if cpu.has_avx2 else "No", style="green" if cpu.has_avx2 else "yellow")
    cpu_text.append(f"\n  AES-NI  : ", style="dim")
    cpu_text.append("Yes ✓" if cpu.has_aes else "No", style="green" if cpu.has_aes else "yellow")

    gpu_text = Text()
    for g in info.gpus:
        gpu_text.append(f"  {g.name}\n", style="bold white")
        gpu_text.append(f"  └ Vendor : ", style="dim")
        gpu_text.append(f"{g.vendor}  ", style="magenta")
        if g.is_igpu:
            gpu_text.append("[iGPU]", style="dim cyan")
        gpu_text.append(f"\n  └ Gen    : ", style="dim")
        gpu_text.append(f"{g.generation}\n", style="white")

    net_text = Text()
    for n in info.network:
        icon = "📶" if n.is_wifi else "🔌"
        net_text.append(f"  {icon} {n.name}\n", style="bold white")
        net_text.append(f"  └ Chipset: ", style="dim")
        net_text.append(f"{n.chipset_family}\n", style="cyan")

    ram_text = Text()
    ram_text.append(f"  Total RAM : ", style="dim")
    ram_text.append(f"{info.ram_gb:.1f} GB\n", style="bold white")
    ram_text.append(f"  Storage   : ", style="dim")
    storage_info = []
    if info.storage.has_nvme:
        storage_info.append("NVMe SSD")
    if info.storage.has_sata:
        storage_info.append("SATA")
    ram_text.append(", ".join(storage_info) if storage_info else "Unknown", style="white")
    ram_text.append(f"\n  UEFI      : ", style="dim")
    ram_text.append("Yes ✓" if info.uefi else "No", style="green" if info.uefi else "yellow")
    ram_text.append(f"\n  Secure Boot: ", style="dim")
    ram_text.append("Enabled ⚠" if info.secure_boot else "Disabled ✓",
                    style="yellow" if info.secure_boot else "green")

    mb_text = Text()
    mb_text.append(f"  Board  : ", style="dim")
    mb_text.append(f"{info.motherboard}\n", style="bold white")
    mb_text.append(f"  BIOS   : ", style="dim")
    mb_text.append(f"{info.bios_vendor}\n", style="white")
    mb_text.append(f"  Host   : ", style="dim")
    mb_text.append(f"{info.hostname}\n", style="white")

    columns = Columns([
        Panel(cpu_text,  title="[bold cyan]CPU[/bold cyan]",     border_style="cyan",    width=52),
        Panel(gpu_text,  title="[bold magenta]GPU[/bold magenta]", border_style="magenta", width=52),
    ], equal=False)
    console.print(columns)

    columns2 = Columns([
        Panel(net_text,  title="[bold yellow]Network[/bold yellow]", border_style="yellow", width=52),
        Panel(ram_text,  title="[bold green]Memory & Storage[/bold green]", border_style="green", width=52),
    ], equal=False)
    console.print(columns2)

    console.print(Panel(mb_text, title="[bold white]Motherboard & System[/bold white]",
                        border_style="white", width=107))
    console.print()


def display_scores(scores: list[CompatScore], console: "Console") -> None:
    console.print(Rule("[bold cyan]  macOS HACKINTOSH COMPATIBILITY SCORES  [/bold cyan]",
                       style="cyan"))
    console.print()

    # Build table
    table = Table(
        box=box.ROUNDED,
        header_style="bold cyan",
        border_style="cyan",
        show_lines=True,
        expand=False,
        title="[bold]macOS 10.0 → 26.0 Hackintosh Rating[/bold]",
    )

    table.add_column("macOS", style="bold white", no_wrap=True, width=14)
    table.add_column("Version", style="dim", width=8)
    table.add_column("Codename", style="italic cyan", width=14)
    table.add_column("Score", justify="center", width=8)
    table.add_column("Grade", justify="center", width=7)
    table.add_column("Bar", width=24)
    table.add_column("CPU", justify="center", width=5)
    table.add_column("GPU", justify="center", width=5)
    table.add_column("Net", justify="center", width=5)
    table.add_column("RAM", justify="center", width=5)
    table.add_column("Boot", justify="center", width=6)
    table.add_column("Verdict", width=30)

    for cs in scores:
        v = cs.version
        ver_str = f"{v.major}.{v.minor}"
        bar, bar_color = make_bar(cs.total)
        grade_style = GRADE_COLOR.get(cs.grade, "white")
        sym = GRADE_SYMBOL.get(cs.grade, "?")

        # Year badge
        year_suffix = f" ({v.year})" if v.year >= 2020 else ""

        # Row style
        row_style = ""
        if v.recommended:
            row_style = "on grey11"
        if v.eol and v.major < 11:
            row_style = "dim"

        table.add_row(
            v.name,
            ver_str,
            v.codename,
            f"[bold]{cs.total}/100[/bold]",
            f"[{grade_style}]{sym} {cs.grade}[/{grade_style}]",
            f"[{bar_color}]{bar}[/{bar_color}]",
            f"[cyan]{cs.cpu_score}/40[/cyan]",
            f"[magenta]{cs.gpu_score}/25[/magenta]",
            f"[yellow]{cs.net_score}/15[/yellow]",
            f"[green]{cs.ram_score}/10[/green]",
            f"[white]{cs.platform_score}/10[/white]",
            cs.verdict,
            style=row_style,
        )

    console.print(table)
    console.print()


def display_top_picks(scores: list[CompatScore], console: "Console") -> None:
    """Show top 5 recommended versions."""
    modern = [cs for cs in scores if cs.version.major >= 11 and not cs.version.eol]
    modern.sort(key=lambda x: x.total, reverse=True)
    top = modern[:5]

    if not top:
        return

    console.print(Rule("[bold green]  TOP RECOMMENDED macOS VERSIONS  [/bold green]",
                       style="green"))
    console.print()

    for i, cs in enumerate(top):
        v = cs.version
        medal = ["🥇", "🥈", "🥉", "4️⃣ ", "5️⃣ "][i]
        grade_style = GRADE_COLOR.get(cs.grade, "white")
        bar, bar_color = make_bar(cs.total)

        title_txt = f"{medal}  {v.name} — {v.codename}  [{grade_style}]{cs.grade}  {cs.total}/100[/{grade_style}]"
        body = Text()
        body.append(f"  Score: ", style="dim")
        body += Text.from_markup(f"[{bar_color}]{bar}[/{bar_color}]")
        body.append(f"  {cs.total}/100\n")
        body.append(f"  {cs.verdict}\n", style="italic")

        if cs.highlights:
            body.append(f"  ✓ ", style="green")
            body.append(" | ".join(cs.highlights[:3]) + "\n", style="dim green")
        if cs.issues:
            body.append(f"  ⚠ ", style="yellow")
            body.append(" | ".join(cs.issues[:2]) + "\n", style="dim yellow")

        body.append(f"\n  OC: ", style="dim")
        oc_col = "green" if v.opencore_support == "full" else "yellow" if v.opencore_support in ("partial","legacy") else "red"
        body.append(v.opencore_support.upper(), style=oc_col)
        body.append(f"  |  Clover: ", style="dim")
        cl_col = "green" if v.clover_support == "full" else "yellow" if v.clover_support in ("partial","legacy") else "red"
        body.append(v.clover_support.upper(), style=cl_col)
        body.append(f"  |  Year: {v.year}\n", style="dim")
        body.append(f"  Note: {v.notes}", style="dim italic")

        console.print(Panel(body, title=title_txt, border_style="green", padding=(0, 1)))
        console.print()


def display_detail(cs: CompatScore, console: "Console") -> None:
    v = cs.version
    grade_style = GRADE_COLOR.get(cs.grade, "white")
    bar, bar_color = make_bar(cs.total)

    title = f"  {v.name} — {v.codename} ({v.year})  "
    body = Text()
    body.append(f"  Overall Score : ", style="dim")
    body += Text.from_markup(f"[{bar_color}]{bar}[/{bar_color}] ")
    body += Text.from_markup(f"[{grade_style}]{cs.total}/100  Grade: {cs.grade}[/{grade_style}]\n\n")

    sub_scores = [
        ("CPU", cs.cpu_score, 40, "cyan"),
        ("GPU", cs.gpu_score, 25, "magenta"),
        ("Network", cs.net_score, 15, "yellow"),
        ("RAM", cs.ram_score, 10, "green"),
        ("Bootloader", cs.platform_score, 10, "white"),
    ]
    for label, score, max_s, col in sub_scores:
        sbar, scol = make_bar(score, max_s, 15)
        body.append(f"  {label:<12}: ", style="dim")
        body += Text.from_markup(f"[{scol}]{sbar}[/{scol}] ")
        body += Text.from_markup(f"[{col}]{score}/{max_s}[/{col}]\n")

    body.append(f"\n  Verdict : ", style="dim")
    body.append(f"[{grade_style}]{cs.verdict}[/{grade_style}]\n")
    body.append(f"  OC      : ", style="dim")
    body.append(f"{v.opencore_support}  ", style="cyan")
    body.append(f"Clover: ", style="dim")
    body.append(f"{v.clover_support}\n", style="cyan")
    body.append(f"  Notes   : ", style="dim")
    body.append(f"{v.notes}\n", style="italic white")

    if cs.highlights:
        body.append(f"\n  ✓ Highlights:\n", style="bold green")
        for h in cs.highlights:
            body.append(f"    • {h}\n", style="green")

    if cs.issues:
        body.append(f"\n  ⚠ Issues:\n", style="bold yellow")
        for issue in cs.issues:
            body.append(f"    • {issue}\n", style="yellow")

    console.print(Panel(body, title=f"[bold]{title}[/bold]",
                        border_style=GRADE_COLOR.get(cs.grade, "white")))


def display_plain(info: SystemInfo, scores: list[CompatScore]) -> None:
    """Fallback plain text output (no rich)."""
    print("=" * 70)
    print("  HACKINTOSH COMPATIBILITY CHECKER")
    print("=" * 70)
    print(f"CPU: {info.cpu.brand}  (Gen {info.cpu.generation})  Cores: {info.cpu.cores}")
    print(f"RAM: {info.ram_gb:.1f} GB   UEFI: {info.uefi}  SecureBoot: {info.secure_boot}")
    for g in info.gpus:
        print(f"GPU: {g.name}  ({g.vendor})")
    for n in info.network:
        kind = "Wi-Fi" if n.is_wifi else "Ethernet"
        print(f"Net [{kind}]: {n.name}  ({n.chipset_family})")
    print()
    print(f"{'macOS':<30} {'Score':>6}  {'Grade':>5}  Verdict")
    print("-" * 70)
    for cs in scores:
        v = cs.version
        print(f"{v.name:<30} {cs.total:>5}/100  [{cs.grade:>1}]   {cs.verdict}")
    print()


# ═══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Hackintosh Compatibility Checker — rates macOS 10.0–26.0 on your hardware",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 hackintosh_checker.py
  python3 hackintosh_checker.py --version 14.0
  python3 hackintosh_checker.py --json
  python3 hackintosh_checker.py --no-color
  python3 hackintosh_checker.py --top
        """
    )
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--version", metavar="VER",
                        help="Show detailed report for a specific macOS version (e.g. 14.0)")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable ANSI colors")
    parser.add_argument("--top", action="store_true",
                        help="Show only top recommended versions")
    parser.add_argument("--min-score", type=int, default=0, metavar="N",
                        help="Only show versions with score >= N (default 0)")
    args = parser.parse_args()

    use_rich = RICH and not args.no_color and not args.json

    if use_rich:
        console = Console(highlight=False)
        console.print()
        console.print(Panel(
            Text.assemble(
                ("  ██╗  ██╗ █████╗  ██████╗██╗  ██╗██╗███╗   ██╗████████╗ ██████╗ ███████╗██╗  ██╗\n", "bold bright_cyan"),
                ("  ██║  ██║██╔══██╗██╔════╝██║ ██╔╝██║████╗  ██║╚══██╔══╝██╔═══██╗██╔════╝██║  ██║\n", "bold cyan"),
                ("  ███████║███████║██║     █████╔╝ ██║██╔██╗ ██║   ██║   ██║   ██║███████╗███████║\n", "bold cyan"),
                ("  ██╔══██║██╔══██║██║     ██╔═██╗ ██║██║╚██╗██║   ██║   ██║   ██║╚════██║██╔══██║\n", "bold blue"),
                ("  ██║  ██║██║  ██║╚██████╗██║  ██╗██║██║ ╚████║   ██║   ╚██████╔╝███████║██║  ██║\n", "bold blue"),
                ("  ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚══════╝╚═╝  ╚═╝\n", "bold bright_blue"),
                ("         COMPATIBILITY CHECKER  ·  macOS 10.0 → 26.0  ·  Hackintosh Edition\n", "bold white"),
            ),
            border_style="bright_cyan",
            padding=(0, 2),
        ))
        console.print()

    # ── Detect hardware ─────────────────────────────────────────
    if use_rich:
        from rich.progress import Progress, SpinnerColumn, TextColumn
        with Progress(
            SpinnerColumn(spinner_name="dots12", style="cyan"),
            TextColumn("[cyan]{task.description}"),
            console=console,
            transient=True,
        ) as prog:
            task = prog.add_task("Detecting hardware...", total=None)
            info = detect_system_info()
    else:
        if not args.json:
            print("Detecting hardware...")
        info = detect_system_info()

    # ── Score all versions ──────────────────────────────────────
    all_scores = [score_version(info, ver) for ver in MACOS_VERSIONS]
    filtered_scores = [cs for cs in all_scores if cs.total >= args.min_score]

    # ── JSON output ─────────────────────────────────────────────
    if args.json:
        out = {
            "system": {
                "cpu": {
                    "brand": info.cpu.brand,
                    "vendor": info.cpu.vendor,
                    "generation": info.cpu.generation,
                    "cores": info.cpu.cores,
                    "threads": info.cpu.threads,
                    "has_avx2": info.cpu.has_avx2,
                    "has_avx": info.cpu.has_avx,
                    "has_sse4_2": info.cpu.has_sse4_2,
                    "vt_x": info.cpu.vt_x,
                },
                "gpus": [{"name": g.name, "vendor": g.vendor, "generation": g.generation,
                          "is_igpu": g.is_igpu} for g in info.gpus],
                "network": [{"name": n.name, "vendor": n.vendor, "chipset": n.chipset_family,
                             "is_wifi": n.is_wifi} for n in info.network],
                "ram_gb": info.ram_gb,
                "uefi": info.uefi,
                "secure_boot": info.secure_boot,
                "motherboard": info.motherboard,
            },
            "scores": [
                {
                    "macos": f"{cs.version.major}.{cs.version.minor}",
                    "name": cs.version.name,
                    "codename": cs.version.codename,
                    "year": cs.version.year,
                    "score": cs.total,
                    "grade": cs.grade,
                    "verdict": cs.verdict,
                    "sub_scores": {
                        "cpu": cs.cpu_score,
                        "gpu": cs.gpu_score,
                        "network": cs.net_score,
                        "ram": cs.ram_score,
                        "platform": cs.platform_score,
                    },
                    "issues": cs.issues,
                    "highlights": cs.highlights,
                }
                for cs in filtered_scores
            ]
        }
        print(json.dumps(out, indent=2))
        return

    # ── Rich output ─────────────────────────────────────────────
    if use_rich:
        # Specific version detail
        if args.version:
            target = args.version.strip()
            found = None
            for cs in all_scores:
                v = cs.version
                if f"{v.major}.{v.minor}" == target or f"{v.major}" == target:
                    found = cs
                    break
            if found:
                display_system_info(info, console)
                display_detail(found, console)
            else:
                console.print(f"[red]Version '{target}' not found.[/red]")
                console.print("Available: " + ", ".join(
                    f"{v.major}.{v.minor}" for v in MACOS_VERSIONS
                ))
            return

        display_system_info(info, console)

        if args.top:
            display_top_picks(filtered_scores, console)
        else:
            display_scores(filtered_scores, console)
            display_top_picks(filtered_scores, console)

        # Footer
        console.print(Rule(style="dim"))
        console.print(
            "[dim]  Scores are estimates based on known Hackintosh compatibility data.[/dim]\n"
            "[dim]  Always verify with [link=https://dortania.github.io/OpenCore-Install-Guide/]Dortania's OpenCore Guide[/link] before proceeding.[/dim]\n"
            "[dim]  Speculative scores for macOS 17+ are based on Apple Silicon transition trends.[/dim]"
        )
        console.print()
    else:
        # Fallback
        display_plain(info, all_scores)


if __name__ == "__main__":
    main()
