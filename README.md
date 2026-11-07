## **This repo stands with Palestine !!**
# Vischem  v0.2

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

## Mouse Controls

Vischem features full mouse integration designed for an intuitive visual workflow:

| Mouse Action | Description |
|---|---|
| **Hover / Movement** | The canvas grid cursor smoothly follows the mouse pointer in real time, updating the coordinate display `(X, Y)` and hovering component information in the topbar |
| **Left Click** | Select a component or place the grid cursor at a specific cell |
| **Left Drag** | Drag and drop any component or wire label across the canvas to reposition it (with automatic cell collision avoidance) |
| **Shift + Left Drag** | Move a component while automatically stretching connected wire endpoints attached to its pins |
| **Double Click** | Open the type-aware Properties dialog for the clicked component (equivalent to pressing `E`) |
| **Right Click** | Rotate the clicked component 90° clockwise (or cancel active wire routing in Wire mode) |
| **Interactive Wiring** | In Wire mode (`W`), the routing preview dynamically follows the mouse; left-clicking places vertices |
| **Scroll Wheel** | Scroll canvas vertically (`Shift + Scroll` for horizontal) |
| **Ctrl + Scroll Wheel** | Zoom in / out smoothly |

---

## Hotkeys

| Key | Action |
|---|---|
| `↑ ↓ ← →` | Move cursor |
| `Ctrl + Z` / `u` | Undo last schematic change |
| `Ctrl + Y` / `Ctrl + Shift + Z` / `U` | Redo last undone change |
| `Ctrl + C` | Copy component or net label at cursor |
| `Ctrl + V` | Paste copied component or net label |
| `Ctrl + X` | Cut component or net label at cursor |
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

## History & Clipboard Operations

Vischem provides full undo/redo and clipboard integration via toolbar buttons, hotkeys, and command bar:

- **Undo & Redo**:
  - Up to 60 levels of deep history.
  - Automatically records all schematic modifications: placing components/devices, drawing wires, mouse drag-and-drop moves (with or without Shift wire stretching), rotating, flipping, deleting, net labelling, clearing, and property edits in dialogs.
  - Available via **Undo** / **Redo** toolbar buttons, `Ctrl+Z` / `Ctrl+Y` (`Ctrl+Shift+Z`, `u`, `U`), or `:undo` / `:redo`.
- **Copy, Cut & Paste**:
  - Copy or cut any component or net label at the cursor with `Ctrl+C` / `Ctrl+X` or the topbar buttons.
  - Paste with `Ctrl+V` or the **Paste** button.
  - Transistor sizing ($W/L$), parallel fingers ($M$), bulk connections, and PDK model references are faithfully duplicated while generating fresh collision-free sequential instance labels (e.g. `M1` → `M2`, `R1` → `R2`).
  - Net labels can be quickly duplicated across wire junctions.

---

## Command dialog

Press shift + `:` then type one of these commands:

```
undo / redo               Undo / Redo last schematic change
copy / paste / cut        Copy / Paste / Cut component or net label
nmos  pmos  npn  pnp      Place transistor
in  out  inout  vdd  vss  Place port / power symbol
pdk <sky130|gf180|ihp>   Switch active PDK preset
sim                       Simulation setup
save                      Save schematic (.json / .svg / .png …)
load                      Load schematic (.json)
netlist                   Export SPICE netlist (.cir)
doc                       Export black-on-white documentation image
clear                     Clear canvas (undoable)
```

---

## Model Manager  `Models` & PDK Support

Configure device models project-wide:

- **Inline** — built-in SPICE Level 1 parameters, no file needed
- **External file** — point to a `.sp` or `.spi` file (`.include`)
- **Library file** — point to a `.lib` file with a corner (`.lib "file" tt`)
- **PDK Presets** — full out-of-the-box support for open-source PDKs:
  - **SkyWater 130nm** (`sky130A` / `sky130B`)
  - **GlobalFoundries 180nm MCU** (`gf180mcuD` / `gf180mcuC`)
  - **IHP SG13G2 130nm BiCMOS** (`ihp-sg13g2`)

### Using Open-Source PDKs

