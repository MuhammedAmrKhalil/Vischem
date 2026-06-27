"""
netlist.py  —  Schematic → NGspice SPICE Netlist Generator
===========================================================

Given the component list and wire list from the schematic editor,
this module:

  1. Computes pin world-grid positions for every component (with rotation).
  2. Runs Union-Find on all wire endpoints + pin positions to group
     electrically connected nodes into nets.
  3. Names nets: any net touching a GND symbol becomes "0" (SPICE ground);
     all others get N001, N002 … in order of first encounter.
  4. Emits a valid NGspice netlist with the correct element line format
     for every supported component type.

Public API
----------
  generate(comps, wires, wlbls, sim_config, model_config, title) -> NetlistResult

  NetlistResult.netlist  : str   — the full SPICE text (ready to write to .cir)
  NetlistResult.nets     : dict  — {net_name: [grid_points]}
  NetlistResult.errors   : list  — validation warnings / errors
  NetlistResult.warnings : list

ModelConfig
-----------
  Carries all model information for the header section of the netlist.
  mode        : "inline"  — write .model card(s) directly into the netlist
              : "include" — emit  .include "path/to/file.sp"
              : "lib"     — emit  .lib "path/to/file.lib" <corner>
  level       : 1, 2, 3, "BSIM3", "BSIM4"  (used in inline mode only)
  file_path   : path to .sp / .lib file  (include / lib modes)
  corner      : corner name e.g. "tt"   (lib mode only)
  models      : {device_type: {"name": str, "params": {k:v}}}
                device_type  ∈ {"NMOS","PMOS","NPN","PNP"}
                In include/lib modes, "name" is what the device line references;
                "params" is ignored (the file supplies them).

Level 1 defaults  (inline mode, SPICE LEVEL=1 Shichman-Hodges)
  NMOS: VTO=1.0  KP=200u  LAMBDA=0.01  GAMMA=0.5  PHI=0.6
  PMOS: VTO=-1.0 KP=80u   LAMBDA=0.01  GAMMA=0.5  PHI=0.6
  NPN:  IS=1e-14 BF=100   VAF=50  TF=0.5n  CJE=1p  CJC=0.5p
  PNP:  IS=1e-14 BF=50    VAF=50  TF=1n    CJE=1p  CJC=0.5p

Supported SPICE element formats
---------------------------------
  R  →  Rlabel  n+ n-  value
  C  →  Clabel  n+ n-  value
  L  →  Llabel  n+ n-  value
  V  →  Vlabel  n+ n-  DC value  AC 0
  I  →  Ilabel  n+ n-  DC value
  G  →  (defines ground — no element line, marks net as "0")
  NMOS → Mlabel  drain  gate  source  bulk  model  W=x L=y
  PMOS → Mlabel  drain  gate  source  bulk  model  W=x L=y
  NPN  → Qlabel  collector  base  emitter  model
  PNP  → Qlabel  collector  base  emitter  model
"""

from __future__ import annotations
import math
import re
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass   # avoid circular import with editor


# ── Level parameter tables ─────────────────────────────────────────────────────
# Each level defines the default parameters for NMOS, PMOS, NPN, PNP.
# Higher levels (2, 3, BSIM3, BSIM4) are stubs — structure is in place
# so adding them later requires only filling in the param dicts.

