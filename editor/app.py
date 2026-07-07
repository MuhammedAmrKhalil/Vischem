#!/usr/bin/env python3
"""
Vischem — Visual Schematic Editor  v0.1
Based on the stable v0.5 Toplevel-dialog architecture.


HOTKEYS
  ↑ ↓ ← →     Move cursor
  M            Toggle MOUSE mode
  + / -        Zoom in / out   (also Ctrl+Wheel)
  R C L V I G  Place passive component
  W            Wire mode  (W/Enter=commit · Esc=cancel)
  Space        Rotate 90°
  F            Flip  (horizontal mirror)
  E            Edit label → value
  shift + ":"            Open command dialog

COMMAND DIALOG (:)
  nmos pmos npn pnp    Place transistor
  save                 File-dialog → .json / .csv / .png / .svg
  load                 File-dialog → .json / .csv
  netlist              File-dialog → .cir
  doc                  File-dialog → B&W documentation image (.png/.jpg/.bmp)
  zoom [%]             Set zoom percentage
  clear                Clear canvas
  help                 List commands
"""

import tkinter as tk
from tkinter import filedialog
import math, csv, os, sys, json, tempfile

try:
    from PIL import ImageGrab, Image, ImageOps
    _PILLOW = True
except ImportError:
    _PILLOW = False

# ── Symbol + netlist packages ───────────────────────────────────────────────────
# _ROOT is the project root (one level above editor/)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from symbols import draw_symbol, KNOWN_TYPES, DrawContext   # noqa: E402

try:
    from editor.netlist import generate as generate_netlist, ModelConfig, \
                               parse_model_file, LEVEL_LABELS
    _HAS_NETLIST = True
except ImportError:
    try:
        from netlist import generate as generate_netlist, ModelConfig, \
                            parse_model_file, LEVEL_LABELS
        _HAS_NETLIST = True
    except ImportError:
        _HAS_NETLIST = False
        class ModelConfig:           # type: ignore
            def __init__(self, **kw): pass
            def to_dict(self): return {}
            @classmethod
            def from_dict(cls, d): return cls()
            def model_name(self, dt): return f"{dt}_GENERIC"
            def default_wl(self, dt): return ("2u","180n")
        def parse_model_file(p): return {"NMOS":[],"PMOS":[],"NPN":[],"PNP":[]}
        LEVEL_LABELS = {1:"Level 1",2:"Level 2",3:"Level 3",
                        "BSIM3":"BSIM3","BSIM4":"BSIM4"}

try:
    from editor.simulation import find_ngspice, run as run_simulation, \
                                  simulator_version, SimRun
    _HAS_SIM = True
except ImportError:
    try:
        from simulation import find_ngspice, run as run_simulation, \
                               simulator_version, SimRun
        _HAS_SIM = True
    except ImportError:
        _HAS_SIM = False
        def find_ngspice(): return None       # type: ignore
        def simulator_version(p): return ""   # type: ignore

# ── Grid ───────────────────────────────────────────────────────────────────────
GS_DEFAULT = 72
GS_MIN     = 32
GS_MAX     = 130
COLS       = 50
ROWS       = 50

# File-dialog filter specs
FD_JSON    = [("VLSI Schematic",  "*.json"), ("All files", "*.*")]
FD_NETLIST = [("SPICE Netlist",   "*.cir"),  ("All files", "*.*")]
FD_SVG     = [("SVG Image",       "*.svg"),  ("All files", "*.*")]
FD_RASTER  = [("PNG Image",       "*.png"),
              ("JPEG Image",      "*.jpg"),
              ("Bitmap",          "*.bmp"),
              ("All files",       "*.*")]
FD_MODEL   = [("SPICE Model File", "*.sp *.lib *.spi *.mod"),
              ("SP File",  "*.sp"), ("LIB File", "*.lib"),
              ("All files", "*.*")]
FD_LOAD    = [("VLSI Schematic",  "*.json"),
              ("CSV Schematic",   "*.csv"),
              ("All files",       "*.*")]
FD_SAVE_ALL= [("VLSI Schematic",  "*.json"),
              ("PNG Image",       "*.png"),
              ("JPEG Image",      "*.jpg"),
              ("SVG Image",       "*.svg"),
              ("All files",       "*.*")]

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}

# ── Palette ────────────────────────────────────────────────────────────────────
BG        = "#07090f"
GRID_DOT  = "#131d30"
WIRE_C    = "#22c55e"
WIRE_PRV  = "#4ade80"
CURSOR_C  = "#f59e0b"
PANEL_BG  = "#0b0f1c"
BORDER    = "#141c2e"
SEL_RECT  = "#1a1200"
SEL_OUT   = "#f59e0b"
LBL_NORMAL= "#94a3b8"
LBL_SEL   = "#fbbf24"
VAL_NORMAL= "#818cf8"
VAL_SEL   = "#c4b5fd"
FLIP_DOT  = "#f472b6"   # magenta indicator for flipped components

MODE_COLS = {
    "NORMAL": ("#10082a", "#a78bfa"),
    "WIRE":   ("#071a07", "#4ade80"),
    "MOUSE":  ("#0a1520", "#38bdf8"),
}

DEFAULTS = {
    "R":"1kΩ",  "C":"1pF",  "L":"1nH",
    "V":"DC=1V AC=0", "I":"DC=1mA", "G":"",
    "NMOS":"W/L=2u/180n", "PMOS":"W/L=4u/180n",
    "NPN":"β=100",        "PNP":"β=100",
    # Ports / pins — value holds the net name shown in the flag
    "PIN_IN":    "IN",
    "PIN_OUT":   "OUT",
    "PIN_INOUT": "INOUT",
    "PIN_VDD":   "VDD",
    "PIN_VSS":   "VSS",
}
PREFIX = {
    "R":"R","C":"C","L":"L","V":"V","I":"I","G":"GND",
    "NMOS":"M","PMOS":"M","NPN":"Q","PNP":"Q",
    "PIN_IN":"P","PIN_OUT":"P","PIN_INOUT":"P",
    "PIN_VDD":"P","PIN_VSS":"P",
}

# Types that share the same label counter (so NMOS and PMOS both use M1, M2, ...)
COUNTER_GROUP = {
    "NMOS": "MOS",
    "PMOS": "MOS",
    "NPN":  "BJT",
    "PNP":  "BJT",
    "PIN_IN":    "PIN",
    "PIN_OUT":   "PIN",
    "PIN_INOUT": "PIN",
    "PIN_VDD":   "PIN",
    "PIN_VSS":   "PIN",
}

# Pin types (used for rendering and netlist port declarations)
PIN_TYPES = {"PIN_IN", "PIN_OUT", "PIN_INOUT", "PIN_VDD", "PIN_VSS"}
WIRE_LBL_COLOR = "#38bdf8"   # cyan — wire net labels
PIN_COLOR      = "#7dd3fc"   # sky-blue — pin flags

# ── Voltage source waveform definitions ───────────────────────────────────────
# Used by the V-source Properties dialog (E key) and by netlist.py emit logic.
# spice lambda signature: (params, dc_bias, ac_mag, ac_phase)
# DC and AC tabs handle their own bias internally (params already contain them).
# Transient tabs (SIN/PULSE/EXP/PWL/SFFM) receive dc/ac/phase as separate args
# so the dialog can show dedicated "DC bias" + "AC magnitude" + "AC phase" fields.
VSRC_TYPES = {
    "DC": {
        "label": "DC",
        "params": [
            ("DC voltage (V)",         "1"),
            ("AC magnitude (V)",       "0"),
            ("AC phase (deg)",         "0"),
        ],
        "spice": lambda p, dc, ac, aph: (
            f"DC {p[0]}"
            + (f" AC {p[1]}" if float(p[1] or 0) != 0 else "")
            + (f" {p[2]}" if float(p[1] or 0) != 0 and float(p[2] or 0) != 0 else "")
        ),
    },
    "AC": {
        "label": "AC",
        "params": [
            ("DC bias (V)",            "0"),
            ("AC magnitude (V)",       "1"),
            ("AC phase (deg)",         "0"),
        ],
        "spice": lambda p, dc, ac, aph: (
            f"DC {p[0]} AC {p[1]}"
            + (f" {p[2]}" if float(p[2] or 0) != 0 else "")
        ),
    },
    "SIN": {
        "label": "SIN",
        "params": [
            ("DC offset Voff (V)",     "0"),
            ("Amplitude Vpk (V)",      "1"),
            ("Frequency (Hz)",         "1k"),
            ("Delay Td (s)",           "0"),
            ("Damping factor θ (1/s)", "0"),
            ("Phase φ (deg)",          "0"),
        ],
        "spice": lambda p, dc, ac, aph: (
            f"DC {dc}"
            + (f" AC {ac}" if float(ac or 0) != 0 else "")
            + (f" {aph}" if float(ac or 0) != 0 and float(aph or 0) != 0 else "")
            + f" SIN({p[0]} {p[1]} {p[2]} {p[3]} {p[4]} {p[5]})"
        ),
    },
    "PULSE": {
        "label": "PULSE",
        "params": [
            ("Initial voltage V1 (V)", "0"),
            ("Pulsed voltage V2 (V)",  "5"),
            ("Delay time Td (s)",      "0"),
            ("Rise time Tr (s)",       "1n"),
            ("Fall time Tf (s)",       "1n"),
            ("Pulse width PW (s)",     "500n"),
            ("Period PER (s)",         "1u"),
        ],
        "spice": lambda p, dc, ac, aph: (
            f"DC {dc}"
            + (f" AC {ac}" if float(ac or 0) != 0 else "")
            + (f" {aph}" if float(ac or 0) != 0 and float(aph or 0) != 0 else "")
            + f" PULSE({p[0]} {p[1]} {p[2]} {p[3]} {p[4]} {p[5]} {p[6]})"
        ),
    },
    "EXP": {
        "label": "EXP",
        "params": [
            ("Initial voltage V1 (V)", "0"),
            ("Pulsed voltage V2 (V)",  "1"),
            ("Rise delay Td1 (s)",     "0"),
            ("Rise time const τ1 (s)", "100n"),
            ("Fall delay Td2 (s)",     "200n"),
            ("Fall time const τ2 (s)", "100n"),
        ],
        "spice": lambda p, dc, ac, aph: (
            f"DC {dc}"
            + (f" AC {ac}" if float(ac or 0) != 0 else "")
            + (f" {aph}" if float(ac or 0) != 0 and float(aph or 0) != 0 else "")
            + f" EXP({p[0]} {p[1]} {p[2]} {p[3]} {p[4]} {p[5]})"
        ),
    },
    "PWL": {
        "label": "PWL",
        "params": [
            ("Time-value pairs (t v ...)", "0 0  100n 1  200n 1  300n 0"),
        ],
        "spice": lambda p, dc, ac, aph: (
            f"DC {dc}"
            + (f" AC {ac}" if float(ac or 0) != 0 else "")
            + (f" {aph}" if float(ac or 0) != 0 and float(aph or 0) != 0 else "")
            + f" PWL({p[0]})"
        ),
    },
    "SFFM": {
        "label": "SFFM",
        "params": [
            ("DC offset Voff (V)",     "0"),
            ("Amplitude Vpk (V)",      "1"),
            ("Carrier freq Fc (Hz)",   "1k"),
            ("Modulation index Mdi",   "5"),
            ("Signal freq Fs (Hz)",    "200"),
        ],
        "spice": lambda p, dc, ac, aph: (
            f"DC {dc}"
            + (f" AC {ac}" if float(ac or 0) != 0 else "")
            + (f" {aph}" if float(ac or 0) != 0 and float(aph or 0) != 0 else "")
            + f" SFFM({p[0]} {p[1]} {p[2]} {p[3]} {p[4]})"
        ),
    },
}

# Keep WAVEFORMS as an alias so any existing code that references it still works
WAVEFORMS = VSRC_TYPES

# ── Simulation analysis definitions ───────────────────────────────────────────
ANALYSES = {
    "OP": {
        "label": "DC Operating Point  (.op)",
        "params": [],
        "spice": lambda p: ".op",
        "desc":  "Finds the DC bias point. No parameters needed.",
    },
    "DC": {
        "label": "DC Sweep  (.dc)",
        "params": [
            ("Source name",            "V1"),
            ("Start value (V)",        "0"),
            ("Stop value (V)",         "5"),
            ("Step size (V)",          "0.01"),
        ],
        "spice": lambda p: f".dc {p[0]} {p[1]} {p[2]} {p[3]}",
        "desc":  "Sweeps a voltage/current source over a range.",
    },
    "TRAN": {
        "label": "Transient  (.tran)",
        "params": [
            ("Time step (s)",          "1n"),
            ("Stop time (s)",          "1u"),
            ("Start time (s)",         "0"),
        ],
        "spice": lambda p: f".tran {p[0]} {p[1]} {p[2]}",
        "desc":  "Time-domain simulation. Set step << stop/100.",
    },
    "AC": {
        "label": "AC Small-Signal  (.ac)",
        "params": [
            ("Scale  (dec/lin/oct)",   "dec"),
            ("Points per decade",      "100"),
            ("Start freq (Hz)",        "1"),
            ("Stop freq (Hz)",         "10G"),
        ],
        "spice": lambda p: f".ac {p[0]} {p[1]} {p[2]} {p[3]}",
        "desc":  "Frequency-domain analysis (Bode plots).",
    },
    "NOISE": {
        "label": "Noise  (.noise)",
        "params": [
            ("Output node",            "out"),
            ("Input source",           "V1"),
            ("Scale  (dec/lin/oct)",   "dec"),
            ("Points per decade",      "100"),
            ("Start freq (Hz)",        "1"),
            ("Stop freq (Hz)",         "10G"),
        ],
        "spice": lambda p: f".noise V({p[0]}) {p[1]} {p[2]} {p[3]} {p[4]} {p[5]}",
        "desc":  "Noise spectral density analysis.",
    },
}

class SimConfig:
    """Stores the active simulation analysis and its parameters."""
    def __init__(self):
        self.analysis = "TRAN"        # active analysis key
        self.params   = {             # param values per analysis
            k: [p[1] for p in v["params"]]
            for k, v in ANALYSES.items()
        }

    def spice_line(self) -> str:
        a = ANALYSES[self.analysis]
        return a["spice"](self.params[self.analysis])

    def to_dict(self):
        return {"analysis": self.analysis, "params": self.params}

    @classmethod
    def from_dict(cls, d):
        cfg = cls()
        cfg.analysis = d.get("analysis", "TRAN")
        for k, v in d.get("params", {}).items():
            if k in cfg.params:
                cfg.params[k] = v
        return cfg

