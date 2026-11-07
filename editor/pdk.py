"""
editor/pdk.py — PDK configuration & detection for Vischem
=========================================================
Supports:
  - SkyWater 130nm (sky130A / sky130B)
  - GlobalFoundries 180nm MCU (gf180mcuD / gf180mcuC / gf180mcuA)
  - IHP SG13G2 130nm BiCMOS (ihp-sg13g2)

Detects installations in $PDK_ROOT, standard home locations, and provides:
  - Model and library file resolution
  - Corner lists and default corner selection
  - Device model catalogs for NMOS, PMOS, NPN, PNP
  - Subcircuit and dimension formatting rules
"""

from __future__ import annotations
import os
import re
from dataclasses import dataclass, field


# ── Search locations for PDKs ──────────────────────────────────────────────────
def find_pdk_roots() -> list[str]:
    """Return all valid root directory candidates where PDKs may be located."""
    candidates = []

    # Priority 1: Vischem bundled local PDK directory (e.g. Vischem/pdks or Vischem/pdk)
    vischem_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for local_name in ("pdks", "pdk"):
        local_p = os.path.join(vischem_root, local_name)
        if os.path.isdir(local_p) and local_p not in candidates:
            candidates.append(local_p)

    env_root = os.environ.get("PDK_ROOT")
    if env_root and os.path.isdir(env_root):
        candidates.append(os.path.abspath(env_root))

    home = os.path.expanduser("~")
    for p in [
        os.path.join(home, "pdk"),
        os.path.join(home, "IHP-Open-PDK"),
        "/usr/local/share/pdk",
        "/opt/pdk",
    ]:
        if os.path.isdir(p) and p not in candidates:
            candidates.append(p)
    return candidates


# ── PDK Specification ──────────────────────────────────────────────────────────
@dataclass
class PDKSpec:
    key: str
    display_name: str
    dir_candidates: list[str]
    lib_relative: str
    include_relatives: list[str] = field(default_factory=list)
    secondary_lib_relative: str = ""
    secondary_lib_corner: str = ""
    default_corner: str = "tt"
    corners: list[str] = field(default_factory=list)
    models: dict[str, list[str]] = field(default_factory=dict)
    default_models: dict[str, str] = field(default_factory=dict)
    default_wl: dict[str, tuple[str, str]] = field(default_factory=dict)
    min_wl: dict[str, tuple[str, str]] = field(default_factory=dict)
    is_subcircuit: bool = True
    scale_microns: bool = False
    bjt_terminals: int = 3  # 3 or 4