LEVEL_PARAMS: dict = {
    1: {
        "NMOS": {
            "VTO":    1.0,
            "KP":     200e-6,
            "LAMBDA": 0.01,
            "GAMMA":  0.5,
            "PHI":    0.6,
        },
        "PMOS": {
            "VTO":    -1.0,
            "KP":     80e-6,
            "LAMBDA": 0.01,
            "GAMMA":  0.5,
            "PHI":    0.6,
        },
        "NPN": {
            "IS":  1e-14,
            "BF":  100,
            "VAF": 50,
            "TF":  0.5e-9,
            "CJE": 1e-12,
            "CJC": 0.5e-12,
        },
        "PNP": {
            "IS":  1e-14,
            "BF":  50,
            "VAF": 50,
            "TF":  1e-9,
            "CJE": 1e-12,
            "CJC": 0.5e-12,
        },
    },
    2: {
        # SPICE Level 2 — placeholder, extend when needed
        "NMOS": {"VTO": 1.0, "KP": 200e-6, "LAMBDA": 0.01,
                 "GAMMA": 0.5, "PHI": 0.6, "LD": 0.1e-6, "TOX": 20e-9},
        "PMOS": {"VTO": -1.0, "KP": 80e-6,  "LAMBDA": 0.01,
                 "GAMMA": 0.5, "PHI": 0.6, "LD": 0.1e-6, "TOX": 20e-9},
        "NPN":  {},
        "PNP":  {},
    },
    3: {
        # SPICE Level 3 — placeholder
        "NMOS": {"VTO": 1.0, "KP": 200e-6, "LAMBDA": 0.01,
                 "GAMMA": 0.5, "PHI": 0.6, "LD": 0.1e-6, "TOX": 20e-9,
                 "DELTA": 0.0, "ETA": 0.0, "THETA": 0.0, "KAPPA": 0.2},
        "PMOS": {"VTO": -1.0, "KP": 80e-6, "LAMBDA": 0.01,
                 "GAMMA": 0.5, "PHI": 0.6, "LD": 0.1e-6, "TOX": 20e-9,
                 "DELTA": 0.0, "ETA": 0.0, "THETA": 0.0, "KAPPA": 0.2},
        "NPN":  {},
        "PNP":  {},
    },
    "BSIM3": {
        # BSIM3v3 — placeholder (real params come from PDK file)
        "NMOS": {"TNOM": 27, "TOX": 7.5e-9, "XJ": 1.5e-7, "NCH": 2.3549e17},
        "PMOS": {"TNOM": 27, "TOX": 7.5e-9, "XJ": 1.5e-7, "NCH": 4.1589e17},
        "NPN":  {},
        "PNP":  {},
    },
    "BSIM4": {
        # BSIM4 — placeholder (real params come from PDK file)
        "NMOS": {"TNOM": 27, "TOXE": 6e-9, "TOXP": 5e-9, "TOXM": 6e-9},
        "PMOS": {"TNOM": 27, "TOXE": 6e-9, "TOXP": 5e-9, "TOXM": 6e-9},
        "NPN":  {},
        "PNP":  {},
    },
}

# Human-readable level labels for the UI
LEVEL_LABELS: dict = {
    1:       "Level 1  (Shichman-Hodges)",
    2:       "Level 2  (Grove-Frohman)",
    3:       "Level 3  (Semi-empirical)",
    "BSIM3": "BSIM3v3  (require PDK file)",
    "BSIM4": "BSIM4    (require PDK file)",
}

# Default model names per device type (inline mode)
_DEFAULT_MODEL_NAMES: dict = {
    "NMOS": "NMOS_GENERIC",
    "PMOS": "PMOS_GENERIC",
    "NPN":  "NPN_GENERIC",
    "PNP":  "PNP_GENERIC",
}

# Default W/L for transistors (used when not set on the component)
_DEFAULT_WL: dict = {
    "NMOS": ("2u",  "180n"),
    "PMOS": ("4u",  "180n"),
}

# Device type each transistor type belongs to
_MOSFET_TYPES = {"NMOS", "PMOS"}
_BJT_TYPES    = {"NPN", "PNP"}


# ── ModelConfig ────────────────────────────────────────────────────────────────
@dataclass
class ModelConfig:
    """
    Project-level model configuration.  One instance per project,
    shared across all transistors of each type.

    mode
        "inline"  — write .model cards directly into the netlist
        "include" — emit .include "file.sp"
        "lib"     — emit .lib "file.lib" <corner>

    level
        SPICE model level key: 1, 2, 3, "BSIM3", "BSIM4"
        Only meaningful in "inline" mode.

    file_path
        Absolute path to the .sp / .lib / .spi model file.
        Only used in "include" and "lib" modes.

    corner
        Corner string e.g. "tt", "ff", "ss".
        Only used in "lib" mode.

    device_models
        {device_type: {"name": str, "params": {param: value}, "w": str, "l": str}}
        device_type ∈ {"NMOS", "PMOS", "NPN", "PNP"}
        "name"   — model name referenced in the element line
        "params" — inline parameter overrides (ignored in include/lib modes)
        "w","l"  — default W/L for new MOSFETs (NMOS/PMOS only)
    """
    mode         : str  = "inline"   # "inline" | "include" | "lib"
    level        : object = 1        # 1 | 2 | 3 | "BSIM3" | "BSIM4"
    file_path    : str  = ""
    corner       : str  = "tt"
    device_models: dict = field(default_factory=dict)

    def __post_init__(self):
        # Ensure all four device types exist with sane defaults
        for dt in ("NMOS", "PMOS", "NPN", "PNP"):
            if dt not in self.device_models:
                w, l = _DEFAULT_WL.get(dt, ("", ""))
                self.device_models[dt] = {
                    "name":   _DEFAULT_MODEL_NAMES[dt],
                    "params": dict(LEVEL_PARAMS[1].get(dt, {})),
                    "w": w, "l": l,
                }

    # ── Serialisation ──────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "mode":          self.mode,
            "level":         self.level,
            "file_path":     self.file_path,
            "corner":        self.corner,
            "device_models": self.device_models,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ModelConfig":
        cfg = cls(
            mode      = d.get("mode",      "inline"),
            level     = d.get("level",     1),
            file_path = d.get("file_path", ""),
            corner    = d.get("corner",    "tt"),
        )
        # Restore saved per-device config, merging over defaults
        for dt, saved in d.get("device_models", {}).items():
            if dt in cfg.device_models:
                cfg.device_models[dt].update(saved)
            else:
                cfg.device_models[dt] = saved
        return cfg

    # ── Helpers used by the editor UI ─────────────────────────────────────────
    def model_name(self, device_type: str) -> str:
        """Return the model name string for a given device type."""
        return self.device_models.get(device_type, {}).get(
            "name", _DEFAULT_MODEL_NAMES.get(device_type, "UNKNOWN"))

    def default_wl(self, device_type: str) -> tuple[str, str]:
        """Return (W, L) defaults for a MOSFET device type."""
        dm = self.device_models.get(device_type, {})
        w = dm.get("w") or _DEFAULT_WL.get(device_type, ("2u", "180n"))[0]
        l = dm.get("l") or _DEFAULT_WL.get(device_type, ("2u", "180n"))[1]
        return w, l


