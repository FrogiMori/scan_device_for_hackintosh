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

def _run(cmd: str, default: str = "") -> str:
    """Run a shell command and return stdout, or default on error."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return default


def _run_lines(cmd: str) -> list[str]:
    return [l for l in _run(cmd).splitlines() if l.strip()]


def detect_cpu() -> CPUInfo:
    cpu = CPUInfo()

    # lscpu parsing
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
            try:
                cpu.family = int(val)
            except ValueError:
                pass
        elif key == "Model":
            try:
                cpu.model_num = int(val)
            except ValueError:
                pass
        elif key == "CPU(s)":
            try:
                cpu.threads = int(val)
            except ValueError:
                pass
        elif key == "Core(s) per socket":
            try:
                cpu.cores = int(val)
            except ValueError:
                pass
        elif key == "CPU max MHz":
            try:
                cpu.max_mhz = float(val)
            except ValueError:
                pass
        elif key == "Virtualization":
            cpu.vt_x = "VT-x" in val or "AMD-V" in val
        elif key == "Flags":
            cpu.flags = val.split()

    cpu.has_avx = "avx" in cpu.flags
    cpu.has_avx2 = "avx2" in cpu.flags
    cpu.has_sse4_2 = "sse4_2" in cpu.flags
    cpu.has_aes = "aes" in cpu.flags

    # Intel generation detection
    if cpu.vendor == "Intel":
        cpu.generation = _detect_intel_gen(cpu.brand, cpu.family, cpu.model_num)
    elif cpu.vendor == "AMD":
        cpu.generation = _detect_amd_gen(cpu.brand)

    return cpu


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


def detect_gpus() -> list[GPUInfo]:
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
                svid = current.get("SVendor", "")
                g.name = current.get("Device", "Unknown")
                g.pci_id = current.get("SDevice", "")
                g.vendor = (
                    "Intel" if "Intel" in vendor_str else
                    "NVIDIA" if "NVIDIA" in vendor_str or "nVidia" in vendor_str else
                    "AMD" if "AMD" in vendor_str or "Advanced Micro" in vendor_str else
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

    # Fallback: simple lspci grep
    if not gpus:
        for line in _run_lines("lspci 2>/dev/null | grep -iE 'vga|3d|display'"):
            g = GPUInfo()
            g.name = line.split(":", 1)[-1].strip()
            g.vendor = (
                "Intel" if "Intel" in g.name else
                "NVIDIA" if "NVIDIA" in g.name or "nVidia" in g.name else
                "AMD" if "AMD" in g.name or "Radeon" in g.name else
                "Unknown"
            )
            g.is_igpu = "Intel" in g.name and ("Iris" in g.name or "HD" in g.name)
            g.generation = _gpu_generation(g.vendor, g.name)
            gpus.append(g)

    return gpus


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


def detect_network() -> list[NetworkInfo]:
    nets = []
    lspci_out = _run("lspci -vmm 2>/dev/null")
    current: dict = {}
    for line in lspci_out.splitlines():
        if line.strip() == "":
            cls = current.get("Class", "").lower()
            if "network" in cls or "ethernet" in cls:
                n = NetworkInfo()
                vendor_str = current.get("Vendor", "")
                n.name = current.get("Device", "Unknown")
                n.vendor = (
                    "Intel" if "Intel" in vendor_str else
                    "Realtek" if "Realtek" in vendor_str else
                    "Broadcom" if "Broadcom" in vendor_str else
                    "Qualcomm" if "Qualcomm" in vendor_str else
                    vendor_str
                )
                n.is_wifi = "wireless" in cls or "wifi" in n.name.lower() or \
                            "wi-fi" in n.name.lower() or "ax" in n.name.lower()
                n.chipset_family = _net_chipset(n.vendor, n.name)
                nets.append(n)
            current = {}
        else:
            kv = line.split(":", 1)
            if len(kv) == 2:
                current[kv[0].strip()] = kv[1].strip()

    # Fallback
    if not nets:
        for line in _run_lines("lspci 2>/dev/null | grep -iE 'network|ethernet'"):
            n = NetworkInfo()
            n.name = line.split(":", 1)[-1].strip()
            n.vendor = (
                "Intel" if "Intel" in n.name else
                "Realtek" if "Realtek" in n.name else
                "Broadcom" if "Broadcom" in n.name else
                "Unknown"
            )
            n.is_wifi = "wireless" in n.name.lower() or "wi-fi" in n.name.lower()
            n.chipset_family = _net_chipset(n.vendor, n.name)
            nets.append(n)
    return nets


def _net_chipset(vendor: str, name: str) -> str:
    name_l = name.lower()
    if vendor == "Intel":
        if "ax" in name_l or "wi-fi 6" in name_l:       return "Intel Wi-Fi 6 (itlwm)"
        if "wireless" in name_l or "wifi" in name_l:     return "Intel Wi-Fi (itlwm)"
        if "i219" in name_l:                              return "Intel I219 Ethernet"
        if "i211" in name_l:                              return "Intel I211 Ethernet"
        if "i225" in name_l:                              return "Intel I225 Ethernet"
        return "Intel Network"
    if vendor == "Realtek":
        if "8125" in name_l:                              return "Realtek 8125 (2.5GbE)"
        if "811" in name_l or "8111" in name_l:          return "Realtek 8111 Ethernet"
        return "Realtek Ethernet"
    if vendor == "Broadcom":
        if "bcm94360" in name_l or "bcm943602" in name_l: return "Broadcom (natively OOB)"
        return "Broadcom"
    if vendor == "Qualcomm":                               return "Qualcomm Atheros"
    return vendor


def detect_audio() -> list[AudioInfo]:
    audios = []
    lspci_out = _run("lspci -vmm 2>/dev/null")
    current: dict = {}
    for line in lspci_out.splitlines():
        if line.strip() == "":
            cls = current.get("Class", "").lower()
            if "audio" in cls or "sound" in cls or "multimedia" in cls:
                a = AudioInfo()
                a.name = current.get("Device", "Unknown")
                a.is_hda = "hda" in a.name.lower() or "high definition audio" in a.name.lower() \
                           or "smart sound" in a.name.lower()
                a.codec = _detect_audio_codec(a.name)
                audios.append(a)
            current = {}
        else:
            kv = line.split(":", 1)
            if len(kv) == 2:
                current[kv[0].strip()] = kv[1].strip()
    return audios


def _detect_audio_codec(name: str) -> str:
    name_l = name.lower()
    if "smart sound" in name_l or "sst" in name_l: return "Intel SST (AppleALC)"
    if "hda" in name_l or "high def" in name_l:    return "HDA (AppleALC)"
    if "alc" in name_l:                            return "Realtek ALC (AppleALC)"
    return "Unknown"


def detect_storage() -> StorageInfo:
    s = StorageInfo()
    lsblk_out = _run("lsblk -d -o NAME,ROTA,TYPE 2>/dev/null")
    nvme_list = _run("ls /dev/nvme* 2>/dev/null")
    s.has_nvme = bool(nvme_list)
    for line in lsblk_out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1] == "disk":
            s.drives.append(parts[0])
            if "0" in parts[1]:  # ROTA=0 means SSD/NVMe
                if parts[0].startswith("nvme"):
                    s.has_nvme = True
                else:
                    s.has_sata = True
            else:
                s.has_sata = True
    return s


def detect_system_info() -> SystemInfo:
    info = SystemInfo()
    info.cpu = detect_cpu()
    info.gpus = detect_gpus()
    info.network = detect_network()
    info.audio = detect_audio()
    info.storage = detect_storage()

    # RAM
    mem_info = _run("grep MemTotal /proc/meminfo 2>/dev/null")
    m = re.search(r"(\d+)\s*kB", mem_info)
    if m:
        info.ram_gb = int(m.group(1)) / 1024 / 1024

    # Motherboard
    mb = _run("cat /sys/class/dmi/id/board_name 2>/dev/null")
    mb_vendor = _run("cat /sys/class/dmi/id/board_vendor 2>/dev/null")
    info.motherboard = f"{mb_vendor} {mb}".strip() if mb else "Unknown"

    # BIOS
    info.bios_vendor = _run("cat /sys/class/dmi/id/bios_vendor 2>/dev/null") or "Unknown"
    info.uefi = os.path.exists("/sys/firmware/efi")

    # Secure Boot
    sb = _run("mokutil --sb-state 2>/dev/null")
    info.secure_boot = "enabled" in sb.lower()

    info.os_name = platform.version()
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
        body.append(f"[{bar_color}]{bar}[/{bar_color}]", style="")
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
    body.append(f"[{bar_color}]{bar}[/{bar_color}] ", style="")
    body.append(f"[{grade_style}]{cs.total}/100  Grade: {cs.grade}[/{grade_style}]\n\n")

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
        body.append(f"[{scol}]{sbar}[/{scol}] ", style="")
        body.append(f"[{col}]{score}/{max_s}[/{col}]\n")

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
