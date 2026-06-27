# Vischem  v0.1

**Visual Schematic Editor for analog and mixed-signal circuit design.**

Draw schematics, configure device models, export SPICE netlists, and simulate with NGspice.

---

## Requirements

- Python 3.10 or newer — https://www.python.org/downloads/
- Pillow *(optional)* — enables PNG / JPEG / BMP and documentation image export
- NGspice *(optional)* — for running the exported `.cir` netlist

## Installation

```bash
# 1. Clone or unzip the project
cd vischem

# 2. Install optional Python dependency
pip install pillow

# 3. Run
python main.py
```

NGspice is a separate system install and is not required to draw schematics or export netlists:

| OS | Command |
|---|---|
| Ubuntu / Debian | `sudo apt install ngspice` |
| Windows | Installer at https://ngspice.sourceforge.io/download.html |
| macOS | `brew install ngspice` |

---

## Project structure

```
vischem/
├── main.py            ← entry point — run this
├── editor/
│   ├── app.py         ← main editor window and UI logic
│   └── netlist.py     ← schematic → SPICE netlist generator
├── symbols/           ← drawing functions for each component type
├── examples/          ← sample schematics (coming soon)
├── requirements.txt
└── README.md
```

---

## Hotkeys

| Key | Action |
|---|---|
| `↑ ↓ ← →` | Move cursor |
| `R` | Place Resistor |
| `C` | Place Capacitor |
| `L` | Place Inductor |
| `V` | Place Voltage source |
| `I` | Place Current source |
| `G` | Place Ground |
| `W` | Wire mode  (Enter = commit, Esc = cancel) |
| `Space` | Rotate 90° |
| `F` | Flip (horizontal mirror) |
| `E` | Open Properties dialog |
| `T` | Add net label |
| `M` | Toggle mouse mode |
| `+ / -` | Zoom in / out |
| `Del` | Delete component at cursor |
| `:` | Open command dialog |

---

## Command dialog  `:`

Type `:` then one of these commands:

```
nmos  pmos  npn  pnp     Place transistor
in  out  inout  vdd  vss Place port / power symbol
sim                       Simulation setup
save                      Save schematic (.json / .svg / .png …)
load                      Load schematic (.json)
netlist                   Export SPICE netlist (.cir)
doc                       Export black-on-white documentation image
zoom <pct>                Set zoom level (e.g. zoom 150)
clear                     Clear canvas
help                      List all commands
```

---

## Voltage source waveforms

Press `E` on a placed `V` source to open the waveform dialog.
Supported types: **DC**, **AC**, **SIN**, **PULSE**, **EXP**, **PWL**, **SFFM**.

Each transient waveform (SIN / PULSE / EXP / PWL / SFFM) has independent
**DC bias** and **AC magnitude + phase** fields, so a single source can
participate in `.op`, `.ac`, and `.tran` analyses simultaneously.

---

## Model Manager  `⚛ Models`

Configure device models project-wide:

- **Inline** — built-in SPICE Level 1 parameters, no file needed
- **External file** — point to a `.sp` or `.spi` file (`.include`)
- **Library file** — point to a `.lib` file with a corner (`.lib "file" tt`)

The tool parses the file and populates model name dropdowns automatically.
When you press `E` on a MOSFET or BJT, pick the model from the dropdown —
no manual typing of model names.

---

## Netlist export

The exported `.cir` file is ready for NGspice batch mode:

```bash
ngspice -b my_circuit.cir
```

---

## License

See `LICENSE`.