def _vsrc_spice_fallback(vsrc_type: str, vsrc_params: dict,
                          vsrc_dc: str, vsrc_ac: str = "0",
                          vsrc_ac_phase: str = "0") -> str:
    """
    Build a SPICE V-source body string from structured attributes,
    used when the schematic_editor module is not importable (e.g. unit tests).
    """
    p   = vsrc_params.get(vsrc_type, [])
    dc  = vsrc_dc       or "0"
    ac  = vsrc_ac       or "0"
    aph = vsrc_ac_phase or "0"

    def _g(i, default="0"):
        return p[i] if i < len(p) else default

    def _ac_suffix():
        """Build ' AC x [phase]' only when ac != 0."""
        try:
            if float(ac) == 0:
                return ""
        except ValueError:
            pass
        s = f" AC {ac}"
        try:
            if float(aph) != 0:
                s += f" {aph}"
        except ValueError:
            pass
        return s

    if vsrc_type == "DC":
        body = f"DC {_g(0,'1')}"
        try:
            ac_val = _g(1,"0")
            if float(ac_val) != 0:
                body += f" AC {ac_val}"
                ph = _g(2,"0")
                try:
                    if float(ph) != 0:
                        body += f" {ph}"
                except ValueError:
                    pass
        except ValueError:
            pass
        return body

    if vsrc_type == "AC":
        body = f"DC {_g(0,'0')} AC {_g(1,'1')}"
        ph = _g(2,"0")
        try:
            if float(ph) != 0:
                body += f" {ph}"
        except ValueError:
            pass
        return body

    if vsrc_type == "SIN":
        return (f"DC {dc}{_ac_suffix()}"
                f" SIN({_g(0,'0')} {_g(1,'1')} {_g(2,'1k')} "
                f"{_g(3,'0')} {_g(4,'0')} {_g(5,'0')})")
    if vsrc_type == "PULSE":
        return (f"DC {dc}{_ac_suffix()}"
                f" PULSE({_g(0,'0')} {_g(1,'5')} {_g(2,'0')} "
                f"{_g(3,'1n')} {_g(4,'1n')} {_g(5,'500n')} {_g(6,'1u')})")
    if vsrc_type == "EXP":
        return (f"DC {dc}{_ac_suffix()}"
                f" EXP({_g(0,'0')} {_g(1,'1')} {_g(2,'0')} "
                f"{_g(3,'100n')} {_g(4,'200n')} {_g(5,'100n')})")
    if vsrc_type == "PWL":
        return f"DC {dc}{_ac_suffix()} PWL({_g(0,'0 0  100n 1  200n 0')})"
    if vsrc_type == "SFFM":
        return (f"DC {dc}{_ac_suffix()}"
                f" SFFM({_g(0,'0')} {_g(1,'1')} {_g(2,'1k')} "
                f"{_g(3,'5')} {_g(4,'200')})")
    return f"DC {dc}"


