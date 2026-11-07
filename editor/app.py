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
  Ctrl+A       Select all elements
  Shift+Click  Toggle selection of multiple items
  Drag box     Marquee-select multiple elements
  Escape       Clear selection / cancel wire
  Ctrl+Z / u   Undo
  Ctrl+Y / U   Redo
  Ctrl+C       Copy selected items or item at cursor
  Ctrl+V       Paste copied items
  Ctrl+X       Cut selected items or item at cursor
  shift + ":"  Open command dialog

COMMAND DIALOG (:)
  all / deselect       Select all / Deselect all elements
  undo / redo          Undo / Redo last schematic change
  copy / paste / cut   Copy / Paste / Cut component(s) or net label(s)
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
import math, csv, os, sys, json, tempfile, copy

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
                               parse_model_file, parse_model_file_corners, LEVEL_LABELS, _PINS
    _HAS_NETLIST = True
except ImportError:
    try:
        from netlist import generate as generate_netlist, ModelConfig, \
                            parse_model_file, parse_model_file_corners, LEVEL_LABELS, _PINS
        _HAS_NETLIST = True
    except ImportError:
        _HAS_NETLIST = False
        _PINS = {}
        class ModelConfig:           # type: ignore
            def __init__(self, **kw):
                self.pdk_name = kw.get("pdk_name", "")
                self.mode = kw.get("mode", "inline")
                self.level = kw.get("level", 1)
                self.file_path = kw.get("file_path", "")
                self.corner = kw.get("corner", "tt")
                self.wl_mode = kw.get("wl_mode", "min")
                self.device_models = {}
            def apply_pdk(self, pdk_name, corner=None):
                self.pdk_name = pdk_name
                if corner: self.corner = corner
            def to_dict(self): return {}
            @classmethod
            def from_dict(cls, d): return cls()
            def model_name(self, dt): return f"{dt}_GENERIC"
            def default_wl(self, dt): return ("180n","180n")
            def min_wl(self, dt): return ("180n","180n")
        def parse_model_file(p): return {"NMOS":[],"PMOS":[],"NPN":[],"PNP":[]}
        def parse_model_file_corners(p): return []
        LEVEL_LABELS = {1:"Level 1",2:"Level 2",3:"Level 3",
                        "BSIM3":"BSIM3","BSIM4":"BSIM4"}

try:
    from editor.pdk import (
        detect_installed_pdks, resolve_pdk, format_pdk_dim, PDK_SPECS
    )
    _HAS_PDK = True
except ImportError:
    try:
        from pdk import (
            detect_installed_pdks, resolve_pdk, format_pdk_dim, PDK_SPECS
        )
        _HAS_PDK = True
    except ImportError:
        _HAS_PDK = False
        detect_installed_pdks = lambda: {}
        resolve_pdk = lambda k: None
        format_pdk_dim = lambda v, p: v
        PDK_SPECS = {}

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
BG             = "#12131a"   # Deep matte charcoal canvas background
GRID_DOT       = "#252836"   # Crisp, subtle grid dots
WIRE_C         = "#38bdf8"   # Sky cyan — modern high-visibility schematic wiring
WIRE_PRV       = "#f59e0b"   # Amber for in-progress wire
CURSOR_C       = "#60a5fa"   # Accent blue crosshair
PANEL_BG       = "#181924"   # Sleek dark slate panel background
PANEL_ALT      = "#1e202e"   # Panel section / header background
BORDER         = "#282a3a"   # Crisp modern border
BTN_BG         = "#232535"   # Uniform sleek button background
BTN_FG         = "#cbd5e1"   # Clean readable light slate text
BTN_ACTIVE_BG  = "#2e3146"   # Button hover/pressed background
BTN_ACTIVE_FG  = "#ffffff"   # Button hover/pressed foreground
BTN_PRIMARY_BG = "#2563eb"   # Primary action button background (blue)
BTN_PRIMARY_FG = "#ffffff"   # Primary action button foreground
BTN_PRIMARY_ACT= "#1d4ed8"   # Primary action button active
BTN_RUN_BG     = "#166534"   # Run button background (emerald)
BTN_RUN_FG     = "#ffffff"   # Run button foreground
BTN_RUN_ACT    = "#15803d"   # Run button active
ENTRY_BG       = "#12131a"   # Input entry background
ENTRY_FG       = "#f1f5f9"   # Input entry foreground
SEL_RECT       = "#1e293b"   # Selection box background
SEL_OUT        = "#38bdf8"   # Selection outline
LBL_NORMAL     = "#f1f5f9"   # Component reference label (M1, R1, etc.)
LBL_SEL        = "#38bdf8"   # Selected label
VAL_NORMAL     = "#94a3b8"   # Component value (W/L=..., 1k)
VAL_SEL        = "#bae6fd"   # Selected value
FLIP_DOT       = "#ec4899"   # Flipped component indicator
PIN_COLOR      = "#f59e0b"   # Port flag text color

MODE_COLS = {
    "NORMAL": ("#232535", "#94a3b8"),
    "WIRE":   ("#14532d", "#4ade80"),
    "MOUSE":  ("#1e3a5f", "#38bdf8"),
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

# ── Command Palette Catalog (command template, aliases, description) ─────────
COMMAND_CATALOG = [
    ("resistor [val]",                  ["r", "res", "resistor"],           "Place resistor (e.g. :r 10k)"),
    ("capacitor [val]",                 ["c", "cap", "capacitor"],          "Place capacitor (e.g. :c 100p)"),
    ("inductor [val]",                  ["l", "ind", "inductor"],           "Place inductor (e.g. :l 10u)"),
    ("vsource [val]",                   ["v", "vsrc"],                      "Place voltage source (e.g. :v 5V)"),
    ("isource [val]",                   ["i", "isrc"],                      "Place current source (e.g. :i 1m)"),
    ("ground",                          ["g", "gnd", "ground"],             "Place ground (:gnd)"),
    ("nmos [w|min|def] [l]",            ["nmos", "m", "mos"],               "Place NMOS (:nmos, :nmos min, :nmos 10u 0.18u)"),
    ("pmos [w|min|def] [l]",            ["pmos"],                           "Place PMOS (:pmos, :pmos min, :pmos 20u 0.18u)"),
    ("npn [model]",                     ["npn", "bjt"],                     "Place NPN BJT (e.g. :npn 2N2222)"),
    ("pnp [model]",                     ["pnp"],                            "Place PNP BJT (e.g. :pnp 2N2907)"),
    ("in [name]",                       ["in"],                             "Place input pin (e.g. :in VIN)"),
    ("out [name]",                      ["out"],                            "Place output pin (e.g. :out VOUT)"),
    ("inout [name]",                    ["inout"],                          "Place bidir pin (e.g. :inout CLK)"),
    ("vdd [name]",                      ["vdd"],                            "Place VDD power pin (e.g. :vdd VDD)"),
    ("vss [name]",                      ["vss"],                            "Place VSS power pin (e.g. :vss VSS)"),
    ("pin [name] [type]",               ["pin"],                            "Place pin (:pin VIN in)"),
    ("wire",                            ["w", "wire"],                      "Start routing wire from cursor (:w)"),
    ("label <name>",                    ["lbl", "label", "t", "net"],       "Place net label at cursor (:lbl VIN)"),
    ("undo",                            ["u", "undo"],                      "Undo last action (:u)"),
    ("redo",                            ["U", "redo"],                      "Redo last undone action (:U)"),
    ("copy",                            ["copy", "cp"],                     "Copy selection to clipboard (:cp)"),
    ("cut",                             ["cut", "x"],                       "Cut selection to clipboard"),
    ("paste",                           ["paste", "p"],                     "Paste from clipboard (:paste)"),
    ("delete",                          ["del", "delete", "rm", "d"],       "Delete selected components/wires"),
    ("rotate [deg]",                    ["rot", "rotate", "r90"],           "Rotate selection 90° or [deg] (:rot 90)"),
    ("flip",                            ["flip", "fl"],                     "Flip / mirror selection horizontally"),
    ("all",                             ["all", "selectall", "sa", "sel"],  "Select all components and wires"),
    ("deselect",                        ["deselect", "none", "unselect", "desel"], "Clear selection"),
    ("pdk [name] [corner]",             ["pdk", "pdks"],                    "Switch PDK (:pdk sky130 tt | gf180 | ihp | none)"),
    ("corner <corner>",                 ["corner"],                         "Switch active corner (tt/ss/ff/sf/fs)"),
    ("wl [default|min|apply]",          ["wl", "wlmode", "sizing"],         "Set transistor W/L sizing mode (:wl min, :wl apply)"),
    ("sim",                             ["sim", "simulate", "analysis"],    "Open simulation settings dialog"),
    ("run",                             ["run"],                            "Run NGspice simulation"),
    ("op",                              ["op"],                             "Enable DC Operating Point simulation (.op)"),
    ("tran [tstop] [tstep]",            ["tran"],                           "Configure Transient simulation (:tran 10u 1n)"),
    ("ac [dec] [pts] [fstart] [fstop]", ["ac"],                             "Configure AC sweep simulation"),
    ("dc [src] [start] [stop] [step]",  ["dc"],                             "Configure DC sweep simulation"),
    ("noise [out] [src]",               ["noise"],                          "Configure Noise simulation"),
    ("tf [out] [src]",                  ["tf"],                             "Configure Transfer Function simulation (:tf V(out) V1)"),
    ("pz [in+] [in-] [out+] [out-]",    ["pz"],                             "Configure Pole-Zero simulation"),
    ("sens [out]",                      ["sens"],                           "Configure Sensitivity simulation (:sens V(out))"),
    ("disto [scale] [pts] [fstart] [fstop]", ["disto"],                     "Configure Distortion simulation"),
    ("nosim <analysis>",                ["nosim", "unsim", "disablesim"],   "Disable an analysis (:nosim tran)"),
    ("netlist [path]",                  ["netlist", "nl"],                  "Export or view NGspice netlist"),
    ("raw",                             ["raw", "showraw"],                 "Show raw simulation results file"),
    ("models",                          ["models"],                         "Open Model Manager dialog"),
    ("save [path]",                     ["save"],                           "Save schematic to JSON (:save circuit.json)"),
    ("load [path]",                     ["load", "open"],                   "Open schematic from JSON (:load circuit.json)"),
    ("export <png|svg>",                ["export", "savepng", "savesvg"],   "Export raster PNG or vector SVG"),
    ("doc [path]",                      ["doc", "docimg", "savedoc"],       "Save publication-quality doc image"),
    ("zoom [pct|in|out|fit]",           ["zoom", "z"],                      "Set zoom level (:zoom 150, :z +)"),
    ("goto <x> <y>",                    ["goto", "move", "pos"],            "Jump cursor to grid position (:goto 10 15)"),
    ("mouse",                           ["mouse", "m"],                     "Toggle mouse crosshair cursor"),
    ("clear",                           ["clear", "cls", "clr"],            "Clear schematic canvas"),
    ("help [topic]",                    ["help", "?"],                      "Show command help and hotkeys"),
    ("quit",                            ["quit", "exit", "q"],              "Quit Vischem"),
]

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
    "OP": {
        "label": "DC Operating Point  (.op)",
        "params": [],
        "spice": lambda p: ".op",
        "desc":  "Finds the DC quiescent bias point (voltages & currents). No parameters needed.",
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
        "desc":  "Frequency-domain analysis (Bode magnitude and phase plots).",
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
        "desc":  "Sweeps an independent voltage/current source over a range.",
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
        "desc":  "Noise spectral density analysis (input/output referred noise).",
    },
    "TF": {
        "label": "Transfer Function  (.tf)",
        "params": [
            ("Output variable",        "V(out)"),
            ("Input source",           "V1"),
        ],
        "spice": lambda p: f".tf {p[0]} {p[1]}",
        "desc":  "Small-signal DC gain, input resistance, and output resistance.",
    },
    "PZ": {
        "label": "Pole-Zero  (.pz)",
        "params": [
            ("Input node +",           "in"),
            ("Input node -",           "0"),
            ("Output node +",          "out"),
            ("Output node -",          "0"),
            ("Transfer (vol/cur)",     "vol"),
            ("Analysis (pz/pol/zer)",  "pz"),
        ],
        "spice": lambda p: f".pz {p[0]} {p[1]} {p[2]} {p[3]} {p[4]} {p[5]}",
        "desc":  "Finds the poles and zeros of small-signal transfer function.",
    },
    "SENS": {
        "label": "Sensitivity  (.sens)",
        "params": [
            ("Output variable",        "V(out)"),
        ],
        "spice": lambda p: f".sens {p[0]}",
        "desc":  "DC small-signal sensitivity of output to all parameters.",
    },
    "DISTO": {
        "label": "Distortion  (.disto)",
        "params": [
            ("Scale  (dec/lin/oct)",   "dec"),
            ("Points per decade",      "10"),
            ("Start freq (Hz)",        "1k"),
            ("Stop freq (Hz)",         "100Meg"),
            ("2nd freq frac (skw2)",   "0.9"),
        ],
        "spice": lambda p: f".disto {p[0]} {p[1]} {p[2]} {p[3]} {p[4]}",
        "desc":  "Small-signal harmonic and intermodulation distortion.",
    },
}