PDK_SPECS: dict[str, PDKSpec] = {
    "gf180": PDKSpec(
        key="gf180",
        display_name="GlobalFoundries 180nm (GF180MCU)",
        dir_candidates=["gf180mcuD", "gf180mcuC", "gf180mcuB", "gf180mcuA"],
        lib_relative=os.path.join("libs.tech", "ngspice", "sm141064.ngspice"),
        include_relatives=[os.path.join("libs.tech", "ngspice", "design.ngspice")],
        default_corner="typical",
        corners=["typical", "ff", "ss", "fs", "sf"],
        models={
            "NMOS": ["nfet_03v3", "nfet_06v0", "nfet_06v0_nvt", "nfet_03v3_dss", "nfet_06v0_dss"],
            "PMOS": ["pfet_03v3", "pfet_06v0", "pfet_03v3_dss", "pfet_06v0_dss"],
            "NPN":  ["npn_10p00x10p00", "npn_05p00x05p00", "npn_00p54x16p00", "npn_00p54x08p00"],
            "PNP":  ["pnp_10p00x10p00", "pnp_05p00x05p00", "pnp_10p00x00p42", "pnp_05p00x00p42"],
        },
        default_models={
            "NMOS": "nfet_03v3",
            "PMOS": "pfet_03v3",
            "NPN":  "npn_10p00x10p00",
            "PNP":  "pnp_10p00x10p00",
        },
        default_wl={
            "NMOS": ("2u", "0.28u"),
            "PMOS": ("4u", "0.28u"),
        },
        min_wl={
            "NMOS": ("0.22u", "0.28u"),
            "PMOS": ("0.22u", "0.28u"),
        },
        is_subcircuit=True,
        scale_microns=False,
        bjt_terminals=3,
    ),
    "sky130": PDKSpec(
        key="sky130",
        display_name="SkyWater 130nm (sky130A)",
        dir_candidates=["sky130A", "sky130B"],
        lib_relative=os.path.join("libs.tech", "ngspice", "sky130.lib.spice"),
        include_relatives=[],
        default_corner="tt",
        corners=["tt", "ss", "ff", "sf", "fs"],
        models={
            "NMOS": [
                "sky130_fd_pr__nfet_01v8",
                "sky130_fd_pr__nfet_01v8_lvt",
                "sky130_fd_pr__nfet_03v3_nvt",
                "sky130_fd_pr__nfet_05v0_nvt",
                "sky130_fd_pr__nfet_g5v0d10v5",
                "sky130_fd_pr__nfet_20v0",
            ],
            "PMOS": [
                "sky130_fd_pr__pfet_01v8",
                "sky130_fd_pr__pfet_01v8_lvt",
                "sky130_fd_pr__pfet_01v8_hvt",
                "sky130_fd_pr__pfet_g5v0d10v5",
                "sky130_fd_pr__pfet_g5v0d16v0",
            ],
            "NPN":  ["sky130_fd_pr__npn_05v5"],
            "PNP":  ["sky130_fd_pr__pnp_05v5"],
        },
        default_models={
            "NMOS": "sky130_fd_pr__nfet_01v8",
            "PMOS": "sky130_fd_pr__pfet_01v8",
            "NPN":  "sky130_fd_pr__npn_05v5",
            "PNP":  "sky130_fd_pr__pnp_05v5",
        },
        default_wl={
            "NMOS": ("1u", "0.15u"),
            "PMOS": ("2u", "0.15u"),
        },
        min_wl={
            "NMOS": ("0.42u", "0.15u"),
            "PMOS": ("0.42u", "0.15u"),
        },
        is_subcircuit=True,
        scale_microns=True,
        bjt_terminals=3,
    ),
    "ihp": PDKSpec(
        key="ihp",
        display_name="IHP SG13G2 (130nm BiCMOS)",
        dir_candidates=["ihp-sg13g2"],
        lib_relative=os.path.join("libs.tech", "ngspice", "models", "cornerMOSlv.lib"),
        include_relatives=[],
        secondary_lib_relative=os.path.join("libs.tech", "ngspice", "models", "cornerHBT.lib"),
        secondary_lib_corner="hbt_typ",
        default_corner="mos_tt",
        corners=["mos_tt", "mos_ff", "mos_ss", "mos_fs", "mos_sf"],
        models={
            "NMOS": ["sg13_lv_nmos", "sg13_hv_nmos"],
            "PMOS": ["sg13_lv_pmos", "sg13_hv_pmos"],
            "NPN":  ["npn13G2", "npn13G2l", "npn13G2v"],
            "PNP":  ["pnpMPA"],
        },
        default_models={
            "NMOS": "sg13_lv_nmos",
            "PMOS": "sg13_lv_pmos",
            "NPN":  "npn13G2",
            "PNP":  "pnpMPA",
        },
        default_wl={
            "NMOS": ("1.0u", "0.45u"),
            "PMOS": ("2.0u", "0.45u"),
        },
        min_wl={
            "NMOS": ("0.15u", "0.13u"),
            "PMOS": ("0.15u", "0.13u"),
        },
        is_subcircuit=True,
        scale_microns=False,
        bjt_terminals=4,  # Subcircuit expects 4 pins: c b e bn (substrate)
    ),
}


# Alias mappings
PDK_ALIASES: dict[str, str] = {
    "gf180": "gf180",
    "gf180mcu": "gf180",
    "gf": "gf180",
    "sky130": "sky130",
    "sky": "sky130",
    "skywater": "sky130",
    "ihp": "ihp",
    "sg13g2": "ihp",
    "ihp-sg13g2": "ihp",
}