# ── Model file parser ──────────────────────────────────────────────────────────
def parse_model_file(path: str) -> dict[str, list[str]]:
    """
    Scan a .sp / .lib / .spi file and extract all .model definitions.

    Returns
    -------
    {device_type: [model_name, ...]}
    e.g. {"NMOS": ["nmos_rf", "nmos_lvt"], "PMOS": ["pmos_lvt"], "NPN": [], "PNP": []}

    Handles:
      .model  name  NMOS  (...)
      .model  name  PMOS  (...)
      .model  name  NPN   (...)
      .model  name  PNP   (...)
      .MODEL  (case-insensitive)
    Multi-line continuations (+) are collapsed before parsing.
    """
    result: dict[str, list[str]] = {"NMOS": [], "PMOS": [], "NPN": [], "PNP": []}

    if not path or not os.path.isfile(path):
        return result

    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except Exception:
        return result

    # Collapse SPICE line continuations (lines starting with +)
    collapsed = re.sub(r"\n\+", " ", raw)

    for line in collapsed.splitlines():
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        # Match:  .model  <name>  <type>  [optional params]
        m = re.match(
            r"\.model\s+(\S+)\s+(NMOS|PMOS|NPN|PNP|NMOS\w*|PMOS\w*)",
            line, re.IGNORECASE)
        if m:
            name  = m.group(1)
            dtype = m.group(2).upper()
            # Normalise to the four canonical keys
            if dtype.startswith("NMOS"): dtype = "NMOS"
            elif dtype.startswith("PMOS"): dtype = "PMOS"
            elif dtype == "NPN": pass
            elif dtype == "PNP": pass
            else: continue
            if name not in result[dtype]:
                result[dtype].append(name)

    return result


# ── Value normaliser ───────────────────────────────────────────────────────────
_UNIT_MAP = [
    ("meg", "Meg"), ("Meg", "Meg"),
    ("k",   "k"),   ("K",   "k"),
    ("m",   "m"),   ("M",   "Meg"),
    ("u",   "u"),   ("µ",   "u"),  ("μ", "u"),
    ("n",   "n"),
    ("p",   "p"),
    ("f",   "f"),
    ("g",   "G"),   ("G",   "G"),
    ("t",   "T"),   ("T",   "T"),
]

def _normalise_value(raw: str, typ: str) -> str:
    v = raw.strip()
    if typ in ("NMOS", "PMOS"):
        wl = re.search(r"W[/]?L\s*=\s*([\d.]+\w+)\s*/\s*([\d.]+\w+)", v, re.I)
        if wl:
            return f"W={_si(wl.group(1))} L={_si(wl.group(2))}"
        w = re.search(r"W\s*=\s*([\d.]+\w+)", v, re.I)
        l = re.search(r"L\s*=\s*([\d.]+\w+)", v, re.I)
        if w and l:
            return f"W={_si(w.group(1))} L={_si(l.group(1))}"
        return "W=2u L=180n"
    if typ in ("NPN", "PNP"):
        return ""
    v = v.replace("Ω","").replace("Ω","").replace("ohm","")
    v = v.replace("F","").replace("H","").replace("A","").replace("V","")
    v = v.strip()
    return _si(v)


def _si(v: str) -> str:
    v = v.strip()
    for human, spice in _UNIT_MAP:
        if re.search(re.escape(human) + r"\s*$", v):
            num = re.sub(re.escape(human) + r"\s*$", "", v).strip()
            return f"{num}{spice}"
    return v


# ── SI formatter for inline model params ───────────────────────────────────────
def _fmt_param(val) -> str:
    """
    Format a numeric model parameter value for a .model card.
    Keeps scientific notation where appropriate.
    """
    try:
        v = float(val)
    except (ValueError, TypeError):
        return str(val)
    if v == 0:
        return "0"
    # Use engineering notation for very small/large values
    if abs(v) < 1e-9:
        return f"{v:.3e}"
    if abs(v) < 1e-6:
        return f"{v*1e9:.4g}n"
    if abs(v) < 1e-3:
        return f"{v*1e6:.4g}u"
    if abs(v) < 1:
        return f"{v*1e3:.4g}m"
    if abs(v) >= 1e9:
        return f"{v/1e9:.4g}G"
    if abs(v) >= 1e6:
        return f"{v/1e6:.4g}Meg"
    if abs(v) >= 1e3:
        return f"{v/1e3:.4g}k"
    return f"{v:.6g}"


