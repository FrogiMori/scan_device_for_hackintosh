# 🍎 Hackintosh Compatibility Checker

> A terminal tool that detects your PC hardware and rates its Hackintosh compatibility for every macOS version from **10.0 (Cheetah) → 26.0**, complete with scores, grades, and actionable notes.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Linux-orange?logo=linux&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-blue?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Dependencies](https://img.shields.io/badge/Dependencies-rich%20%7C%20psutil-purple)

---

## 📋 Table of Contents

- [Features](#-features)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Usage](#-usage)
- [How Scoring Works](#-how-scoring-works)
- [macOS Version Reference](#-macos-version-reference-100--260)
- [Hackintosh Compatibility Notes](#-hackintosh-compatibility-notes-by-era)
- [Hardware Compatibility Quick Reference](#-hardware-compatibility-quick-reference)
- [FAQ](#-faq)
- [Disclaimer](#-disclaimer)

---

## ✨ Features

- 🔍 **Automatic hardware detection** — CPU, GPU, Network, Audio, Storage, RAM, UEFI/Secure Boot
- 📊 **100-point scoring system** — broken down into 5 weighted sub-scores
- 🏆 **Grade system** — S / A / B / C / D / E / F with color-coded terminal output
- 📅 **Full macOS history** — covers every release from 10.0 (2001) through 26.0 (speculative)
- 💡 **Actionable highlights & warnings** — tells you exactly what works and what doesn't
- 🖥️ **Beautiful terminal UI** — powered by [Rich](https://github.com/Textualize/rich)
- 📄 **JSON export** — pipe output to other tools or scripts
- 🎯 **Per-version deep dive** — `--version 14.0` for a detailed single-version report

---

## 📦 Requirements

| Requirement | Version |
|---|---|
| Python | 3.10+ |
| `rich` | 13.0+ |
| `psutil` | 5.0+ |
| OS | Linux (any distro) , Window 10,11 |

System tools used (standard on all major distros):
`lscpu`, `lspci`, `lsblk`, `dmidecode` (optional), `mokutil` (optional for Secure Boot detection)

If python version under 10 , the UI may not display

---

## 🚀 Installation

```bash
# 1. Clone or download the project
git clone https://github.com/youruser/hackintosh-checker.git
cd hackintosh-checker

# 2. Install Python dependencies
pip3 install rich psutil

# 3. Make the script executable (optional)
chmod +x hackintosh_checker.py

# 4. Run it!
python3 hackintosh_checker.py
```

---

## 🖥️ Usage

### Default — Full Report

```bash
python3 hackintosh_checker.py
```

Shows your system info panel, then the full compatibility table for all macOS versions, followed by your top 5 recommended versions.

---

### Top Picks Only

```bash
python3 hackintosh_checker.py --top
```

Shows only the top 5 recommended modern macOS versions for your hardware.

---

### Single Version Deep Dive

```bash
python3 hackintosh_checker.py --version 14.0
python3 hackintosh_checker.py --version 13
```

Displays a detailed breakdown — sub-scores, highlights, issues, bootloader support, and notes — for one specific macOS version.

---

### Filter by Minimum Score

```bash
python3 hackintosh_checker.py --min-score 70
```

Only displays versions where your compatibility score is ≥ 70/100.

---

### JSON Output

```bash
python3 hackintosh_checker.py --json
python3 hackintosh_checker.py --json | jq '.scores[] | select(.score >= 80)'
```

Outputs structured JSON — useful for scripting, piping into `jq`, or building your own tooling.

---

### No Color (Plain Text)

```bash
python3 hackintosh_checker.py --no-color
```

Plain ANSI-free output, useful for logging or minimal terminals.

---

### All Options

```
usage: hackintosh_checker.py [-h] [--json] [--version VER] [--no-color] [--top] [--min-score N]

Options:
  --json            Output results as JSON
  --version VER     Detailed report for a specific macOS version (e.g. 14.0)
  --no-color        Disable ANSI colors / rich output
  --top             Show only top recommended versions
  --min-score N     Only show versions with score >= N (default: 0)
```

---

## 📐 How Scoring Works

Each macOS version is scored out of **100 points** across 5 categories:

| Category | Max Points | What's Evaluated |
|---|:---:|---|
| **CPU** | 40 | Vendor support, generation range, AVX2/AVX/SSE4.2 instruction sets |
| **GPU** | 25 | Driver availability, Metal support, dGPU vs iGPU, vendor |
| **Network** | 15 | Kext availability (itlwm, IntelMausi, Realtek, Broadcom OOB) |
| **RAM** | 10 | Meets minimum and recommended requirements |
| **Bootloader** | 10 | OpenCore/Clover support level, UEFI firmware, Secure Boot |

### Grade Scale

| Grade | Score | Meaning |
|:---:|:---:|---|
| **S** | 90–100 | Perfect Hackintosh candidate |
| **A** | 80–89 | Excellent compatibility |
| **B** | 70–79 | Good, minor patches needed |
| **C** | 55–69 | Fair, some issues expected |
| **D** | 40–54 | Difficult, significant work required |
| **E** | 20–39 | Very poor, not recommended |
| **F** | 0–19 | Not compatible |

---

## 🗂️ macOS Version Reference (10.0 → 26.0)

### Legacy Era — PowerPC / Early Intel (2001–2009)

| Version | Codename | Year | Min RAM | Intel Gen | Hackintosh Difficulty |
|---|---|---|---|---|---|
| 10.0 | Cheetah | 2001 | 128 MB | PPC/Core | ⛔ Impossible |
| 10.1 | Puma | 2001 | 128 MB | PPC/Core | ⛔ Impossible |
| 10.2 | Jaguar | 2002 | 128 MB | PPC/Core | ⛔ Impossible |
| 10.3 | Panther | 2003 | 128 MB | PPC/Core | ⛔ Impossible |
| 10.4 | Tiger | 2005 | 256 MB | Core/Core 2 | 🔴 Extremely Hard |
| 10.5 | Leopard | 2007 | 512 MB | Core 2 | 🔴 Very Hard |
| 10.6 | Snow Leopard | 2009 | 1 GB | 1st–5th gen | 🟠 Hard |

> **Note:** 10.0–10.3 were PowerPC only. Intel support arrived with 10.4.4 (2006). Hackintosh on these versions is a collector's challenge, not a practical target.

---

### Classic Intel Era (2011–2016)

| Version | Codename | Year | Min RAM | Notable Change | Hackintosh Rating |
|---|---|---|---|---|---|
| 10.7 | Lion | 2011 | 2 GB | SSE4.2 required, Rosetta dropped | 🟡 Moderate |
| 10.8 | Mountain Lion | 2012 | 2 GB | Clover bootloader matures | 🟢 Good |
| 10.9 | Mavericks | 2013 | 2 GB | USB kext fixes needed | 🟢 Good |
| 10.10 | Yosemite | 2014 | 2 GB | Very stable Hackintosh target | 🟢 Good |
| 10.11 | El Capitan | 2015 | 2 GB | SIP introduced, USB 15-port limit | 🟢 Good |
| 10.12 | Sierra | 2016 | 2 GB | NVIDIA Web Drivers available | 🟢 Good |

> **Bootloader:** Clover is king for this era. USB patches, FakeSMC, and NullCPUPowerManagement kexts are your best friends.

---

### Modern Hackintosh Era (2017–2019)

| Version | Codename | Year | Min RAM | Notable Change | Hackintosh Rating |
|---|---|---|---|---|---|
| 10.13 | High Sierra | 2017 | 4 GB | Last NVIDIA Web Driver support | 🟢 Great |
| 10.14 | Mojave | 2018 | 4 GB | Metal GPU required, no more NVIDIA | 🟢 Great |
| 10.15 | Catalina | 2019 | 4 GB | AVX required, 32-bit apps dropped | 🟢 Great |

> **NVIDIA Warning:** Web Drivers were never released for 10.14+. If you have a Pascal (GTX 10xx) or later NVIDIA card, iGPU is your only option from Mojave onwards.

---

### OpenCore Era (2020–2025)

| Version | Codename | Year | Min CPU Gen | Min RAM | OpenCore | Hackintosh Rating |
|---|---|---|---|---|---|---|
| 11 | Big Sur | 2020 | 3rd gen | 4 GB | ✅ Full | 🟢 Excellent |
| 12 | Monterey | 2021 | 4th gen | 4 GB | ✅ Full | 🟢 Excellent |
| 13 | Ventura | 2022 | 6th gen | 4 GB | ✅ Full | ⭐ Best Target |
| 14 | Sonoma | 2023 | 7th gen | 4 GB | ✅ Full | ⭐ Best Target |
| 15 | Sequoia | 2024 | 8th gen | 8 GB | ✅ Full | 🟢 Excellent |
| 16 | Tahoe | 2025 | 9th gen | 8 GB | ✅ Full | 🟢 Excellent |

> **Clover is deprecated** from Ventura (13) onwards. Use [OpenCore](https://github.com/acidanthera/OpenCorePkg) exclusively for any modern macOS.

> **AMD CPUs:** AMD Hackintosh is possible on macOS 11–15 using [AMD Vanilla patches](https://github.com/AMD-OSX/AMD_Vanilla), but some features (DRM, certain apps) may not work.

---

### Speculative Future Releases (2026–2035)

| Version | Est. Year | Likely CPU Gen | Intel Support | AMD Support | Notes |
|---|---|---|---|---|---|
| 17 | 2026 | 10th gen+ | ⚠️ Uncertain | ✅ Likely | Early OC support expected |
| 18 | 2027 | 11th gen+ | ⚠️ Limited | ✅ Likely | Community patches needed |
| 19 | 2028 | 11th gen+ | ❌ Dropping | ⚠️ Maybe | Apple Silicon focus |
| 20 | 2029 | 11th gen+ | ❌ Unlikely | ❌ Unlikely | Near-impossible Hackintosh |
| 21–26 | 2030–2035 | 12–14th gen+ | ❌ No | ❌ No | Apple Silicon only assumption |

> ⚠️ **Disclaimer:** macOS 17+ scores are **speculative**, based on Apple's trajectory toward Apple Silicon exclusivity. These ratings will be updated as real information becomes available.

---

## 🔧 Hackintosh Compatibility Notes by Era

### CPU

| Vendor | Compatibility | Notes |
|---|---|---|
| Intel 1st–5th gen | ✅ macOS 10.6–10.15 | Legacy, Clover required |
| Intel 6th gen (Skylake) | ✅ macOS 10.11–13 | Great support, iGPU works |
| Intel 7th gen (Kaby Lake) | ✅ macOS 10.12–14 | Excellent support |
| Intel 8th–9th gen (Coffee Lake) | ✅ macOS 10.13–15 | Best sweet spot |
| Intel 10th gen (Comet/Ice Lake) | ✅ macOS 10.15–16 | Good OC support |
| Intel 11th gen (Tiger Lake) | ✅ macOS 11–16 | Iris Xe needs WhateverGreen |
| Intel 12th–14th gen (Alder/Raptor) | ⚠️ macOS 12–16 | E-core issues, needs fixes |
| AMD Ryzen (Zen 2+) | ⚠️ macOS 10.13–15 | AMD Vanilla patches required |
| AMD Ryzen (Zen 4/5) | ❌ Limited | Very experimental |

---

### GPU

| GPU | Status | Works Until |
|---|---|---|
| Intel HD 4000 (Ivy Bridge) | ⚠️ Legacy | macOS 12 (dropped in 12.0) |
| Intel HD 530 / UHD 630 | ✅ Great | macOS 14 (ongoing) |
| Intel Iris Xe (Tiger Lake) | ✅ Good | macOS 15+ (WhateverGreen) |
| AMD Polaris (RX 4xx/5xx) | ✅ Excellent | Ongoing (OOB in macOS 11+) |
| AMD Vega | ✅ Excellent | Ongoing |
| AMD RDNA (RX 5xxx) | ✅ Good | Ongoing |
| AMD RDNA 2 (RX 6xxx) | ✅ Best | Ongoing (OOB in macOS 12+) |
| AMD RDNA 3 (RX 7xxx) | ⚠️ Partial | macOS 14+ (limited) |
| NVIDIA Kepler (GTX 6xx/7xx) | ⚠️ Legacy | Dropped after macOS 10.15 |
| NVIDIA Maxwell/Pascal (GTX 9xx/10xx) | ❌ No driver | Dropped after macOS 10.13 |
| NVIDIA Turing/Ampere/Ada (RTX) | ❌ No driver | Never supported |

---

### Network (Wi-Fi & Ethernet)

| Chipset | Type | Support | Kext |
|---|---|---|---|
| Intel Wi-Fi 6 (AX200/AX201) | Wi-Fi | ✅ Excellent | [itlwm](https://github.com/OpenIntelWireless/itlwm) / AirportItlwm |
| Intel I219 / I225 Ethernet | Ethernet | ✅ Excellent | IntelMausi / AppleIGC |
| Broadcom BCM94360/BCM943602 | Wi-Fi | ✅ OOB | Native (no kext needed) |
| Realtek RTL8111/8125 | Ethernet | ✅ Good | RealtekRTL8111 |
| Qualcomm Atheros | Wi-Fi | ⚠️ Limited | Older macOS only |
| MediaTek Wi-Fi | Wi-Fi | ❌ None | Not supported |

---

## ⚡ Hardware Compatibility Quick Reference

Use this as a **pre-purchase** or **pre-build** guide:

### Best Intel CPUs for Hackintosh (2024)
1. **Intel Core i5/i7/i9 8th–10th gen** — widest macOS support range
2. **Intel Core i5/i7 7th gen (Kaby Lake)** — runs up to Sonoma
3. **Intel Core i5/i7 11th gen (Tiger Lake)** — Iris Xe iGPU works with patches
4. **Intel Core i7/i9 12th–13th gen** — works with E-core disabling workarounds

### Best AMD GPUs for Hackintosh (2024)
1. **RX 6600 / RX 6600 XT** — plug-and-play on macOS 12+
2. **RX 6800 / RX 6800 XT** — excellent performance + OOB support
3. **RX 5500 XT / RX 5700 XT** — RDNA1, solid macOS 11+ support
4. **RX 580 / RX 590** — Polaris, extremely well supported, budget pick

### Avoid for Hackintosh
- ❌ Any NVIDIA GPU (RTX or GTX 10xx+) as primary display
- ❌ Intel Arc GPUs (no macOS driver)
- ❌ AMD RX 7900 series (incomplete driver)
- ❌ MediaTek or Ralink Wi-Fi cards
- ❌ Killer (Rivet Networks) Ethernet

---

## ❓ FAQ

**Q: Does this tool install anything or modify my system?**
> No. It is read-only. It only reads hardware info via standard system commands and `/sys` filesystem entries. Nothing is installed, modified, or written outside this script's output.

**Q: Why are macOS 17–26 scores speculative?**
> Apple has been transitioning to Apple Silicon (ARM) since macOS 11 (2020). By macOS 13–14, dropped support for many Intel configurations began. The trend strongly suggests Intel support will end by macOS 17–18, making Hackintosh increasingly difficult. These scores are community projections, not official data.

**Q: My score is high but I know Hackintosh on my machine is hard — why?**
> The score reflects *hardware potential*, not real-world ease. Hackintosh also depends on your BIOS quality, specific laptop OEM restrictions, specific sub-variants of chips, DSDT patches, and ongoing community kext support. Always verify at [Dortania's OpenCore Guide](https://dortania.github.io/OpenCore-Install-Guide/).

**Q: I have Secure Boot enabled. Will it affect Hackintosh?**
> Yes — Secure Boot **must be disabled** in your BIOS/UEFI for OpenCore to work. The checker flags this automatically. Look for "Secure Boot" in your BIOS settings and set it to **Disabled**.

**Q: AMD CPU compatibility?**
> AMD Hackintosh is possible using [AMD Vanilla patches](https://github.com/AMD-OSX/AMD_Vanilla) for macOS 10.13–15. However, features like iMessage, FaceTime, DRM content, and some apps may behave unexpectedly. It's doable but requires more effort than Intel.

**Q: Can I run this on Windows/macOS?**
> The script uses Linux-specific commands (`lscpu`, `lspci`, `/proc`, `/sys`). It is designed for Linux only. Running on macOS natively would require rewriting the hardware detection layer.

---

## 🔗 Useful Resources

| Resource | Link |
|---|---|
| Dortania OpenCore Guide | https://dortania.github.io/OpenCore-Install-Guide/ |
| OpenCore Pkg (acidanthera) | https://github.com/acidanthera/OpenCorePkg |
| AMD Vanilla Patches | https://github.com/AMD-OSX/AMD_Vanilla |
| Intel Wi-Fi (itlwm) | https://github.com/OpenIntelWireless/itlwm |
| WhateverGreen (GPU fixes) | https://github.com/acidanthera/WhateverGreen |
| AppleALC (Audio) | https://github.com/acidanthera/AppleALC |
| IntelMausi (Intel Ethernet) | https://github.com/acidanthera/IntelMausi |
| Lilu (kext framework) | https://github.com/acidanthera/Lilu |
| VirtualSMC | https://github.com/acidanthera/VirtualSMC |
| r/hackintosh | https://www.reddit.com/r/hackintosh/ |

---

## ⚖️ Disclaimer

This tool is provided for **educational and informational purposes only**. Hackintosh involves running macOS on non-Apple hardware, which may violate Apple's [macOS Software License Agreement](https://www.apple.com/legal/sla/). The authors of this tool do not condone piracy or license violations. Use at your own risk.

Scores for macOS 17–26 are **speculative community estimates** and carry no guarantee of accuracy.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Made with ❤️ for the Hackintosh community<br>
  <sub>Always refer to <a href="https://dortania.github.io/OpenCore-Install-Guide/">Dortania's OpenCore Guide</a> before building your Hackintosh.</sub>
</p>
