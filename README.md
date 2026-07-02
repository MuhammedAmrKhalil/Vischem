## **This repo stands with Palestine !!**
# Vischem  v0.1

**Visual Schematic Editor for VLSI design**

Draw schematics, configure device models, export SPICE netlists, and simulate with NGspice.

---

## Requirements

- Python 3.10 or newer — https://www.python.org/downloads/
- Pillow  — enables image export
- NGspice — for running the exported netlist

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
| shift + `:` | Open command dialog |

---

## Command dialog

Press shift + `:` then type one of these commands:

```
nmos  pmos  npn  pnp     Place transistor
in  out  inout  vdd  vss Place port / power symbol
sim                       Simulation setup
save                      Save schematic (.json / .svg / .png …)
load                      Load schematic (.json)
netlist                   Export SPICE netlist (.cir)
doc                       Export black-on-white documentation image
clear                     Clear canvas
```

---

## Model Manager  `Models`

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