def _emit_model_header(model_config: "ModelConfig | None") -> list[str]:
    """
    Produce the header lines (.model / .include / .lib) for the netlist.
    Returns a list of SPICE text lines.
    """
    if model_config is None:
        # Legacy fallback — bare placeholder names, no .model cards
        return [
            "* No model configured — add models via Model Manager",
            "* Transistors reference NMOS_GENERIC / PMOS_GENERIC / NPN_GENERIC / PNP_GENERIC",
            "* These must be defined in an external file or replaced via Model Manager",
            "*",
        ]

    lines: list[str] = []
    mode = model_config.mode

    if mode == "include":
        fp = model_config.file_path or "model_file.sp"
        lines.append(f'.include "{fp}"')
        lines.append("*")

    elif mode == "lib":
        fp     = model_config.file_path or "model_file.lib"
        corner = model_config.corner    or "tt"
        lines.append(f'.lib "{fp}" {corner}')
        lines.append("*")

    else:  # "inline"
        level  = model_config.level
        lvl_lbl = LEVEL_LABELS.get(level, f"Level {level}")
        lines.append(f"* ── Inline models  ({lvl_lbl}) ──────────────────────────────")

        for dt in ("NMOS", "PMOS", "NPN", "PNP"):
            dm = model_config.device_models.get(dt, {})
            name   = dm.get("name", _DEFAULT_MODEL_NAMES[dt])
            params = dm.get("params", {})

            if not params:
                # Stub level — warn and emit a bare placeholder
                lines.append(
                    f"* WARNING: {dt} model '{name}' has no inline params "
                    f"— use a PDK file for {lvl_lbl}")
                lines.append(
                    f".model {name:<20} {dt}  "
                    f"(LEVEL={level if isinstance(level,int) else 3})")
                continue

            # Build parameter string, 4 per line for readability
            param_items = list(params.items())
            level_int   = level if isinstance(level, int) else 3
            first_chunk = f"LEVEL={level_int}"
            chunks      = [first_chunk]
            for k, v in param_items:
                chunks.append(f"{k}={_fmt_param(v)}")

            # Wrap at 4 params per continuation line
            def _wrap(items, per_line=4):
                out = []
                for i in range(0, len(items), per_line):
                    out.append("  ".join(items[i:i+per_line]))
                return out

            param_lines = _wrap(chunks)
            lines.append(f".model {name:<20} {dt}  (")
            for i, pl in enumerate(param_lines):
                cont = "+" if i > 0 else " "
                sep  = ")" if i == len(param_lines)-1 else ""
                lines.append(f"+ {pl}{sep}")
            lines.append("*")

    return lines


# ── Pin definitions ────────────────────────────────────────────────────────────
_PINS: dict[str, list[tuple[float, float, str]]] = {
    "R":    [(-1, 0, "p"), ( 1,  0, "n")],
    "C":    [(-1, 0, "p"), ( 1,  0, "n")],
    "L":    [(-1, 0, "p"), ( 1,  0, "n")],
    "V":    [( 0,-1, "p"), ( 0,  1, "n")],
    "I":    [( 0,-1, "p"), ( 0,  1, "n")],
    "G":    [( 0, 0, "gnd")],
    "NMOS": [(-1, 0, "gate"), (0, -1, "drain"), (0,  1, "source")],
    "PMOS": [(-1, 0, "gate"), (0, -1, "source"), (0,  1, "drain")],
    "NPN":  [(-1, 0, "base"), (0, -1, "collector"), (0,  1, "emitter")],
    "PNP":  [(-1, 0, "base"), (0, -1, "collector"), (0,  1, "emitter")],
    "PIN_IN":    [(0, 0, "port")],
    "PIN_OUT":   [(0, 0, "port")],
    "PIN_INOUT": [(0, 0, "port")],
    "PIN_VDD":   [(0, 0, "port")],
    "PIN_VSS":   [(0, 0, "port")],
}


# ── Union-Find ─────────────────────────────────────────────────────────────────
class _UF:
    def __init__(self):
        self._p: dict = {}

    def find(self, x):
        self._p.setdefault(x, x)
        if self._p[x] != x:
            self._p[x] = self.find(self._p[x])
        return self._p[x]

    def union(self, a, b):
        self._p[self.find(a)] = self.find(b)

    def groups(self) -> dict:
        out: dict = {}
        for x in self._p:
            r = self.find(x)
            out.setdefault(r, []).append(x)
        return out