1. **Auto-Detection**: Vischem automatically locates installed PDKs via `$PDK_ROOT`, `~/pdk`, and standard paths.
2. **Preset Selection**: Open `Models` in the toolbar, select **PDK Preset**, pick your PDK, and choose a corner (`typical`/`tt`, `ss`, `ff`, `sf`, `fs`).
3. **Command Bar**: You can also switch PDKs directly using the command bar:
   ```
   :pdk sky130 [corner]
   :pdk gf180 [corner]
   :pdk ihp [corner]
   :pdk none
   ```
4. **Smart SPICE & Device Management**:
   - Automatically handles `.subckt` vs `.model` device declarations and applies `X` subcircuit prefixes (`XM1`, `XQ1`).
   - Adapts dimension scaling to PDK rules (e.g., SkyWater 130 bare micron formatting for `.option scale=1.0u`).
   - Accommodates PDK-specific terminal definitions (e.g. 4-pin RF/BiCMOS BJTs like `npn13G2` with substrate tap).
   - Auto-populates MOSFET and BJT model name dropdowns with genuine PDK device models (e.g., `sky130_fd_pr__nfet_01v8`, `nfet_03v3`, `sg13_lv_nmos`).
   - Real-time symbol synchronization: updating Width, Length, or parallel fingers ($M$) in the Properties dialog immediately updates the displayed $W/L$ text on the canvas and emits `m=<fingers>` into the SPICE netlist.

---

## Example PDK Circuits

Pre-configured schematic examples are available in `examples/`:
- **`examples/GF180/`**: GF180 MCU circuit with `nfet_03v3` (`180.json`, `180.cir`, `180.raw`)
- **`examples/sky130/`**: SkyWater 130 CMOS inverter with `sky130_fd_pr__nfet_01v8` & `sky130_fd_pr__pfet_01v8` (`sky130_inv.json`, `sky130_inv.cir`, `sky130_inv.raw`)
- **`examples/ihp/`**: IHP SG13G2 Common-Source amplifier with `sg13_lv_nmos` (`ihp_cs.json`, `ihp_cs.cir`, `ihp_cs.raw`)

---

## Netlist Export & Simulation

- **Exporting**: Use `:netlist` in the command dialog or click the `Netlist` toolbar button to inspect the generated SPICE deck.
- **Simulating**: Click the **Run** toolbar button (or `:sim`) to execute the simulation in NGspice. Results and progress stream live to the simulation log panel, and a `.raw` output file is generated in the circuit directory.

To run NGspice manually from the command line:

```bash
ngspice -b my_circuit.cir
```

---

## PDK Licenses & Acknowledgments

Vischem interfaces with open-source Process Design Kits (PDKs). The PDK models, device definitions, and rules are the property of their respective creators and are distributed under the **Apache License 2.0**:

- **SkyWater 130nm PDK (`sky130`)**:
  - **License**: [Apache License 2.0](https://github.com/google/skywater-pdk/blob/main/LICENSE)
  - **Copyright**: © 2020 SkyWater Technology International, Inc. and Google LLC
  - **Repository**: [google/skywater-pdk](https://github.com/google/skywater-pdk)

- **GlobalFoundries 180nm MCU PDK (`gf180mcu`)**:
  - **License**: [Apache License 2.0](https://github.com/google/gf180mcu-pdk/blob/main/LICENSE)
  - **Copyright**: © 2022 GlobalFoundries Inc. and Google LLC
  - **Repository**: [google/gf180mcu-pdk](https://github.com/google/gf180mcu-pdk)

- **IHP SG13G2 130nm BiCMOS PDK (`ihp-sg13g2`)**:
  - **License**: [Apache License 2.0](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/main/LICENSE)
  - **Copyright**: © 2023–2024 IHP GmbH - Innovations for High Performance Microelectronics
  - **Repository**: [IHP-GmbH/IHP-Open-PDK](https://github.com/IHP-GmbH/IHP-Open-PDK)

---

## License

Vischem is licensed under the MIT License. See [`LICENSE`](file:///home/ziad/Vischem/LICENSE) for details.