@dataclass
class ResolvedPDK:
    spec: PDKSpec
    pdk_dir: str
    lib_file: str
    include_files: list[str]
    secondary_lib_file: str
    available: bool = False

    @property
    def key(self) -> str:
        return self.spec.key

    @property
    def display_name(self) -> str:
        return self.spec.display_name

    @property
    def corners(self) -> list[str]:
        return self.spec.corners

    @property
    def default_corner(self) -> str:
        return self.spec.default_corner

    @property
    def models(self) -> dict[str, list[str]]:
        return self.spec.models

    @property
    def default_models(self) -> dict[str, str]:
        return self.spec.default_models

    @property
    def default_wl(self) -> dict[str, tuple[str, str]]:
        return self.spec.default_wl

    @property
    def min_wl(self) -> dict[str, tuple[str, str]]:
        return self.spec.min_wl


def resolve_pdk(pdk_key: str) -> ResolvedPDK | None:
    """Find and resolve file paths for a specified PDK key."""
    canonical = PDK_ALIASES.get(pdk_key.lower().strip())
    if not canonical or canonical not in PDK_SPECS:
        return None

    spec = PDK_SPECS[canonical]
    roots = find_pdk_roots()

    resolved_dir = None
    for r in roots:
        # 1. Check if root itself is the pdk dir (e.g. /home/ziad/IHP-Open-PDK/ihp-sg13g2)
        base = os.path.basename(r)
        if base in spec.dir_candidates:
            resolved_dir = r
            break
        # 2. Check subdirectories under root
        for cand in spec.dir_candidates:
            p = os.path.join(r, cand)
            if os.path.isdir(p):
                resolved_dir = p
                break
        if resolved_dir:
            break

    if not resolved_dir:
        # Fallback placeholder path
        resolved_dir = os.path.join(roots[0] if roots else "/pdk", spec.dir_candidates[0])

    lib_path = os.path.join(resolved_dir, spec.lib_relative)
    inc_paths = [os.path.join(resolved_dir, rel) for rel in spec.include_relatives]
    sec_lib = (os.path.join(resolved_dir, spec.secondary_lib_relative)
               if spec.secondary_lib_relative else "")

    available = os.path.isfile(lib_path)

    return ResolvedPDK(
        spec=spec,
        pdk_dir=resolved_dir,
        lib_file=lib_path,
        include_files=inc_paths,
        secondary_lib_file=sec_lib,
        available=available,
    )


def detect_installed_pdks() -> dict[str, ResolvedPDK]:
    """Scan and return all configured PDKs with their detected system status."""
    res = {}
    for key in ("gf180", "sky130", "ihp"):
        pdk = resolve_pdk(key)
        if pdk:
            res[key] = pdk
    return res


# ── Dimension normaliser for PDKs ──────────────────────────────────────────────
def format_pdk_dim(val: str, pdk_key: str | None) -> str:
    """
    Format a W or L dimension value string according to PDK rules.
    SkyWater 130 sets .option scale=1.0u, so dimensions must be in microns
    without the 'u' suffix (e.g. 2u -> 2, 180n -> 0.18).
    GF180 and IHP expect standard SI suffixes (e.g. 2u, 180n).
    """
    s = val.strip()
    if not pdk_key or pdk_key.lower() not in ("sky130", "sky", "skywater"):
        return s

    # Normalise for Sky130
    m = re.match(r"^([\d.]+)\s*([a-zA-Zµμ]*)$", s)
    if not m:
        return s
    try:
        num = float(m.group(1))
    except ValueError:
        return s

    unit = m.group(2).lower()
    if unit in ("u", "um", "µ", "μ", "µm", "μm"):
        return f"{num:g}"
    elif unit in ("n", "nm"):
        return f"{num * 1e-3:g}"
    elif unit in ("p", "pm"):
        return f"{num * 1e-6:g}"
    elif unit in ("m", "mm"):
        return f"{num * 1e3:g}"
    elif not unit:
        # Bare number is already in microns
        return f"{num:g}"

    return s