# ── Result type ────────────────────────────────────────────────────────────────
@dataclass
class NetlistResult:
    netlist  : str       = ""
    nets     : dict      = field(default_factory=dict)
    point_net: dict      = field(default_factory=dict)
    errors   : list[str] = field(default_factory=list)
    warnings : list[str] = field(default_factory=list)


# ── Main entry point ───────────────────────────────────────────────────────────
def generate(comps: list, wires: list, wlbls: list = None,
             sim_config=None,
             model_config: "ModelConfig | None" = None,
             title: str = "Vischem",
             pdk_include: str = "") -> NetlistResult:
    """
    Build a complete NGspice netlist from editor component + wire lists.

    Parameters
    ----------
    comps        : list of Component objects (from editor)
    wires        : list of Wire objects (from editor)
    wlbls        : list of WireLabel objects (optional)
    sim_config   : SimConfig object (optional)
    model_config : ModelConfig object (optional).
    title        : first-line title comment
    pdk_include  : DEPRECATED — use model_config instead.
    """
    if wlbls is None:
        wlbls = []
    result = NetlistResult()

    # ── Step 1: pin world positions ────────────────────────────────────────────
    pin_map: dict[tuple, list] = {}
    for comp in comps:
        pins = _PINS.get(comp.type)
        if pins is None:
            result.warnings.append(f"Unknown component type '{comp.type}' — skipped")
            continue
        rad = math.radians(comp.rot)
        cr, sr = math.cos(rad), math.sin(rad)
        flip = getattr(comp, 'flip', False)
        for dx, dy, role in pins:
            fdx = -dx if flip else dx
            rx = comp.gx + round(fdx * cr - dy * sr)
            ry = comp.gy + round(fdx * sr + dy * cr)
            pt = (rx, ry)
            pin_map.setdefault(pt, []).append((comp, role))

    # ── Step 2: union-find ─────────────────────────────────────────────────────
    uf = _UF()
    for pt in pin_map:
        uf.find(pt)
    for w in wires:
        uf.union((w.x1, w.y1), (w.x2, w.y2))
        for pt in ((w.x1, w.y1), (w.x2, w.y2)):
            if pt in pin_map:
                uf.union(pt, pt)
    for pt in pin_map:
        uf.find(pt)

    # ── Step 3: GND nets ───────────────────────────────────────────────────────
    gnd_roots: set = set()
    for comp in comps:
        if comp.type == "G":
            pt = (comp.gx, comp.gy)
            gnd_roots.add(uf.find(pt))
        for pt, entries in pin_map.items():
            for c, role in entries:
                if role == "gnd":
                    gnd_roots.add(uf.find(pt))

    # ── Step 3b: global net merging (wire labels + pin symbols) ───────────────
    gnd_names = {"GND", "VSS", "0"}
    upper_to_roots: dict = {}
    upper_to_canon: dict = {}

    def _register(txt, pt):
        uf.find(pt)
        root = uf.find(pt)
        key  = txt.strip().upper()
        if not key: return
        upper_to_roots.setdefault(key, set()).add(root)
        if key not in upper_to_canon:
            upper_to_canon[key] = txt.strip()

    for wl in wlbls:
        _register(wl.text, (wl.gx, wl.gy))

    PIN_SYM = {"PIN_VDD","PIN_VSS","PIN_IN","PIN_OUT","PIN_INOUT"}
    for comp in comps:
        if comp.type not in PIN_SYM: continue
        txt = (comp.value or comp.type.replace("PIN_","")).strip()
        _register(txt, (comp.gx, comp.gy))

    for key, roots_set in upper_to_roots.items():
        roots_list = list(roots_set)
        for i in range(1, len(roots_list)):
            uf.union(roots_list[0], roots_list[i])

    for key, roots_set in upper_to_roots.items():
        if key in gnd_names:
            for root in roots_set:
                gnd_roots.add(uf.find(root))

    label_roots: dict = {}
    for key, roots_set in upper_to_roots.items():
        if key in gnd_names: continue
        canon = upper_to_canon[key]
        for root in roots_set:
            merged = uf.find(root)
            if merged not in label_roots:
                label_roots[merged] = canon

    # ── Step 4: name all nets ──────────────────────────────────────────────────
    counter  = [0]
    root_name: dict = {}

    def net_name(pt):
        r = uf.find(pt)
        if r not in root_name:
            if r in gnd_roots:
                root_name[r] = "0"
            elif r in label_roots:
                root_name[r] = label_roots[r]
            else:
                counter[0] += 1
                root_name[r] = f"N{counter[0]:03d}"
        return root_name[r]

    all_pts = set(pin_map.keys())
    for w in wires:
        all_pts.add((w.x1, w.y1))
        all_pts.add((w.x2, w.y2))
    for pt in all_pts:
        name = net_name(pt)
        result.point_net[pt] = name
        result.nets.setdefault(name, []).append(pt)

    def pin_net(comp, role: str) -> str:
        pins = _PINS.get(comp.type, [])
        rad  = math.radians(comp.rot)
        cr, sr = math.cos(rad), math.sin(rad)
        flip = getattr(comp, 'flip', False)
        for dx, dy, r in pins:
            if r == role:
                fdx = -dx if flip else dx
                rx = comp.gx + round(fdx * cr - dy * sr)
                ry = comp.gy + round(fdx * sr + dy * cr)
                return net_name((rx, ry))
        return "?"

    # ── Step 5: validation ─────────────────────────────────────────────────────
    if not any(c.type == "G" for c in comps):
        result.warnings.append(
            "No GND symbol found — add at least one G to define net '0'")
    if sum(1 for c in comps if c.type == "V") == 0:
        result.warnings.append("No voltage source found — add a V source")

    for comp in comps:
        if comp.type == "G": continue
        pins = _PINS.get(comp.type, [])
        rad  = math.radians(comp.rot)
        cr, sr = math.cos(rad), math.sin(rad)
        flip = getattr(comp, 'flip', False)
        for dx, dy, role in pins:
            fdx = -dx if flip else dx
            rx = comp.gx + round(fdx * cr - dy * sr)
            ry = comp.gy + round(fdx * sr + dy * cr)
            pt = (rx, ry)
            wire_touches = any(
                (w.x1==rx and w.y1==ry) or (w.x2==rx and w.y2==ry)
                for w in wires)
            pin_mates = len(pin_map.get(pt, []))
            if not wire_touches and pin_mates < 2:
                result.warnings.append(
                    f"Floating pin: {comp.label} pin '{role}' at ({rx},{ry})")

    # ── Step 6: emit SPICE lines ───────────────────────────────────────────────
    lines: list[str] = []
    lines.append(f"* {title}")
    lines.append("* Generated by Vischem v0.1 — NGspice ready")
    lines.append("*")

    # Model header — ModelConfig takes priority over legacy pdk_include
    if model_config is not None:
        lines.append("* ── Models ──────────────────────────────────────────────────────────")
        lines.extend(_emit_model_header(model_config))
    elif pdk_include:
        # Legacy path — kept for backward compatibility
        lines.append(f'.include "{pdk_include}"')
        lines.append("*")
    else:
        lines.extend(_emit_model_header(None))

    if result.warnings:
        lines.append("* ── Warnings ──")
        for w in result.warnings:
            lines.append(f"* [!] {w}")
        lines.append("*")

    lines.append("* ── Netlist ──")

    for comp in comps:
        t   = comp.type
        if t == "G": continue

        val = _normalise_value(comp.value, t)

        if t == "R":
            p = pin_net(comp, "p"); n = pin_net(comp, "n")
            lines.append(f"{comp.label:<10} {p:<8} {n:<8} {val}")

        elif t == "C":
            p = pin_net(comp, "p"); n = pin_net(comp, "n")
            lines.append(f"{comp.label:<10} {p:<8} {n:<8} {val}")

        elif t == "L":
            p = pin_net(comp, "p"); n = pin_net(comp, "n")
            lines.append(f"{comp.label:<10} {p:<8} {n:<8} {val}")

        elif t == "V":
            p_net = pin_net(comp, "p"); n_net = pin_net(comp, "n")
            vsrc_type   = getattr(comp, "vsrc_type",   None)
            vsrc_params = getattr(comp, "vsrc_params",  {})
            vsrc_dc     = getattr(comp, "vsrc_dc",     "0") or "0"

            if vsrc_type and vsrc_type in ("DC","AC","SIN","PULSE","EXP","PWL","SFFM"):
                vsrc_ac       = getattr(comp, "vsrc_ac",       "0") or "0"
                vsrc_ac_phase = getattr(comp, "vsrc_ac_phase", "0") or "0"
                body = _vsrc_spice_fallback(
                    vsrc_type, vsrc_params, vsrc_dc, vsrc_ac, vsrc_ac_phase)
                lines.append(f"{comp.label:<10} {p_net:<8} {n_net:<8} {body}")
            else:
                # ── Legacy plain-text value path ───────────────────────────
                v = _normalise_value(comp.value, "V") or "0"
                if re.search(r"\bac\b", comp.value, re.I):
                    lines.append(f"{comp.label:<10} {p_net:<8} {n_net:<8} DC 0 AC {v}")
                else:
                    lines.append(f"{comp.label:<10} {p_net:<8} {n_net:<8} DC {v} AC 0")

        elif t == "I":
            p = pin_net(comp, "p"); n = pin_net(comp, "n")
            lines.append(f"{comp.label:<10} {p:<8} {n:<8} DC {val or '0'}")

        elif t in _MOSFET_TYPES:
            d   = pin_net(comp, "drain")
            g   = pin_net(comp, "gate")
            s   = pin_net(comp, "source")
            # Bulk: use per-component bulk_net attribute if set, else 0
            blk = getattr(comp, 'bulk_net', "0") or "0"

            # Model name: from component attribute, else from ModelConfig, else generic
            if model_config:
                mdl = getattr(comp, 'model_name', None) or model_config.model_name(t)
            else:
                mdl = getattr(comp, 'model_name', None) or _DEFAULT_MODEL_NAMES[t]

            # W/L: from component attributes if set, else ModelConfig defaults, else hardcoded
            w = getattr(comp, 'mos_w', None)
            l = getattr(comp, 'mos_l', None)
            if not w or not l:
                if model_config:
                    dw, dl = model_config.default_wl(t)
                    w = w or dw
                    l = l or dl
                else:
                    w = w or ("2u" if t=="NMOS" else "4u")
                    l = l or "180n"
            lines.append(f"{comp.label:<10} {d:<8} {g:<8} {s:<8} {blk:<6} "
                         f"{mdl}  W={_si(w)} L={_si(l)}")

        elif t in _BJT_TYPES:
            c   = pin_net(comp, "collector")
            b   = pin_net(comp, "base")
            e   = pin_net(comp, "emitter")
            if model_config:
                mdl = getattr(comp, 'model_name', None) or model_config.model_name(t)
            else:
                mdl = getattr(comp, 'model_name', None) or _DEFAULT_MODEL_NAMES[t]
            lines.append(f"{comp.label:<10} {c:<8} {b:<8} {e:<8} {mdl}")

        else:
            result.warnings.append(f"No SPICE emitter for type '{t}' — skipped")

    # ── Step 7: simulation command ─────────────────────────────────────────────
    lines.append("*")
    lines.append("* ── Simulation ──────────────────────────────────────────────────────")
    if sim_config is not None:
        try:
            spice_line = sim_config.spice_line()
            ana_key    = sim_config.analysis
            lines.append(f"* Active: {ana_key}")
            lines.append(spice_line)
            lines.append("*")
            lines.append("* Other analyses (uncomment to use):")
            for key in ["OP","DC","TRAN","AC","NOISE"]:
                if key == ana_key: continue
                lines.append(f"* .{key.lower()} ...")
        except Exception as e:
            lines.append(f"* (sim_config error: {e})")
            lines.append("*.op")
    else:
        lines.append("* No simulation configured — uncomment one:")
        lines.append("*.op")
        lines.append("*.dc V1 0 5 0.01")
        lines.append("*.tran 1n 100n")
        lines.append("*.ac dec 100 1k 10G")
    lines.append("*")
    lines.append(".end")
    result.netlist = "\n".join(lines)
    return result


# ── CLI smoke-test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    class _C:
        def __init__(self, t, gx, gy, label, value, rot=0):
            self.type=t; self.gx=gx; self.gy=gy
            self.label=label; self.value=value; self.rot=rot; self.flip=False
            self.model_name=None; self.bulk_net="0"
            self.mos_w=None; self.mos_l=None

    class _W:
        def __init__(self, x1,y1,x2,y2):
            self.x1=x1; self.y1=y1; self.x2=x2; self.y2=y2

    comps = [
        _C("V",    2, 5, "V1",  "1V"),
        _C("NMOS", 5, 5, "M1",  "W/L=2u/180n"),
        _C("R",    5, 2, "RD",  "10kΩ"),
        _C("G",    2, 6, "GND1",""),
        _C("G",    5, 6, "GND2",""),
    ]
    wires = [
        _W(2,5, 5,5),
        _W(5,4, 5,3),
        _W(5,1, 5,2),
        _W(2,6, 2,5),
        _W(5,6, 5,5),
    ]
    cfg = ModelConfig(mode="inline", level=1)
    r = generate(comps, wires, model_config=cfg, title="NMOS Inverter Test")
    print(r.netlist)
    print("\n── Warnings ──")
    for w in r.warnings: print(" *", w)