def _parse_legacy_vsrc(raw: str) -> tuple:
    """
    Parse an old free-text V/FUNC value string into
    (vsrc_type, vsrc_params_dict, vsrc_dc, vsrc_ac, vsrc_ac_phase).
    """
    import re
    s = raw.strip()

    for key in ("SIN", "PULSE", "EXP", "PWL", "SFFM"):
        m = re.search(key + r"\(([^)]*)\)", s, re.I)
        if m:
            inner  = m.group(1).strip()
            fields = inner.split() if key != "PWL" else [inner]
            n_params = len(VSRC_TYPES[key]["params"])
            defaults = [p[1] for p in VSRC_TYPES[key]["params"]]
            while len(fields) < n_params:
                fields.append(defaults[len(fields)])
            dc_m = re.match(r"DC\s+([\w.+-]+)", s, re.I)
            dc   = dc_m.group(1) if dc_m else "0"
            ac_m = re.search(r"\bAC\s+([\w.+-]+)(?:\s+([\w.+-]+))?", s, re.I)
            ac   = ac_m.group(1) if ac_m else "0"
            aph  = ac_m.group(2) if (ac_m and ac_m.group(2)) else "0"
            return key, {key: fields[:n_params]}, dc, ac, aph

    ac_m = re.search(r"\bAC\s+([\w.+-]+)(?:\s+([\w.+-]+))?", s, re.I)
    if ac_m:
        dc_m = re.match(r"DC\s+([\w.+-]+)", s, re.I)
        dc   = dc_m.group(1) if dc_m else "0"
        mag  = ac_m.group(1)
        ph   = ac_m.group(2) or "0"
        return "AC", {"AC": [dc, mag, ph]}, "0", "0", "0"

    dc_m = re.search(r"DC\s+([\w.+-]+)", s, re.I)
    val  = dc_m.group(1) if dc_m else re.sub(r"[VvΩ]", "", s).strip() or "1"
    return "DC", {"DC": [val, "0", "0"]}, "0", "0", "0"


# ── Data model ─────────────────────────────────────────────────────────────────
class Component:
    _uid = 0
    _cnt: dict = {}

    def __init__(self, typ, gx, gy, label=None, value=None, rot=0, flip=False):
        Component._uid += 1
        self.uid   = Component._uid
        if label is None:
            cnt_key = COUNTER_GROUP.get(typ, typ)
            Component._cnt[cnt_key] = Component._cnt.get(cnt_key, 0) + 1
            label = f"{PREFIX[typ]}{Component._cnt[cnt_key]}"
        self.label = label
        self.type  = typ
        self.gx    = gx
        self.gy    = gy
        self.rot   = rot
        self.flip  = flip
        self.value = value if value is not None else DEFAULTS.get(typ, "")
        # Transistor-specific properties (set via Properties dialog, not free text)
        self.model_name : str = ""    # e.g. "nmos_rf"  — populated from Model Manager
        self.mos_w      : str = ""    # MOSFET width  e.g. "2u"
        self.mos_l      : str = ""    # MOSFET length e.g. "180n"
        self.bulk_net   : str = "0"   # bulk/body connection
        # V-source structured waveform (set via V Properties dialog, not free text)
        self.vsrc_type    : str  = "DC" # active tab: DC|AC|SIN|PULSE|EXP|PWL|SFFM
        self.vsrc_params  : dict = {}   # {type_key: [param_str, ...]}
        self.vsrc_dc      : str  = "0"  # DC bias alongside transient waveforms
        self.vsrc_ac      : str  = "0"  # AC magnitude alongside transient waveforms
        self.vsrc_ac_phase: str  = "0"  # AC phase alongside transient waveforms

    def to_dict(self) -> dict:
        d = {
            "type":  self.type,  "label": self.label, "value": self.value,
            "gx":    self.gx,    "gy":    self.gy,
            "rot":   self.rot,   "flip":  self.flip,
        }
        if self.model_name: d["model_name"] = self.model_name
        if self.mos_w:      d["mos_w"]      = self.mos_w
        if self.mos_l:      d["mos_l"]      = self.mos_l
        if self.bulk_net and self.bulk_net != "0":
            d["bulk_net"] = self.bulk_net
        if self.type == "V":
            d["vsrc_type"]     = self.vsrc_type
            d["vsrc_params"]   = self.vsrc_params
            d["vsrc_dc"]       = self.vsrc_dc
            d["vsrc_ac"]       = self.vsrc_ac
            d["vsrc_ac_phase"] = self.vsrc_ac_phase
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Component":
        typ = d["type"]
        # ── FUNC → V migration ──────────────────────────────────────────────
        # FUNC was a separate component type for waveform sources.
        # It is now merged into the V source with structured vsrc_params.
        if typ == "FUNC":
            typ = "V"
            d   = dict(d)   # don't mutate the caller's dict
            d["type"] = "V"
            # Relabel  FUNCn → Vn  keeping the number
            old_lbl = d.get("label", "V1")
            import re as _re
            num = _re.search(r"\d+$", old_lbl)
            d["label"] = f"V{num.group() if num else '1'}"
            # Parse the old raw SPICE value string back into vsrc_params
            raw = (d.get("value") or "").strip()
            d["vsrc_type"], d["vsrc_params"], d["vsrc_dc"], \
                d["vsrc_ac"], d["vsrc_ac_phase"] = \
                _parse_legacy_vsrc(raw)
        # ────────────────────────────────────────────────────────────────────
        c = cls(
            typ, d["gx"], d["gy"],
            label=d.get("label"), value=d.get("value"),
            rot=d.get("rot", 0), flip=d.get("flip", False),
        )
        c.model_name   = d.get("model_name",   "")
        c.mos_w        = d.get("mos_w",        "")
        c.mos_l        = d.get("mos_l",        "")
        c.bulk_net     = d.get("bulk_net",     "0")
        c.vsrc_type    = d.get("vsrc_type",    "DC")
        c.vsrc_params  = d.get("vsrc_params",  {})
        c.vsrc_dc      = d.get("vsrc_dc",      "0")
        c.vsrc_ac      = d.get("vsrc_ac",      "0")
        c.vsrc_ac_phase= d.get("vsrc_ac_phase","0")
        return c


class Wire:
    _uid = 0
    def __init__(self, x1, y1, x2, y2):
        Wire._uid += 1
        self.uid = Wire._uid
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2

    def to_dict(self):
        return {"x1":self.x1,"y1":self.y1,"x2":self.x2,"y2":self.y2}

    @classmethod
    def from_dict(cls, d):
        return cls(d["x1"], d["y1"], d["x2"], d["y2"])


class WireLabel:
    """A named net label attached to a specific grid point on a wire."""
    def __init__(self, gx, gy, text):
        self.gx   = gx
        self.gy   = gy
        self.text = text

    def to_dict(self):
        return {"gx": self.gx, "gy": self.gy, "text": self.text}

    @classmethod
    def from_dict(cls, d):
        return cls(d["gx"], d["gy"], d["text"])


# ── Flip-aware DrawContext ─────────────────────────────────────────────────────
class FlipContext(DrawContext):
    """
    Subclass of DrawContext that applies a horizontal mirror AFTER rotation.
    The flip is purely visual — pin roles (Gate/Drain/Source) are unchanged,
    so the netlist extractor can still rely on the standard pin offsets.
    The extractor must account for flip when computing world pin positions.
    """
    def __init__(self, cv, ox, oy, S, rot, sel, flip: bool):
        super().__init__(cv, ox, oy, S, rot, sel)
        self._flip = flip
        if flip:
            # Recompute rotation matrix with x-axis mirrored:
            # mirror first (x → -x), then rotate.
            # Result: T(x,y) = R(-x, y)  where R is standard rotation.
            import math as _m
            rad = _m.radians(rot)
            # Store mirrored cos/sin so base class T() works correctly
            self._cr =  _m.cos(rad)   # same
            self._sr =  _m.sin(rad)   # same

    def T(self, x, y):
        """Apply horizontal mirror then rotation."""
        if self._flip:
            x = -x    # mirror across vertical axis before rotating
        return (self.ox + x * self._cr - y * self._sr,
                self.oy + x * self._sr + y * self._cr)