class SimConfig:
    """Stores simulation analyses and parameters with multi-analysis support."""
    def __init__(self):
        self.analysis = "TRAN"        # primary / focused analysis key
        self.enabled_analyses: list[str] = ["TRAN"]  # list of enabled analyses
        self.params: dict = {         # param values per analysis
            k: [p[1] for p in v["params"]]
            for k, v in ANALYSES.items()
        }

    def is_enabled(self, key: str) -> bool:
        return key in self.enabled_analyses

    def set_enabled(self, key: str, enabled: bool):
        if enabled:
            if key not in self.enabled_analyses and key in ANALYSES:
                self.enabled_analyses.append(key)
        else:
            if key in self.enabled_analyses:
                self.enabled_analyses.remove(key)
        if self.enabled_analyses:
            self.analysis = self.enabled_analyses[0]

    def active_analyses(self) -> list[str]:
        return [k for k in self.enabled_analyses if k in ANALYSES]

    def spice_lines(self) -> list[str]:
        lines = []
        for k in self.active_analyses():
            try:
                line = ANALYSES[k]["spice"](self.params[k])
                lines.append(line)
            except Exception:
                pass
        return lines

    def spice_line(self) -> str:
        lines = self.spice_lines()
        if lines:
            return "  ·  ".join(lines)
        if self.analysis in ANALYSES:
            try:
                return ANALYSES[self.analysis]["spice"](self.params.get(self.analysis, []))
            except Exception:
                pass
        return ".op"

    @property
    def analysis_type(self) -> str:
        return self.analysis

    @analysis_type.setter
    def analysis_type(self, val: str):
        uval = val.upper()
        self.analysis = uval
        if uval in ANALYSES and uval not in self.enabled_analyses:
            self.enabled_analyses.append(uval)

    @property
    def tstep(self) -> str:
        return self.params.get("TRAN", ["1n", "1u", "0"])[0]

    @tstep.setter
    def tstep(self, val: str):
        if "TRAN" in self.params:
            self.params["TRAN"][0] = val

    @property
    def tstop(self) -> str:
        return self.params.get("TRAN", ["1n", "1u", "0"])[1]

    @tstop.setter
    def tstop(self, val: str):
        if "TRAN" in self.params:
            self.params["TRAN"][1] = val

    @property
    def ac_variation(self) -> str:
        return self.params.get("AC", ["dec", "100", "1", "10G"])[0]

    @ac_variation.setter
    def ac_variation(self, val: str):
        if "AC" in self.params:
            self.params["AC"][0] = val

    @property
    def ac_points(self) -> str:
        return self.params.get("AC", ["dec", "100", "1", "10G"])[1]

    @ac_points.setter
    def ac_points(self, val: str):
        if "AC" in self.params:
            self.params["AC"][1] = val

    @property
    def fstart(self) -> str:
        return self.params.get("AC", ["dec", "100", "1", "10G"])[2]

    @fstart.setter
    def fstart(self, val: str):
        if "AC" in self.params:
            self.params["AC"][2] = val

    @property
    def fstop(self) -> str:
        return self.params.get("AC", ["dec", "100", "1", "10G"])[3]

    @fstop.setter
    def fstop(self, val: str):
        if "AC" in self.params:
            self.params["AC"][3] = val

    @property
    def dc_source(self) -> str:
        return self.params.get("DC", ["V1", "0", "5", "0.01"])[0]

    @dc_source.setter
    def dc_source(self, val: str):
        if "DC" in self.params:
            self.params["DC"][0] = val

    @property
    def dc_start(self) -> str:
        return self.params.get("DC", ["V1", "0", "5", "0.01"])[1]

    @dc_start.setter
    def dc_start(self, val: str):
        if "DC" in self.params:
            self.params["DC"][1] = val

    @property
    def dc_stop(self) -> str:
        return self.params.get("DC", ["V1", "0", "5", "0.01"])[2]

    @dc_stop.setter
    def dc_stop(self, val: str):
        if "DC" in self.params:
            self.params["DC"][2] = val

    @property
    def dc_step(self) -> str:
        return self.params.get("DC", ["V1", "0", "5", "0.01"])[3]

    @dc_step.setter
    def dc_step(self, val: str):
        if "DC" in self.params:
            self.params["DC"][3] = val

    def to_dict(self):
        return {
            "analysis": self.analysis,
            "enabled_analyses": list(self.enabled_analyses),
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, d):
        cfg = cls()
        cfg.analysis = d.get("analysis", "TRAN")
        if "enabled_analyses" in d:
            cfg.enabled_analyses = [k for k in d["enabled_analyses"] if k in ANALYSES]
            if not cfg.enabled_analyses and cfg.analysis in ANALYSES:
                cfg.enabled_analyses = [cfg.analysis]
        else:
            cfg.enabled_analyses = [cfg.analysis] if cfg.analysis in ANALYSES else ["TRAN"]
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
        self.fingers    : int = 1     # parallel fingers / multiplier
        self.bulk_net   : str = "0"   # bulk/body connection
        # V-source structured waveform (set via V Properties dialog, not free text)
        self.vsrc_type    : str  = "DC" # active tab: DC|AC|SIN|PULSE|EXP|PWL|SFFM
        self.vsrc_params  : dict = {}   # {type_key: [param_str, ...]}
        self.vsrc_dc      : str  = "0"  # DC bias alongside transient waveforms
        self.vsrc_ac      : str  = "0"  # AC magnitude alongside transient waveforms
        self.vsrc_ac_phase: str  = "0"  # AC phase alongside transient waveforms

    def update_mos_value(self):
        """Keep self.value in sync with mos_w, mos_l, and fingers for canvas display."""
        if self.type not in ("NMOS", "PMOS"):
            return
        w = self.mos_w
        l = self.mos_l
        if w and l:
            val = f"W/L={w}/{l}"
        elif w:
            val = f"W={w}"
        elif l:
            val = f"L={l}"
        else:
            val = self.value or DEFAULTS.get(self.type, "")
        fingers = getattr(self, "fingers", 1)
        if fingers > 1:
            val += f" M={fingers}"
        self.value = val

    def to_dict(self) -> dict:
        d = {
            "type":  self.type,  "label": self.label, "value": self.value,
            "gx":    self.gx,    "gy":    self.gy,
            "rot":   self.rot,   "flip":  self.flip,
        }
        if self.model_name: d["model_name"] = self.model_name
        if self.mos_w:      d["mos_w"]      = self.mos_w
        if self.mos_l:      d["mos_l"]      = self.mos_l
        if getattr(self, "fingers", 1) > 1:
            d["fingers"] = self.fingers
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
        c.fingers      = d.get("fingers",      1)
        c.bulk_net     = d.get("bulk_net",     "0")
        if c.type in ("NMOS", "PMOS") and (c.mos_w or c.mos_l):
            c.update_mos_value()
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

        # Mouse interaction & drag-and-drop state
        self._drag_target   = None
        self._drag_type     = None   # "COMP" | "WLBL"
        self._drag_start_gx = 0
        self._drag_start_gy = 0
        self._drag_press_x  = 0
        self._drag_press_y  = 0
        self._drag_moved    = False
        self._drag_undo_snapshot: dict | None = None

        # History (Undo / Redo) and Clipboard
        self._undo_stack : list[dict] = []
        self._redo_stack : list[dict] = []
        self._clipboard  : dict | None = None
        self._cmd_history: list[str] = []
        self._cmd_dlg    : tk.Toplevel | None = None

        # Multi-element selection
        self.selected_comps : set[Component]  = set()
        self.selected_wires : set[Wire]       = set()
        self.selected_wlbls : set[WireLabel]  = set()
        self._box_sel_active: bool            = False
        self._box_sel_x0    : float           = 0.0
        self._box_sel_y0    : float           = 0.0
        self._box_sel_x1    : float           = 0.0
        self._box_sel_y1    : float           = 0.0

        self.GS = GS_DEFAULT
        self._update_canvas_size()

        self.wlbls      : list = []
        self.sim_config  = SimConfig()
        self.model_config = ModelConfig()       # project-level model settings
        self._model_names_cache: dict = {}      # parsed model names from file
        self._pdk_cache = detect_installed_pdks()
        if getattr(self.model_config, "pdk_name", ""):
            resolved = resolve_pdk(self.model_config.pdk_name)
            if resolved:
                self._model_names_cache = dict(resolved.models)
        self._netlist_visible = False
        self._netlist_win     : tk.Toplevel | None = None
        self._last_netlist_sig: tuple | None = None
        self.netlist_frame    = None   # backward-compatibility reference
        self.nl_text          = None
        self.nl_warn          = None
        self.nl_nets          = None
        self.nl_status        = None
        self.nl_pdk_chip      = None
        self._last_result     = None
        self._last_dir        = os.path.expanduser("~")
        self._current_file    : str | None = None   # path of last saved/loaded .json
        self._ngspice_exe     : str | None = None   # located once at startup
        self._sim_log_visible : bool = False        # simulation log panel state
        self._pan_start       : tuple[int, int] | None = None  # middle-click pan origin

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
            bg=PANEL_BG, fg="#64748b", font=("Courier", 9))
        self.lbl_coord.pack(side=tk.LEFT)

        self.lbl_info = tk.Label(top, text="",
            bg=PANEL_BG, fg="#cbd5e1", font=("Courier", 9, "bold"))
        self.lbl_info.pack(side=tk.LEFT, padx=8)

        zf = tk.Frame(top, bg=PANEL_BG); zf.pack(side=tk.LEFT, padx=6)
        tk.Button(zf, text="−", command=lambda: self._zoom(-8),
            bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
            font=("Courier", 10, "bold"), relief="flat",
            width=2, cursor="hand2").pack(side=tk.LEFT)
        self.lbl_zoom = tk.Label(zf, text="100%", width=5,
            bg=PANEL_BG, fg="#64748b", font=("Courier", 8))
        self.lbl_zoom.pack(side=tk.LEFT, padx=2)
        tk.Button(zf, text="+", command=lambda: self._zoom(+8),
            bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
            font=("Courier", 10, "bold"), relief="flat",
            width=2, cursor="hand2").pack(side=tk.LEFT)

        # Edit operations: Undo / Redo / Copy / Paste
        ef = tk.Frame(top, bg=PANEL_BG); ef.pack(side=tk.LEFT, padx=(8, 4))
        self.btn_undo = tk.Button(ef, text="Undo", command=self._undo,
            bg=BTN_BG, fg="#4b5563", activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
            font=("Courier", 8, "bold"), relief="flat", state=tk.DISABLED,
            cursor="hand2", padx=6)
        self.btn_undo.pack(side=tk.LEFT, padx=1)
        self.btn_redo = tk.Button(ef, text="Redo", command=self._redo,
            bg=BTN_BG, fg="#4b5563", activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
            font=("Courier", 8, "bold"), relief="flat", state=tk.DISABLED,
            cursor="hand2", padx=6)
        self.btn_redo.pack(side=tk.LEFT, padx=1)
        self.btn_copy = tk.Button(ef, text="Copy", command=self._copy,
            bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
            font=("Courier", 8, "bold"), relief="flat",
            cursor="hand2", padx=6)
        self.btn_copy.pack(side=tk.LEFT, padx=(4, 1))
        self.btn_paste = tk.Button(ef, text="Paste", command=self._paste,
            bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
            font=("Courier", 8, "bold"), relief="flat",
            cursor="hand2", padx=6)
        self.btn_paste.pack(side=tk.LEFT, padx=1)
        self.btn_cmd = tk.Button(ef, text="Cmd", command=self._open_cmd,
            bg=BTN_BG, fg="#38bdf8", activebackground=BTN_ACTIVE_BG, activeforeground="#ffffff",
            font=("Courier", 8, "bold"), relief="flat",
            cursor="hand2", padx=6)
        self.btn_cmd.pack(side=tk.LEFT, padx=(4, 1))

        tk.Button(top, text="Clear", command=self._clear,
            bg=BTN_BG, fg="#f87171", activebackground="#3d1e28",
            activeforeground="#fca5a5", relief="flat",
            font=("Courier", 8, "bold"), cursor="hand2", padx=8
        ).pack(side=tk.RIGHT, padx=4)

        self.btn_netlist = tk.Button(top, text="Netlist",
            command=self._toggle_netlist_panel,
            bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG,
            activeforeground=BTN_ACTIVE_FG, relief="flat",
            font=("Courier", 8, "bold"), cursor="hand2", padx=8)
        self.btn_netlist.pack(side=tk.RIGHT, padx=4)

        self.btn_sim = tk.Button(top, text="Simulation",
            command=self._open_sim_dialog,
            bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG,
            activeforeground=BTN_ACTIVE_FG, relief="flat",
            font=("Courier", 8, "bold"), cursor="hand2", padx=8)
        self.btn_sim.pack(side=tk.RIGHT, padx=4)

        self.btn_run = tk.Button(top, text="Run",
            command=self._run_simulation,
            bg=BTN_RUN_BG, fg=BTN_RUN_FG, activebackground=BTN_RUN_ACT,
            activeforeground="#ffffff", relief="flat",
            font=("Courier", 9, "bold"), cursor="hand2", padx=10)
        self.btn_run.pack(side=tk.RIGHT, padx=4)

        self.btn_doc = tk.Button(top, text="Doc Image",
            command=self._dialog_save_doc_image,
            bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG,
            activeforeground=BTN_ACTIVE_FG, relief="flat",
            font=("Courier", 8, "bold"), cursor="hand2", padx=8)
        self.btn_doc.pack(side=tk.RIGHT, padx=4)

        self.btn_models = tk.Button(top, text="Models",
            command=self._open_model_manager,
            bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG,
            activeforeground=BTN_ACTIVE_FG, relief="flat",
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
            cursor="none",
            xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.hbar.config(command=self.cv.xview)
        self.vbar.config(command=self.cv.yview)
        self.cv.focus_set()

        # Note: Netlist viewer is now a dedicated separate Toplevel window (_open_netlist_window)
        self.netlist_frame = None

        # ── Simulation log panel (hidden by default) ───────────────────────────
        self.sim_log_frame = tk.Frame(self.workspace, bg=PANEL_BG, bd=1, relief="solid", highlightthickness=1, highlightbackground=BORDER, width=440)

        slh = tk.Frame(self.sim_log_frame, bg=PANEL_ALT, pady=4)
        slh.pack(fill=tk.X)
        self.lbl_sim_header = tk.Label(slh, text="  Simulation Log",
            bg=PANEL_ALT, fg="#cbd5e1",
            font=("Courier", 9, "bold"))
        self.lbl_sim_header.pack(side=tk.LEFT)
        tk.Button(slh, text="Close",
            command=self._hide_sim_log,
            bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
            relief="flat", font=("Courier", 8), cursor="hand2", padx=6
        ).pack(side=tk.RIGHT, padx=4)
        self.btn_show_raw = tk.Button(slh, text="Show .raw",
            command=self._reveal_raw_file,
            bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
            relief="flat", font=("Courier", 8, "bold"), cursor="hand2", padx=6)
        self.btn_show_raw.pack(side=tk.RIGHT, padx=2)

        # log text area
        sl_tf = tk.Frame(self.sim_log_frame, bg=PANEL_BG)
        sl_tf.pack(fill=tk.BOTH, expand=True)
        sl_vsb = tk.Scrollbar(sl_tf, orient=tk.VERTICAL, bg=PANEL_BG, troughcolor=BORDER)
        sl_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.sim_log_text = tk.Text(sl_tf,
            bg="#12131a", fg="#e2e8f0", font=("Courier", 8),
            insertbackground=CURSOR_C, selectbackground="#1e3a5f",
            relief="flat", bd=0, wrap=tk.WORD, state=tk.DISABLED,
            yscrollcommand=sl_vsb.set)
        self.sim_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sl_vsb.config(command=self.sim_log_text.yview)
        self.sim_log_text.tag_config("ok",      foreground="#4ade80")
        self.sim_log_text.tag_config("err",     foreground="#f87171")
        self.sim_log_text.tag_config("warn",    foreground="#fbbf24")
        self.sim_log_text.tag_config("dim",     foreground="#64748b")
        self.sim_log_text.tag_config("header",  foreground="#38bdf8",
                                                font=("Courier", 9, "bold"))
        self._last_raw_path: str | None = None  # set after each successful run

        self.lbl_status = tk.Label(self.root, text="", anchor="w",
            bg=PANEL_BG, fg="#94a3b8", font=("Courier", 8), padx=10, pady=3)
        self.lbl_status.pack(fill=tk.X, side=tk.BOTTOM)

    # ── Modal dialog (the stable input method from v0.5) ───────────────────────
    def _ask(self, title: str, prompt: str, initial: str = "",
             color: str = "#38bdf8") -> "str | None":
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
                        bg=ENTRY_BG, fg=ENTRY_FG,
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
                  bg=BTN_PRIMARY_BG, fg=BTN_PRIMARY_FG,
                  activebackground=BTN_PRIMARY_ACT, activeforeground="#ffffff",
                  font=("Helvetica", 9, "bold"),
                  relief="flat", padx=16, pady=4,
                  cursor="hand2").pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(bf, text="Cancel", command=_cancel,
                  bg=BTN_BG, fg=BTN_FG,
                  activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
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
        cv.bind("<B1-Motion>",          self._on_drag)
        cv.bind("<ButtonRelease-1>",    self._on_release)
        cv.bind("<Double-Button-1>",    self._on_double_click)
        cv.bind("<Button-3>",           self._on_right_click)
        cv.bind("<Motion>",             self._on_motion)
        # Mouse wheel zoom (all platforms: Windows/macOS <MouseWheel>, Linux <Button-4>/<Button-5>)
        cv.bind("<MouseWheel>",         self._on_mouse_wheel)
        cv.bind("<Button-4>",           lambda e: self._on_wheel_zoom(+1, e))
        cv.bind("<Button-5>",           lambda e: self._on_wheel_zoom(-1, e))
        cv.bind("<Control-MouseWheel>", self._on_mouse_wheel)
        cv.bind("<Control-Button-4>",   lambda e: self._on_wheel_zoom(+1, e))
        cv.bind("<Control-Button-5>",   lambda e: self._on_wheel_zoom(-1, e))

        # Shift + Wheel for horizontal scrolling
        cv.bind("<Shift-MouseWheel>",   self._on_wheel_x)
        cv.bind("<Shift-Button-4>",     lambda e: cv.xview_scroll(-2, "units"))
        cv.bind("<Shift-Button-5>",     lambda e: cv.xview_scroll(+2, "units"))

        # Middle-click drag to pan canvas
        cv.bind("<Button-2>",           self._on_pan_start)
        cv.bind("<B2-Motion>",          self._on_pan_move)
        cv.bind("<ButtonRelease-2>",    self._on_pan_end)
        cv.bind("<Enter>",              self._on_canvas_enter)

        for w in (cv, self.root):
            w.bind("<Control-z>",       lambda e: (self._undo(), "break")[1])
            w.bind("<Control-Z>",       lambda e: (self._redo(), "break")[1])
            w.bind("<Control-y>",       lambda e: (self._redo(), "break")[1])
            w.bind("<Control-Y>",       lambda e: (self._redo(), "break")[1])
            w.bind("<Control-Shift-Z>", lambda e: (self._redo(), "break")[1])
            w.bind("<Control-Shift-z>", lambda e: (self._redo(), "break")[1])
            w.bind("<Control-c>",       lambda e: (self._copy(), "break")[1])
            w.bind("<Control-C>",       lambda e: (self._copy(), "break")[1])
            w.bind("<Control-v>",       lambda e: (self._paste(), "break")[1])
            w.bind("<Control-V>",       lambda e: (self._paste(), "break")[1])
            w.bind("<Control-x>",       lambda e: (self._cut(), "break")[1])
            w.bind("<Control-X>",       lambda e: (self._cut(), "break")[1])
            w.bind("<Control-a>",       lambda e: (self._select_all(), "break")[1])
            w.bind("<Control-A>",       lambda e: (self._select_all(), "break")[1])
            w.bind("<Control-p>",       lambda e: (self._open_cmd(), "break")[1])
            w.bind("<Control-P>",       lambda e: (self._open_cmd(), "break")[1])

    def _on_canvas_enter(self, ev=None):
        try:
            self.cv.config(cursor="none")
        except Exception:
            pass

    # ── Mouse Interaction & Drag-and-Drop Helpers ──────────────────────────────
    def _get_comp_pins(self, comp) -> list[tuple[int, int]]:
        """Return world grid positions (rx, ry) of all pins of comp."""
        pins = _PINS.get(comp.type, [])
        rad = math.radians(comp.rot)
        cr, sr = math.cos(rad), math.sin(rad)
        flip = getattr(comp, "flip", False)
        pts = []
        for dx, dy, _ in pins:
            fdx = -dx if flip else dx
            rx = comp.gx + round(fdx * cr - dy * sr)
            ry = comp.gy + round(fdx * sr + dy * cr)
            pts.append((rx, ry))
        return pts

    def _find_comp_at(self, canvas_x: float, canvas_y: float) -> "Component | None":
        """Find the component closest to (canvas_x, canvas_y), checking body and pins."""
        gx_f = canvas_x / self.GS
        gy_f = canvas_y / self.GS
        best_c = None
        best_dist = 1.35   # hit tolerance in grid steps

        for c in self.comps:
            d = math.hypot(c.gx - gx_f, c.gy - gy_f)
            if d < best_dist:
                best_dist = d
                best_c = c

            for rx, ry in self._get_comp_pins(c):
                d_pin = math.hypot(rx - gx_f, ry - gy_f)
                if d_pin < best_dist:
                    best_dist = d_pin
                    best_c = c

        return best_c

    def _find_wlbl_at(self, canvas_x: float, canvas_y: float) -> "WireLabel | None":
        """Find a wire label at (canvas_x, canvas_y)."""
        gx_f = canvas_x / self.GS
        gy_f = canvas_y / self.GS
        for wl in self.wlbls:
            if math.hypot(wl.gx - gx_f, wl.gy - gy_f) < 0.9:
                return wl
        return None

    def _find_wire_at(self, canvas_x: float, canvas_y: float) -> "Wire | None":
        """Find a wire close to (canvas_x, canvas_y)."""
        best_w = None
        best_d = max(8.0, self.GS * 0.18)
        GS = self.GS
        for w in self.wires:
            x1, y1 = w.x1 * GS, w.y1 * GS
            x2, y2 = w.x2 * GS, w.y2 * GS
            dx, dy = x2 - x1, y2 - y1
            length_sq = dx * dx + dy * dy
            if length_sq == 0:
                d = math.hypot(canvas_x - x1, canvas_y - y1)
            else:
                t = max(0.0, min(1.0, ((canvas_x - x1) * dx + (canvas_y - y1) * dy) / length_sq))
                proj_x = x1 + t * dx
                proj_y = y1 + t * dy
                d = math.hypot(canvas_x - proj_x, canvas_y - proj_y)
            if d < best_d:
                best_d = d
                best_w = w
        return best_w

    def has_selection(self) -> bool:
        return bool(self.selected_comps or self.selected_wires or self.selected_wlbls)

    def _clear_selection(self):
        self.selected_comps.clear()
        self.selected_wires.clear()
        self.selected_wlbls.clear()

    def _select_all(self):
        self.selected_comps = set(self.comps)
        self.selected_wires = set(self.wires)
        self.selected_wlbls = set(self.wlbls)
        n = len(self.comps) + len(self.wires) + len(self.wlbls)
        self._status(f"✓ Selected all {n} items ({len(self.comps)} comps, {len(self.wires)} wires)", "#38bdf8")
        self._render()

    def _on_click(self, ev):
        self.cv.focus_set()
        mx = self.cv.canvasx(ev.x)
        my = self.cv.canvasy(ev.y)
        cx = max(0, min(COLS - 1, int(round(mx / self.GS))))
        cy = max(0, min(ROWS - 1, int(round(my / self.GS))))

        if self.mode == "WIRE":
            self.cursor = [cx, cy]
            self._commit_wire()
            return

        shift_pressed = bool(getattr(ev, "state", 0) & 0x0001)
        ctrl_pressed  = bool(getattr(ev, "state", 0) & 0x0004)
        is_multi_mod  = shift_pressed or ctrl_pressed

        c = self._find_comp_at(mx, my)
        wl = self._find_wlbl_at(mx, my) if not c else None
        w = self._find_wire_at(mx, my) if (not c and not wl) else None

        if c:
            self.cursor = [c.gx, c.gy]
            if is_multi_mod:
                if c in self.selected_comps:
                    self.selected_comps.remove(c)
                else:
                    self.selected_comps.add(c)
            else:
                if c not in self.selected_comps:
                    self._clear_selection()
                    self.selected_comps.add(c)

            self._drag_target = c
            self._drag_type = "COMP"
            self._drag_start_gx = c.gx
            self._drag_start_gy = c.gy
            self._drag_press_x = ev.x
            self._drag_press_y = ev.y
            self._drag_moved = False
            self._drag_undo_snapshot = self._snapshot()
            n_sel = len(self.selected_comps)
            if n_sel > 1:
                self._status(f"Selected {n_sel} components — drag to move together", "#38bdf8")
            else:
                self._status(f"Selected {c.label} ({c.type}) — drag to move, double-click for properties", "#38bdf8")
        elif wl:
            self.cursor = [wl.gx, wl.gy]
            if is_multi_mod:
                if wl in self.selected_wlbls:
                    self.selected_wlbls.remove(wl)
                else:
                    self.selected_wlbls.add(wl)
            else:
                if wl not in self.selected_wlbls:
                    self._clear_selection()
                    self.selected_wlbls.add(wl)

            self._drag_target = wl
            self._drag_type = "WLBL"
            self._drag_start_gx = wl.gx
            self._drag_start_gy = wl.gy
            self._drag_press_x = ev.x
            self._drag_press_y = ev.y
            self._drag_moved = False
            self._drag_undo_snapshot = self._snapshot()
            self._status(f"Selected label '{wl.text}' — drag to move", "#38bdf8")
        elif w:
            self.cursor = [cx, cy]
            if is_multi_mod:
                if w in self.selected_wires:
                    self.selected_wires.remove(w)
                else:
                    self.selected_wires.add(w)
            else:
                if w not in self.selected_wires:
                    self._clear_selection()
                    self.selected_wires.add(w)

            self._drag_target = w
            self._drag_type = "WIRE"
            self._drag_start_gx = cx
            self._drag_start_gy = cy
            self._drag_press_x = ev.x
            self._drag_press_y = ev.y
            self._drag_moved = False
            self._drag_undo_snapshot = self._snapshot()
            n_w = len(self.selected_wires)
            self._status(f"Selected {n_w} wire{'s' if n_w!=1 else ''} — drag to move", "#38bdf8")
        else:
            self.cursor = [cx, cy]
            if not is_multi_mod:
                self._clear_selection()
            self._drag_target = None
            self._drag_type = None
            self._drag_moved = False
            self._drag_undo_snapshot = None
            self._active_status = None
            # Setup rubberband marquee box
            self._box_sel_active = False
            self._box_sel_x0 = mx
            self._box_sel_y0 = my
            self._box_sel_x1 = mx
            self._box_sel_y1 = my

        self._render()

    def _on_drag(self, ev):
        mx = self.cv.canvasx(ev.x)
        my = self.cv.canvasy(ev.y)
        cx = max(0, min(COLS - 1, int(round(mx / self.GS))))
        cy = max(0, min(ROWS - 1, int(round(my / self.GS))))

        if self.mode == "WIRE":
            if [cx, cy] != self.cursor:
                self.cursor = [cx, cy]
                self._render()
            return

        if not self._drag_target:
            if math.hypot(ev.x - self._drag_press_x, ev.y - self._drag_press_y) >= 4:
                self._box_sel_active = True
                self._box_sel_x1 = mx
                self._box_sel_y1 = my
                self.cursor = [cx, cy]
                self._render()
            elif [cx, cy] != self.cursor:
                self.cursor = [cx, cy]
                self._render()
            return

        if not self._drag_moved:
            if math.hypot(ev.x - self._drag_press_x, ev.y - self._drag_press_y) < 4:
                return
            self._drag_moved = True

        new_gx = max(1, min(COLS - 2, int(round(mx / self.GS))))
        new_gy = max(1, min(ROWS - 2, int(round(my / self.GS))))

        target = self._drag_target
        if (new_gx, new_gy) == (target.gx, target.gy):
            return

        # Multi-component group drag
        if self._drag_type == "COMP" and self._drag_target in self.selected_comps and len(self.selected_comps) > 1:
            dx = new_gx - target.gx
            dy = new_gy - target.gy
            if dx == 0 and dy == 0:
                return

            # Check bounds for all selected components
            if any(not (1 <= c.gx + dx <= COLS - 2 and 1 <= c.gy + dy <= ROWS - 2) for c in self.selected_comps):
                return

            # Check collisions with unselected components
            unselected = { (c.gx, c.gy) for c in self.comps if c not in self.selected_comps }
            for c in self.selected_comps:
                if (c.gx + dx, c.gy + dy) in unselected:
                    self._status(f"[!] Target cell ({c.gx+dx}, {c.gy+dy}) occupied", "#f59e0b")
                    return

            # Move all selected components
            for c in self.selected_comps:
                c.gx += dx
                c.gy += dy

            # Move all selected wire labels
            for l in self.selected_wlbls:
                l.gx += dx
                l.gy += dy

            # Move all selected wires
            for w in self.selected_wires:
                w.x1 += dx; w.y1 += dy
                w.x2 += dx; w.y2 += dy

            # Shift+drag stretches connected unselected wires
            shift_pressed = bool(getattr(ev, "state", 0) & 0x0001)
            if shift_pressed:
                old_pins = set()
                for c in self.selected_comps:
                    for px, py in self._get_comp_pins(c):
                        old_pins.add((px - dx, py - dy))
                for w in self.wires:
                    if w not in self.selected_wires:
                        if (w.x1, w.y1) in old_pins:
                            w.x1 += dx; w.y1 += dy
                        if (w.x2, w.y2) in old_pins:
                            w.x2 += dx; w.y2 += dy

            self.cursor = [target.gx, target.gy]
            self._status(f"Moving {len(self.selected_comps)} components → ({target.gx}, {target.gy})", "#a78bfa")
            self._render()
            return

        if self._drag_type == "COMP":
            occ = next((c for c in self.comps if c is not target and c.gx == new_gx and c.gy == new_gy), None)
            if occ:
                self._status(f"[!] Cell ({new_gx}, {new_gy}) occupied by {occ.label}", "#f59e0b")
                return

            dx = new_gx - target.gx
            dy = new_gy - target.gy

            shift_pressed = bool(getattr(ev, "state", 0) & 0x0001)
            if shift_pressed:
                old_pins = set(self._get_comp_pins(target))
                for w in self.wires:
                    if (w.x1, w.y1) in old_pins:
                        w.x1 += dx; w.y1 += dy
                    if (w.x2, w.y2) in old_pins:
                        w.x2 += dx; w.y2 += dy

            target.gx = new_gx
            target.gy = new_gy
            self.cursor = [new_gx, new_gy]
            shift_info = " [+wires]" if shift_pressed else " (hold Shift to stretch wires)"
            self._status(f"Moving {target.label} → ({new_gx}, {new_gy}){shift_info}", "#a78bfa")
            self._render()

        elif self._drag_type == "WLBL":
            target.gx = new_gx
            target.gy = new_gy
            self.cursor = [new_gx, new_gy]
            self._status(f"Moving label '{target.text}' → ({new_gx}, {new_gy})", "#a78bfa")
            self._render()

    def _on_release(self, ev):
        try:
            self.cv.config(cursor="none")
        except Exception:
            pass

        # Complete marquee box selection
        if getattr(self, "_box_sel_active", False):
            self._box_sel_active = False
            mx0, my0 = self._box_sel_x0, self._box_sel_y0
            mx1, my1 = self._box_sel_x1, self._box_sel_y1
            bx0 = min(mx0, mx1)
            bx1 = max(mx0, mx1)
            by0 = min(my0, my1)
            by1 = max(my0, my1)

            shift_pressed = bool(getattr(ev, "state", 0) & 0x0001)
            ctrl_pressed  = bool(getattr(ev, "state", 0) & 0x0004)
            if not (shift_pressed or ctrl_pressed):
                self._clear_selection()

            GS = self.GS
            # Select components in or touching box
            for c in self.comps:
                cx, cy = c.gx * GS, c.gy * GS
                if bx0 <= cx + GS*0.75 and bx1 >= cx - GS*0.75 and by0 <= cy + GS*0.75 and by1 >= cy - GS*0.75:
                    self.selected_comps.add(c)

            # Select wire labels in box
            for wl in self.wlbls:
                wx, wy = wl.gx * GS, wl.gy * GS
                if bx0 <= wx + GS*0.5 and bx1 >= wx - GS*0.5 and by0 <= wy + GS*0.5 and by1 >= wy - GS*0.5:
                    self.selected_wlbls.add(wl)

            # Select wires in or crossing box
            for w in self.wires:
                wx1, wy1 = w.x1 * GS, w.y1 * GS
                wx2, wy2 = w.x2 * GS, w.y2 * GS
                if bx0 <= max(wx1, wx2) and bx1 >= min(wx1, wx2) and by0 <= max(wy1, wy2) and by1 >= min(wy1, wy2):
                    self.selected_wires.add(w)

            n_c = len(self.selected_comps)
            n_w = len(self.selected_wires)
            n_l = len(self.selected_wlbls)
            parts = []
            if n_c: parts.append(f"{n_c} comp{'s' if n_c!=1 else ''}")
            if n_w: parts.append(f"{n_w} wire{'s' if n_w!=1 else ''}")
            if n_l: parts.append(f"{n_l} label{'s' if n_l!=1 else ''}")
            if parts:
                self._status(f"✓ Selected {', '.join(parts)}", "#38bdf8")
            else:
                self._status("No items selected", "#94a3b8")
            self._render()
            self._drag_target = None
            self._drag_type = None
            self._drag_moved = False
            self._drag_undo_snapshot = None
            return

        if self._drag_target and self._drag_moved:
            target = self._drag_target
            name = getattr(target, "label", getattr(target, "text", "Item"))
            n_sel = len(self.selected_comps)
            if (target.gx, target.gy) != (self._drag_start_gx, self._drag_start_gy) or n_sel > 1:
                if getattr(self, "_drag_undo_snapshot", None):
                    self._undo_stack.append(self._drag_undo_snapshot)
                    if len(self._undo_stack) > 60:
                        self._undo_stack.pop(0)
                    self._redo_stack.clear()
                    self._update_undo_redo_ui()
                    self._drag_undo_snapshot = None
                if n_sel > 1:
                    self._status(f"✓ Moved {n_sel} components", "#4ade80")
                else:
                    self._status(f"✓ Moved {name} to ({target.gx}, {target.gy})", "#4ade80")
            else:
                self._status(f"· {name} at ({target.gx}, {target.gy})", "#94a3b8")
            self._render()

        self._drag_target = None
        self._drag_type   = None
        self._drag_moved  = False
        self._drag_undo_snapshot = None

    def _on_double_click(self, ev):
        """Double clicking on an instance opens its Properties dialog."""
        mx = self.cv.canvasx(ev.x)
        my = self.cv.canvasy(ev.y)
        c = self._find_comp_at(mx, my)
        if c:
            self.cursor = [c.gx, c.gy]
            self._render()
            self._start_edit()

    def _on_right_click(self, ev):
        """Right click: in WIRE mode cancels wire; on a component rotates it 90°."""
        if self.mode == "WIRE":
            self.mode = "NORMAL"
            self.ws = None
            self._status("Wire cancelled", "#94a3b8")
            self._render()
            return
        mx = self.cv.canvasx(ev.x)
        my = self.cv.canvasy(ev.y)
        c = self._find_comp_at(mx, my)
        if c:
            self.cursor = [c.gx, c.gy]
            self._rotate()
            self._status(f"Rotated {c.label} to {c.rot}°", "#38bdf8")

    def _on_motion(self, ev):
        """Update cursor position, appearance on hover, and wire guide in WIRE mode."""
        mx = self.cv.canvasx(ev.x)
        my = self.cv.canvasy(ev.y)
        cx = max(0, min(COLS - 1, int(round(mx / self.GS))))
        cy = max(0, min(ROWS - 1, int(round(my / self.GS))))

        # If currently dragging an item, drag handler manages motion
        if self._drag_moved:
            return

        # Ensure OS mouse cursor stays hidden so only the EDA grid cursor is visible
        try:
            self.cv.config(cursor="none")
        except Exception:
            pass

        # Move the grid cursor with the mouse whenever it enters a new cell
        if [cx, cy] != self.cursor:
            self.cursor = [cx, cy]
            self._render()

    def _on_wheel_zoom(self, direction: int, ev=None):
        """Zoom in (direction > 0) or out (direction < 0) centered at mouse pointer."""
        delta = 6 if direction > 0 else -6
        self._zoom(delta, ev)

    def _on_mouse_wheel(self, ev):
        """Handle <MouseWheel> (Windows / macOS / modern X11)."""
        delta = getattr(ev, "delta", 0)
        if delta > 0:
            self._on_wheel_zoom(+1, ev)
        elif delta < 0:
            self._on_wheel_zoom(-1, ev)

    def _on_wheel_y(self, ev):
        """Vertical wheel zoom alias."""
        self._on_mouse_wheel(ev)

    def _on_wheel_x(self, ev):
        """Shift + Wheel horizontal scrolling."""
        delta = getattr(ev, "delta", 0)
        units = int(-1 * delta / 120) if abs(delta) >= 120 else (-2 if delta > 0 else 2)
        self.cv.xview_scroll(units, "units")

    def _on_ctrl_wheel(self, ev):
        """Ctrl + Wheel zoom alias."""
        self._on_mouse_wheel(ev)

    def _on_pan_start(self, ev):
        """Middle-click press to begin canvas panning."""
        self._pan_start = (ev.x, ev.y)

    def _on_pan_move(self, ev):
        """Middle-click drag to pan canvas smoothly."""
        if getattr(self, "_pan_start", None) is None:
            return
        dx = ev.x - self._pan_start[0]
        dy = ev.y - self._pan_start[1]
        self._pan_start = (ev.x, ev.y)
        if dx == 0 and dy == 0:
            return
        left_px = self.cv.canvasx(0) - dx
        top_px  = self.cv.canvasy(0) - dy
        fx = max(0.0, min(1.0, left_px / max(1, self.CW)))
        fy = max(0.0, min(1.0, top_px  / max(1, self.CH)))
        self.cv.xview_moveto(fx)
        self.cv.yview_moveto(fy)

    def _on_pan_end(self, ev):
        """Middle-click release to end canvas panning."""
        self._pan_start = None

    def _on_key(self, ev):
        k  = ev.keysym.lower()
        ku = (ev.char or "").upper()
        ctrl = bool(getattr(ev, "state", 0) & 4)

        # Global clipboard & history shortcuts with Ctrl modifier
        if ctrl:
            if k == "a":
                self._select_all()
                return "break"
            if k == "z":
                if getattr(ev, "state", 0) & 1:  # Shift + Ctrl + Z
                    self._redo()
                else:
                    self._undo()
                return "break"
            if k == "y":
                self._redo()
                return "break"
            if k == "c":
                self._copy()
                return "break"
            if k == "v":
                self._paste()
                return "break"
            if k == "x":
                self._cut()
                return "break"

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
            if ev.char == "u": self._undo(); return
            if ev.char == "U": self._redo(); return
            if ku in ("R","C","L","V","I","G"): self._place(ku); return
            if ku == "W":  self._start_wire(); return
            if ku == "M":  self._toggle_mouse(); return
            if ev.char == " ": self._rotate(); return
            if ku == "F":  self._flip(); return
            if ku == "T":  self._label_wire(); return
            if ku == "E":  self._start_edit(); return
            if ev.char == ":": self._open_cmd(); return
            if k in ("delete","backspace"): self._delete(); return
            if k == "escape":
                if self.has_selection():
                    self._clear_selection()
                    self._status("Selection cleared", "#94a3b8")
                    self._render()
                    return
                if self.mode == "MOUSE":
                    self._toggle_mouse()
                    return

        elif self.mode == "WIRE":
            if k in ("w","return"): self._commit_wire(); return
            if k == "escape":
                self.mode="NORMAL"; self.ws=None; self._render()

    # ── History & Clipboard Operations ─────────────────────────────────────────
    def _snapshot(self) -> dict:
        """Create a deep snapshot of current schematic state."""
        return {
            "components": [c.to_dict() for c in self.comps],
            "wires":      [w.to_dict() for w in self.wires],
            "wirelabels": [l.to_dict() for l in self.wlbls],
            "uid_comp":   Component._uid,
            "cnt_comp":   dict(Component._cnt),
            "uid_wire":   Wire._uid,
        }

    def _restore_snapshot(self, snap: dict):
        """Restore schematic state from a snapshot."""
        self._clear_selection()
        self.comps = [Component.from_dict(d) for d in snap.get("components", [])]
        self.wires = [Wire.from_dict(d) for d in snap.get("wires", [])]
        self.wlbls = [WireLabel.from_dict(d) for d in snap.get("wirelabels", [])]
        Component._uid = snap.get("uid_comp", 0)
        Component._cnt = dict(snap.get("cnt_comp", {}))
        Wire._uid      = snap.get("uid_wire", 0)

    def _push_undo(self):
        """Push current state onto undo stack and clear redo stack."""
        self._undo_stack.append(self._snapshot())
        if len(self._undo_stack) > 60:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._update_undo_redo_ui()

    def _update_undo_redo_ui(self):
        """Update toolbar button states according to undo/redo/clipboard availability."""
        try:
            if hasattr(self, "btn_undo"):
                if self._undo_stack:
                    self.btn_undo.config(state=tk.NORMAL, fg=BTN_FG)
                else:
                    self.btn_undo.config(state=tk.DISABLED, fg="#4b5563")
            if hasattr(self, "btn_redo"):
                if self._redo_stack:
                    self.btn_redo.config(state=tk.NORMAL, fg=BTN_FG)
                else:
                    self.btn_redo.config(state=tk.DISABLED, fg="#4b5563")
            if hasattr(self, "btn_paste"):
                if self._clipboard:
                    self.btn_paste.config(state=tk.NORMAL, fg=BTN_FG)
                else:
                    self.btn_paste.config(state=tk.DISABLED, fg="#4b5563")
        except Exception:
            pass

    def _undo(self):
        """Undo last schematic modification."""
        if not self._undo_stack:
            self._status("Already at oldest change", "#94a3b8")
            return
        self._redo_stack.append(self._snapshot())
        prev = self._undo_stack.pop()
        self._restore_snapshot(prev)
        self._update_undo_redo_ui()
        self._status("✓ Undo", "#38bdf8")
        self.cv.focus_set()
        self._render()

    def _redo(self):
        """Redo last undone schematic modification."""
        if not self._redo_stack:
            self._status("Already at newest change", "#94a3b8")
            return
        self._undo_stack.append(self._snapshot())
        nxt = self._redo_stack.pop()
        self._restore_snapshot(nxt)
        self._update_undo_redo_ui()
        self._status("✓ Redo", "#38bdf8")
        self.cv.focus_set()
        self._render()

    def _copy(self):
        """Copy selected items (or item at cursor) to clipboard."""
        if self.has_selection():
            comps = list(self.selected_comps)
            wires = list(self.selected_wires)
            labels = list(self.selected_wlbls)

            if len(comps) == 1 and not wires and not labels:
                c = comps[0]
                self._clipboard = {"kind": "comp", "data": c.to_dict()}
                self._update_undo_redo_ui()
                self._status(f"✓ Copied {c.label} ({c.type})", "#38bdf8")
                self.cv.focus_set()
                return

            if len(labels) == 1 and not comps and not wires:
                wl = labels[0]
                self._clipboard = {"kind": "label", "data": wl.to_dict()}
                self._update_undo_redo_ui()
                self._status(f"✓ Copied net label '{wl.text}'", "#38bdf8")
                self.cv.focus_set()
                return

            all_gx = [c.gx for c in comps] + [w.x1 for w in wires] + [w.x2 for w in wires] + [l.gx for l in labels]
            all_gy = [c.gy for c in comps] + [w.y1 for w in wires] + [w.y2 for w in wires] + [l.gy for l in labels]
            orig_gx = min(all_gx) if all_gx else self.cursor[0]
            orig_gy = min(all_gy) if all_gy else self.cursor[1]

            self._clipboard = {
                "kind": "group",
                "comps": [c.to_dict() for c in comps],
                "wires": [w.to_dict() for w in wires],
                "labels": [l.to_dict() for l in labels],
                "orig_gx": orig_gx,
                "orig_gy": orig_gy,
            }
            self._update_undo_redo_ui()
            n_tot = len(comps) + len(wires) + len(labels)
            self._status(f"✓ Copied {n_tot} items to clipboard", "#38bdf8")
            self.cv.focus_set()
            return

        c = self._at_cursor()
        if c:
            self._clipboard = {"kind": "comp", "data": c.to_dict()}
            self._update_undo_redo_ui()
            self._status(f"✓ Copied {c.label} ({c.type})", "#38bdf8")
            self.cv.focus_set()
            return

        wl = next((l for l in self.wlbls if l.gx == self.cursor[0] and l.gy == self.cursor[1]), None)
        if wl:
            self._clipboard = {"kind": "label", "data": wl.to_dict()}
            self._update_undo_redo_ui()
            self._status(f"✓ Copied net label '{wl.text}'", "#38bdf8")
            self.cv.focus_set()
            return

        self._status("[!] Nothing to copy at cursor or in selection", "#f87171")
        self.cv.focus_set()

    def _cut(self):
        """Cut selected items (or item at cursor) to clipboard."""
        if self.has_selection():
            self._copy()
            self._push_undo()
            n_c = len(self.selected_comps)
            n_w = len(self.selected_wires)
            n_l = len(self.selected_wlbls)
            self.comps = [c for c in self.comps if c not in self.selected_comps]
            self.wires = [w for w in self.wires if w not in self.selected_wires]
            self.wlbls = [l for l in self.wlbls if l not in self.selected_wlbls]
            self._clear_selection()
            self._update_undo_redo_ui()
            self._status(f"✓ Cut {n_c} comps, {n_w} wires, {n_l} labels", "#38bdf8")
            self.cv.focus_set()
            self._render()
            return

        c = self._at_cursor()
        if c:
            self._clipboard = {"kind": "comp", "data": c.to_dict()}
            self._push_undo()
            self.comps = [x for x in self.comps if x is not c]
            self._update_undo_redo_ui()
            self._status(f"✓ Cut {c.label} ({c.type})", "#38bdf8")
            self.cv.focus_set()
            self._render()
            return

        wl = next((l for l in self.wlbls if l.gx == self.cursor[0] and l.gy == self.cursor[1]), None)
        if wl:
            self._clipboard = {"kind": "label", "data": wl.to_dict()}
            self._push_undo()
            self.wlbls = [x for x in self.wlbls if x is not wl]
            self._update_undo_redo_ui()
            self._status(f"✓ Cut net label '{wl.text}'", "#38bdf8")
            self.cv.focus_set()
            self._render()
            return

        self._status("[!] Nothing to cut at cursor or in selection", "#f87171")
        self.cv.focus_set()

    def _paste(self):
        """Paste copied item(s) from clipboard at current cursor position."""
        if not self._clipboard:
            self._status("[!] Clipboard empty — copy an item first (Ctrl+C)", "#f87171")
            self.cv.focus_set()
            return

        kind = self._clipboard.get("kind")
        gx, gy = self.cursor

        if kind == "group":
            self._push_undo()
            orig_gx = self._clipboard.get("orig_gx", gx)
            orig_gy = self._clipboard.get("orig_gy", gy)
            dx = gx - orig_gx
            dy = gy - orig_gy

            self._clear_selection()

            new_comps = []
            for d_orig in self._clipboard.get("comps", []):
                d = copy.deepcopy(d_orig)
                d["gx"] += dx
                d["gy"] += dy
                d["label"] = None
                c = Component.from_dict(d)
                cnt_key = COUNTER_GROUP.get(c.type, c.type)
                pfx = PREFIX.get(c.type, c.type[0])
                existing_labels = {comp.label for comp in self.comps} | {comp.label for comp in new_comps}
                while c.label in existing_labels:
                    Component._cnt[cnt_key] = Component._cnt.get(cnt_key, 0) + 1
                    c.label = f"{pfx}{Component._cnt[cnt_key]}"
                new_comps.append(c)

            new_wires = []
            for d_orig in self._clipboard.get("wires", []):
                d = copy.deepcopy(d_orig)
                w = Wire(d["x1"] + dx, d["y1"] + dy, d["x2"] + dx, d["y2"] + dy)
                new_wires.append(w)

            new_labels = []
            for d_orig in self._clipboard.get("labels", []):
                d = copy.deepcopy(d_orig)
                l = WireLabel(d["gx"] + dx, d["gy"] + dy, d["text"])
                new_labels.append(l)

            self.comps.extend(new_comps)
            self.wires.extend(new_wires)
            self.wlbls.extend(new_labels)

            self.selected_comps = set(new_comps)
            self.selected_wires = set(new_wires)
            self.selected_wlbls = set(new_labels)

            n_tot = len(new_comps) + len(new_wires) + len(new_labels)
            self._status(f"✓ Pasted {n_tot} items at ({gx}, {gy})", "#4ade80")
            self.cv.focus_set()
            self._render()
            return

        if kind == "comp":
            if self._at_cursor():
                self._status("[!] Cell occupied — move cursor first", "#f87171")
                self.cv.focus_set()
                return

            self._push_undo()
            d = copy.deepcopy(self._clipboard["data"])
            d["gx"] = gx
            d["gy"] = gy
            d["label"] = None  # Force generation of a fresh sequential label

            c = Component.from_dict(d)
            cnt_key = COUNTER_GROUP.get(c.type, c.type)
            pfx = PREFIX.get(c.type, c.type[0])
            existing_labels = {comp.label for comp in self.comps}
            while c.label in existing_labels:
                Component._cnt[cnt_key] = Component._cnt.get(cnt_key, 0) + 1
                c.label = f"{pfx}{Component._cnt[cnt_key]}"

            self.comps.append(c)
            self._clear_selection()
            self.selected_comps.add(c)
            self._status(f"✓ Pasted {c.label} ({c.type}) at ({gx}, {gy})", "#4ade80")
            self.cv.focus_set()
            self._render()

        elif kind == "label":
            self._push_undo()
            d = copy.deepcopy(self._clipboard["data"])
            self.wlbls = [l for l in self.wlbls if not (l.gx == gx and l.gy == gy)]
            wl_new = WireLabel(gx, gy, d["text"])
            self.wlbls.append(wl_new)
            self._clear_selection()
            self.selected_wlbls.add(wl_new)
            self._status(f"✓ Pasted net label '{d['text']}' at ({gx}, {gy})", "#4ade80")
            self.cv.focus_set()
            self._render()

    # ── Actions ────────────────────────────────────────────────────────────────
    def _at_cursor(self):
        gx, gy = self.cursor
        return next((c for c in self.comps if c.gx==gx and c.gy==gy), None)

    def _status(self, msg, col="#94a3b8", sticky=True):
        self._active_status = (msg, col) if sticky else None
        self.lbl_status.config(text=msg, fg=col)

    def _place(self, typ):
        if self._at_cursor():
            self._status("[!] Cell occupied — move cursor first", "#f87171"); return
        self._push_undo()
        self._clear_selection()
        c = Component(typ, *self.cursor)
        self.comps.append(c)
        self.selected_comps.add(c)
        self._render()

    def _place_device(self, typ):
        if self._at_cursor():
            self._status("[!] Cell occupied — move cursor first", "#f87171"); return
        self._push_undo()
        self._clear_selection()
        c = Component(typ, *self.cursor)
        if typ in ("NMOS", "PMOS"):
            dw, dl = self.model_config.default_wl(typ)
            if dw or dl:
                c.mos_w = dw
                c.mos_l = dl
                c.update_mos_value()
            c.model_name = self.model_config.model_name(typ)
        elif typ in ("NPN", "PNP"):
            c.model_name = self.model_config.model_name(typ)
            if c.model_name and not c.model_name.endswith("_GENERIC"):
                c.value = c.model_name
        self.comps.append(c)
        self.selected_comps.add(c)
        self._render()

    def _rotate(self):
        if self.selected_comps:
            self._push_undo()
            for c in self.selected_comps:
                c.rot = (c.rot + 90) % 360
            self._status(f"Rotated {len(self.selected_comps)} components", "#38bdf8")
            self._render()
            return
        c = self._at_cursor()
        if c:
            self._push_undo()
            c.rot = (c.rot + 90) % 360
        self._render()

    def _flip(self):
        """Toggle horizontal mirror on selected components or component at cursor."""
        if self.selected_comps:
            self._push_undo()
            for c in self.selected_comps:
                c.flip = not c.flip
            self._status(f"Flipped {len(self.selected_comps)} components", "#f472b6")
            self._render()
            return
        c = self._at_cursor()
        if not c:
            self._status("[!] No component at cursor", "#f87171"); return
        self._push_undo()
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
        stripped = new_text.strip()
        if (existing and existing.text == stripped) or (not existing and not stripped):
            return
        self._push_undo()
        # Remove any existing label at this point
        self.wlbls = [l for l in self.wlbls if not (l.gx==gx and l.gy==gy)]
        if stripped:
            self.wlbls.append(WireLabel(gx, gy, stripped))
            self._status(f"✓ Net labelled '{stripped}'", "#38bdf8")
        else:
            self._status("✓ Wire label removed", "#38bdf8")
        self._render()

    # ── V-source / waveform properties are handled in _open_vsrc_props ───────────
    # (FUNC component type removed — all waveforms now live on the V source)

    # ── Simulation analysis dialog ──────────────────────────────────────────────
    def _open_sim_dialog(self):
        """Open the multi-analysis simulation configurator."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Simulation Setup — Multiple Analyses")
        dlg.configure(bg=PANEL_BG)
        dlg.geometry("780x560")
        dlg.minsize(700, 480)
        dlg.transient(self.root)
        dlg.grab_set()

        result = [False]       # True = confirmed
        should_run = [False]   # True = confirmed & immediately run

        # Active selected analysis in detail pane
        initial_sel = self.sim_config.analysis if self.sim_config.analysis in ANALYSES else "TRAN"
        active_sel = [initial_sel]

        # Checkbox state per analysis (local copy)
        check_vars: dict[str, tk.BooleanVar] = {}
        for key in ANALYSES:
            check_vars[key] = tk.BooleanVar(value=self.sim_config.is_enabled(key))

        # ── Header ─────────────────────────────────────────────────────────
        hdr = tk.Frame(dlg, bg=PANEL_BG)
        hdr.pack(fill=tk.X, padx=18, pady=(12, 6))

        tk.Label(hdr, text="Simulation & Analysis Manager",
                 bg=PANEL_BG, fg="#38bdf8",
                 font=("Helvetica", 12, "bold")).pack(anchor="w")
        tk.Label(hdr, text="Configure one or more analyses to run sequentially in NGspice (.control). Check all that apply.",
                 bg=PANEL_BG, fg="#94a3b8",
                 font=("Helvetica", 8, "italic")).pack(anchor="w", pady=(2, 0))

        # ── Body: Two-Pane Split Layout (Master / Detail) ───────────────────
        body = tk.Frame(dlg, bg=PANEL_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

        # ── Left Pane: Master Analysis Checklist ────────────────────────────
        left_frame = tk.Frame(body, bg=PANEL_ALT, bd=1, relief="solid", width=280)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left_frame.pack_propagate(False)

        # Header in left pane
        lf_hdr = tk.Frame(left_frame, bg=PANEL_ALT)
        lf_hdr.pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Label(lf_hdr, text="ANALYSES (Check to Run)", bg=PANEL_ALT, fg="#cbd5e1",
                 font=("Helvetica", 9, "bold")).pack(side=tk.LEFT)

        # Quick action buttons
        qf = tk.Frame(left_frame, bg=PANEL_ALT)
        qf.pack(fill=tk.X, padx=8, pady=(0, 6))

        def _select_all():
            for v in check_vars.values():
                v.set(True)
            _update_summary()

        def _clear_all():
            for v in check_vars.values():
                v.set(False)
            _update_summary()

        def _default_selection():
            for k, v in check_vars.items():
                v.set(k in ("OP", "TRAN"))
            _update_summary()

        tk.Button(qf, text="All", command=_select_all,
                  bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG,
                  font=("Helvetica", 7, "bold"), relief="flat", padx=6, pady=2, cursor="hand2"
                 ).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(qf, text="Clear", command=_clear_all,
                  bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG,
                  font=("Helvetica", 7), relief="flat", padx=6, pady=2, cursor="hand2"
                 ).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(qf, text="Default (OP+TRAN)", command=_default_selection,
                  bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG,
                  font=("Helvetica", 7), relief="flat", padx=6, pady=2, cursor="hand2"
                 ).pack(side=tk.LEFT)

        # Separator line
        tk.Frame(left_frame, bg="#282a3a", height=1).pack(fill=tk.X, padx=6, pady=(0, 4))

        # Master list rows
        row_frames: dict[str, tk.Frame] = {}
        row_cbs: dict[str, tk.Checkbutton] = {}
        row_labels: dict[str, tk.Label] = {}

        def _select_analysis(key: str):
            active_sel[0] = key
            for k, rf in row_frames.items():
                if k == key:
                    c = "#26293b"
                    rf.config(bg=c)
                    row_cbs[k].config(bg=c, activebackground=c)
                    row_labels[k].config(bg=c, fg="#38bdf8")
                else:
                    c = PANEL_ALT
                    rf.config(bg=c)
                    row_cbs[k].config(bg=c, activebackground=c)
                    row_labels[k].config(bg=c, fg="#cbd5e1")
            _show_detail(key)

        for key, info in ANALYSES.items():
            rf = tk.Frame(left_frame, bg=PANEL_ALT, cursor="hand2")
            rf.pack(fill=tk.X, padx=4, pady=1)
            row_frames[key] = rf

            cb = tk.Checkbutton(rf,
                                variable=check_vars[key],
                                bg=PANEL_ALT,
                                selectcolor=PANEL_BG,
                                activebackground=PANEL_ALT,
                                cursor="hand2",
                                command=lambda: _update_summary())
            cb.pack(side=tk.LEFT, padx=(4, 0))
            row_cbs[key] = cb

            lbl_text = f"{key:5s} · {info['label'].split('(')[0].strip()}"
            lbl = tk.Label(rf, text=lbl_text,
                           bg=PANEL_ALT, fg="#cbd5e1",
                           font=("Helvetica", 9), anchor="w", cursor="hand2")
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 4), pady=3)
            row_labels[key] = lbl

            def _bind_row(k=key):
                return lambda e: _select_analysis(k)
            rf.bind("<Button-1>", _bind_row())
            lbl.bind("<Button-1>", _bind_row())

        # ── Right Pane: Detail & Parameter Configuration ───────────────────
        right_frame = tk.Frame(body, bg=PANEL_ALT, bd=1, relief="solid")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Store entry widgets per analysis
        ana_entries: dict[str, tuple[tk.Frame, list[tk.StringVar]]] = {}

        # Detail header (Analysis title + enable toggle)
        det_header = tk.Frame(right_frame, bg=PANEL_ALT)
        det_header.pack(fill=tk.X, padx=16, pady=(12, 4))

        det_title_lbl = tk.Label(det_header, text="",
                                 bg=PANEL_ALT, fg="#38bdf8",
                                 font=("Helvetica", 11, "bold"))
        det_title_lbl.pack(side=tk.LEFT)

        det_enable_cb = tk.Checkbutton(det_header,
                                       text="Enable in simulation run",
                                       bg=PANEL_ALT, fg="#4ade80",
                                       selectcolor=PANEL_BG,
                                       activebackground=PANEL_ALT,
                                       activeforeground="#4ade80",
                                       font=("Helvetica", 9, "bold"),
                                       cursor="hand2")
        det_enable_cb.pack(side=tk.RIGHT)

        det_desc_lbl = tk.Label(right_frame, text="",
                                bg=PANEL_ALT, fg="#94a3b8",
                                font=("Helvetica", 8, "italic"),
                                wraplength=440, anchor="w", justify=tk.LEFT)
        det_desc_lbl.pack(fill=tk.X, padx=16, pady=(0, 6))

        tk.Frame(right_frame, bg="#282a3a", height=1).pack(fill=tk.X, padx=16, pady=(0, 8))

        # Parameter cards container
        param_container = tk.Frame(right_frame, bg=PANEL_ALT)
        param_container.pack(fill=tk.BOTH, expand=True, padx=16)

        for key, info in ANALYSES.items():
            f = tk.Frame(param_container, bg=PANEL_ALT)
            evars = []
            if info["params"]:
                for i, (plabel, pdefault) in enumerate(info["params"]):
                    row = tk.Frame(f, bg=PANEL_ALT)
                    row.pack(fill=tk.X, pady=3)
                    tk.Label(row, text=plabel, bg=PANEL_ALT, fg="#94a3b8",
                             font=("Helvetica", 9), width=24, anchor="w"
                            ).pack(side=tk.LEFT)
                    cur_val = self.sim_config.params.get(key, [])
                    val_str = cur_val[i] if i < len(cur_val) else pdefault
                    ev = tk.StringVar(value=val_str)
                    ent = tk.Entry(row, textvariable=ev,
                                   bg=ENTRY_BG, fg=ENTRY_FG,
                                   insertbackground=CURSOR_C,
                                   font=("Courier", 10), relief="flat", bd=3,
                                   selectbackground="#1e3a5f", width=18)
                    ent.pack(side=tk.LEFT, padx=(6, 0))
                    evars.append(ev)
            else:
                tk.Label(f, text=f"• {info['desc']}\n• No parameters needed for this analysis.",
                         bg=PANEL_ALT, fg="#64748b",
                         font=("Helvetica", 9, "italic"), justify=tk.LEFT).pack(anchor="w", pady=16)
            ana_entries[key] = (f, evars)

        # Single SPICE Directive Preview Card
        preview_card = tk.Frame(right_frame, bg="#12131a", bd=1, relief="solid")
        preview_card.pack(fill=tk.X, padx=16, pady=(6, 12))

        tk.Label(preview_card, text="SPICE DIRECTIVE PREVIEW",
                 bg="#12131a", fg="#64748b",
                 font=("Helvetica", 7, "bold"), anchor="w").pack(fill=tk.X, padx=10, pady=(6, 2))

        single_preview_lbl = tk.Label(preview_card, text="",
                                      bg="#12131a", fg="#4ade80",
                                      font=("Courier", 9, "bold"), anchor="w")
        single_preview_lbl.pack(fill=tk.X, padx=10, pady=(0, 6))

        # Detail switching and update helpers
        current_detail_frame = [None]

        def _update_single_preview():
            key = active_sel[0]
            _, evars = ana_entries[key]
            vals = [ev.get().strip() for ev in evars]
            try:
                line = ANALYSES[key]["spice"](vals)
                single_preview_lbl.config(text=f"  {line}", fg="#4ade80")
            except Exception:
                single_preview_lbl.config(text="  (fill all parameters)", fg="#f59e0b")

        def _show_detail(key: str):
            if current_detail_frame[0]:
                current_detail_frame[0].pack_forget()
            frame, _ = ana_entries[key]
            frame.pack(fill=tk.BOTH, expand=True)
            current_detail_frame[0] = frame

            det_title_lbl.config(text=ANALYSES[key]["label"])
            det_desc_lbl.config(text=ANALYSES[key]["desc"])
            det_enable_cb.config(variable=check_vars[key],
                                 command=lambda: _update_summary())
            _update_single_preview()

        # Listen to entry changes across all analyses
        for key, (_, evars) in ana_entries.items():
            for ev in evars:
                ev.trace_add("write", lambda *_: (_update_single_preview(), _update_summary()))

        # ── Bottom Live Summary Banner ──────────────────────────────────────
        sum_frame = tk.Frame(dlg, bg="#12131a", bd=1, relief="solid")
        sum_frame.pack(fill=tk.X, padx=16, pady=(4, 6))

        sum_title_lbl = tk.Label(sum_frame, text="Active Directives:",
                                 bg="#12131a", fg="#38bdf8",
                                 font=("Helvetica", 8, "bold"), anchor="w")
        sum_title_lbl.pack(fill=tk.X, padx=10, pady=(4, 0))

        sum_content_lbl = tk.Label(sum_frame, text="",
                                   bg="#12131a", fg="#4ade80",
                                   font=("Courier", 9), anchor="w",
                                   wraplength=730, justify=tk.LEFT)
        sum_content_lbl.pack(fill=tk.X, padx=10, pady=(0, 6))

        def _get_active_directives() -> list[tuple[str, str]]:
            res = []
            for k in ANALYSES:
                if check_vars[k].get():
                    _, evars = ana_entries[k]
                    vals = [ev.get().strip() for ev in evars]
                    try:
                        line = ANALYSES[k]["spice"](vals)
                        res.append((k, line))
                    except Exception:
                        res.append((k, f".{k.lower()} (?)"))
            return res

        def _update_summary(*_):
            active = _get_active_directives()
            count = len(active)
            if count == 0:
                sum_title_lbl.config(text="Active Directives (0):", fg="#f59e0b")
                sum_content_lbl.config(
                    text="  (No analyses selected — check at least one analysis to run simulation)",
                    fg="#f59e0b"
                )
                btn_run.config(state=tk.DISABLED)
            else:
                sum_title_lbl.config(text=f"Active Directives ({count}):", fg="#38bdf8")
                lines_str = "    ·    ".join(sline for _, sline in active)
                sum_content_lbl.config(text=f"  {lines_str}", fg="#4ade80")
                btn_run.config(state=tk.NORMAL)

        # ── Action Buttons Footer ───────────────────────────────────────────
        bf = tk.Frame(dlg, bg=PANEL_BG)
        bf.pack(fill=tk.X, padx=16, pady=(4, 12))

        def _apply_changes():
            for k in ANALYSES:
                _, evars = ana_entries[k]
                self.sim_config.params[k] = [ev.get().strip() for ev in evars]
            enabled = [k for k in ANALYSES if check_vars[k].get()]
            self.sim_config.enabled_analyses = enabled if enabled else ["TRAN"]
            self.sim_config.analysis = active_sel[0] if active_sel[0] in enabled else (enabled[0] if enabled else "TRAN")
            result[0] = True

        def _on_run():
            _apply_changes()
            should_run[0] = True
            dlg.destroy()

        def _on_ok():
            _apply_changes()
            dlg.destroy()

        def _on_cancel():
            dlg.destroy()

        # Left side: Run simulation button
        btn_run = tk.Button(bf, text="▶ Run Simulation", command=_on_run,
                            bg=BTN_RUN_BG, fg=BTN_RUN_FG,
                            activebackground=BTN_RUN_ACT, activeforeground="#ffffff",
                            font=("Helvetica", 10, "bold"),
                            relief="flat", padx=18, pady=6, cursor="hand2")
        btn_run.pack(side=tk.LEFT)

        # Right side: Cancel, Apply & Close
        tk.Button(bf, text="Cancel", command=_on_cancel,
                  bg=BTN_BG, fg=BTN_FG,
                  activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
                  font=("Helvetica", 9), relief="flat",
                  padx=12, pady=6, cursor="hand2"
                 ).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Button(bf, text="Apply & Close", command=_on_ok,
                  bg=BTN_PRIMARY_BG, fg=BTN_PRIMARY_FG,
                  activebackground=BTN_PRIMARY_ACT, activeforeground="#ffffff",
                  font=("Helvetica", 10, "bold"),
                  relief="flat", padx=16, pady=6, cursor="hand2"
                 ).pack(side=tk.RIGHT)

        # Initialize selection and summary
        _select_analysis(active_sel[0])
        _update_summary()

        dlg.bind("<Return>", lambda _: _on_ok())
        dlg.bind("<Escape>", lambda _: _on_cancel())
        self._center_dialog(dlg)
        self.root.wait_window(dlg)
        self.cv.focus_set()

        if result[0]:
            lines = self.sim_config.spice_lines()
            line_str = " · ".join(lines) if lines else "(none)"
            self._status(
                f"✓ Simulation configured ({len(lines)} active): {line_str}",
                "#a78bfa")
            # Rebuild netlist panel if open
            if self._netlist_visible:
                self._rebuild_netlist()
            if should_run[0]:
                self.root.after(30, self._run_simulation)

    # ── Dialog centering helper ─────────────────────────────────────────────────
    def _center_dialog(self, dlg):
        self.root.update_idletasks()
        dlg.update_idletasks()
        rx = self.root.winfo_rootx() + self.root.winfo_width()  // 2
        ry = self.root.winfo_rooty() + self.root.winfo_height() // 2
        dlg.geometry(f"+{rx - dlg.winfo_width()//2}+{ry - dlg.winfo_height()//2}")

    def _delete(self):
        if self.has_selection():
            self._push_undo()
            n_c = len(self.selected_comps)
            n_w = len(self.selected_wires)
            n_l = len(self.selected_wlbls)
            self.comps = [c for c in self.comps if c not in self.selected_comps]
            self.wires = [w for w in self.wires if w not in self.selected_wires]
            self.wlbls = [l for l in self.wlbls if l not in self.selected_wlbls]
            self._clear_selection()
            self._status(f"✓ Deleted {n_c} comp{'s' if n_c!=1 else ''}, {n_w} wire{'s' if n_w!=1 else ''}", "#38bdf8")
            self._render()
            return

        gx, gy = self.cursor
        has_comp = any(c.gx == gx and c.gy == gy for c in self.comps)
        has_wire = any((w.x1 == gx and w.y1 == gy) or (w.x2 == gx and w.y2 == gy) for w in self.wires)
        has_lbl  = any(l.gx == gx and l.gy == gy for l in self.wlbls)
        if not (has_comp or has_wire or has_lbl):
            return
        self._push_undo()
        self.comps = [c for c in self.comps if not (c.gx==gx and c.gy==gy)]
        self.wires = [w for w in self.wires
                      if not((w.x1==gx and w.y1==gy) or (w.x2==gx and w.y2==gy))]
        self.wlbls = [l for l in self.wlbls if not (l.gx==gx and l.gy==gy)]
        self._status("Deleted item at cursor", "#94a3b8")
        self._render()

    def _start_wire(self):
        self.mode="WIRE"; self.ws=list(self.cursor); self._render()

    def _commit_wire(self):
        cx, cy = self.cursor
        if self.ws and (self.ws[0]!=cx or self.ws[1]!=cy):
            self._push_undo()
            self.wires.append(Wire(self.ws[0],self.ws[1],cx,cy))
            self.ws=[cx,cy]
        else:
            self.mode="NORMAL"; self.ws=None
        self._render()

    def _toggle_mouse(self):
        self.mode = "NORMAL" if self.mode=="MOUSE" else "MOUSE"
        self._render()

    def _zoom(self, delta, ev=None):
        old_gs = self.GS
        new_gs = max(GS_MIN, min(GS_MAX, old_gs + delta))
        if new_gs == old_gs:
            return

        if ev is not None and hasattr(ev, "x") and hasattr(ev, "y"):
            mx = self.cv.canvasx(ev.x)
            my = self.cv.canvasy(ev.y)
            gx = mx / old_gs
            gy = my / old_gs

            self.GS = new_gs
            self._update_canvas_size()
            self.cv.config(scrollregion=(0, 0, self.CW, self.CH))

            new_mx = gx * new_gs
            new_my = gy * new_gs

            target_left = new_mx - ev.x
            target_top  = new_my - ev.y

            fx = max(0.0, min(1.0, target_left / max(1, self.CW)))
            fy = max(0.0, min(1.0, target_top  / max(1, self.CH)))
            self.cv.xview_moveto(fx)
            self.cv.yview_moveto(fy)

            # Move grid cursor to cell under mouse
            cx = max(0, min(COLS - 1, int(round(new_mx / new_gs))))
            cy = max(0, min(ROWS - 1, int(round(new_my / new_gs))))
            self.cursor = [cx, cy]

            self._render()
        else:
            self.GS = new_gs
            self._update_canvas_size()
            self.cv.config(scrollregion=(0, 0, self.CW, self.CH))
            self._scroll_to_cursor()
            self._render()

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

        tk.Label(dlg, text="Voltage Source Properties",
            bg=PANEL_BG, fg="#38bdf8",
            font=("Helvetica", 11, "bold"), pady=8).pack()

        # ── Label row ──────────────────────────────────────────────────────
        lr = tk.Frame(dlg, bg=PANEL_BG)
        lr.pack(fill=tk.X, padx=20, pady=(0,6))
        tk.Label(lr, text="Label", bg=PANEL_BG, fg="#94a3b8",
            font=("Helvetica", 9), width=10, anchor="w").pack(side=tk.LEFT)
        sv_label = tk.StringVar(value=c.label)
        tk.Entry(lr, textvariable=sv_label,
            bg=ENTRY_BG, fg="#fbbf24",
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
                    b.config(bg=BTN_PRIMARY_BG, fg=BTN_PRIMARY_FG,
                             relief="flat", font=("Courier", 8, "bold"))
                else:
                    b.config(bg=BTN_BG, fg=BTN_FG,
                             activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
                             relief="flat", font=("Courier", 8))
            _rebuild_params(key)
            _update_preview()

        for key in TAB_KEYS:
            b = tk.Button(tab_frame, text=key,
                command=lambda k=key: _select_tab(k),
                bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
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
                        bg=ENTRY_BG, fg=color,
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
                        bg=ENTRY_BG, fg=ENTRY_FG,
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
                        bg=ENTRY_BG, fg=ENTRY_FG,
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
            bg="#12131a", fg="#4ade80",
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
            bg=BTN_PRIMARY_BG, fg=BTN_PRIMARY_FG,
            activebackground=BTN_PRIMARY_ACT, activeforeground="#ffffff",
            font=("Helvetica", 9, "bold"),
            relief="flat", padx=16, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT)
        tk.Button(bf, text="Cancel", command=_cancel,
            bg=BTN_BG, fg=BTN_FG,
            activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
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
            self._push_undo()
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

        tk.Label(dlg, text=f"{c.type} Properties",
            bg=PANEL_BG, fg="#38bdf8",
            font=("Helvetica", 11, "bold"), pady=10).pack()

        def _row(parent, lbl, val, color="#e2e8f0"):
            f = tk.Frame(parent, bg=PANEL_BG)
            f.pack(fill=tk.X, padx=20, pady=3)
            tk.Label(f, text=lbl, bg=PANEL_BG, fg="#94a3b8",
                font=("Helvetica", 9), width=10, anchor="w").pack(side=tk.LEFT)
            sv = tk.StringVar(value=val)
            e  = tk.Entry(f, textvariable=sv,
                bg=ENTRY_BG, fg=color,
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
            bg=BTN_PRIMARY_BG, fg=BTN_PRIMARY_FG,
            activebackground=BTN_PRIMARY_ACT, activeforeground="#ffffff",
            font=("Helvetica", 9, "bold"),
            relief="flat", padx=16, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT)
        tk.Button(bf, text="Cancel", command=_cancel,
            bg=BTN_BG, fg=BTN_FG,
            activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
            font=("Helvetica", 9), relief="flat",
            padx=10, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT, padx=(8,0))

        dlg.bind("<Return>", _ok)
        dlg.bind("<Escape>", _cancel)
        self._center_dialog(dlg)
        self.root.wait_window(dlg)
        self.cv.focus_set()

        if result[0]:
            self._push_undo()
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

        tk.Label(dlg, text=f"{c.type} Properties",
            bg=PANEL_BG, fg="#38bdf8",
            font=("Helvetica", 11, "bold"), pady=10).pack()

        body = tk.Frame(dlg, bg=PANEL_BG)
        body.pack(fill=tk.X, padx=20, pady=4)

        def _lbl(row, text):
            tk.Label(row, text=text, bg=PANEL_BG, fg="#94a3b8",
                font=("Helvetica", 9), width=12, anchor="w").pack(side=tk.LEFT)

        def _entry(row, val, w=14, color="#e2e8f0"):
            sv = tk.StringVar(value=val)
            e  = tk.Entry(row, textvariable=sv,
                bg=ENTRY_BG, fg=color,
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
        mode_opt.config(bg=ENTRY_BG, fg="#38bdf8",
            activebackground=BTN_ACTIVE_BG, activeforeground="#ffffff",
            font=("Courier", 9), relief="flat", bd=0,
            highlightthickness=0, width=18)
        mode_opt["menu"].config(bg=ENTRY_BG, fg="#38bdf8",
            font=("Courier", 9))
        mode_opt.pack(side=tk.LEFT, padx=(4,0))

        # Model source hint
        if not self._model_names_cache.get(c.type):
            tk.Label(r1, text="  ← configure in Models",
                bg=PANEL_BG, fg="#64748b",
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

        # PDK Presets row
        resolved_pdk = resolve_pdk(self.model_config.pdk_name) if self.model_config.pdk_name else None
        min_w, min_l = self.model_config.min_wl(c.type)

        preset_row = tk.Frame(body, bg=PANEL_BG)
        preset_row.pack(fill=tk.X, pady=(2, 6))
        _lbl(preset_row, "PDK Sizing")

        tk.Button(preset_row, text=f"PDK Min ({min_w}/{min_l})",
            command=lambda: (sv_w.set(min_w), sv_l.set(min_l)),
            bg=BTN_BG, fg="#4ade80", activebackground=BTN_ACTIVE_BG,
            font=("Helvetica", 8, "bold"), relief="flat", padx=6, pady=2, cursor="hand2"
        ).pack(side=tk.LEFT, padx=(0, 6))

        if resolved_pdk and c.type in resolved_pdk.default_wl:
            nom_w, nom_l = resolved_pdk.default_wl[c.type]
            tk.Button(preset_row, text=f"Nominal ({nom_w}/{nom_l})",
                command=lambda: (sv_w.set(nom_w), sv_l.set(nom_l)),
                bg=BTN_BG, fg="#38bdf8", activebackground=BTN_ACTIVE_BG,
                font=("Helvetica", 8), relief="flat", padx=6, pady=2, cursor="hand2"
            ).pack(side=tk.LEFT)

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
        bulk_opt.config(bg=ENTRY_BG, fg=ENTRY_FG,
            activebackground=BTN_ACTIVE_BG, activeforeground="#ffffff",
            font=("Courier", 9), relief="flat", bd=0,
            highlightthickness=0, width=8)
        bulk_opt["menu"].config(bg=ENTRY_BG, fg=ENTRY_FG, font=("Courier",9))
        bulk_opt.pack(side=tk.LEFT, padx=(4,0))

        # ── Live SPICE preview ──
        tk.Frame(body, bg=BORDER, height=1).pack(fill=tk.X, pady=(10,4))
        tk.Label(body, text="SPICE preview",
            bg=PANEL_BG, fg="#4b5563",
            font=("Courier", 7)).pack(anchor="w")
        sv_preview = tk.StringVar()
        lbl_preview = tk.Label(body, textvariable=sv_preview,
            bg="#12131a", fg="#4ade80",
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
            bg=BTN_PRIMARY_BG, fg=BTN_PRIMARY_FG,
            activebackground=BTN_PRIMARY_ACT, activeforeground="#ffffff",
            font=("Helvetica", 9, "bold"),
            relief="flat", padx=16, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT)
        tk.Button(bf, text="Cancel", command=_cancel,
            bg=BTN_BG, fg=BTN_FG,
            activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
            font=("Helvetica", 9), relief="flat",
            padx=10, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT, padx=(8,0))

        dlg.bind("<Return>", _ok)
        dlg.bind("<Escape>", _cancel)
        self._center_dialog(dlg)
        self.root.wait_window(dlg)
        self.cv.focus_set()

        if result[0]:
            self._push_undo()
            r = result[0]
            if r["label"]:      c.label      = r["label"]
            c.model_name = r["model_name"]
            c.mos_w      = r["mos_w"]
            c.mos_l      = r["mos_l"]
            c.bulk_net   = r["bulk_net"]
            try:   c.fingers = int(r["fingers"])
            except: c.fingers = 1
            c.update_mos_value()
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

        tk.Label(dlg, text=f"{c.type} Properties",
            bg=PANEL_BG, fg="#38bdf8",
            font=("Helvetica", 11, "bold"), pady=10).pack()

        body = tk.Frame(dlg, bg=PANEL_BG)
        body.pack(fill=tk.X, padx=20, pady=4)

        def _row(lbl_text, val, color="#e2e8f0"):
            f = tk.Frame(body, bg=PANEL_BG); f.pack(fill=tk.X, pady=2)
            tk.Label(f, text=lbl_text, bg=PANEL_BG, fg="#94a3b8",
                font=("Helvetica", 9), width=12, anchor="w").pack(side=tk.LEFT)
            sv = tk.StringVar(value=val)
            e  = tk.Entry(f, textvariable=sv,
                bg=ENTRY_BG, fg=color,
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
        opt.config(bg=ENTRY_BG, fg="#38bdf8",
            activebackground=BTN_ACTIVE_BG, activeforeground="#ffffff",
            font=("Courier", 9), relief="flat", bd=0,
            highlightthickness=0, width=18)
        opt["menu"].config(bg=ENTRY_BG, fg="#38bdf8", font=("Courier", 9))
        opt.pack(side=tk.LEFT, padx=(4,0))
        if not self._model_names_cache.get(c.type):
            tk.Label(rf, text="  ← configure in Models",
                bg=PANEL_BG, fg="#64748b",
                font=("Helvetica", 8)).pack(side=tk.LEFT)

        # Preview
        tk.Frame(body, bg=BORDER, height=1).pack(fill=tk.X, pady=(10,4))
        sv_preview = tk.StringVar()
        tk.Label(body, textvariable=sv_preview,
            bg="#12131a", fg="#4ade80",
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
            bg=BTN_PRIMARY_BG, fg=BTN_PRIMARY_FG,
            activebackground=BTN_PRIMARY_ACT, activeforeground="#ffffff",
            font=("Helvetica", 9, "bold"),
            relief="flat", padx=16, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT)
        tk.Button(bf, text="Cancel", command=_cancel,
            bg=BTN_BG, fg=BTN_FG,
            activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
            font=("Helvetica", 9), relief="flat",
            padx=10, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT, padx=(8,0))
        dlg.bind("<Return>", _ok)
        dlg.bind("<Escape>", _cancel)
        self._center_dialog(dlg)
        self.root.wait_window(dlg)
        self.cv.focus_set()

        if result[0]:
            self._push_undo()
            lbl, mdl = result[0]
            if lbl: c.label = lbl
            c.model_name = mdl
            if mdl and not mdl.endswith("_GENERIC"):
                c.value = mdl
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

        tk.Label(dlg, text="Model Manager",
            bg=PANEL_BG, fg="#38bdf8",
            font=("Helvetica", 12, "bold"), pady=12).pack()

        body = tk.Frame(dlg, bg=PANEL_BG)
        body.pack(fill=tk.X, padx=22, pady=4)

        # ── PDK Presets ──
        installed_pdks = detect_installed_pdks()
        sv_pdk = tk.StringVar(value=getattr(mc, "pdk_name", "") or "none")

        pdk_frame = tk.LabelFrame(body, text="  PDK Preset (Auto-Config)  ",
            bg=PANEL_BG, fg="#38bdf8",
            font=("Helvetica", 9, "bold"), bd=1, relief="solid")
        pdk_frame.pack(fill=tk.X, pady=(0, 10))

        pdk_radio_frame = tk.Frame(pdk_frame, bg=PANEL_BG)
        pdk_radio_frame.pack(fill=tk.X, padx=6, pady=3)

        lbl_pdk_status = tk.Label(pdk_frame, text="", bg=PANEL_BG, fg="#94a3b8",
                                  font=("Helvetica", 8), anchor="w", padx=8, pady=1)
        lbl_pdk_status.pack(fill=tk.X)

        lbl_pdk_wl = tk.Label(pdk_frame, text="", bg=PANEL_BG, fg="#4ade80",
                              font=("Courier", 8), anchor="w", padx=8, pady=2)
        lbl_pdk_wl.pack(fill=tk.X, pady=(0, 4))

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
                bg=PANEL_BG, fg="#cbd5e1", selectcolor=PANEL_ALT,
                activebackground=PANEL_BG, activeforeground="#38bdf8",
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
                selectcolor=PANEL_ALT,
                activebackground=PANEL_BG, activeforeground="#38bdf8",
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
            bg=ENTRY_BG, fg=ENTRY_FG,
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
            bg=BTN_BG, fg=BTN_FG,
            activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
            font=("Helvetica", 8), relief="flat",
            padx=6, pady=2, cursor="hand2"
        ).pack(side=tk.LEFT)

        fr2 = tk.Frame(file_frame, bg=PANEL_BG); fr2.pack(fill=tk.X, padx=8, pady=(0,4))
        tk.Label(fr2, text="Corner:", bg=PANEL_BG, fg="#94a3b8",
            font=("Helvetica", 9), width=7, anchor="w").pack(side=tk.LEFT)
        sv_corner = tk.StringVar(value=mc.corner or "tt")
        corner_opts = ["tt", "ff", "ss", "fs", "sf"]
        corner_menu = tk.OptionMenu(fr2, sv_corner, *corner_opts)
        corner_menu.config(bg=ENTRY_BG, fg=ENTRY_FG,
            activebackground=BTN_ACTIVE_BG, activeforeground="#ffffff",
            font=("Courier", 9), relief="flat", bd=0,
            highlightthickness=0, width=12)
        corner_menu["menu"].config(bg=ENTRY_BG, fg=ENTRY_FG, font=("Courier",9))
        corner_menu.pack(side=tk.LEFT, padx=(4,0))
        tk.Label(fr2, text="  (for .lib / PDK files)",
            bg=PANEL_BG, fg="#4b5563",
            font=("Helvetica", 8)).pack(side=tk.LEFT)

        def _update_corner_menu(opts, default=None):
            corner_menu["menu"].delete(0, "end")
            for c in opts:
                corner_menu["menu"].add_command(
                    label=c, command=lambda val=c: sv_corner.set(val))
            if default:
                sv_corner.set(default)
            elif opts and sv_corner.get() not in opts:
                sv_corner.set(opts[0])

        # ── Detected models list ──
        det_frame = tk.LabelFrame(body, text="  Detected Models  ",
            bg=PANEL_BG, fg="#94a3b8",
            font=("Helvetica", 9), bd=1, relief="solid")
        det_frame.pack(fill=tk.X, pady=(0,10))

        det_text = tk.Text(det_frame, height=7, width=52,
            bg="#12131a", fg="#4ade80",
            font=("Courier", 8), relief="flat",
            state=tk.DISABLED, padx=6, pady=4)
        det_text.pack(fill=tk.X, padx=4, pady=4)

        def _set_detected_text(txt):
            det_text.config(state=tk.NORMAL)
            det_text.delete("1.0", tk.END)
            det_text.insert(tk.END, txt)
            det_text.config(state=tk.DISABLED)

        # ── PDK selection callback ──
        def _on_pdk_select():
            val = sv_pdk.get()
            if val == "none":
                lbl_pdk_status.config(text="Custom/Inline model mode", fg="#94a3b8")
                lbl_pdk_wl.config(text="  Min Sizing: NMOS W/L=180n/180n  ·  PMOS W/L=180n/180n", fg="#94a3b8")
                return
            pdk = installed_pdks.get(val)
            if not pdk:
                lbl_pdk_status.config(text=f"[!] PDK '{val}' not recognized", fg="#ef4444")
                lbl_pdk_wl.config(text="")
                return
            if not pdk.available:
                lbl_pdk_status.config(
                    text=f"[!] PDK files not found at: {pdk.pdk_dir}", fg="#f59e0b")
            else:
                lbl_pdk_status.config(
                    text=f"✓ Detected at: {pdk.pdk_dir}", fg="#4ade80")

            nw, nl = pdk.min_wl.get("NMOS", ("?", "?"))
            pw, pl = pdk.min_wl.get("PMOS", ("?", "?"))
            lbl_pdk_wl.config(text=f"  ✓ Applied Min Dimensions: NMOS W/L = {nw}/{nl}   PMOS W/L = {pw}/{pl}", fg="#4ade80")

            sv_mode.set("lib")
            sv_file.set(pdk.lib_file)
            _update_corner_menu(pdk.corners, pdk.default_corner)
            self._model_names_cache = dict(pdk.models)

            lines = [f"  PDK: {pdk.display_name}", f"  Root: {pdk.pdk_dir}", ""]
            lines.append(f"  Applied Min Dimensions: NMOS={nw}/{nl}, PMOS={pw}/{pl}")
            lines.append("")
            for dt in ("NMOS", "PMOS", "NPN", "PNP"):
                models = pdk.models.get(dt, [])
                if models:
                    lines.append(f"  {dt}:")
                    for m in models:
                        lines.append(f"    ✓  {m}")
            _set_detected_text("\n".join(lines))

        pdk_radio_items = [
            ("none",   "None / Custom"),
            ("gf180",  "GF180MCU"),
            ("sky130", "SkyWater 130"),
            ("ihp",    "IHP SG13G2"),
        ]
        for pval, plbl in pdk_radio_items:
            tk.Radiobutton(pdk_radio_frame, text=plbl, variable=sv_pdk, value=pval,
                command=_on_pdk_select,
                bg=PANEL_BG, fg="#cbd5e1", selectcolor=PANEL_ALT,
                activebackground=PANEL_BG, activeforeground="#38bdf8",
                font=("Helvetica", 9), anchor="w"
            ).pack(side=tk.LEFT, padx=6, pady=2)

        def _parse_file(path=None):
            if sv_pdk.get() != "none":
                return  # PDK mode manages its own catalog
            p = path or sv_file.get().strip()
            if not p or not os.path.isfile(p):
                _set_detected_text(
                    "(no file — using inline defaults)" if not p
                    else f"[!] File not found:\n{p}")
                return
            found = parse_model_file(p)
            corners = parse_model_file_corners(p)
            if corners:
                _update_corner_menu(corners)
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
                lines.append("  [!] No .model or .subckt definitions found")
            _set_detected_text("\n".join(lines))

        # Populate on open
        cur_pdk = getattr(mc, "pdk_name", "")
        if cur_pdk and cur_pdk in installed_pdks:
            sv_pdk.set(cur_pdk)
            _on_pdk_select()
        elif mc.file_path and os.path.isfile(mc.file_path):
            _on_pdk_select()
            _parse_file(mc.file_path)
        elif mc.mode == "inline":
            _on_pdk_select()
            _set_detected_text(
                "  Inline mode — built-in Level 1 parameters\n\n"
                "  NMOS_GENERIC  (VTO=1.0  KP=200u  LAMBDA=0.01)\n"
                "  PMOS_GENERIC  (VTO=-1.0 KP=80u   LAMBDA=0.01)\n"
                "  NPN_GENERIC   (IS=1e-14 BF=100   VAF=50)\n"
                "  PNP_GENERIC   (IS=1e-14 BF=50    VAF=50)")
        else:
            _on_pdk_select()
            _set_detected_text("  No file configured yet — click Browse… or choose a PDK")

        sv_file.trace_add("write", lambda *_: _parse_file())

        # ── Buttons ──
        def _ok(_=None):
            level_val = sv_level.get()
            try:    level_val = int(level_val)
            except: pass   # stays as "BSIM3" / "BSIM4"
            pdk_val = sv_pdk.get()
            result[0] = {
                "mode":             sv_mode.get(),
                "level":            level_val,
                "file_path":        sv_file.get().strip(),
                "corner":           sv_corner.get(),
                "pdk_name":         "" if pdk_val == "none" else pdk_val,
            }
            dlg.destroy()

        def _cancel(_=None): dlg.destroy()

        bf = tk.Frame(dlg, bg=PANEL_BG)
        bf.pack(fill=tk.X, padx=22, pady=(4,14))
        tk.Button(bf, text="Apply", command=_ok,
            bg=BTN_PRIMARY_BG, fg=BTN_PRIMARY_FG,
            activebackground=BTN_PRIMARY_ACT, activeforeground="#ffffff",
            font=("Helvetica", 9, "bold"),
            relief="flat", padx=16, pady=4, cursor="hand2"
        ).pack(side=tk.LEFT)
        tk.Button(bf, text="Cancel", command=_cancel,
            bg=BTN_BG, fg=BTN_FG,
            activebackground=BTN_ACTIVE_BG, activeforeground=BTN_ACTIVE_FG,
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
            self.model_config.wl_mode   = "min"
            pdk_name = r.get("pdk_name", "")
            self.model_config.apply_pdk(pdk_name, r["corner"])
            if pdk_name:
                resolved = resolve_pdk(pdk_name)
                if resolved:
                    self._model_names_cache = dict(resolved.models)
                    nw, nl = resolved.min_wl.get("NMOS", ("?", "?"))
                    pw, pl = resolved.min_wl.get("PMOS", ("?", "?"))
                    upd = 0
                    for c in self.comps:
                        if c.type == "NMOS":
                            c.mos_w, c.mos_l = nw, nl
                            c.model_name = self.model_config.model_name("NMOS")
                            c.update_mos_value()
                            upd += 1
                        elif c.type == "PMOS":
                            c.mos_w, c.mos_l = pw, pl
                            c.model_name = self.model_config.model_name("PMOS")
                            c.update_mos_value()
                            upd += 1
                    if upd:
                        self._render()
                        if self._netlist_visible:
                            self._rebuild_netlist()
            elif r["file_path"]:
                self._model_names_cache = parse_model_file(r["file_path"])
            elif r["mode"] == "inline":
                self._model_names_cache = {}   # use generic names

            try:
                if self.model_config.pdk_name:
                    self.btn_models.config(text=f"Models: {self.model_config.pdk_name.upper()}")
                else:
                    self.btn_models.config(text="Models")
            except Exception:
                pass

            mode_lbl = self.model_config.pdk_name.upper() if self.model_config.pdk_name else {"inline":"inline","include":".include","lib":".lib"}[r["mode"]]
            status_text = f"✓ Models: {mode_lbl}"
            if self.model_config.pdk_name:
                nw, nl = self.model_config.default_wl("NMOS")
                pw, pl = self.model_config.default_wl("PMOS")
                status_text += f" [{r['corner']}]  ·  Min W/L applied: NMOS={nw}/{nl}, PMOS={pw}/{pl}"
            elif r["mode"] == "lib":
                status_text += f" [{r['corner']}]"
            elif r["file_path"]:
                status_text += f"  {os.path.basename(r['file_path'])}"
            self._status(status_text, "#38bdf8" if self.model_config.pdk_name else "#4ade80")

    def _open_cmd(self):
        """Open a sleek, flexible, modern command palette with autocomplete, history, and parameter support."""
        if getattr(self, "_cmd_dlg", None) and self._cmd_dlg.winfo_exists():
            self._cmd_dlg.lift()
            return

        dlg = tk.Toplevel(self.root)
        self._cmd_dlg = dlg
        dlg.title("Command Palette")
        dlg.configure(bg=PANEL_BG)
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        # Modern palette frame
        main_frame = tk.Frame(dlg, bg=PANEL_BG, padx=8, pady=8)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Top input box - NO TEXT ABOVE THE ENTRY!
        inp_box = tk.Frame(main_frame, bg=ENTRY_BG, bd=1, relief="solid",
                           highlightbackground="#38bdf8", highlightcolor="#38bdf8", highlightthickness=1)
        inp_box.pack(fill=tk.X, pady=(0, 6))

        prompt_lbl = tk.Label(inp_box, text=">", bg=ENTRY_BG, fg="#38bdf8",
                              font=("Courier", 13, "bold"), padx=8, pady=6)
        prompt_lbl.pack(side=tk.LEFT)

        cmd_var = tk.StringVar()
        ent = tk.Entry(inp_box, textvariable=cmd_var, bg=ENTRY_BG, fg=ENTRY_FG,
                       insertbackground="#38bdf8", font=("Courier", 11),
                       relief="flat", bd=0, selectbackground="#1e3a5f", width=48)
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), pady=6)
        ent.focus_set()

        # Suggestion listbox
        sugg_box = tk.Frame(main_frame, bg="#14151f", bd=1, relief="solid",
                            highlightbackground=BORDER, highlightthickness=1)
        sugg_box.pack(fill=tk.BOTH, expand=True)

        sugg_list = tk.Listbox(sugg_box, bg="#14151f", fg="#cbd5e1",
                               selectbackground="#1e3a5f", selectforeground="#38bdf8",
                               font=("Courier", 10), relief="flat", bd=0,
                               highlightthickness=0, height=8, activestyle="none")
        sugg_scroll = tk.Scrollbar(sugg_box, orient=tk.VERTICAL, command=sugg_list.yview,
                                   bg=PANEL_BG, troughcolor="#14151f", relief="flat", bd=0)
        sugg_list.config(yscrollcommand=sugg_scroll.set)
        sugg_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sugg_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Footer help guide (at the bottom)
        footer = tk.Label(main_frame,
                          text="[↵] Run   [Tab] Complete   [↑/↓] Navigate / History   [Esc] Close",
                          bg=PANEL_BG, fg="#64748b", font=("Helvetica", 8))
        footer.pack(fill=tk.X, pady=(6, 0))

        # Data & autocomplete filtering logic
        displayed_items = []
        hist_idx = [len(self._cmd_history)]

        def _update_suggestions(*args):
            nonlocal displayed_items
            sugg_list.delete(0, tk.END)
            displayed_items = []
            raw = cmd_var.get().strip()
            if raw.startswith(":"):
                raw = raw[1:].strip()
            tokens = raw.split()
            prefix = tokens[0].lower() if tokens else ""

            if not prefix:
                matches = list(COMMAND_CATALOG)
            else:
                exact_matches = []
                prefix_matches = []
                sub_matches = []
                for entry in COMMAND_CATALOG:
                    cmd_tmpl, aliases, desc = entry
                    # 1. Exact match on alias or primary word
                    if prefix in aliases or prefix == cmd_tmpl.split()[0].lower():
                        exact_matches.append(entry)
                    # 2. Prefix match on any alias or primary word
                    elif any(a.startswith(prefix) for a in aliases) or cmd_tmpl.lower().startswith(prefix):
                        prefix_matches.append(entry)
                    # 3. Substring match in description or command
                    elif prefix in cmd_tmpl.lower() or prefix in desc.lower():
                        sub_matches.append(entry)
                matches = exact_matches + prefix_matches + sub_matches

            displayed_items = matches
            for cmd_tmpl, aliases, desc in matches:
                display_str = f":{cmd_tmpl:<24}  {desc}"
                sugg_list.insert(tk.END, display_str)

            if matches:
                sugg_list.selection_clear(0, tk.END)
                sugg_list.selection_set(0)
                sugg_list.activate(0)
                sugg_list.see(0)

        cmd_var.trace_add("write", _update_suggestions)
        _update_suggestions()

        def _close():
            try:
                dlg.grab_release()
            except Exception:
                pass
            try:
                dlg.destroy()
            except Exception:
                pass
            self._cmd_dlg = None
            self.cv.focus_set()
            self._render()

        def _run_and_close(cmd_text: str | None = None):
            if cmd_text is None:
                cmd_text = cmd_var.get().strip()
                if not cmd_text and displayed_items:
                    sel = sugg_list.curselection()
                    idx = sel[0] if sel else 0
                    if 0 <= idx < len(displayed_items):
                        cmd_tmpl, aliases, _ = displayed_items[idx]
                        cmd_text = aliases[0]
            _close()
            if cmd_text:
                clean_cmd = cmd_text.strip()
                if clean_cmd.startswith(":"):
                    clean_cmd = clean_cmd[1:].strip()
                if clean_cmd:
                    if not self._cmd_history or self._cmd_history[-1] != clean_cmd:
                        self._cmd_history.append(clean_cmd)
                    self._exec_cmd(clean_cmd)

        def _on_tab(e=None):
            sel = sugg_list.curselection()
            if sel and displayed_items:
                idx = sel[0]
                if 0 <= idx < len(displayed_items):
                    cmd_tmpl, aliases, _ = displayed_items[idx]
                    alias_cmd = aliases[0]
                    raw = cmd_var.get().strip()
                    if raw.startswith(":"):
                        raw = raw[1:].strip()
                    parts = raw.split()
                    extra = (" " + " ".join(parts[1:])) if len(parts) > 1 else " "
                    cmd_var.set(f":{alias_cmd}{extra}")
                    ent.icursor(tk.END)
            return "break"

        def _on_down(e=None):
            sel = sugg_list.curselection()
            if displayed_items:
                curr = sel[0] if sel else -1
                nxt = min(len(displayed_items) - 1, curr + 1)
                sugg_list.selection_clear(0, tk.END)
                sugg_list.selection_set(nxt)
                sugg_list.activate(nxt)
                sugg_list.see(nxt)
            elif self._cmd_history:
                if hist_idx[0] < len(self._cmd_history) - 1:
                    hist_idx[0] += 1
                    cmd_var.set(f":{self._cmd_history[hist_idx[0]]}")
                    ent.icursor(tk.END)
                elif hist_idx[0] == len(self._cmd_history) - 1:
                    hist_idx[0] = len(self._cmd_history)
                    cmd_var.set("")
            return "break"

        def _on_up(e=None):
            sel = sugg_list.curselection()
            curr = sel[0] if sel else 0
            if curr > 0 and displayed_items:
                prev_i = curr - 1
                sugg_list.selection_clear(0, tk.END)
                sugg_list.selection_set(prev_i)
                sugg_list.activate(prev_i)
                sugg_list.see(prev_i)
            else:
                if self._cmd_history and hist_idx[0] > 0:
                    hist_idx[0] -= 1
                    cmd_var.set(f":{self._cmd_history[hist_idx[0]]}")
                    ent.icursor(tk.END)
            return "break"

        def _on_list_click(e=None):
            sel = sugg_list.curselection()
            if sel and displayed_items:
                idx = sel[0]
                if 0 <= idx < len(displayed_items):
                    cmd_tmpl, aliases, _ = displayed_items[idx]
                    cmd_var.set(f":{aliases[0]} ")
                    ent.icursor(tk.END)
                    ent.focus_set()

        def _on_list_double_click(e=None):
            sel = sugg_list.curselection()
            if sel and displayed_items:
                idx = sel[0]
                if 0 <= idx < len(displayed_items):
                    cmd_tmpl, aliases, _ = displayed_items[idx]
                    if "[" in cmd_tmpl or "<" in cmd_tmpl:
                        cmd_var.set(f":{aliases[0]} ")
                        ent.icursor(tk.END)
                        ent.focus_set()
                    else:
                        _run_and_close(aliases[0])

        ent.bind("<Return>", lambda e: _run_and_close())
        ent.bind("<Escape>", lambda e: _close())
        ent.bind("<Tab>",    _on_tab)
        ent.bind("<Down>",   _on_down)
        ent.bind("<Up>",     _on_up)
        sugg_list.bind("<Button-1>", _on_list_click)
        sugg_list.bind("<Double-Button-1>", _on_list_double_click)
        sugg_list.bind("<Return>", lambda e: _run_and_close())
        dlg.bind("<Escape>", lambda e: _close())

        self.root.update_idletasks()
        rx = self.root.winfo_rootx() + (self.root.winfo_width() - 580) // 2
        ry = self.root.winfo_rooty() + max(40, (self.root.winfo_height() - 250) // 4)
        dlg.geometry(f"580x250+{max(10, rx)}+{max(10, ry)}")

    # ── Command dispatcher ─────────────────────────────────────────────────────
    def _exec_cmd(self, raw: str):
        if not raw:
            return
        raw = raw.strip()
        if raw.startswith(":"):
            raw = raw[1:].strip()
        parts = raw.split()
        if not parts:
            return
        cmd = parts[0].lower()
        args = parts[1:]
        arg = args[0] if args else None

        # Selection & Clear
        if cmd in ("all", "selectall", "sa", "sel"):
            self._select_all()
        elif cmd in ("none", "deselect", "unselect", "desel"):
            self._clear_selection()
            self._status("Selection cleared", "#94a3b8")
            self._render()
        elif cmd in ("clear", "cls", "clr"):
            self._clear()

        # Edit Operations
        elif cmd in ("undo", "u"):
            self._undo()
        elif cmd in ("redo", "u"):
            self._redo()
        elif cmd in ("copy", "cp"):
            self._copy()
        elif cmd in ("paste", "p"):
            self._paste()
        elif cmd in ("cut", "x"):
            self._cut()
        elif cmd in ("del", "delete", "rm", "d"):
            self._delete()
        elif cmd in ("rot", "rotate", "r90"):
            deg = 90
            if args:
                try: deg = int(args[0])
                except: deg = 90
            steps = ((deg % 360) + 360) % 360 // 90
            if steps == 0: steps = 1
            targets = list(self.selected_comps) if self.selected_comps else ([self._at_cursor()] if self._at_cursor() else [])
            if not targets:
                self._status("[!] No selection or component at cursor to rotate", "#f87171")
            else:
                self._push_undo()
                for c in targets:
                    c.rot = (c.rot + steps * 90) % 360
                self._status(f"✓ Rotated {len(targets)} component(s) by {steps * 90}°", "#38bdf8")
                self._render()
        elif cmd in ("flip", "fl"):
            self._flip()

        # Component Placement with parameter support
        elif cmd in ("r", "res", "resistor"):
            if self._at_cursor():
                self._status("[!] Cell occupied — move cursor first", "#f87171"); return
            self._push_undo()
            self._clear_selection()
            val = args[0] if args else None
            c = Component("R", *self.cursor, value=val)
            self.comps.append(c)
            self.selected_comps.add(c)
            self._status(f"✓ Placed Resistor ({c.label} = {c.value}) at {self.cursor}", "#4ade80")
            self._render()

        elif cmd in ("c", "cap", "capacitor"):
            if self._at_cursor():
                self._status("[!] Cell occupied — move cursor first", "#f87171"); return
            self._push_undo()
            self._clear_selection()
            val = args[0] if args else None
            c = Component("C", *self.cursor, value=val)
            self.comps.append(c)
            self.selected_comps.add(c)
            self._status(f"✓ Placed Capacitor ({c.label} = {c.value}) at {self.cursor}", "#4ade80")
            self._render()

        elif cmd in ("l", "ind", "inductor"):
            if self._at_cursor():
                self._status("[!] Cell occupied — move cursor first", "#f87171"); return
            self._push_undo()
            self._clear_selection()
            val = args[0] if args else None
            c = Component("L", *self.cursor, value=val)
            self.comps.append(c)
            self.selected_comps.add(c)
            self._status(f"✓ Placed Inductor ({c.label} = {c.value}) at {self.cursor}", "#4ade80")
            self._render()

        elif cmd in ("v", "vsrc"):
            if self._at_cursor():
                self._status("[!] Cell occupied — move cursor first", "#f87171"); return
            self._push_undo()
            self._clear_selection()
            val = " ".join(args) if args else None
            c = Component("V", *self.cursor, value=val)
            if val:
                c.vsrc_dc = val.split()[0]
            self.comps.append(c)
            self.selected_comps.add(c)
            self._status(f"✓ Placed Voltage Source ({c.label} = {c.value}) at {self.cursor}", "#4ade80")
            self._render()

        elif cmd in ("i", "isrc"):
            if self._at_cursor():
                self._status("[!] Cell occupied — move cursor first", "#f87171"); return
            self._push_undo()
            self._clear_selection()
            val = " ".join(args) if args else None
            c = Component("I", *self.cursor, value=val)
            self.comps.append(c)
            self.selected_comps.add(c)
            self._status(f"✓ Placed Current Source ({c.label} = {c.value}) at {self.cursor}", "#4ade80")
            self._render()

        elif cmd in ("g", "gnd", "ground"):
            if self._at_cursor():
                self._status("[!] Cell occupied — move cursor first", "#f87171"); return
            self._push_undo()
            self._clear_selection()
            c = Component("G", *self.cursor)
            self.comps.append(c)
            self.selected_comps.add(c)
            self._status(f"✓ Placed Ground at {self.cursor}", "#4ade80")
            self._render()

        elif cmd in ("nmos", "pmos", "m", "mos"):
            typ = "PMOS" if cmd == "pmos" else "NMOS"
            if self._at_cursor():
                self._status("[!] Cell occupied — move cursor first", "#f87171"); return
            self._push_undo()
            self._clear_selection()
            c = Component(typ, *self.cursor)
            if args and args[0].lower() in ("min", "minimum"):
                mw, ml = self.model_config.min_wl(typ)
                c.mos_w = mw
                c.mos_l = ml
            elif args and args[0].lower() in ("default", "def", "nominal"):
                resolved = resolve_pdk(self.model_config.pdk_name) if self.model_config.pdk_name else None
                if resolved and typ in resolved.default_wl:
                    c.mos_w, c.mos_l = resolved.default_wl[typ]
                else:
                    c.mos_w, c.mos_l = ("2u" if typ=="NMOS" else "4u", "180n")
            elif len(args) >= 2:
                c.mos_w = args[0]
                c.mos_l = args[1]
            elif len(args) == 1:
                c.mos_w = args[0]
                dw, dl = self.model_config.default_wl(typ)
                if dl: c.mos_l = dl
            else:
                dw, dl = self.model_config.default_wl(typ)
                if dw or dl:
                    c.mos_w = dw
                    c.mos_l = dl
            c.update_mos_value()
            c.model_name = self.model_config.model_name(typ)
            self.comps.append(c)
            self.selected_comps.add(c)
            self._status(f"✓ Placed {typ} ({c.label} {c.value}) at {self.cursor}", "#4ade80")
            self._render()

        elif cmd in ("npn", "pnp", "bjt"):
            typ = "PNP" if cmd == "pnp" else "NPN"
            if self._at_cursor():
                self._status("[!] Cell occupied — move cursor first", "#f87171"); return
            self._push_undo()
            self._clear_selection()
            c = Component(typ, *self.cursor)
            model = args[0] if args else self.model_config.model_name(typ)
            if model:
                c.model_name = model
                if not model.endswith("_GENERIC"):
                    c.value = model
            self.comps.append(c)
            self.selected_comps.add(c)
            self._status(f"✓ Placed {typ} ({c.label} = {c.value}) at {self.cursor}", "#4ade80")
            self._render()

        elif cmd in ("pin", "in", "out", "inout", "vdd", "vss"):
            _map = {"pin":"PIN_IN","in":"PIN_IN","out":"PIN_OUT",
                    "inout":"PIN_INOUT","vdd":"PIN_VDD","vss":"PIN_VSS"}
            typ = _map.get(cmd, "PIN_IN")
            lbl_name = None
            if cmd == "pin":
                if len(args) >= 2:
                    lbl_name = args[0]
                    typ = _map.get(args[1].lower(), "PIN_IN")
                elif len(args) == 1:
                    if args[0].lower() in _map:
                        typ = _map[args[0].lower()]
                    else:
                        lbl_name = args[0]
            elif args:
                lbl_name = args[0]

            if self._at_cursor():
                self._status("[!] Cell occupied — move cursor first", "#f87171"); return
            self._push_undo()
            self._clear_selection()
            c = Component(typ, *self.cursor, label=lbl_name)
            self.comps.append(c)
            self.selected_comps.add(c)
            self._status(f"✓ Placed Pin ({c.label} {typ}) at {self.cursor}", "#4ade80")
            self._render()

        # Wiring & Labels
        elif cmd in ("w", "wire"):
            if cmd == "w" and args:
                self._save_json(args[0])
            else:
                self._start_wire()

        elif cmd in ("lbl", "label", "t", "net"):
            if args:
                text = " ".join(args)
                gx, gy = self.cursor
                self._push_undo()
                existing = next((l for l in self.wlbls if l.gx == gx and l.gy == gy), None)
                if existing:
                    existing.text = text
                else:
                    wl = WireLabel(gx, gy, text)
                    self.wlbls.append(wl)
                    self.selected_wlbls = {wl}
                self._status(f"✓ Net label '{text}' set at ({gx},{gy})", "#38bdf8")
                self._render()
            else:
                self._label_wire()

        # PDK & Corner
        elif cmd in ("pdk", "pdks"):
            if not arg or arg in ("status", "list"):
                pdks = detect_installed_pdks()
                cur = getattr(self.model_config, "pdk_name", "") or "none (inline)"
                avail = ", ".join(f"{k} ({'✓' if v.available else '✗'})" for k, v in pdks.items())
                self._status(f"Active PDK: {cur}  ·  Available: {avail}  ·  Usage: :pdk <sky130|gf180|ihp|none> [corner]", "#38bdf8")
            elif arg in ("none", "inline", "clear", "custom"):
                self.model_config.apply_pdk("")
                self._model_names_cache = {}
                try: self.btn_models.config(text="Models")
                except Exception: pass
                self._status("✓ Switched to Inline Level 1 models", "#4ade80")
                self._render()
            else:
                pdk_key = arg.lower()
                resolved = resolve_pdk(pdk_key)
                if not resolved:
                    self._status(f"[!] Unknown PDK: '{arg}'. Options: sky130, gf180, ihp, none", "#ef4444")
                else:
                    corner = parts[2].lower() if len(parts) > 2 else resolved.default_corner
                    self.model_config.apply_pdk(resolved.key, corner)
                    self._model_names_cache = dict(resolved.models)
                    try: self.btn_models.config(text=f"Models: {resolved.key.upper()}")
                    except Exception: pass
                    nw, nl = self.model_config.default_wl("NMOS")
                    pw, pl = self.model_config.default_wl("PMOS")
                    upd_cnt = 0
                    for c in self.comps:
                        if c.type == "NMOS":
                            c.mos_w, c.mos_l = nw, nl
                            c.model_name = self.model_config.model_name("NMOS")
                            c.update_mos_value()
                            upd_cnt += 1
                        elif c.type == "PMOS":
                            c.mos_w, c.mos_l = pw, pl
                            c.model_name = self.model_config.model_name("PMOS")
                            c.update_mos_value()
                            upd_cnt += 1
                    status_icon = "✓" if resolved.available else "[!] (files not found)"
                    upd_msg = f"  ·  Applied to {upd_cnt} schematic FET(s)" if upd_cnt else ""
                    self._status(f"{status_icon} PDK set to {resolved.display_name} [{corner}]  ·  Min W/L: NMOS={nw}/{nl}, PMOS={pw}/{pl}{upd_msg}",
                                 "#4ade80" if resolved.available else "#f59e0b")
                    self._render()
                    if self._netlist_visible:
                        self._rebuild_netlist()

        elif cmd == "corner":
            if not arg:
                self._status(f"Active corner: [{self.model_config.corner}]  ·  Usage: :corner <tt|ss|ff|sf|fs>", "#38bdf8")
            else:
                c_name = arg.lower()
                self.model_config.corner = c_name
                self._status(f"✓ Simulation corner set to: [{c_name}]", "#4ade80")
                self._render()

        elif cmd in ("wl", "wlmode", "sizing"):
            if not arg or arg in ("status", "info"):
                nw, nl = self.model_config.default_wl("NMOS")
                pw, pl = self.model_config.default_wl("PMOS")
                pdk_info = self.model_config.pdk_name.upper() if self.model_config.pdk_name else "Generic"
                self._status(f"PDK: [{pdk_info}]  ·  Min W/L: NMOS={nw}/{nl}, PMOS={pw}/{pl}  ·  Usage: :wl [apply]", "#38bdf8")
            elif arg.lower() in ("apply", "reset", "all", "min"):
                self._push_undo()
                nw, nl = self.model_config.default_wl("NMOS")
                pw, pl = self.model_config.default_wl("PMOS")
                count = 0
                for c in self.comps:
                    if c.type in ("NMOS", "PMOS"):
                        dw, dl = self.model_config.default_wl(c.type)
                        c.mos_w = dw
                        c.mos_l = dl
                        c.update_mos_value()
                        count += 1
                self._status(f"✓ Applied PDK min W/L (NMOS={nw}/{nl}, PMOS={pw}/{pl}) to {count} transistor(s)", "#4ade80")
                self._render()
                if self._netlist_visible:
                    self._rebuild_netlist()
            else:
                self._status("Usage: :wl [apply]", "#f59e0b")

        elif cmd in ("models", "model"):
            self._open_model_manager()

        # Simulation
        elif cmd in ("sim", "analysis", "simulate"):
            self._open_sim_dialog()
        elif cmd == "run":
            self._run_simulation()
        elif cmd == "op":
            self.sim_config.set_enabled("OP", True)
            self._status(f"✓ Enabled Operating Point (.op) — Active: {', '.join(self.sim_config.active_analyses())}", "#38bdf8")
            if self._netlist_visible: self._rebuild_netlist()
        elif cmd == "tran":
            self.sim_config.set_enabled("TRAN", True)
            if len(args) >= 2:
                self.sim_config.tstop = args[0]
                self.sim_config.tstep = args[1]
            elif len(args) == 1:
                self.sim_config.tstop = args[0]
            if len(args) >= 3:
                self.sim_config.params["TRAN"][2] = args[2]
            self._status(f"✓ Enabled Transient: {ANALYSES['TRAN']['spice'](self.sim_config.params['TRAN'])} — Active: {', '.join(self.sim_config.active_analyses())}", "#38bdf8")
            if self._netlist_visible: self._rebuild_netlist()
        elif cmd == "ac":
            self.sim_config.set_enabled("AC", True)
            if len(args) >= 4:
                self.sim_config.ac_variation = args[0]
                self.sim_config.ac_points = args[1]
                self.sim_config.fstart = args[2]
                self.sim_config.fstop = args[3]
            elif len(args) >= 2:
                self.sim_config.fstart = args[0]
                self.sim_config.fstop = args[1]
            self._status(f"✓ Enabled AC Sweep: {ANALYSES['AC']['spice'](self.sim_config.params['AC'])} — Active: {', '.join(self.sim_config.active_analyses())}", "#38bdf8")
            if self._netlist_visible: self._rebuild_netlist()
        elif cmd == "dc":
            self.sim_config.set_enabled("DC", True)
            if len(args) >= 4:
                self.sim_config.dc_source = args[0]
                self.sim_config.dc_start = args[1]
                self.sim_config.dc_stop = args[2]
                self.sim_config.dc_step = args[3]
            elif len(args) >= 3:
                self.sim_config.dc_start = args[0]
                self.sim_config.dc_stop = args[1]
                self.sim_config.dc_step = args[2]
            self._status(f"✓ Enabled DC Sweep: {ANALYSES['DC']['spice'](self.sim_config.params['DC'])} — Active: {', '.join(self.sim_config.active_analyses())}", "#38bdf8")
            if self._netlist_visible: self._rebuild_netlist()
        elif cmd == "noise":
            self.sim_config.set_enabled("NOISE", True)
            if len(args) >= 2:
                self.sim_config.params["NOISE"][0] = args[0]
                self.sim_config.params["NOISE"][1] = args[1]
            if len(args) >= 6:
                self.sim_config.params["NOISE"][2] = args[2]
                self.sim_config.params["NOISE"][3] = args[3]
                self.sim_config.params["NOISE"][4] = args[4]
                self.sim_config.params["NOISE"][5] = args[5]
            self._status(f"✓ Enabled Noise: {ANALYSES['NOISE']['spice'](self.sim_config.params['NOISE'])} — Active: {', '.join(self.sim_config.active_analyses())}", "#38bdf8")
            if self._netlist_visible: self._rebuild_netlist()
        elif cmd == "tf":
            self.sim_config.set_enabled("TF", True)
            if len(args) >= 2:
                self.sim_config.params["TF"][0] = args[0]
                self.sim_config.params["TF"][1] = args[1]
            elif len(args) == 1:
                self.sim_config.params["TF"][0] = args[0]
            self._status(f"✓ Enabled Transfer Function: {ANALYSES['TF']['spice'](self.sim_config.params['TF'])} — Active: {', '.join(self.sim_config.active_analyses())}", "#38bdf8")
            if self._netlist_visible: self._rebuild_netlist()
        elif cmd == "pz":
            self.sim_config.set_enabled("PZ", True)
            for i, val in enumerate(args[:6]):
                self.sim_config.params["PZ"][i] = val
            self._status(f"✓ Enabled Pole-Zero: {ANALYSES['PZ']['spice'](self.sim_config.params['PZ'])} — Active: {', '.join(self.sim_config.active_analyses())}", "#38bdf8")
            if self._netlist_visible: self._rebuild_netlist()
        elif cmd == "sens":
            self.sim_config.set_enabled("SENS", True)
            if len(args) >= 1:
                self.sim_config.params["SENS"][0] = args[0]
            self._status(f"✓ Enabled Sensitivity: {ANALYSES['SENS']['spice'](self.sim_config.params['SENS'])} — Active: {', '.join(self.sim_config.active_analyses())}", "#38bdf8")
            if self._netlist_visible: self._rebuild_netlist()
        elif cmd == "disto":
            self.sim_config.set_enabled("DISTO", True)
            for i, val in enumerate(args[:5]):
                self.sim_config.params["DISTO"][i] = val
            self._status(f"✓ Enabled Distortion: {ANALYSES['DISTO']['spice'](self.sim_config.params['DISTO'])} — Active: {', '.join(self.sim_config.active_analyses())}", "#38bdf8")
            if self._netlist_visible: self._rebuild_netlist()
        elif cmd in ("nosim", "unsim", "disablesim"):
            if not arg:
                self._status("Usage: :nosim <op|tran|ac|dc|noise|tf|pz|sens|disto>", "#f59e0b")
            else:
                k = arg.strip().upper()
                if k in ANALYSES:
                    self.sim_config.set_enabled(k, False)
                    active_str = ', '.join(self.sim_config.active_analyses()) or "(none)"
                    self._status(f"✓ Disabled {k} analysis — Active: {active_str}", "#38bdf8")
                    if self._netlist_visible: self._rebuild_netlist()
                else:
                    self._status(f"[!] Unknown analysis '{arg}'", "#f87171")
        elif cmd in ("raw", "showraw"):
            self._reveal_raw_file()

        # Files & Export
        elif cmd == "save":
            if arg: self._save_json(arg)
            else: self._dialog_save()
        elif cmd in ("load", "open"):
            if arg: self._load_json(arg)
            else: self._dialog_load()
        elif cmd in ("netlist", "nl", "net"):
            if arg: self._save_netlist_to(arg)
            else: self._toggle_netlist_panel()
        elif cmd in ("savepng", "png"):
            if arg: self._save_raster(arg)
            else: self._dialog_save_image()
        elif cmd in ("savesvg", "svg"):
            if arg: self._save_svg(arg)
            else: self._dialog_save_svg()
        elif cmd in ("doc", "docimg", "savedoc"):
            if arg: self._save_doc_image(arg)
            else: self._dialog_save_doc_image()
        elif cmd == "export":
            if not arg:
                self._status("Usage: :export <png|svg|netlist|doc> [filename]", "#38bdf8")
            elif arg.lower() in ("png", "raster"):
                t = args[1] if len(args) > 1 else None
                if t: self._save_raster(t)
                else: self._dialog_save_image()
            elif arg.lower() == "svg":
                t = args[1] if len(args) > 1 else None
                if t: self._save_svg(t)
                else: self._dialog_save_svg()
            elif arg.lower() in ("netlist", "cir"):
                t = args[1] if len(args) > 1 else None
                if t: self._save_netlist_to(t)
                else: self._dialog_save_netlist()
            elif arg.lower() in ("doc", "docimg"):
                t = args[1] if len(args) > 1 else None
                if t: self._save_doc_image(t)
                else: self._dialog_save_doc_image()

        # View & Navigation
        elif cmd in ("zoom", "z"):
            if not arg:
                self._status(f"Zoom: {self._zoom_pct()}%  ·  Usage: :zoom <pct|+|-|fit>", "#38bdf8")
            elif arg in ("+", "in"):
                self._zoom(+8)
            elif arg in ("-", "out"):
                self._zoom(-8)
            elif arg in ("fit", "reset", "100"):
                self._zoom_to(100)
            else:
                try: self._zoom_to(int(arg.replace("%", "")))
                except: self._status("[!] zoom needs a number, +, -, or fit", "#f87171")
        elif cmd in ("goto", "pos", "move", "coord"):
            if len(args) >= 2:
                try:
                    gx, gy = int(args[0]), int(args[1])
                    gx = max(0, min(COLS - 1, gx))
                    gy = max(0, min(ROWS - 1, gy))
                    self.cursor = (gx, gy)
                    self._scroll_to_cursor()
                    self._render()
                    self._status(f"Cursor moved to ({gx},{gy})", "#38bdf8")
                except Exception:
                    self._status("[!] goto needs coordinates: :goto <x> <y>", "#f87171")
            else:
                self._status("Usage: :goto <x> <y>", "#38bdf8")
        elif cmd in ("mouse", "m"):
            self._toggle_mouse()

        # System & Help
        elif cmd in ("quit", "exit", "q"):
            self.root.destroy()
        elif cmd in ("help", "?"):
            self._status("PALETTE: :r [val] · :c [val] · :nmos [w] [l] · :wire · :sim · :run · :pdk · :undo · :save · Tab to complete", "#38bdf8")
        else:
            self._status(f"[!] Unknown: '{cmd}' — try :help or press Tab for suggestions", "#f87171")

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
                # Refresh parsed-model cache if PDK or an external file is configured
                pdk_name = getattr(self.model_config, "pdk_name", "")
                if pdk_name:
                    resolved = resolve_pdk(pdk_name)
                    if resolved:
                        self._model_names_cache = dict(resolved.models)
                        try:
                            self.btn_models.config(text=f"Models: {pdk_name.upper()}")
                        except Exception:
                            pass
                else:
                    fp = self.model_config.file_path
                    if fp and os.path.isfile(fp):
                        self._model_names_cache = parse_model_file(fp)
                    else:
                        self._model_names_cache = {}
                    try:
                        self.btn_models.config(text="Models")
                    except Exception:
                        pass
            self._status(
                f"✓ Loaded {len(self.comps)} comp · {len(self.wires)} wire"
                f" from {os.path.basename(path)}", "#4ade80")
            self._current_file = path
            stem = os.path.splitext(os.path.basename(path))[0]
            self.root.title(f"Vischem  v0.1  —  {stem}")
            self._undo_stack.clear()
            self._redo_stack.clear()
            self._update_undo_redo_ui()
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
            if comp.type in ("NMOS", "PMOS") and (comp.mos_w or comp.mos_l):
                comp.update_mos_value()
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
        Main Run handler — called by the Run button.
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
        active_ans = self.sim_config.active_analyses() if hasattr(self.sim_config, "active_analyses") else ([self.sim_config.analysis] if getattr(self.sim_config, "analysis", None) else [])
        if not self.sim_config or not active_ans:
            self._status(
                "[!] No simulation configured — open Simulation first",
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
        active_dirs = self.sim_config.spice_lines() if hasattr(self.sim_config, "spice_lines") else [self.sim_config.spice_line()]
        directives_log = "".join(f"     {d}\n" for d in active_dirs)
        self._sim_log_write(
            f">> Running simulation: {stem}\n"
            f"   Netlist   : {cir_path}\n"
            f"   Output    : {raw_path}\n"
            f"   Solver    : {self._ngspice_exe}\n"
            f"   Analyses  : {', '.join(active_ans)}\n"
            f"   Directives:\n{directives_log}"
            + "─" * 52 + "\n",
            tag="header")

        self.btn_run.config(text="Running…", state=tk.DISABLED)
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
        self.btn_run.config(text="Run", state=tk.NORMAL)

        sep = "─" * 52
        if sim.success:
            self._last_raw_path = sim.raw_path
            self.btn_show_raw.config(fg="#4ade80")
            msg = (f"\n{sep}\n"
                   f"✓  Simulation complete  ({sim.duration_s:.2f}s)\n"
                   f"   Results → {sim.raw_path}\n")
            self._sim_log_write(msg, tag="ok")
            self.lbl_sim_header.config(text="  Simulation complete",
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
            self.lbl_sim_header.config(text="  Simulation failed",
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
        self.lbl_sim_header.config(text="  Simulation Log", fg="#cbd5e1")

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

    # ── Separate Netlist Viewer Window ──────────────────────────────────────────
    def _open_netlist_window(self):
        """Open or focus the separate Netlist viewer window."""
        if getattr(self, "_netlist_win", None) and self._netlist_win.winfo_exists():
            self._netlist_win.lift()
            self._netlist_win.focus_set()
            self._rebuild_netlist()
            return

        win = tk.Toplevel(self.root)
        self._netlist_win = win
        self._netlist_visible = True
        win.title("Vischem  —  SPICE Netlist Viewer")
        win.configure(bg=PANEL_BG)
        win.minsize(440, 320)

        # Smart positioning alongside the main schematic window
        self.root.update_idletasks()
        rx = self.root.winfo_rootx() + self.root.winfo_width() + 10
        ry = self.root.winfo_rooty()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = 600, 660
        if rx + w > sw:
            rx = max(20, self.root.winfo_rootx() + 40)
            ry = max(20, self.root.winfo_rooty() + 40)
        win.geometry(f"{w}x{h}+{rx}+{ry}")

        # Toolbar header frame
        nlh = tk.Frame(win, bg=PANEL_ALT, pady=5, padx=8)
        nlh.pack(fill=tk.X)

        tk.Label(nlh, text="SPICE Netlist", bg=PANEL_ALT, fg="#cbd5e1",
                 font=("Courier", 10, "bold")).pack(side=tk.LEFT)

        # PDK chip
        cur_pdk = getattr(self.model_config, "pdk_name", "")
        pdk_text = f"PDK: {cur_pdk.upper()} [{getattr(self.model_config, 'corner', 'tt')}]" if cur_pdk else "Inline L1"
        self.nl_pdk_chip = tk.Label(nlh, text=f" [{pdk_text}] ", bg="#232535", fg="#38bdf8",
                                    font=("Courier", 8, "bold"), padx=4, pady=1)
        self.nl_pdk_chip.pack(side=tk.LEFT, padx=(8, 0))

        # Action Buttons
        tk.Button(nlh, text="Close",
                  command=self._close_netlist_win,
                  bg=BTN_BG, fg="#94a3b8", activebackground=BTN_ACTIVE_BG,
                  activeforeground="#ffffff", relief="flat", font=("Courier", 8, "bold"),
                  cursor="hand2", padx=8).pack(side=tk.RIGHT, padx=(4, 0))

        tk.Button(nlh, text="Save .cir",
                  command=self._dialog_save_netlist,
                  bg=BTN_BG, fg=BTN_FG, activebackground=BTN_ACTIVE_BG,
                  activeforeground=BTN_ACTIVE_FG, relief="flat", font=("Courier", 8, "bold"),
                  cursor="hand2", padx=8).pack(side=tk.RIGHT, padx=4)

        self.btn_nl_copy = tk.Button(nlh, text="Copy",
                                     command=self._copy_netlist_to_clipboard,
                                     bg=BTN_BG, fg="#38bdf8", activebackground=BTN_ACTIVE_BG,
                                     activeforeground="#ffffff", relief="flat", font=("Courier", 8, "bold"),
                                     cursor="hand2", padx=8)
        self.btn_nl_copy.pack(side=tk.RIGHT, padx=4)

        tk.Button(nlh, text="Rebuild", command=self._rebuild_netlist,
                  bg=BTN_PRIMARY_BG, fg=BTN_PRIMARY_FG, activebackground=BTN_PRIMARY_ACT,
                  activeforeground="#ffffff", relief="flat", font=("Courier", 8, "bold"),
                  cursor="hand2", padx=8).pack(side=tk.RIGHT, padx=4)

        # Warnings label
        self.nl_warn = tk.Label(win, text="",
                                bg="#2a1f10", fg="#fbbf24",
                                font=("Courier", 8), anchor="w", padx=8, pady=3, wraplength=560)
        self.nl_warn.pack(fill=tk.X)

        # Nets summary label
        self.nl_nets = tk.Label(win, text="",
                                bg=PANEL_BG, fg="#64748b",
                                font=("Courier", 8), anchor="w", padx=8, pady=2)
        self.nl_nets.pack(fill=tk.X)

        # Text area container with scrollbars
        nl_tf = tk.Frame(win, bg=PANEL_BG)
        nl_tf.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 4))
        nl_vsb = tk.Scrollbar(nl_tf, orient=tk.VERTICAL, bg=PANEL_BG, troughcolor=BORDER)
        nl_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        nl_hsb = tk.Scrollbar(nl_tf, orient=tk.HORIZONTAL, bg=PANEL_BG, troughcolor=BORDER)
        nl_hsb.pack(side=tk.BOTTOM, fill=tk.X)

        self.nl_text = tk.Text(nl_tf,
                               bg="#12131a", fg="#e2e8f0", font=("Courier", 10),
                               insertbackground=CURSOR_C, selectbackground="#1e3a5f",
                               relief="flat", bd=0, wrap=tk.NONE,
                               yscrollcommand=nl_vsb.set, xscrollcommand=nl_hsb.set)
        self.nl_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        nl_vsb.config(command=self.nl_text.yview)
        nl_hsb.config(command=self.nl_text.xview)

        # Syntax tags
        self.nl_text.tag_config("comment",  foreground="#64748b")
        self.nl_text.tag_config("control",  foreground="#a78bfa")
        self.nl_text.tag_config("element",  foreground="#f1f5f9")
        self.nl_text.tag_config("net",      foreground="#38bdf8")
        self.nl_text.tag_config("dot",      foreground="#c084fc")
        self.nl_text.tag_config("warning",  foreground="#fbbf24")
        self.nl_text.tag_config("value",    foreground="#67e8f9")
        self.nl_text.tag_config("end",      foreground="#4ade80")

        # Bottom info bar
        self.nl_status = tk.Label(win, text="", bg=PANEL_ALT, fg="#64748b",
                                  font=("Courier", 8), anchor="w", padx=8, pady=3)
        self.nl_status.pack(fill=tk.X, side=tk.BOTTOM)

        # Window protocols & bindings
        win.protocol("WM_DELETE_WINDOW", self._close_netlist_win)
        win.bind("<Escape>", lambda e: self._close_netlist_win())

        self.btn_netlist.config(bg=BTN_ACTIVE_BG, fg=BTN_ACTIVE_FG)
        self._rebuild_netlist()

    def _close_netlist_win(self):
        """Close the separate netlist viewer window."""
        self._netlist_visible = False
        if getattr(self, "_copy_timer", None):
            try:
                self.root.after_cancel(self._copy_timer)
            except Exception:
                pass
            self._copy_timer = None
        if getattr(self, "_netlist_win", None):
            try:
                self._netlist_win.destroy()
            except Exception:
                pass
            self._netlist_win = None
        self.nl_text = None
        self.nl_warn = None
        self.nl_nets = None
        self.nl_status = None
        self.nl_pdk_chip = None
        self.btn_nl_copy = None
        try:
            self.btn_netlist.config(bg=BTN_BG, fg=BTN_FG)
        except Exception:
            pass

    def _copy_netlist_to_clipboard(self):
        """Copy current netlist text to clipboard."""
        if getattr(self, "nl_text", None):
            txt = self.nl_text.get("1.0", tk.END).strip()
            if txt:
                try:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(txt)
                    self._status("✓ Netlist copied to clipboard", "#4ade80")
                    if getattr(self, "btn_nl_copy", None) and self.btn_nl_copy.winfo_exists():
                        self.btn_nl_copy.config(text="✓ Copied!")
                        def _reset_btn():
                            try:
                                if getattr(self, "btn_nl_copy", None) and self.btn_nl_copy.winfo_exists():
                                    self.btn_nl_copy.config(text="Copy")
                            except Exception:
                                pass
                        self._copy_timer = self.root.after(1500, _reset_btn)
                except Exception as e:
                    self._status(f"[!] Clipboard error: {e}", "#f87171")

    def _toggle_netlist_panel(self):
        """Toggle the separate Netlist window."""
        if getattr(self, "_netlist_win", None) and self._netlist_win.winfo_exists():
            self._close_netlist_win()
        else:
            self._open_netlist_window()

    def _rebuild_netlist(self):
        if not self._netlist_visible or not getattr(self, "_netlist_win", None) or not self._netlist_win.winfo_exists():
            return
        if not _HAS_NETLIST:
            self._status("[!] netlist.py not found", "#f87171")
            return
        result = generate_netlist(self.comps, self.wires, self.wlbls,
                                   sim_config=self.sim_config,
                                   model_config=self.model_config,
                                   title="Vischem")
        self._last_result = result
        self._render_netlist_panel(result)

    def _render_netlist_panel(self, result):
        import re
        if not getattr(self, "nl_text", None) or not getattr(self, "_netlist_win", None) or not self._netlist_win.winfo_exists():
            return
        if result.warnings:
            self.nl_warn.config(text="⚠  " + "  ·  ".join(result.warnings), bg="#2a1f10", fg="#fbbf24")
        else:
            self.nl_warn.config(text="  ✓ No netlist warnings", fg="#4ade80", bg=PANEL_BG)

        net_summary = "  ".join(f"{k}:{len(v)}pt" for k, v in sorted(result.nets.items()))
        self.nl_nets.config(text=f"  nets: {net_summary}")

        cur_pdk = getattr(self.model_config, "pdk_name", "")
        pdk_text = f"PDK: {cur_pdk.upper()} [{getattr(self.model_config, 'corner', 'tt')}]" if cur_pdk else "Inline L1"
        if getattr(self, "nl_pdk_chip", None):
            self.nl_pdk_chip.config(text=f" [{pdk_text}] ")

        txt = self.nl_text
        txt.config(state=tk.NORMAL)
        txt.delete("1.0", tk.END)
        lines = result.netlist.splitlines()
        for line in lines:
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
        txt.config(state=tk.DISABLED)
        txt.see("1.0")

        if getattr(self, "nl_status", None):
            sim_info = f"Sim: {self.sim_config.analysis_type.upper()}"
            self.nl_status.config(text=f"  {len(lines)} lines · {len(self.comps)} components · {len(self.wires)} wires · {sim_info}")

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
        """Called from panel 'Save .cir' button."""
        self._dialog_save_netlist()

    def _clear(self):
        if self.comps or self.wires or self.wlbls:
            self._push_undo()
        self.comps=[]; self.wires=[]; self.wlbls=[]
        self._clear_selection()
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
            w_sel = (w in self.selected_wires) and not doc_mode
            w_col = "#60a5fa" if w_sel else WIRE_C
            w_w   = wire_w + 1.2 if w_sel else wire_w
            cv.create_line(w.x1*GS,w.y1*GS,w.x2*GS,w.y2*GS,
                           fill=w_col, width=w_w, capstyle=tk.ROUND)

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
            wl_sel = (wl in self.selected_wlbls) and not doc_mode
            wx, wy = wl.gx * GS, wl.gy * GS
            # Small flag background
            tw = max(30, len(wl.text) * max(6, GS//9))
            th = max(14, GS // 5)
            cv.create_rectangle(
                wx - tw//2 - 3, wy - th//2 - 2,
                wx + tw//2 + 3, wy + th//2 + 2,
                fill=SEL_RECT if wl_sel else "#1e293b",
                outline=SEL_OUT if wl_sel else WIRE_LBL_COLOR,
                width=1.5 if wl_sel else 1.0)
            cv.create_text(wx, wy,
                text=wl.text, fill="#ffffff" if wl_sel else WIRE_LBL_COLOR,
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
        has_sel = self.has_selection()
        for comp in self.comps:
            sel = ((comp in self.selected_comps) or (not has_sel and comp.gx==gx_c and comp.gy==gy_c)) and not doc_mode
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
                if comp.type in ("NMOS", "PMOS") and (comp.mos_w or comp.mos_l):
                    comp.update_mos_value()
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

            # Rubberband marquee box selection
            if getattr(self, "_box_sel_active", False):
                bx0 = getattr(self, "_box_sel_x0", 0)
                by0 = getattr(self, "_box_sel_y0", 0)
                bx1 = getattr(self, "_box_sel_x1", 0)
                by1 = getattr(self, "_box_sel_y1", 0)
                cv.create_rectangle(
                    min(bx0, bx1), min(by0, by1),
                    max(bx0, bx1), max(by0, by1),
                    fill=SEL_RECT, outline=SEL_OUT, width=1.0, dash=(4, 3))

        # Real-time update for separate Netlist window if open
        if getattr(self, "_netlist_visible", False) and getattr(self, "_netlist_win", None) and self._netlist_win.winfo_exists():
            sig = (len(self.comps), len(self.wires), len(self.wlbls),
                   tuple((c.uid, c.gx, c.gy, c.value, c.label, c.rot, getattr(c, "flip", False)) for c in self.comps),
                   getattr(self.model_config, "pdk_name", ""),
                   getattr(self.model_config, "corner", ""),
                   getattr(self.sim_config, "analysis_type", ""),
                   self.sim_config.spice_line())
            if sig != getattr(self, "_last_netlist_sig", None):
                self._last_netlist_sig = sig
                self._rebuild_netlist()

        # Topbar
        self.lbl_coord.config(text=f"({self.cursor[0]},{self.cursor[1]})")
        self.lbl_zoom.config(text=f"{self._zoom_pct()}%")
        if self.has_selection():
            n_c = len(self.selected_comps)
            n_w = len(self.selected_wires)
            n_l = len(self.selected_wlbls)
            parts = []
            if n_c: parts.append(f"{n_c} comp{'s' if n_c!=1 else ''}")
            if n_w: parts.append(f"{n_w} wire{'s' if n_w!=1 else ''}")
            if n_l: parts.append(f"{n_l} label{'s' if n_l!=1 else ''}")
            self.lbl_info.config(text=f"[{', '.join(parts)} selected]")
        else:
            c = self._at_cursor()
            flip_tag = "  ⟺" if (c and c.flip) else ""
            self.lbl_info.config(
                text=f"· {c.label}  {c.value}{flip_tag}" if c else "")
        bg_,fg_ = MODE_COLS.get(self.mode,("#232535","#cbd5e1"))
        self.lbl_mode.config(text=self.mode, bg=bg_, fg=fg_)

        if getattr(self, "_active_status", None):
            self.lbl_status.config(text=self._active_status[0], fg=self._active_status[1])
        else:
            pil_note = "" if _PILLOW else "  [pip install pillow for PNG]"
            self.lbl_status.config(
                text=f"{len(self.comps)} comp · {len(self.wires)} wire · "
                     f"{len(self.wlbls)} net label  │  "
                     "mouse=drag/move · Ctrl+Z/Y=undo/redo · Ctrl+C/V=copy/paste · "
                     "arrows · R/C/L/V/I/G · W=wire · T=net-label · Spc=rot · F=flip · E=edit · :=cmd{pil_note}",
                fg="#94a3b8")


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    Editor(root)
    root.mainloop()