# ── Editor ─────────────────────────────────────────────────────────────────────
class Editor:
    def __init__(self, root: tk.Tk):
        self.root   = root
        self.comps  : list[Component] = []
        self.wires  : list[Wire]      = []
        self.cursor = [6, 5]
        self.mode   = "NORMAL"
        self.ws     = None

        self.GS = GS_DEFAULT
        self._update_canvas_size()

        self.wlbls      : list = []
        self.sim_config  = SimConfig()
        self.model_config = ModelConfig()       # project-level model settings
        self._model_names_cache: dict = {}      # parsed model names from file
        self._netlist_visible = False
        self._last_result     = None
        self._last_dir        = os.path.expanduser("~")
        self._current_file    : str | None = None   # path of last saved/loaded .json
        self._ngspice_exe     : str | None = None   # located once at startup
        self._sim_log_visible : bool = False        # simulation log panel state

        root.title("Vischem  v0.1")
        root.configure(bg=PANEL_BG)
        root.resizable(True, True)
        self._build_ui()
        self._bind()
        self._render()
        # Locate ngspice once at startup (non-blocking — just a PATH search)
        self.root.after(200, self._locate_ngspice)

    def _update_canvas_size(self):
        self.CW = COLS * self.GS
        self.CH = ROWS * self.GS

    def _zoom_pct(self):
        return round(self.GS / GS_DEFAULT * 100)

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        top = tk.Frame(self.root, bg=PANEL_BG, pady=4)
        top.pack(fill=tk.X)

        self.lbl_mode = tk.Label(top, text="NORMAL", width=8,
            font=("Courier", 9, "bold"),
            bg=MODE_COLS["NORMAL"][0], fg=MODE_COLS["NORMAL"][1],
            relief="flat", padx=6, pady=2)
        self.lbl_mode.pack(side=tk.LEFT, padx=(10, 4))

        self.lbl_coord = tk.Label(top, text="(6,5)",
            bg=PANEL_BG, fg="#2d4055", font=("Courier", 9))
        self.lbl_coord.pack(side=tk.LEFT)

        self.lbl_info = tk.Label(top, text="",
            bg=PANEL_BG, fg="#c9d1d9", font=("Courier", 9, "bold"))
        self.lbl_info.pack(side=tk.LEFT, padx=8)

        zf = tk.Frame(top, bg=PANEL_BG); zf.pack(side=tk.LEFT, padx=6)
        tk.Button(zf, text="−", command=lambda: self._zoom(-8),
            bg=BORDER, fg="#94a3b8", activebackground="#1e2c3e",
            font=("Courier", 10, "bold"), relief="flat",
            width=2, cursor="hand2").pack(side=tk.LEFT)
        self.lbl_zoom = tk.Label(zf, text="100%", width=5,
            bg=PANEL_BG, fg="#4b5563", font=("Courier", 8))
        self.lbl_zoom.pack(side=tk.LEFT, padx=2)
        tk.Button(zf, text="+", command=lambda: self._zoom(+8),
            bg=BORDER, fg="#94a3b8", activebackground="#1e2c3e",
            font=("Courier", 10, "bold"), relief="flat",
            width=2, cursor="hand2").pack(side=tk.LEFT)

        tk.Button(top, text="⌀ Clear", command=self._clear,
            bg=PANEL_BG, fg="#7a2020", activebackground="#1a0a0a",
            activeforeground="#f87171", relief="flat",
            font=("Courier", 8, "bold"), cursor="hand2", padx=8
        ).pack(side=tk.RIGHT, padx=4)

        self.btn_netlist = tk.Button(top, text="{ } Netlist",
            command=self._toggle_netlist_panel,
            bg="#0d1a0d", fg="#4ade80", activebackground="#0a1f0a",
            activeforeground="#86efac", relief="flat",
            font=("Courier", 8, "bold"), cursor="hand2", padx=8)
        self.btn_netlist.pack(side=tk.RIGHT, padx=4)

        self.btn_sim = tk.Button(top, text="⚡ Simulation",
            command=self._open_sim_dialog,
            bg="#100a28", fg="#a78bfa", activebackground="#1a1040",
            activeforeground="#c4b5fd", relief="flat",
            font=("Courier", 8, "bold"), cursor="hand2", padx=8)
        self.btn_sim.pack(side=tk.RIGHT, padx=4)

        self.btn_run = tk.Button(top, text="▶ Run",
            command=self._run_simulation,
            bg="#071a07", fg="#4ade80", activebackground="#0a2a0a",
            activeforeground="#86efac", relief="flat",
            font=("Courier", 9, "bold"), cursor="hand2", padx=10)
        self.btn_run.pack(side=tk.RIGHT, padx=4)

        self.btn_doc = tk.Button(top, text="🖨 Doc Image",
            command=self._dialog_save_doc_image,
            bg="#13151c", fg="#cbd5e1", activebackground="#1f2430",
            activeforeground="#f1f5f9", relief="flat",
            font=("Courier", 8, "bold"), cursor="hand2", padx=8)
        self.btn_doc.pack(side=tk.RIGHT, padx=4)

        self.btn_models = tk.Button(top, text="⚛ Models",
            command=self._open_model_manager,
            bg="#1a0e0e", fg="#f87171", activebackground="#2a1010",
            activeforeground="#fca5a5", relief="flat",
            font=("Courier", 8, "bold"), cursor="hand2", padx=8)
        self.btn_models.pack(side=tk.RIGHT, padx=4)

        # workspace
        self.workspace = tk.Frame(self.root, bg=PANEL_BG)
        self.workspace.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        cf = tk.Frame(self.workspace, bg=PANEL_BG)
        cf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.hbar = tk.Scrollbar(cf, orient=tk.HORIZONTAL, bg=PANEL_BG, troughcolor=BORDER)
        self.hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.vbar = tk.Scrollbar(cf, orient=tk.VERTICAL, bg=PANEL_BG, troughcolor=BORDER)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.cv = tk.Canvas(cf,
            width=min(self.CW, 1300), height=min(self.CH, 820),
            scrollregion=(0, 0, self.CW, self.CH),
            bg=BG, highlightthickness=1, highlightbackground=BORDER,
            cursor="crosshair",
            xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.hbar.config(command=self.cv.xview)
        self.vbar.config(command=self.cv.yview)
        self.cv.focus_set()

        # netlist panel (hidden by default)
        self.netlist_frame = tk.Frame(self.workspace, bg="#080c10", bd=0, width=420)

        nlh = tk.Frame(self.netlist_frame, bg="#0d1a0d", pady=4)
        nlh.pack(fill=tk.X)
        tk.Label(nlh, text="  SPICE Netlist", bg="#0d1a0d", fg="#4ade80",
            font=("Courier", 9, "bold")).pack(side=tk.LEFT)
        tk.Button(nlh, text="↻ Rebuild", command=self._rebuild_netlist,
            bg="#0d1a0d", fg="#4ade80", activebackground="#0a2a0a",
            relief="flat", font=("Courier", 8, "bold"),
            cursor="hand2", padx=6).pack(side=tk.RIGHT, padx=4)
        tk.Button(nlh, text="⬇ Save .cir",
            command=self._dialog_save_netlist,
            bg="#0d1a0d", fg="#818cf8", activebackground="#12103a",
            relief="flat", font=("Courier", 8, "bold"),
            cursor="hand2", padx=6).pack(side=tk.RIGHT, padx=2)

        self.nl_warn = tk.Label(self.netlist_frame, text="",
            bg="#1a1000", fg="#f59e0b",
            font=("Courier", 7), anchor="w", padx=6, wraplength=400)
        self.nl_warn.pack(fill=tk.X)

        self.nl_nets = tk.Label(self.netlist_frame, text="",
            bg="#080c10", fg="#334155",
            font=("Courier", 7), anchor="w", padx=6)
        self.nl_nets.pack(fill=tk.X)

        nl_tf = tk.Frame(self.netlist_frame, bg="#080c10")
        nl_tf.pack(fill=tk.BOTH, expand=True)
        nl_vsb = tk.Scrollbar(nl_tf, orient=tk.VERTICAL, bg=PANEL_BG)
        nl_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        nl_hsb = tk.Scrollbar(nl_tf, orient=tk.HORIZONTAL, bg=PANEL_BG)
        nl_hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.nl_text = tk.Text(nl_tf,
            bg="#080c10", fg="#c9d1d9", font=("Courier", 9),
            insertbackground=CURSOR_C, selectbackground="#1e3a5f",
            relief="flat", bd=0, wrap=tk.NONE, state=tk.DISABLED,
            yscrollcommand=nl_vsb.set, xscrollcommand=nl_hsb.set)
        self.nl_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        nl_vsb.config(command=self.nl_text.yview)
        nl_hsb.config(command=self.nl_text.xview)
        self.nl_text.tag_config("comment",  foreground="#2d4f35")
        self.nl_text.tag_config("element",  foreground="#c9d1d9")
        self.nl_text.tag_config("net",      foreground="#38bdf8")
        self.nl_text.tag_config("dot",      foreground="#a78bfa")
        self.nl_text.tag_config("warning",  foreground="#f59e0b")
        self.nl_text.tag_config("value",    foreground="#818cf8")
        self.nl_text.tag_config("end",      foreground="#4ade80")

        # ── Simulation log panel (hidden by default) ───────────────────────────
        self.sim_log_frame = tk.Frame(self.workspace, bg="#080c10", bd=0, width=440)

        slh = tk.Frame(self.sim_log_frame, bg="#071a07", pady=4)
        slh.pack(fill=tk.X)
        self.lbl_sim_header = tk.Label(slh, text="  ▶ Simulation Log",
            bg="#071a07", fg="#4ade80",
            font=("Courier", 9, "bold"))
        self.lbl_sim_header.pack(side=tk.LEFT)
        tk.Button(slh, text="✕ Close",
            command=self._hide_sim_log,
            bg="#071a07", fg="#4b5563", activebackground="#0a2a0a",
            relief="flat", font=("Courier", 8), cursor="hand2", padx=6
        ).pack(side=tk.RIGHT, padx=4)
        self.btn_show_raw = tk.Button(slh, text="📂 Show .raw",
            command=self._reveal_raw_file,
            bg="#071a07", fg="#4b5563", activebackground="#0a2a0a",
            relief="flat", font=("Courier", 8, "bold"), cursor="hand2", padx=6)
        self.btn_show_raw.pack(side=tk.RIGHT, padx=2)

        # log text area
        sl_tf = tk.Frame(self.sim_log_frame, bg="#080c10")
        sl_tf.pack(fill=tk.BOTH, expand=True)
        sl_vsb = tk.Scrollbar(sl_tf, orient=tk.VERTICAL, bg=PANEL_BG)
        sl_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.sim_log_text = tk.Text(sl_tf,
            bg="#050810", fg="#c9d1d9", font=("Courier", 8),
            insertbackground=CURSOR_C, selectbackground="#1e3a5f",
            relief="flat", bd=0, wrap=tk.WORD, state=tk.DISABLED,
            yscrollcommand=sl_vsb.set)
        self.sim_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sl_vsb.config(command=self.sim_log_text.yview)
        self.sim_log_text.tag_config("ok",      foreground="#4ade80")
        self.sim_log_text.tag_config("err",     foreground="#f87171")
        self.sim_log_text.tag_config("warn",    foreground="#f59e0b")
        self.sim_log_text.tag_config("dim",     foreground="#334155")
        self.sim_log_text.tag_config("header",  foreground="#4ade80",
                                                font=("Courier", 9, "bold"))
        self._last_raw_path: str | None = None  # set after each successful run

        self.lbl_status = tk.Label(self.root, text="", anchor="w",
            bg=PANEL_BG, fg="#1e2c3a", font=("Courier", 8), padx=10, pady=3)
        self.lbl_status.pack(fill=tk.X, side=tk.BOTTOM)

    # ── Modal dialog (the stable input method from v0.5) ───────────────────────
    def _ask(self, title: str, prompt: str, initial: str = "",
             color: str = "#818cf8") -> "str | None":
        result = [None]
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.configure(bg=PANEL_BG)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text=prompt, bg=PANEL_BG, fg=color,
                 font=("Helvetica", 10, "bold"),
                 padx=14, pady=10).pack(fill=tk.X)

        evar = tk.StringVar(value=initial)
        ent  = tk.Entry(dlg, textvariable=evar,
                        bg="#0c1020", fg="#e2e8f0",
                        insertbackground=CURSOR_C,
                        font=("Courier", 11), relief="flat", bd=4,
                        selectbackground="#1e3a5f", width=36)
        ent.pack(padx=14, pady=(0, 10))
        ent.select_range(0, tk.END)
        ent.focus_set()

        bf = tk.Frame(dlg, bg=PANEL_BG)
        bf.pack(fill=tk.X, padx=14, pady=(0, 10))

        def _ok(_=None):
            result[0] = evar.get(); dlg.destroy()
        def _cancel(_=None):
            result[0] = None; dlg.destroy()

        tk.Button(bf, text="OK", command=_ok,
                  bg="#10082a", fg="#a78bfa",
                  activebackground="#1a1040", activeforeground="#c4b5fd",
                  font=("Helvetica", 9, "bold"),
                  relief="flat", padx=16, pady=4,
                  cursor="hand2").pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(bf, text="Cancel", command=_cancel,
                  bg=BORDER, fg="#4b5563",
                  activebackground="#1e2c3e", activeforeground="#94a3b8",
                  font=("Helvetica", 9), relief="flat",
                  padx=10, pady=4, cursor="hand2").pack(side=tk.LEFT)

        ent.bind("<Return>", _ok)
        ent.bind("<Escape>", _cancel)

        self.root.update_idletasks()
        rx = self.root.winfo_rootx() + self.root.winfo_width()  // 2
        ry = self.root.winfo_rooty() + self.root.winfo_height() // 2
        dlg.update_idletasks()
        dlg.geometry(f"+{rx - dlg.winfo_width()//2}+{ry - dlg.winfo_height()//2}")

        self.root.wait_window(dlg)
        self.cv.focus_set()
        return result[0]

    # ── File dialogs ───────────────────────────────────────────────────────────
    def _savepath(self, title, filetypes, default_ext) -> "str | None":
        path = filedialog.asksaveasfilename(
            title=title, initialdir=self._last_dir,
            defaultextension=default_ext, filetypes=filetypes,
            parent=self.root)
        if path:
            self._last_dir = os.path.dirname(path)
        self.cv.focus_set()
        return path or None

    def _loadpath(self, title, filetypes) -> "str | None":
        path = filedialog.askopenfilename(
            title=title, initialdir=self._last_dir,
            filetypes=filetypes, parent=self.root)
        if path:
            self._last_dir = os.path.dirname(path)
        self.cv.focus_set()
        return path or None

    def _dialog_save(self):
        """General save dialog — routes by extension chosen by user."""
        path = self._savepath("Save Schematic / Image", FD_SAVE_ALL, ".json")
        if not path: return
        ext = os.path.splitext(path)[1].lower()
        if ext == ".json":          self._save_json(path)
        elif ext in IMAGE_EXTS:     self._save_raster(path)
        elif ext == ".svg":         self._save_svg(path)
        elif ext == ".cir":         self._save_netlist_to(path)
        elif ext == ".csv":
            self._status("[!] CSV is legacy — use .json to save for editing", "#f59e0b")
        else:
            self._save_json(path)   # default

    def _dialog_load(self):
        path = self._loadpath("Open Schematic", FD_LOAD)
        if not path: return
        ext = os.path.splitext(path)[1].lower()
        if ext == ".json":      self._load_json(path)
        elif ext == ".csv":     self._load_csv(path)
        else:
            self._status(f"[!] Unknown format: {ext}", "#f87171")

    def _dialog_save_netlist(self):
        if not _HAS_NETLIST:
            self._status("[!] netlist.py not found", "#f87171"); return
        path = self._savepath("Save NGspice Netlist", FD_NETLIST, ".cir")
        if path:
            self._save_netlist_to(path)

    def _dialog_save_image(self):
        path = self._savepath("Save Raster Image", FD_RASTER, ".png")
        if path: self._save_raster(path)

    def _dialog_save_svg(self):
        path = self._savepath("Save SVG Image", FD_SVG, ".svg")
        if path: self._save_svg(path)

    # ── Bindings ───────────────────────────────────────────────────────────────
    def _bind(self):
        cv = self.cv
        cv.bind("<KeyPress>",           self._on_key)
        cv.bind("<Button-1>",           self._on_click)
        cv.bind("<MouseWheel>",         self._on_wheel_y)
        cv.bind("<Button-4>",           lambda e: cv.yview_scroll(-1, "units"))
        cv.bind("<Button-5>",           lambda e: cv.yview_scroll(+1, "units"))
        cv.bind("<Shift-MouseWheel>",   self._on_wheel_x)
        cv.bind("<Control-MouseWheel>", self._on_ctrl_wheel)

    def _on_click(self, ev):
        self.cv.focus_set()
        if self.mode == "MOUSE":
            cx = int(self.cv.canvasx(ev.x) / self.GS)
            cy = int(self.cv.canvasy(ev.y) / self.GS)
            self.cursor[0] = max(0, min(COLS-1, cx))
            self.cursor[1] = max(0, min(ROWS-1, cy))
            self._render()

    def _on_wheel_y(self, ev):
        self.cv.yview_scroll(int(-1 * ev.delta / 120), "units")
    def _on_wheel_x(self, ev):
        self.cv.xview_scroll(int(-1 * ev.delta / 120), "units")
    def _on_ctrl_wheel(self, ev):
        self._zoom(+8 if ev.delta > 0 else -8)

    def _on_key(self, ev):
        k  = ev.keysym.lower()
        ku = (ev.char or "").upper()

        dirs = {"up":(0,-1),"down":(0,1),"left":(-1,0),"right":(1,0)}
        if k in dirs and self.mode in ("NORMAL","WIRE","MOUSE"):
            dx, dy = dirs[k]
            self.cursor[0] = max(0, min(COLS-1, self.cursor[0]+dx))
            self.cursor[1] = max(0, min(ROWS-1, self.cursor[1]+dy))
            self._scroll_to_cursor()
            self._render(); return

        if ev.char in ("+","="): self._zoom(+8); return
        if ev.char in ("-","_"): self._zoom(-8); return

        if self.mode in ("NORMAL", "MOUSE"):
            if ku in ("R","C","L","V","I","G"): self._place(ku); return
            if ku == "W":  self._start_wire(); return
            if ku == "M":  self._toggle_mouse(); return
            if ev.char == " ": self._rotate(); return
            if ku == "F":  self._flip(); return
            if ku == "T":  self._label_wire(); return
            if ku == "E":  self._start_edit(); return
            if ev.char == ":": self._open_cmd(); return
            if k in ("delete","backspace"): self._delete(); return
            if k == "escape" and self.mode == "MOUSE": self._toggle_mouse(); return

        elif self.mode == "WIRE":
            if k in ("w","return"): self._commit_wire(); return
            if k == "escape":
                self.mode="NORMAL"; self.ws=None; self._render()

    # ── Actions ────────────────────────────────────────────────────────────────
    def _at_cursor(self):
        gx, gy = self.cursor
        return next((c for c in self.comps if c.gx==gx and c.gy==gy), None)

    def _status(self, msg, col="#1e2c3a"):
        self.lbl_status.config(text=msg, fg=col)

    def _place(self, typ):
        if self._at_cursor():
            self._status("[!] Cell occupied — move cursor first", "#f87171"); return
        self.comps.append(Component(typ, *self.cursor))
        self._render()

    def _place_device(self, typ):
        if self._at_cursor():
            self._status("[!] Cell occupied — move cursor first", "#f87171"); return
        self.comps.append(Component(typ, *self.cursor))
        self._render()

    def _rotate(self):
        c = self._at_cursor()
        if c: c.rot = (c.rot + 90) % 360
        self._render()

    def _flip(self):
        """Toggle horizontal mirror on the component at cursor."""
        c = self._at_cursor()
        if not c:
            self._status("[!] No component at cursor", "#f87171"); return
        c.flip = not c.flip
        self._status(
            f"⟺  {c.label} flipped {'ON' if c.flip else 'OFF'}", "#f472b6")
        self._render()

    def _label_wire(self):
        """T key: open dialog to name/rename the net at the cursor position."""
        gx, gy = self.cursor
        # Pre-fill with any existing label at this point
        existing = next((l for l in self.wlbls if l.gx==gx and l.gy==gy), None)
        current  = existing.text if existing else ""
        new_text = self._ask(
            f"Wire label at ({gx},{gy})",
            "Net name  (empty = remove label)",
            initial=current, color=WIRE_LBL_COLOR)
        if new_text is None:   # cancelled
            self._render(); return
        # Remove any existing label at this point
        self.wlbls = [l for l in self.wlbls if not (l.gx==gx and l.gy==gy)]
        if new_text.strip():
            self.wlbls.append(WireLabel(gx, gy, new_text.strip()))
            self._status(f"✓ Net labelled '{new_text.strip()}'", "#38bdf8")
        else:
            self._status("✓ Wire label removed", "#38bdf8")
        self._render()

    # ── V-source / waveform properties are handled in _open_vsrc_props ───────────
    # (FUNC component type removed — all waveforms now live on the V source)

    # ── Simulation analysis dialog ──────────────────────────────────────────────
    def _open_sim_dialog(self):
        """Open the user-friendly simulation configurator."""
        result = [False]   # True = confirmed

        dlg = tk.Toplevel(self.root)
        dlg.title("Simulation Setup")
        dlg.configure(bg=PANEL_BG)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        # ── Header ─────────────────────────────────────────────────────────
        tk.Label(dlg, text="⚡  Simulation Setup",
            bg=PANEL_BG, fg="#a78bfa",
            font=("Helvetica", 12, "bold"), pady=10).pack()

        # ── Analysis type selector ──────────────────────────────────────────
        sel_frame = tk.Frame(dlg, bg="#0d1020", bd=1, relief="solid")
        sel_frame.pack(fill=tk.X, padx=16, pady=(0,8))

        ana_var = tk.StringVar(value=self.sim_config.analysis)

        for key, info in ANALYSES.items():
            rb = tk.Radiobutton(sel_frame,
                text=info["label"],
                variable=ana_var, value=key,
                bg="#0d1020", fg="#94a3b8",
                selectcolor="#10082a",
                activebackground="#0d1020",
                activeforeground="#c4b5fd",
                font=("Helvetica", 9),
                anchor="w", padx=12, pady=4,
                cursor="hand2")
            rb.pack(fill=tk.X)

        # ── Description label ───────────────────────────────────────────────
        desc_lbl = tk.Label(dlg, text="",
            bg=PANEL_BG, fg="#4b5563",
            font=("Helvetica", 8, "italic"),
            wraplength=380, anchor="w", padx=18)
        desc_lbl.pack(fill=tk.X)

        # ── Parameter area ──────────────────────────────────────────────────
        param_frame = tk.Frame(dlg, bg=PANEL_BG)
        param_frame.pack(fill=tk.X, padx=16, pady=4)

        # Store entry widgets per analysis
        ana_entries: dict = {}
        for key, info in ANALYSES.items():
            frame = tk.Frame(param_frame, bg=PANEL_BG)
            evars = []
            for i, (plabel, pdefault) in enumerate(info["params"]):
                row = tk.Frame(frame, bg=PANEL_BG)
                row.pack(fill=tk.X, pady=2)
                tk.Label(row, text=plabel, bg=PANEL_BG, fg="#94a3b8",
                    font=("Helvetica", 9), width=26, anchor="w"
                ).pack(side=tk.LEFT)
                ev = tk.StringVar(value=self.sim_config.params[key][i])
                ent = tk.Entry(row, textvariable=ev,
                    bg="#0c1020", fg="#e2e8f0",
                    insertbackground=CURSOR_C,
                    font=("Courier", 10), relief="flat", bd=3,
                    selectbackground="#1e3a5f", width=16)
                ent.pack(side=tk.LEFT, padx=(6,0))
                evars.append(ev)
            if not info["params"]:
                tk.Label(frame, text=info["desc"],
                    bg=PANEL_BG, fg="#4b5563",
                    font=("Helvetica", 9, "italic")).pack(pady=8)
            ana_entries[key] = (frame, evars)

        # Preview line at bottom of params
        preview_lbl = tk.Label(dlg, text="",
            bg="#080c14", fg="#22c55e",
            font=("Courier", 9), anchor="w", padx=16, pady=4)
        preview_lbl.pack(fill=tk.X)

        # ── Switch panel on radio change ────────────────────────────────────
        current_frame = [None]

        def _switch(*_):
            key = ana_var.get()
            if current_frame[0]:
                current_frame[0].pack_forget()
            frame, _ = ana_entries[key]
            frame.pack(fill=tk.X)
            current_frame[0] = frame
            desc_lbl.config(text=ANALYSES[key]["desc"])
            _update_preview()

        def _update_preview(*_):
            key = ana_var.get()
            _, evars = ana_entries[key]
            vals = [ev.get().strip() for ev in evars]
            try:
                line = ANALYSES[key]["spice"](vals)
                preview_lbl.config(text=f"  {line}", fg="#22c55e")
            except Exception:
                preview_lbl.config(text="  (fill all parameters)", fg="#4b5563")

        ana_var.trace_add("write", _switch)
        # Bind all entries to update preview
        for key, (frame, evars) in ana_entries.items():
            for ev in evars:
                ev.trace_add("write", _update_preview)

        _switch()   # initialize display

        # ── Buttons ─────────────────────────────────────────────────────────
        bf = tk.Frame(dlg, bg=PANEL_BG)
        bf.pack(pady=(8,14))

        def _ok(_=None):
            key = ana_var.get()
            _, evars = ana_entries[key]
            self.sim_config.analysis = key
            self.sim_config.params[key] = [ev.get().strip() for ev in evars]
            result[0] = True
            dlg.destroy()

        def _cancel(_=None):
            dlg.destroy()

        tk.Button(bf, text="Apply & Close", command=_ok,
            bg="#10082a", fg="#a78bfa",
            activebackground="#1a1040", activeforeground="#c4b5fd",
            font=("Helvetica", 10, "bold"),
            relief="flat", padx=20, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT, padx=6)
        tk.Button(bf, text="Cancel", command=_cancel,
            bg=BORDER, fg="#4b5563",
            font=("Helvetica", 9), relief="flat",
            padx=10, pady=6, cursor="hand2"
        ).pack(side=tk.LEFT)

        dlg.bind("<Return>", _ok)
        dlg.bind("<Escape>", _cancel)
        self._center_dialog(dlg)
        self.root.wait_window(dlg)
        self.cv.focus_set()

        if result[0]:
            self._status(
                f"✓ Simulation: {ANALYSES[self.sim_config.analysis]['label']} — "
                f"{self.sim_config.spice_line()}", "#a78bfa")
            # Rebuild netlist panel if open
            if self._netlist_visible:
                self._rebuild_netlist()

    # ── Dialog centering helper ─────────────────────────────────────────────────
    def _center_dialog(self, dlg):
        self.root.update_idletasks()
        dlg.update_idletasks()
        rx = self.root.winfo_rootx() + self.root.winfo_width()  // 2
        ry = self.root.winfo_rooty() + self.root.winfo_height() // 2
        dlg.geometry(f"+{rx - dlg.winfo_width()//2}+{ry - dlg.winfo_height()//2}")

    def _delete(self):
        gx, gy = self.cursor
        self.comps = [c for c in self.comps if not (c.gx==gx and c.gy==gy)]
        self.wires = [w for w in self.wires
                      if not((w.x1==gx and w.y1==gy) or (w.x2==gx and w.y2==gy))]
        self.wlbls = [l for l in self.wlbls if not (l.gx==gx and l.gy==gy)]
        self._render()

    def _start_wire(self):
        self.mode="WIRE"; self.ws=list(self.cursor); self._render()

    def _commit_wire(self):
        cx, cy = self.cursor
        if self.ws and (self.ws[0]!=cx or self.ws[1]!=cy):
            self.wires.append(Wire(self.ws[0],self.ws[1],cx,cy))
            self.ws=[cx,cy]
        else:
            self.mode="NORMAL"; self.ws=None
        self._render()

    def _toggle_mouse(self):
        self.mode = "NORMAL" if self.mode=="MOUSE" else "MOUSE"
        self._render()

    def _zoom(self, delta):
        self.GS = max(GS_MIN, min(GS_MAX, self.GS+delta))
        self._update_canvas_size()
        self.cv.config(scrollregion=(0,0,self.CW,self.CH))
        self._scroll_to_cursor(); self._render()

    def _zoom_to(self, pct):
        self.GS = max(GS_MIN, min(GS_MAX, round(GS_DEFAULT*pct/100)))
        self._update_canvas_size()
        self.cv.config(scrollregion=(0,0,self.CW,self.CH))
        self._render()

    def _scroll_to_cursor(self):
        cx, cy = self.cursor[0]*self.GS, self.cursor[1]*self.GS
        x0,x1 = self.cv.xview(); y0,y1 = self.cv.yview()
        left,right = x0*self.CW, x1*self.CW
        top,bottom = y0*self.CH, y1*self.CH
        mg = self.GS*1.5
        if cx < left  +mg: self.cv.xview_scroll(-1,"units")
        if cx > right -mg: self.cv.xview_scroll(+1,"units")
        if cy < top   +mg: self.cv.yview_scroll(-1,"units")
        if cy > bottom-mg: self.cv.yview_scroll(+1,"units")

    def _start_edit(self):
        """E key — open type-aware Properties dialog for the component at cursor."""
        c = self._at_cursor()
        if not c:
            self._status("[!] No component at cursor", "#f87171"); return
        if c.type in ("NMOS", "PMOS"):
            self._open_mos_props(c)
        elif c.type in ("NPN", "PNP"):
            self._open_bjt_props(c)
        elif c.type == "V":
            self._open_vsrc_props(c)
        else:
            self._open_passive_props(c)

    # ── Properties: V source (tabbed waveform dialog) ─────────────────────────
    def _open_vsrc_props(self, c):
        """
        Full V-source Properties dialog.
        A tab strip across the top selects the waveform type.
        The parameter area below updates to show the fields for that type.
        A live SPICE preview updates as any field changes.
        All state is persisted on the component (vsrc_type, vsrc_params, vsrc_dc).
        """
        result = [None]

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Properties — {c.label}  (Voltage Source)")
        dlg.configure(bg=PANEL_BG)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="V  Source  Properties",
            bg=PANEL_BG, fg="#818cf8",
            font=("Helvetica", 11, "bold"), pady=8).pack()

        # ── Label row ──────────────────────────────────────────────────────
        lr = tk.Frame(dlg, bg=PANEL_BG)
        lr.pack(fill=tk.X, padx=20, pady=(0,6))
        tk.Label(lr, text="Label", bg=PANEL_BG, fg="#94a3b8",
            font=("Helvetica", 9), width=10, anchor="w").pack(side=tk.LEFT)
        sv_label = tk.StringVar(value=c.label)
        tk.Entry(lr, textvariable=sv_label,
            bg="#0c1020", fg="#fbbf24",
            insertbackground=CURSOR_C,
            font=("Courier", 10), relief="flat", bd=3,
            selectbackground="#1e3a5f", width=14
        ).pack(side=tk.LEFT, padx=(4,0))

        # ── Tab strip ──────────────────────────────────────────────────────
        tab_frame = tk.Frame(dlg, bg=BORDER)
        tab_frame.pack(fill=tk.X, padx=20, pady=(2,0))

        TAB_KEYS = list(VSRC_TYPES.keys())   # DC AC SIN PULSE EXP PWL SFFM
        active_tab = [c.vsrc_type if c.vsrc_type in TAB_KEYS else "DC"]
        tab_btns   = {}

        def _select_tab(key):
            active_tab[0] = key
            for k, b in tab_btns.items():
                if k == key:
                    b.config(bg="#1e1040", fg="#c4b5fd",
                             relief="flat", font=("Courier", 8, "bold"))
                else:
                    b.config(bg=BORDER, fg="#4b5563",
                             relief="flat", font=("Courier", 8))
            _rebuild_params(key)
            _update_preview()

        for key in TAB_KEYS:
            b = tk.Button(tab_frame, text=key,
                command=lambda k=key: _select_tab(k),
                font=("Courier", 8), relief="flat",
                padx=8, pady=3, cursor="hand2")
            b.pack(side=tk.LEFT, padx=1, pady=2)
            tab_btns[key] = b

        # ── Parameter area (rebuilt on tab switch) ─────────────────────────
        param_frame = tk.Frame(dlg, bg=PANEL_BG)
        param_frame.pack(fill=tk.X, padx=20, pady=4)

        # Stores StringVars for the currently visible tab
        current_svs: list = []

        # DC/AC bias fields shared across transient waveforms
        sv_dc       = tk.StringVar(value=c.vsrc_dc       or "0")
        sv_ac       = tk.StringVar(value=c.vsrc_ac       or "0")
        sv_ac_phase = tk.StringVar(value=c.vsrc_ac_phase or "0")

        def _rebuild_params(key):
            # Clear existing widgets
            for w in param_frame.winfo_children():
                w.destroy()
            current_svs.clear()

            wf = VSRC_TYPES[key]

            # DC + AC bias header for transient waveforms
            if key not in ("DC", "AC"):
                # separator label
                tk.Label(param_frame,
                    text="─── Bias (applied to all analyses) ───",
                    bg=PANEL_BG, fg="#4b5563",
                    font=("Courier", 7)
                ).pack(anchor="w", pady=(0,2))

                bias_frame = tk.Frame(param_frame, bg=PANEL_BG)
                bias_frame.pack(fill=tk.X, pady=(0,4))

                def _bias_row(parent, text, sv, color):
                    r = tk.Frame(parent, bg=PANEL_BG); r.pack(fill=tk.X, pady=1)
                    tk.Label(r, text=text,
                        bg=PANEL_BG, fg=color,
                        font=("Helvetica", 9), width=28, anchor="w"
                    ).pack(side=tk.LEFT)
                    e = tk.Entry(r, textvariable=sv,
                        bg="#0c1020", fg=color,
                        insertbackground=CURSOR_C,
                        font=("Courier", 10), relief="flat", bd=3,
                        selectbackground="#1e3a5f", width=12)
                    e.pack(side=tk.LEFT, padx=(4,0))
                    sv.trace_add("write", lambda *_: _update_preview())
                    return sv

                _bias_row(bias_frame, "DC bias (V)      [.op / .dc]",  sv_dc,       "#f59e0b")
                _bias_row(bias_frame, "AC magnitude (V) [.ac]",         sv_ac,       "#38bdf8")
                _bias_row(bias_frame, "AC phase (deg)   [.ac]",         sv_ac_phase, "#38bdf8")

                tk.Frame(param_frame, bg=BORDER, height=1
                    ).pack(fill=tk.X, pady=(2,4))
                tk.Label(param_frame,
                    text="─── Waveform  (.tran) ───",
                    bg=PANEL_BG, fg="#4b5563",
                    font=("Courier", 7)
                ).pack(anchor="w", pady=(0,2))

            # Restore saved values for this tab if they exist
            saved = c.vsrc_params.get(key, [])
            defaults = [p[1] for p in wf["params"]]

            for i, (lbl_txt, default) in enumerate(wf["params"]):
                val = saved[i] if i < len(saved) else default

                # PWL gets a wider multi-line entry
                if key == "PWL":
                    row = tk.Frame(param_frame, bg=PANEL_BG)
                    row.pack(fill=tk.X, pady=3)
                    tk.Label(row, text=lbl_txt,
                        bg=PANEL_BG, fg="#94a3b8",
                        font=("Helvetica", 9), anchor="w"
                    ).pack(anchor="w")
                    sv = tk.StringVar(value=val)
                    ent = tk.Entry(row, textvariable=sv,
                        bg="#0c1020", fg="#e2e8f0",
                        insertbackground=CURSOR_C,
                        font=("Courier", 9), relief="flat", bd=3,
                        selectbackground="#1e3a5f", width=46)
                    ent.pack(fill=tk.X, pady=(2,0))
                else:
                    row = tk.Frame(param_frame, bg=PANEL_BG)
                    row.pack(fill=tk.X, pady=2)
                    tk.Label(row, text=lbl_txt,
                        bg=PANEL_BG, fg="#94a3b8",
                        font=("Helvetica", 9), width=28, anchor="w"
                    ).pack(side=tk.LEFT)
                    sv = tk.StringVar(value=val)
                    ent = tk.Entry(row, textvariable=sv,
                        bg="#0c1020", fg="#e2e8f0",
                        insertbackground=CURSOR_C,
                        font=("Courier", 10), relief="flat", bd=3,
                        selectbackground="#1e3a5f", width=14)
                    ent.pack(side=tk.LEFT, padx=(4,0))

                sv.trace_add("write", lambda *_: _update_preview())
                current_svs.append(sv)

        # ── Live SPICE preview ─────────────────────────────────────────────
        tk.Frame(dlg, bg=BORDER, height=1).pack(fill=tk.X, padx=20, pady=(6,2))
        tk.Label(dlg, text="SPICE preview",
            bg=PANEL_BG, fg="#4b5563",
            font=("Courier", 7)).pack(anchor="w", padx=22)

        sv_preview = tk.StringVar()
        tk.Label(dlg, textvariable=sv_preview,
            bg="#050810", fg="#4ade80",
            font=("Courier", 9), anchor="w", padx=8, pady=5,
            wraplength=440, justify="left"
        ).pack(fill=tk.X, padx=20, pady=(0,8))

        def _update_preview(*_):
            key = active_tab[0]
            wf  = VSRC_TYPES[key]
            p   = [sv.get().strip() for sv in current_svs]
            dc  = sv_dc.get().strip()       or "0"
            ac  = sv_ac.get().strip()       or "0"
            aph = sv_ac_phase.get().strip() or "0"
            lbl = sv_label.get().strip() or c.label
            try:
                body = wf["spice"](p, dc, ac, aph)
            except Exception:
                body = "..."
            sv_preview.set(f"{lbl:<10} n+       n-       {body}")

        sv_label.trace_add("write", lambda *_: _update_preview())

        # ── Buttons ────────────────────────────────────────────────────────
        def _ok(_=None):
            key = active_tab[0]
            p = [sv.get().strip() for sv in current_svs]
            params_snapshot = dict(c.vsrc_params)
            params_snapshot[key] = p
            result[0] = {
                "label":        sv_label.get().strip(),
                "vsrc_type":    key,
                "vsrc_params":  params_snapshot,
                "vsrc_dc":      sv_dc.get().strip()       or "0",
                "vsrc_ac":      sv_ac.get().strip()       or "0",
                "vsrc_ac_phase":sv_ac_phase.get().strip() or "0",
            }
            dlg.destroy()

        def _cancel(_=None):
            dlg.destroy()

        bf = tk.Frame(dlg, bg=PANEL_BG)
        bf.pack(fill=tk.X, padx=20, pady=(0,14))
        tk.Button(bf, text="OK", command=_ok,
            bg="#10082a", fg="#818cf8",
            activebackground="#1a1040", activeforeground="#c4b5fd",
            font=("Helvetica", 9, "bold"),
            relief="flat", padx=16, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT)
        tk.Button(bf, text="Cancel", command=_cancel,
            bg=BORDER, fg="#4b5563",
            font=("Helvetica", 9), relief="flat",
            padx=10, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT, padx=(8,0))

        dlg.bind("<Escape>", _cancel)

        # ── Initialise the active tab ───────────────────────────────────────
        _select_tab(active_tab[0])
        self._center_dialog(dlg)
        self.root.wait_window(dlg)
        self.cv.focus_set()

        if result[0]:
            r = result[0]
            if r["label"]:    c.label       = r["label"]
            c.vsrc_type    = r["vsrc_type"]
            c.vsrc_params  = r["vsrc_params"]
            c.vsrc_dc      = r["vsrc_dc"]
            c.vsrc_ac      = r["vsrc_ac"]
            c.vsrc_ac_phase= r["vsrc_ac_phase"]
            # Keep c.value in sync as a human-readable summary for the canvas label
            wf  = VSRC_TYPES[r["vsrc_type"]]
            p   = r["vsrc_params"].get(r["vsrc_type"], [])
            try:
                c.value = wf["spice"](p, r["vsrc_dc"], r["vsrc_ac"], r["vsrc_ac_phase"])
            except Exception:
                c.value = r["vsrc_type"]
            self._status(f"✓ {c.label}: {c.value}", "#818cf8")
            self._render()

    # ── Properties: passives (R, C, L, I, G, pins) ────────────────────────────
    def _open_passive_props(self, c):
        """Simple label + value editor for non-transistor components."""
        result = [None]
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Properties — {c.label} ({c.type})")
        dlg.configure(bg=PANEL_BG)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text=f"{c.type}  Properties",
            bg=PANEL_BG, fg="#818cf8",
            font=("Helvetica", 11, "bold"), pady=10).pack()

        def _row(parent, lbl, val, color="#e2e8f0"):
            f = tk.Frame(parent, bg=PANEL_BG)
            f.pack(fill=tk.X, padx=20, pady=3)
            tk.Label(f, text=lbl, bg=PANEL_BG, fg="#94a3b8",
                font=("Helvetica", 9), width=10, anchor="w").pack(side=tk.LEFT)
            sv = tk.StringVar(value=val)
            e  = tk.Entry(f, textvariable=sv,
                bg="#0c1020", fg=color,
                insertbackground=CURSOR_C,
                font=("Courier", 10), relief="flat", bd=3,
                selectbackground="#1e3a5f", width=24)
            e.pack(side=tk.LEFT, padx=(6,0))
            return sv

        sv_label = _row(dlg, "Label", c.label, "#fbbf24")
        sv_value = _row(dlg, "Value", c.value, "#818cf8")

        def _ok(_=None):
            result[0] = (sv_label.get().strip(), sv_value.get().strip())
            dlg.destroy()
        def _cancel(_=None):
            dlg.destroy()

        bf = tk.Frame(dlg, bg=PANEL_BG)
        bf.pack(fill=tk.X, padx=20, pady=(8,12))
        tk.Button(bf, text="OK", command=_ok,
            bg="#10082a", fg="#a78bfa",
            activebackground="#1a1040", activeforeground="#c4b5fd",
            font=("Helvetica", 9, "bold"),
            relief="flat", padx=16, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT)
        tk.Button(bf, text="Cancel", command=_cancel,
            bg=BORDER, fg="#4b5563",
            font=("Helvetica", 9), relief="flat",
            padx=10, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT, padx=(8,0))

        dlg.bind("<Return>", _ok)
        dlg.bind("<Escape>", _cancel)
        self._center_dialog(dlg)
        self.root.wait_window(dlg)
        self.cv.focus_set()

        if result[0]:
            lbl, val = result[0]
            if lbl: c.label = lbl
            if val: c.value = val
            self._status(f"✓ {c.label} = {c.value}", "#4ade80")
            self._render()

    # ── Properties: MOSFET ────────────────────────────────────────────────────
    def _open_mos_props(self, c):
        """Full MOSFET Properties dialog: label, model, W, L, fingers, bulk."""
        result = [None]
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Properties — {c.label} ({c.type})")
        dlg.configure(bg=PANEL_BG)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text=f"{c.type}  Properties",
            bg=PANEL_BG, fg="#f87171",
            font=("Helvetica", 11, "bold"), pady=10).pack()

        body = tk.Frame(dlg, bg=PANEL_BG)
        body.pack(fill=tk.X, padx=20, pady=4)

        def _lbl(row, text):
            tk.Label(row, text=text, bg=PANEL_BG, fg="#94a3b8",
                font=("Helvetica", 9), width=12, anchor="w").pack(side=tk.LEFT)

        def _entry(row, val, w=14, color="#e2e8f0"):
            sv = tk.StringVar(value=val)
            e  = tk.Entry(row, textvariable=sv,
                bg="#0c1020", fg=color,
                insertbackground=CURSOR_C,
                font=("Courier", 10), relief="flat", bd=3,
                selectbackground="#1e3a5f", width=w)
            e.pack(side=tk.LEFT, padx=(4,0))
            return sv

        # ── Label ──
        r0 = tk.Frame(body, bg=PANEL_BG); r0.pack(fill=tk.X, pady=2)
        _lbl(r0, "Label"); sv_label = _entry(r0, c.label, color="#fbbf24")

        # ── Model dropdown ──
        r1 = tk.Frame(body, bg=PANEL_BG); r1.pack(fill=tk.X, pady=2)
        _lbl(r1, "Model")
        # Build model list from cache (populated by Model Manager)
        mdl_list = list(self._model_names_cache.get(c.type, []))
        if not mdl_list:
            # Fallback: use whatever the model_config says, or generic name
            fallback = self.model_config.model_name(c.type)
            mdl_list = [fallback]
        current_model = c.model_name or mdl_list[0]
        if current_model not in mdl_list:
            mdl_list.insert(0, current_model)
        sv_model = tk.StringVar(value=current_model)
        mode_opt = tk.OptionMenu(r1, sv_model, *mdl_list)
        mode_opt.config(bg="#0c1020", fg="#f87171",
            activebackground="#1a0e0e", activeforeground="#fca5a5",
            font=("Courier", 9), relief="flat", bd=0,
            highlightthickness=0, width=18)
        mode_opt["menu"].config(bg="#0c1020", fg="#f87171",
            font=("Courier", 9))
        mode_opt.pack(side=tk.LEFT, padx=(4,0))

        # Model source hint
        if not self._model_names_cache.get(c.type):
            tk.Label(r1, text="  ← configure in ⚛ Models",
                bg=PANEL_BG, fg="#4b5563",
                font=("Helvetica", 8)).pack(side=tk.LEFT)

        # ── W / L ──
        # Pre-fill from component, then from model_config defaults
        dw, dl = self.model_config.default_wl(c.type)
        cur_w  = c.mos_w or dw or ("2u"  if c.type == "NMOS" else "4u")
        cur_l  = c.mos_l or dl or "180n"

        r2 = tk.Frame(body, bg=PANEL_BG); r2.pack(fill=tk.X, pady=2)
        _lbl(r2, "Width")
        sv_w = _entry(r2, cur_w, w=8)
        tk.Label(r2, text="  um  (e.g. 2u, 10u)",
            bg=PANEL_BG, fg="#4b5563", font=("Helvetica", 8)).pack(side=tk.LEFT)

        r3 = tk.Frame(body, bg=PANEL_BG); r3.pack(fill=tk.X, pady=2)
        _lbl(r3, "Length")
        sv_l = _entry(r3, cur_l, w=8)
        tk.Label(r3, text="  nm  (e.g. 180n, 500n)",
            bg=PANEL_BG, fg="#4b5563", font=("Helvetica", 8)).pack(side=tk.LEFT)

        # ── Fingers ──
        cur_fingers = getattr(c, 'fingers', 1)
        r4 = tk.Frame(body, bg=PANEL_BG); r4.pack(fill=tk.X, pady=2)
        _lbl(r4, "Fingers")
        sv_fingers = _entry(r4, str(cur_fingers), w=5)
        tk.Label(r4, text="  parallel fingers",
            bg=PANEL_BG, fg="#4b5563", font=("Helvetica", 8)).pack(side=tk.LEFT)

        # ── Bulk ──
        r5 = tk.Frame(body, bg=PANEL_BG); r5.pack(fill=tk.X, pady=2)
        _lbl(r5, "Bulk / Body")
        bulk_opts = ["0", "VDD", "VSS"] + [
            n for n in sorted(set(
                wl.text for wl in self.wlbls
            )) if n not in ("0","VDD","VSS")]
        cur_bulk = c.bulk_net or "0"
        if cur_bulk not in bulk_opts:
            bulk_opts.insert(0, cur_bulk)
        sv_bulk = tk.StringVar(value=cur_bulk)
        bulk_opt = tk.OptionMenu(r5, sv_bulk, *bulk_opts)
        bulk_opt.config(bg="#0c1020", fg="#e2e8f0",
            activebackground="#1e2c3e", activeforeground="#f0f0f0",
            font=("Courier", 9), relief="flat", bd=0,
            highlightthickness=0, width=8)
        bulk_opt["menu"].config(bg="#0c1020", fg="#e2e8f0", font=("Courier",9))
        bulk_opt.pack(side=tk.LEFT, padx=(4,0))

        # ── Live SPICE preview ──
        tk.Frame(body, bg=BORDER, height=1).pack(fill=tk.X, pady=(10,4))
        tk.Label(body, text="SPICE preview",
            bg=PANEL_BG, fg="#4b5563",
            font=("Courier", 7)).pack(anchor="w")
        sv_preview = tk.StringVar()
        lbl_preview = tk.Label(body, textvariable=sv_preview,
            bg="#050810", fg="#4ade80",
            font=("Courier", 9), anchor="w", padx=6, pady=4,
            wraplength=380, justify="left")
        lbl_preview.pack(fill=tk.X, pady=(0,6))

        def _update_preview(*_):
            mdl  = sv_model.get()
            w    = sv_w.get().strip()   or cur_w
            l    = sv_l.get().strip()   or cur_l
            blk  = sv_bulk.get()
            lbl  = sv_label.get().strip() or c.label
            sv_preview.set(
                f"{lbl:<10} drain    gate     source   {blk:<6} "
                f"{mdl}  W={w} L={l}")

        sv_model.trace_add("write", _update_preview)
        sv_w.trace_add("write",     _update_preview)
        sv_l.trace_add("write",     _update_preview)
        sv_bulk.trace_add("write",  _update_preview)
        sv_label.trace_add("write", _update_preview)
        _update_preview()

        # ── Buttons ──
        def _ok(_=None):
            result[0] = {
                "label":      sv_label.get().strip(),
                "model_name": sv_model.get(),
                "mos_w":      sv_w.get().strip(),
                "mos_l":      sv_l.get().strip(),
                "fingers":    sv_fingers.get().strip(),
                "bulk_net":   sv_bulk.get(),
            }
            dlg.destroy()
        def _cancel(_=None):
            dlg.destroy()

        bf = tk.Frame(dlg, bg=PANEL_BG)
        bf.pack(fill=tk.X, padx=20, pady=(4,12))
        tk.Button(bf, text="OK", command=_ok,
            bg="#1a0e0e", fg="#f87171",
            activebackground="#2a1010", activeforeground="#fca5a5",
            font=("Helvetica", 9, "bold"),
            relief="flat", padx=16, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT)
        tk.Button(bf, text="Cancel", command=_cancel,
            bg=BORDER, fg="#4b5563",
            font=("Helvetica", 9), relief="flat",
            padx=10, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT, padx=(8,0))

        dlg.bind("<Return>", _ok)
        dlg.bind("<Escape>", _cancel)
        self._center_dialog(dlg)
        self.root.wait_window(dlg)
        self.cv.focus_set()

        if result[0]:
            r = result[0]
            if r["label"]:      c.label      = r["label"]
            c.model_name = r["model_name"]
            c.mos_w      = r["mos_w"]
            c.mos_l      = r["mos_l"]
            c.bulk_net   = r["bulk_net"]
            try:   c.fingers = int(r["fingers"])
            except: c.fingers = 1
            self._status(
                f"✓ {c.label}  model={c.model_name}  "
                f"W={c.mos_w} L={c.mos_l}", "#4ade80")
            self._render()

    # ── Properties: BJT ───────────────────────────────────────────────────────
    def _open_bjt_props(self, c):
        """BJT Properties dialog: label and model name."""
        result = [None]
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Properties — {c.label} ({c.type})")
        dlg.configure(bg=PANEL_BG)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text=f"{c.type}  Properties",
            bg=PANEL_BG, fg="#f87171",
            font=("Helvetica", 11, "bold"), pady=10).pack()

        body = tk.Frame(dlg, bg=PANEL_BG)
        body.pack(fill=tk.X, padx=20, pady=4)

        def _row(lbl_text, val, color="#e2e8f0"):
            f = tk.Frame(body, bg=PANEL_BG); f.pack(fill=tk.X, pady=2)
            tk.Label(f, text=lbl_text, bg=PANEL_BG, fg="#94a3b8",
                font=("Helvetica", 9), width=12, anchor="w").pack(side=tk.LEFT)
            sv = tk.StringVar(value=val)
            e  = tk.Entry(f, textvariable=sv,
                bg="#0c1020", fg=color,
                insertbackground=CURSOR_C,
                font=("Courier", 10), relief="flat", bd=3,
                selectbackground="#1e3a5f", width=22)
            e.pack(side=tk.LEFT, padx=(4,0))
            return sv

        sv_label = _row("Label", c.label, "#fbbf24")

        # Model dropdown
        rf = tk.Frame(body, bg=PANEL_BG); rf.pack(fill=tk.X, pady=2)
        tk.Label(rf, text="Model", bg=PANEL_BG, fg="#94a3b8",
            font=("Helvetica", 9), width=12, anchor="w").pack(side=tk.LEFT)
        mdl_list = list(self._model_names_cache.get(c.type, []))
        if not mdl_list:
            mdl_list = [self.model_config.model_name(c.type)]
        current_model = c.model_name or mdl_list[0]
        if current_model not in mdl_list:
            mdl_list.insert(0, current_model)
        sv_model = tk.StringVar(value=current_model)
        opt = tk.OptionMenu(rf, sv_model, *mdl_list)
        opt.config(bg="#0c1020", fg="#f87171",
            activebackground="#1a0e0e", activeforeground="#fca5a5",
            font=("Courier", 9), relief="flat", bd=0,
            highlightthickness=0, width=18)
        opt["menu"].config(bg="#0c1020", fg="#f87171", font=("Courier", 9))
        opt.pack(side=tk.LEFT, padx=(4,0))
        if not self._model_names_cache.get(c.type):
            tk.Label(rf, text="  ← configure in ⚛ Models",
                bg=PANEL_BG, fg="#4b5563",
                font=("Helvetica", 8)).pack(side=tk.LEFT)

        # Preview
        tk.Frame(body, bg=BORDER, height=1).pack(fill=tk.X, pady=(10,4))
        sv_preview = tk.StringVar()
        tk.Label(body, textvariable=sv_preview,
            bg="#050810", fg="#4ade80",
            font=("Courier", 9), anchor="w", padx=6, pady=4
        ).pack(fill=tk.X, pady=(0,6))

        def _upd(*_):
            lbl = sv_label.get().strip() or c.label
            mdl = sv_model.get()
            sv_preview.set(f"{lbl:<10} collector base     emitter  {mdl}")
        sv_model.trace_add("write", _upd)
        sv_label.trace_add("write", _upd)
        _upd()

        def _ok(_=None):
            result[0] = (sv_label.get().strip(), sv_model.get())
            dlg.destroy()
        def _cancel(_=None): dlg.destroy()

        bf = tk.Frame(dlg, bg=PANEL_BG)
        bf.pack(fill=tk.X, padx=20, pady=(4,12))
        tk.Button(bf, text="OK", command=_ok,
            bg="#1a0e0e", fg="#f87171",
            activebackground="#2a1010", activeforeground="#fca5a5",
            font=("Helvetica", 9, "bold"),
            relief="flat", padx=16, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT)
        tk.Button(bf, text="Cancel", command=_cancel,
            bg=BORDER, fg="#4b5563",
            font=("Helvetica", 9), relief="flat",
            padx=10, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT, padx=(8,0))
        dlg.bind("<Return>", _ok)
        dlg.bind("<Escape>", _cancel)
        self._center_dialog(dlg)
        self.root.wait_window(dlg)
        self.cv.focus_set()

        if result[0]:
            lbl, mdl = result[0]
            if lbl: c.label = lbl
            c.model_name = mdl
            self._status(f"✓ {c.label}  model={c.model_name}", "#4ade80")
            self._render()

    # ── Model Manager ─────────────────────────────────────────────────────────
    def _open_model_manager(self):
        """
        Project-level model configuration dialog.
        Sets mode (inline / external file), level (1/2/3/BSIM3/BSIM4),
        file path and corner.  Parses the file to populate the model
        name cache used by MOSFET/BJT Properties dropdowns.
        """
        mc     = self.model_config
        result = [None]

        dlg = tk.Toplevel(self.root)
        dlg.title("Model Manager")
        dlg.configure(bg=PANEL_BG)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="⚛  Model Manager",
            bg=PANEL_BG, fg="#f87171",
            font=("Helvetica", 12, "bold"), pady=12).pack()

        body = tk.Frame(dlg, bg=PANEL_BG)
        body.pack(fill=tk.X, padx=22, pady=4)

        # ── Mode selector ──
        sv_mode = tk.StringVar(value=mc.mode)
        mode_frame = tk.LabelFrame(body, text="  Model Source  ",
            bg=PANEL_BG, fg="#94a3b8",
            font=("Helvetica", 9), bd=1, relief="solid")
        mode_frame.pack(fill=tk.X, pady=(0,10))

        for val, lbl in [("inline",  "Inline  (Level 1 parameters built-in)"),
                         ("include", "External file  (.sp / .spi  — .include)"),
                         ("lib",     "Library file   (.lib  — .lib + corner)")]:
            tk.Radiobutton(mode_frame, text=lbl, variable=sv_mode, value=val,
                bg=PANEL_BG, fg="#cbd5e1", selectcolor="#1a0e0e",
                activebackground=PANEL_BG, activeforeground="#f87171",
                font=("Helvetica", 9), anchor="w"
            ).pack(fill=tk.X, padx=10, pady=1)

        # ── Level selector (inline only) ──
        level_frame = tk.LabelFrame(body, text="  SPICE Level  ",
            bg=PANEL_BG, fg="#94a3b8",
            font=("Helvetica", 9), bd=1, relief="solid")
        level_frame.pack(fill=tk.X, pady=(0,10))

        level_keys = [1, 2, 3, "BSIM3", "BSIM4"]
        sv_level   = tk.StringVar(value=str(mc.level))
        for key in level_keys:
            lbl_text = LEVEL_LABELS.get(key, str(key))
            disabled = key in (2, 3, "BSIM3", "BSIM4")
            rb = tk.Radiobutton(level_frame,
                text=lbl_text + ("  [coming soon]" if disabled else ""),
                variable=sv_level, value=str(key),
                state="disabled" if disabled else "normal",
                bg=PANEL_BG,
                fg="#4b5563" if disabled else "#cbd5e1",
                selectcolor="#1a0e0e",
                activebackground=PANEL_BG, activeforeground="#f87171",
                font=("Helvetica", 9), anchor="w")
            rb.pack(fill=tk.X, padx=10, pady=1)

        # ── File picker ──
        file_frame = tk.LabelFrame(body, text="  Model File  ",
            bg=PANEL_BG, fg="#94a3b8",
            font=("Helvetica", 9), bd=1, relief="solid")
        file_frame.pack(fill=tk.X, pady=(0,10))

        fr1 = tk.Frame(file_frame, bg=PANEL_BG); fr1.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(fr1, text="File:", bg=PANEL_BG, fg="#94a3b8",
            font=("Helvetica", 9), width=7, anchor="w").pack(side=tk.LEFT)
        sv_file = tk.StringVar(value=mc.file_path)
        ent_file = tk.Entry(fr1, textvariable=sv_file,
            bg="#0c1020", fg="#e2e8f0",
            insertbackground=CURSOR_C,
            font=("Courier", 9), relief="flat", bd=3, width=30)
        ent_file.pack(side=tk.LEFT, padx=(4,4))

        def _browse():
            p = filedialog.askopenfilename(
                title="Select Model File",
                filetypes=FD_MODEL,
                initialdir=self._last_dir)
            if p:
                sv_file.set(p)
                self._last_dir = os.path.dirname(p)
                _parse_file(p)
        tk.Button(fr1, text="Browse…", command=_browse,
            bg=BORDER, fg="#94a3b8",
            activebackground="#1e2c3e", activeforeground="#e2e8f0",
            font=("Helvetica", 8), relief="flat",
            padx=6, pady=2, cursor="hand2"
        ).pack(side=tk.LEFT)

        fr2 = tk.Frame(file_frame, bg=PANEL_BG); fr2.pack(fill=tk.X, padx=8, pady=(0,4))
        tk.Label(fr2, text="Corner:", bg=PANEL_BG, fg="#94a3b8",
            font=("Helvetica", 9), width=7, anchor="w").pack(side=tk.LEFT)
        sv_corner = tk.StringVar(value=mc.corner or "tt")
        corner_opts = ["tt", "ff", "ss", "fs", "sf"]
        corner_menu = tk.OptionMenu(fr2, sv_corner, *corner_opts)
        corner_menu.config(bg="#0c1020", fg="#e2e8f0",
            activebackground="#1e2c3e", activeforeground="#f0f0f0",
            font=("Courier", 9), relief="flat", bd=0,
            highlightthickness=0, width=6)
        corner_menu["menu"].config(bg="#0c1020", fg="#e2e8f0", font=("Courier",9))
        corner_menu.pack(side=tk.LEFT, padx=(4,0))
        tk.Label(fr2, text="  (for .lib files only)",
            bg=PANEL_BG, fg="#4b5563",
            font=("Helvetica", 8)).pack(side=tk.LEFT)

        # ── Detected models list ──
        det_frame = tk.LabelFrame(body, text="  Detected Models  ",
            bg=PANEL_BG, fg="#94a3b8",
            font=("Helvetica", 9), bd=1, relief="solid")
        det_frame.pack(fill=tk.X, pady=(0,10))

        det_text = tk.Text(det_frame, height=7, width=52,
            bg="#050810", fg="#4ade80",
            font=("Courier", 8), relief="flat",
            state=tk.DISABLED, padx=6, pady=4)
        det_text.pack(fill=tk.X, padx=4, pady=4)

        def _parse_file(path=None):
            p = path or sv_file.get().strip()
            if not p or not os.path.isfile(p):
                _set_detected_text(
                    "(no file — using inline defaults)" if not p
                    else f"[!] File not found:\n{p}")
                return
            found = parse_model_file(p)
            # Update the live cache
            self._model_names_cache = found
            lines = [f"  File: {os.path.basename(p)}", ""]
            total = 0
            for dt in ("NMOS","PMOS","NPN","PNP"):
                names = found.get(dt, [])
                total += len(names)
                if names:
                    lines.append(f"  {dt}:")
                    for n in names:
                        lines.append(f"    ✓  {n}")
            if total == 0:
                lines.append("  [!] No .model definitions found")
                lines.append("  Check that the file uses:")
                lines.append("  .model <name> NMOS|PMOS|NPN|PNP (...)")
            _set_detected_text("\n".join(lines))

        def _set_detected_text(txt):
            det_text.config(state=tk.NORMAL)
            det_text.delete("1.0", tk.END)
            det_text.insert(tk.END, txt)
            det_text.config(state=tk.DISABLED)

        # Populate on open
        if mc.file_path and os.path.isfile(mc.file_path):
            _parse_file(mc.file_path)
        elif mc.mode == "inline":
            _set_detected_text(
                "  Inline mode — built-in Level 1 parameters\n\n"
                "  NMOS_GENERIC  (VTO=1.0  KP=200u  LAMBDA=0.01)\n"
                "  PMOS_GENERIC  (VTO=-1.0 KP=80u   LAMBDA=0.01)\n"
                "  NPN_GENERIC   (IS=1e-14 BF=100   VAF=50)\n"
                "  PNP_GENERIC   (IS=1e-14 BF=50    VAF=50)")
        else:
            _set_detected_text("  No file configured yet — click Browse…")

        sv_file.trace_add("write", lambda *_: _parse_file())

        # ── Buttons ──
        def _ok(_=None):
            level_val = sv_level.get()
            try:    level_val = int(level_val)
            except: pass   # stays as "BSIM3" / "BSIM4"
            result[0] = {
                "mode":      sv_mode.get(),
                "level":     level_val,
                "file_path": sv_file.get().strip(),
                "corner":    sv_corner.get(),
            }
            dlg.destroy()

        def _cancel(_=None): dlg.destroy()

        bf = tk.Frame(dlg, bg=PANEL_BG)
        bf.pack(fill=tk.X, padx=22, pady=(4,14))
        tk.Button(bf, text="Apply", command=_ok,
            bg="#1a0e0e", fg="#f87171",
            activebackground="#2a1010", activeforeground="#fca5a5",
            font=("Helvetica", 9, "bold"),
            relief="flat", padx=16, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT)
        tk.Button(bf, text="Cancel", command=_cancel,
            bg=BORDER, fg="#4b5563",
            font=("Helvetica", 9), relief="flat",
            padx=10, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT, padx=(8,0))

        dlg.bind("<Escape>", _cancel)
        self._center_dialog(dlg)
        self.root.wait_window(dlg)
        self.cv.focus_set()

        if result[0]:
            r = result[0]
            self.model_config.mode      = r["mode"]
            self.model_config.level     = r["level"]
            self.model_config.file_path = r["file_path"]
            self.model_config.corner    = r["corner"]
            # Re-parse so the cache is fresh when Properties dialogs open
            if r["file_path"]:
                self._model_names_cache = parse_model_file(r["file_path"])
            elif r["mode"] == "inline":
                self._model_names_cache = {}   # use generic names
            mode_lbl = {"inline":"inline","include":".include","lib":".lib"}[r["mode"]]
            self._status(
                f"✓ Models: {mode_lbl}"
                + (f"  {os.path.basename(r['file_path'])}" if r["file_path"] else "")
                + (f"  [{r['corner']}]" if r["mode"]=="lib" else ""),
                "#f87171")

    def _open_cmd(self):
        cmd = self._ask("Command",
            "nmos  pmos  npn  pnp  ·  in  out  inout  vdd  vss  ·  "
            "sim  ·  save  load  netlist  savesvg  savepng  doc clear",
            color="#c21820")
        if cmd and cmd.strip():
            self._exec_cmd(cmd.strip())
        else:
            self._render()

    # ── Command dispatcher ─────────────────────────────────────────────────────
    def _exec_cmd(self, raw: str):
        parts = raw.strip().split()
        if not parts: return
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else None

        if cmd in ("nmos","pmos","npn","pnp"):
            self._place_device(cmd.upper())
        elif cmd in ("pin","in","out","inout","vdd","vss"):
            # map shorthand → internal type
            _map = {"pin":"PIN_IN","in":"PIN_IN","out":"PIN_OUT",
                    "inout":"PIN_INOUT","vdd":"PIN_VDD","vss":"PIN_VSS"}
            self._place_device(_map[cmd])
        elif cmd in ("sim","analysis","simulate"):
            self._open_sim_dialog()
        elif cmd == "save":
            self._dialog_save()
        elif cmd == "load":
            self._dialog_load()
        elif cmd in ("netlist","nl","net"):
            self._dialog_save_netlist()
        elif cmd == "savepng":
            self._dialog_save_image()
        elif cmd == "savesvg":
            self._dialog_save_svg()
        elif cmd in ("doc","docimg","savedoc"):
            self._dialog_save_doc_image()
        elif cmd == "zoom":
            try: self._zoom_to(int(arg or "100"))
            except: self._status("[!] zoom needs a number", "#f87171")
        elif cmd == "clear":
            self._clear()
        elif cmd == "help":
            self._status(
                "HOTKEYS  arrows=move · R/C/L/V/I/G=place · W=wire(Enter/Esc) · "
                "Spc=rotate · F=flip · T=net-label · E=edit · M=mouse-mode · "
                "+/-=zoom · Del=delete  │  "
                "COMMANDS (:)  nmos pmos npn pnp · in out inout vdd vss · "
                "sim · save · load · netlist · savepng · savesvg · doc (B&W) · "
                "zoom <pct> · clear · help",
                "#a78bfa")
        else:
            self._status(f"[!] Unknown: '{cmd}' — try :help", "#f87171")

    # ── JSON save / load  (primary reloadable format) ──────────────────────────
    def _save_json(self, path: str):
        data = {
            "version":      "0.6",
            "components":   [c.to_dict() for c in self.comps],
            "wires":        [w.to_dict() for w in self.wires],
            "wirelabels":   [l.to_dict() for l in self.wlbls],
            "simulation":   self.sim_config.to_dict(),
            "model_config": self.model_config.to_dict(),
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._current_file = path
            stem = os.path.splitext(os.path.basename(path))[0]
            self.root.title(f"Vischem  v0.1  —  {stem}")
            self._status(f"✓ Saved → {os.path.basename(path)}", "#4ade80")
        except Exception as e:
            self._status(f"[!] {e}", "#f87171")

    def _load_json(self, path: str):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._clear()
            for d in data.get("components", []):
                c = Component.from_dict(d)
                Component._uid = max(Component._uid, c.uid)
                Component._cnt[c.type] = Component._cnt.get(c.type, 0) + 1
                self.comps.append(c)
            for d in data.get("wires", []):
                self.wires.append(Wire.from_dict(d))
            for d in data.get("wirelabels", []):
                self.wlbls.append(WireLabel.from_dict(d))
            if "simulation" in data:
                self.sim_config = SimConfig.from_dict(data["simulation"])
            if "model_config" in data:
                self.model_config = ModelConfig.from_dict(data["model_config"])
                # Refresh parsed-model cache if an external file is configured
                fp = self.model_config.file_path
                if fp and os.path.isfile(fp):
                    self._model_names_cache = parse_model_file(fp)
                else:
                    self._model_names_cache = {}
            self._status(
                f"✓ Loaded {len(self.comps)} comp · {len(self.wires)} wire"
                f" from {os.path.basename(path)}", "#4ade80")
            self._current_file = path
            stem = os.path.splitext(os.path.basename(path))[0]
            self.root.title(f"Vischem  v0.1  —  {stem}")
            self._render()
        except Exception as e:
            self._status(f"[!] Load failed: {e}", "#f87171")

    # ── Legacy CSV load (backward compat) ──────────────────────────────────────
    def _load_csv(self, path: str):
        if not os.path.exists(path):
            self._status(f"[!] Not found: {path}", "#f87171"); return
        try:
            self._clear()
            with open(path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row.get("section") == "component":
                        self.comps.append(Component(
                            row["type"], int(row["gx"]), int(row["gy"]),
                            label=row["label"], value=row["value"],
                            rot=int(row.get("rot", 0))))
                    elif row.get("section") == "wire":
                        self.wires.append(Wire(
                            int(row["x1"]),int(row["y1"]),
                            int(row["x2"]),int(row["y2"])))
            self._status(
                f"✓ Loaded (CSV) {len(self.comps)} comp · "
                f"{len(self.wires)} wire", "#4ade80")
            self._render()
        except Exception as e:
            self._status(f"[!] CSV load failed: {e}", "#f87171")

    # ── SVG export ─────────────────────────────────────────────────────────────
    def _save_svg(self, path: str):
        GS = self.GS
        W, H = self.CW, self.CH
        dot_r  = max(1.0, GS/48)
        ww     = max(1.5, GS/40)
        jr     = max(3.0, GS/16)
        fs_lbl = max(7, GS//7)
        fs_val = max(6, GS//9)

        L = []
        L.append('<?xml version="1.0" encoding="UTF-8"?>')
        L.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                 f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
        L.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')

        # Grid dots
        L.append('<g id="grid">')
        for r in range(ROWS+1):
            for c in range(COLS+1):
                L.append(f'<circle cx="{c*GS:.1f}" cy="{r*GS:.1f}" '
                         f'r="{dot_r:.1f}" fill="{GRID_DOT}"/>')
        L.append('</g>')

        # Wires
        L.append(f'<g stroke="{WIRE_C}" stroke-width="{ww:.1f}" '
                 f'stroke-linecap="round">')
        for w in self.wires:
            L.append(f'<line x1="{w.x1*GS:.1f}" y1="{w.y1*GS:.1f}" '
                     f'x2="{w.x2*GS:.1f}" y2="{w.y2*GS:.1f}"/>')
        L.append('</g>')

        # Junction dots
        ep: dict = {}
        for w in self.wires:
            for pt in ((w.x1,w.y1),(w.x2,w.y2)):
                ep[pt] = ep.get(pt,0)+1
        for (gx,gy),cnt in ep.items():
            if cnt > 1:
                L.append(f'<circle cx="{gx*GS:.1f}" cy="{gy*GS:.1f}" '
                         f'r="{jr:.1f}" fill="{WIRE_C}"/>')

        # Components
        L.append('<g id="components">')
        for comp in self.comps:
            cx, cy = comp.gx*GS, comp.gy*GS
            # Build transform: rotate, then optionally flip
            tx = f"translate({cx:.1f},{cy:.1f}) rotate({comp.rot})"
            if comp.flip:
                tx += " scale(-1,1)"
            bw, bh = GS*0.7, GS*0.35
            L.append(f'<g transform="{tx}">')
            L.append(f'<rect x="{-bw/2:.1f}" y="{-bh/2:.1f}" '
                     f'width="{bw:.1f}" height="{bh:.1f}" '
                     f'rx="3" fill="none" stroke="#9fb0c8" stroke-width="1.2"/>')
            L.append(f'<text x="0" y="0" fill="#c9d1d9" '
                     f'font-family="Helvetica" font-size="{fs_lbl}" '
                     f'font-weight="bold" text-anchor="middle" '
                     f'dominant-baseline="central">{comp.type}</text>')
            L.append('</g>')
            # Labels (outside component transform — always readable)
            is_dev = comp.type in ("NMOS","PMOS","NPN","PNP")
            lx = cx + (GS*0.70 if is_dev else 0)
            ly = cy + (-GS*0.88 if not is_dev else -GS*0.64)
            vy = cy + (GS*0.88  if not is_dev else -GS*0.44)
            L.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{LBL_NORMAL}" '
                     f'font-family="Helvetica" font-size="{fs_lbl}" '
                     f'font-weight="bold" text-anchor="middle">{comp.label}</text>')
            if comp.value:
                L.append(f'<text x="{lx:.1f}" y="{vy:.1f}" fill="{VAL_NORMAL}" '
                         f'font-family="Helvetica" font-size="{fs_val}" '
                         f'text-anchor="middle">{comp.value}</text>')
        L.append('</g>')
        L.append('</svg>')

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(L))
            self._status(f"✓ SVG → {os.path.basename(path)}", "#4ade80")
        except Exception as e:
            self._status(f"[!] SVG save failed: {e}", "#f87171")

    # ── Raster image export ────────────────────────────────────────────────────
    def _save_raster(self, path: str):
        self.root.update_idletasks(); self.root.update()
        if _PILLOW:
            try:
                self.root.lift(); self.root.update()
                x = self.root.winfo_rootx() + self.cv.winfo_x()
                y = self.root.winfo_rooty() + self.cv.winfo_y()
                img = ImageGrab.grab(
                    bbox=(x,y,x+self.cv.winfo_width(),y+self.cv.winfo_height()))
                img.save(path)
                self._status(f"✓ Image → {os.path.basename(path)}", "#4ade80")
                return
            except Exception: pass
            try:
                tmp = tempfile.mktemp(suffix=".eps")
                self.cv.postscript(file=tmp, colormode="color",
                                   width=self.CW, height=self.CH)
                Image.open(tmp).save(path); os.unlink(tmp)
                self._status(f"✓ Image (EPS→PIL) → {os.path.basename(path)}", "#4ade80")
                return
            except Exception: pass
        eps = os.path.splitext(path)[0]+".eps"
        try:
            self.cv.postscript(file=eps, colormode="color",
                               width=self.CW, height=self.CH)
            self._status(f"✓ EPS → {os.path.basename(eps)} (install Pillow for PNG)",
                         "#f59e0b")
        except Exception as e:
            self._status(f"[!] Export failed: {e}", "#f87171")

    # ── Documentation image export (clean B&W, for reports/papers) ─────────────
    def _dialog_save_doc_image(self):
        path = self._savepath(
            "Save Documentation Image (black on white)", FD_RASTER, ".png")
        if path:
            self._save_doc_image(path)

    def _save_doc_image(self, path: str):
        """
        Export a print-ready, black-ink-on-white-paper version of the
        schematic — no dark theme, no grid dots, no cursor/selection
        highlighting. This reuses the real on-screen render (same
        draw_symbol() shapes), then converts the captured pixels to a
        clean black-on-white image, so it stays accurate no matter what
        the editor's on-screen color theme looks like.
        """
        if not _PILLOW:
            self._status(
                "[!] Documentation export needs Pillow — pip install pillow",
                "#f87171")
            return
        try:
            self._render(doc_mode=True)   # clean pass: no grid/cursor/selection
            self.root.lift()
            self.root.update_idletasks()
            self.root.update()

            x = self.root.winfo_rootx() + self.cv.winfo_x()
            y = self.root.winfo_rooty() + self.cv.winfo_y()
            img = ImageGrab.grab(
                bbox=(x, y, x + self.cv.winfo_width(), y + self.cv.winfo_height()))

            # Dark theme → white paper: invert, stretch contrast, then snap
            # near-background pixels to pure white for a crisp printed page.
            gray  = img.convert("L")
            paper = ImageOps.invert(gray)
            paper = ImageOps.autocontrast(paper, cutoff=1)
            paper = paper.point(lambda p: 255 if p > 235 else p)
            paper.convert("RGB").save(path)

            self._status(
                f"✓ Documentation image → {os.path.basename(path)}", "#4ade80")
        except Exception as e:
            self._status(f"[!] Documentation export failed: {e}", "#f87171")
        finally:
            self._render()   # restore the normal on-screen theme

    # ── Netlist ────────────────────────────────────────────────────────────────
    # ── NGspice integration ────────────────────────────────────────────────────

    def _locate_ngspice(self):
        """Called once at startup (or on first Run). Caches the exe path."""
        if not _HAS_SIM:
            return
        self._ngspice_exe = find_ngspice()
        if self._ngspice_exe:
            ver = simulator_version(self._ngspice_exe)
            self._status(f"✓ {ver} found at {self._ngspice_exe}", "#4ade80")
            self.btn_run.config(state=tk.NORMAL)
        else:
            self.btn_run.config(state=tk.DISABLED, fg="#4b5563")
            self._status(
                "[!] ngspice not found — install ngspice to enable Run.  "
                "Linux: sudo apt install ngspice  |  "
                "Windows: https://ngspice.sourceforge.io/download.html",
                "#f59e0b")

    def _run_simulation(self):
        """
        Main Run handler — called by the ▶ Run button.
        1. Ensure schematic is saved
        2. Write .cir alongside the .json
        3. Run ngspice in a background thread
        4. Stream output to the log panel
        5. Report success / failure
        """
        import threading

        # ── Guard: ngspice must be present ────────────────────────────────────
        if not _HAS_SIM or not self._ngspice_exe:
            self._locate_ngspice()
            if not self._ngspice_exe:
                return

        # ── Guard: schematic must be saved ────────────────────────────────────
        if not self._current_file:
            answer = self._ask(
                "Save before running",
                "The schematic must be saved first.\n"
                "Save now? (your .cir and .raw will go in the same folder)",
                color="#f59e0b")
            if answer is None:
                return
            self._dialog_save()
            if not self._current_file:
                return   # user cancelled the save dialog

        # ── Guard: simulation analysis must be configured ─────────────────────
        if not self.sim_config or not getattr(self.sim_config, "analysis", None):
            self._status(
                "[!] No simulation configured — press ⚡ Simulation first",
                "#f59e0b")
            self._open_sim_dialog()
            return

        # ── Derive file paths from the saved .json location ───────────────────
        base     = os.path.splitext(self._current_file)[0]   # strip .json
        cir_path = base + ".cir"
        raw_path = base + ".raw"

        # ── Generate and write the netlist ────────────────────────────────────
        if not _HAS_NETLIST:
            self._status("[!] netlist.py not found", "#f87171"); return
        result = generate_netlist(
            self.comps, self.wires, self.wlbls,
            sim_config=self.sim_config,
            model_config=self.model_config,
            raw_filename=os.path.basename(raw_path),   # just "stem.raw"
            title=os.path.basename(base))
        self._last_result = result

        try:
            with open(cir_path, "w", encoding="utf-8") as f:
                f.write(result.netlist)
        except Exception as e:
            self._status(f"[!] Cannot write netlist: {e}", "#f87171"); return

        # ── Open / reset the log panel ────────────────────────────────────────
        self._show_sim_log()
        self._sim_log_clear()
        stem = os.path.basename(base)
        self._sim_log_write(
            f"▶  Running simulation: {stem}\n"
            f"   Netlist : {cir_path}\n"
            f"   Output  : {raw_path}\n"
            f"   Solver  : {self._ngspice_exe}\n"
            f"   Analysis: {self.sim_config.analysis}\n"
            + "─" * 52 + "\n",
            tag="header")

        self.btn_run.config(text="⏳ Running…", state=tk.DISABLED)
        self._last_raw_path = None

        # ── Run ngspice in a background thread so the GUI stays responsive ────
        def _worker():
            def _on_line(line: str, is_err: bool):
                # Schedule GUI update on the main thread
                tag = "err" if is_err else (
                    "warn" if any(w in line.lower()
                                  for w in ("warning","note:")) else "dim")
                self.root.after(0, lambda l=line, t=tag:
                                self._sim_log_write(l + "\n", tag=t))

            sim = run_simulation(cir_path, raw_path,
                                 self._ngspice_exe,
                                 on_line=_on_line)

            # Back on main thread for final UI update
            self.root.after(0, lambda: self._on_sim_done(sim))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_sim_done(self, sim):
        """Called on the main thread when the simulation thread finishes."""
        self.btn_run.config(text="▶ Run", state=tk.NORMAL)

        sep = "─" * 52
        if sim.success:
            self._last_raw_path = sim.raw_path
            self.btn_show_raw.config(fg="#4ade80")
            msg = (f"\n{sep}\n"
                   f"✓  Simulation complete  ({sim.duration_s:.2f}s)\n"
                   f"   Results → {sim.raw_path}\n")
            self._sim_log_write(msg, tag="ok")
            self.lbl_sim_header.config(text="  ✓ Simulation complete",
                                       fg="#4ade80")
            self._status(
                f"✓ Done in {sim.duration_s:.2f}s  →  "
                f"{os.path.basename(sim.raw_path)}", "#4ade80")
        else:
            self.btn_show_raw.config(fg="#4b5563")
            err_text = "\n".join(sim.errors) if sim.errors else "(see log above)"
            msg = (f"\n{sep}\n"
                   f"[!] Simulation failed  (exit {sim.exit_code})\n"
                   f"    {err_text}\n")
            self._sim_log_write(msg, tag="err")
            self.lbl_sim_header.config(text="  [!] Simulation failed",
                                       fg="#f87171")
            self._status(
                f"[!] Simulation failed — check log panel", "#f87171")

    # ── Sim log panel helpers ──────────────────────────────────────────────────
    def _show_sim_log(self):
        if not self._sim_log_visible:
            self._sim_log_visible = True
            self.sim_log_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 0))
            self.sim_log_frame.config(width=440)

    def _hide_sim_log(self):
        self._sim_log_visible = False
        self.sim_log_frame.pack_forget()
        self.lbl_sim_header.config(text="  ▶ Simulation Log", fg="#4ade80")

    def _sim_log_clear(self):
        self.sim_log_text.config(state=tk.NORMAL)
        self.sim_log_text.delete("1.0", tk.END)
        self.sim_log_text.config(state=tk.DISABLED)

    def _sim_log_write(self, text: str, tag: str = "dim"):
        self.sim_log_text.config(state=tk.NORMAL)
        self.sim_log_text.insert(tk.END, text, tag)
        self.sim_log_text.see(tk.END)
        self.sim_log_text.config(state=tk.DISABLED)

    def _reveal_raw_file(self):
        """Open the folder containing the .raw file in the OS file manager."""
        if not self._last_raw_path or not os.path.isfile(self._last_raw_path):
            self._status("[!] No .raw file yet — run simulation first",
                         "#f59e0b")
            return
        folder = os.path.dirname(self._last_raw_path)
        import subprocess as _sp
        try:
            if sys.platform == "win32":
                _sp.Popen(["explorer", "/select,",
                           os.path.normpath(self._last_raw_path)])
            elif sys.platform == "darwin":
                _sp.Popen(["open", "-R", self._last_raw_path])
            else:   # Linux
                _sp.Popen(["xdg-open", folder])
        except Exception as e:
            self._status(f"[!] Cannot open folder: {e}", "#f87171")

    def _toggle_netlist_panel(self):
        self._netlist_visible = not self._netlist_visible
        if self._netlist_visible:
            self.netlist_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(4,0))
            self.netlist_frame.config(width=420)
            self._rebuild_netlist()
            self.btn_netlist.config(bg="#0a2a0a", fg="#86efac")
        else:
            self.netlist_frame.pack_forget()
            self.btn_netlist.config(bg="#0d1a0d", fg="#4ade80")

    def _rebuild_netlist(self):
        if not self._netlist_visible: return
        if not _HAS_NETLIST:
            self._status("[!] netlist.py not found", "#f87171"); return
        result = generate_netlist(self.comps, self.wires, self.wlbls,
                                   sim_config=self.sim_config,
                                   model_config=self.model_config,
                                   title="Vischem")
        self._last_result = result
        self._render_netlist_panel(result)

    def _render_netlist_panel(self, result):
        import re
        if result.warnings:
            self.nl_warn.config(text="⚠  " + "  ·  ".join(result.warnings))
        else:
            self.nl_warn.config(text="  ✓ No warnings",
                                 fg="#2d6a35", bg="#080c10")
        net_summary = "  ".join(
            f"{k}:{len(v)}pt" for k,v in sorted(result.nets.items()))
        self.nl_nets.config(text=f"  nets: {net_summary}")
        txt = self.nl_text
        txt.config(state=tk.NORMAL); txt.delete("1.0", tk.END)
        for line in result.netlist.splitlines():
            start = txt.index(tk.END)
            txt.insert(tk.END, line + "\n")
            end = txt.index(tk.END)
            ls = int(start.split(".")[0])
            if line.startswith("*"):
                txt.tag_add("comment", start, end)
                txt.tag_add("control", start, end)
            elif line.startswith(".end"):
                txt.tag_add("end", start, end)
            elif line.startswith("."):
                txt.tag_add("dot", start, end)
            else:
                for m in re.finditer(r"(N\d{3}|0)", line):
                    txt.tag_add("net", f"{ls}.{m.start()}", f"{ls}.{m.end()}")
                for m in re.finditer(r"(\d[\d.]*[kKmMuµnpfgGT]?)", line):
                    txt.tag_add("value", f"{ls}.{m.start()}", f"{ls}.{m.end()}")
        txt.config(state=tk.DISABLED); txt.see("1.0")

    def _save_netlist_to(self, path: str):
        if not _HAS_NETLIST:
            self._status("[!] netlist.py not found", "#f87171"); return
        if not self._last_result:
            self._last_result = generate_netlist(
                self.comps, self.wires, self.wlbls,
                sim_config=self.sim_config,
                model_config=self.model_config,
                title="Vischem")
        if not path.endswith(".cir"): path += ".cir"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._last_result.netlist)
            self._status(f"✓ Netlist → {os.path.basename(path)}", "#4ade80")
        except Exception as e:
            self._status(f"[!] {e}", "#f87171")

    def _save_netlist_file(self, path=None):
        """Called from panel '⬇ Save .cir' button."""
        self._dialog_save_netlist()

    def _clear(self):
        self.comps=[]; self.wires=[]; self.wlbls=[]
        Component._uid=0; Component._cnt={}
        Wire._uid=0
        self.mode="NORMAL"; self.ws=None
        self._render()

    # ── Render ─────────────────────────────────────────────────────────────────
    def _render(self, doc_mode: bool = False):
        GS = self.GS
        cv = self.cv
        cv.delete("all")

        f_lbl = ("Helvetica", max(7, GS//7), "bold")
        f_val = ("Helvetica", max(6, GS//9))
        dot_r  = max(1.0, GS/48)
        wire_w = max(1.5, GS/40)
        junc_r = max(3,   GS/16)

        # Grid dots (skipped in documentation mode — clean page, no grid)
        if not doc_mode:
            for r in range(ROWS+1):
                for c in range(COLS+1):
                    x, y = c*GS, r*GS
                    cv.create_oval(x-dot_r,y-dot_r,x+dot_r,y+dot_r,
                                   fill=GRID_DOT, outline="")

        # Wires
        for w in self.wires:
            cv.create_line(w.x1*GS,w.y1*GS,w.x2*GS,w.y2*GS,
                           fill=WIRE_C, width=wire_w, capstyle=tk.ROUND)

        # Junction dots
        ep: dict = {}
        for w in self.wires:
            for pt in ((w.x1,w.y1),(w.x2,w.y2)):
                ep[pt] = ep.get(pt,0)+1
        for (gx,gy),cnt in ep.items():
            if cnt > 1:
                x0,y0 = gx*GS, gy*GS
                cv.create_oval(x0-junc_r,y0-junc_r,
                               x0+junc_r,y0+junc_r,
                               fill=WIRE_C, outline="")

        # Wire labels (net names on wires)
        f_wlbl = ("Helvetica", max(7, GS//8), "bold")
        for wl in self.wlbls:
            wx, wy = wl.gx * GS, wl.gy * GS
            # Small flag background
            tw = max(30, len(wl.text) * max(6, GS//9))
            th = max(14, GS // 5)
            cv.create_rectangle(
                wx - tw//2 - 3, wy - th//2 - 2,
                wx + tw//2 + 3, wy + th//2 + 2,
                fill="#0a1a2a", outline=WIRE_LBL_COLOR,
                width=1.0)
            cv.create_text(wx, wy,
                text=wl.text, fill=WIRE_LBL_COLOR,
                font=f_wlbl, anchor="center")

        # Wire preview
        if self.mode == "WIRE" and self.ws and not doc_mode:
            cx_, cy_ = self.cursor
            cv.create_line(self.ws[0]*GS,self.ws[1]*GS,cx_*GS,cy_*GS,
                fill=WIRE_PRV,width=wire_w,dash=(7,3),capstyle=tk.ROUND)
            s0x,s0y = self.ws[0]*GS,self.ws[1]*GS
            cv.create_oval(s0x-5,s0y-5,s0x+5,s0y+5,
                outline=WIRE_PRV,width=1.2,dash=(3,2))

        # Components
        gx_c, gy_c = self.cursor
        for comp in self.comps:
            sel = (comp.gx==gx_c and comp.gy==gy_c) and not doc_mode
            ox, oy = comp.gx*GS, comp.gy*GS

            if sel:
                cv.create_rectangle(
                    ox-GS*.78,oy-GS*.78,ox+GS*.78,oy+GS*.78,
                    fill=SEL_RECT,outline=SEL_OUT,width=1.0,dash=(4,3))

            # Use FlipContext so the symbol is drawn mirrored when flip=True
            ctx = FlipContext(cv, ox, oy, GS, comp.rot, sel, comp.flip)
            draw_symbol(ctx, comp.type)

            # Labels
            lc = LBL_SEL  if sel else LBL_NORMAL
            vc = VAL_SEL  if sel else VAL_NORMAL
            is_dev = comp.type in ("NMOS","PMOS","NPN","PNP")
            is_pin = comp.type in PIN_TYPES
            rad = math.radians(comp.rot)
            cr, sr = math.cos(rad), math.sin(rad)

            def Tp(x, y, _cr=cr, _sr=sr, _ox=ox, _oy=oy):
                return _ox + x*_cr - y*_sr, _oy + x*_sr + y*_cr

            if is_pin:
                # Pin value (net name) is drawn inside the flag by the symbol.
                # Draw the net name centered on the symbol body, and the
                # reference label (P1, P2...) just below in small text.
                f_pin = ("Helvetica", max(7, GS//8), "bold")
                f_plbl = ("Helvetica", max(5, GS//12))
                # Net name centered on symbol
                cv.create_text(ox, oy, text=comp.value,
                    fill=PIN_COLOR if not sel else LBL_SEL,
                    font=f_pin, anchor="center")
                # Reference label below
                cv.create_text(ox, oy + GS*0.60, text=comp.label,
                    fill=lc, font=f_plbl, anchor="center")
            else:
                lx,ly = (GS*0.70,-GS*0.62) if is_dev else (0,-GS*0.90)
                vx,vy = (GS*0.70,-GS*0.42) if is_dev else (0, GS*0.90)
                lx0,ly0 = Tp(lx,ly)
                vx0,vy0 = Tp(vx,vy)
                cv.create_text(lx0,ly0, text=comp.label,
                    fill=lc, font=f_lbl, anchor="center")
                if comp.value:
                    cv.create_text(vx0,vy0, text=comp.value,
                        fill=vc, font=f_val, anchor="center")

        # Cursor crosshair + mouse-mode hover box — editing aids only,
        # hidden in documentation mode so the export is just the circuit
        if not doc_mode:
            cx_, cy_ = self.cursor[0]*GS, self.cursor[1]*GS
            arm = min(GS*.45, 28)
            cv.create_line(cx_-arm,cy_,cx_+arm,cy_, fill=CURSOR_C,width=1.5)
            cv.create_line(cx_,cy_-arm,cx_,cy_+arm, fill=CURSOR_C,width=1.5)
            dot = max(2.5,GS/22)
            cv.create_oval(cx_-dot,cy_-dot,cx_+dot,cy_+dot,
                           fill=CURSOR_C, outline="")

            if self.mode == "MOUSE":
                cv.create_rectangle(
                    self.cursor[0]*GS+1,self.cursor[1]*GS+1,
                    self.cursor[0]*GS+GS-1,self.cursor[1]*GS+GS-1,
                    outline="#38bdf8",width=0.6,dash=(3,4))

        # Topbar
        self.lbl_coord.config(text=f"({self.cursor[0]},{self.cursor[1]})")
        self.lbl_zoom.config(text=f"{self._zoom_pct()}%")
        c = self._at_cursor()
        flip_tag = "  ⟺" if (c and c.flip) else ""
        self.lbl_info.config(
            text=f"· {c.label}  {c.value}{flip_tag}" if c else "")
        bg_,fg_ = MODE_COLS.get(self.mode,("#0d1117","#c9d1d9"))
        self.lbl_mode.config(text=self.mode, bg=bg_, fg=fg_)

        pil_note = "" if _PILLOW else "  [pip install pillow for PNG]"
        self._status(
            f"{len(self.comps)} comp · {len(self.wires)} wire · "
            f"{len(self.wlbls)} net label  │  "
            "arrows=move · R/C/L/V/I/G · W=wire · T=net label · "
            f"Spc=rot · F=flip · E=edit · :=cmd (in/out/vdd/...) · +/-=zoom{pil_note}")


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    Editor(root)
    root.mainloop()
