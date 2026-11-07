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
| **Left Click** | Select an element (component, wire, or net label) or place the grid cursor at a specific cell |
| **Shift / Ctrl + Click** | Toggle selection of multiple elements without deselecting others |
| **Marquee Box Drag** | Drag on empty canvas to draw a rubberband selection box, selecting all components, wires, and labels within |
| **Left Drag** | Drag and drop selected component(s), wire(s), or wire label(s) across the canvas to reposition them together (with automatic cell collision avoidance) |
| **Shift + Left Drag** | Move component(s) while automatically stretching connected unselected wire endpoints |
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
| `Ctrl + A` | Select all elements on canvas |
| `Escape` | Clear active selection / cancel wire |
| `Ctrl + Z` / `u` | Undo last schematic change |
| `Ctrl + Y` / `Ctrl + Shift + Z` / `U` | Redo last undone change |
| `Ctrl + C` | Copy selected element(s) or item at cursor |
| `Ctrl + V` | Paste copied element(s) relative to cursor |
| `Ctrl + X` | Cut selected element(s) or item at cursor |
| `R` | Place Resistor |
| `C` | Place Capacitor |
| `L` | Place Inductor |
| `V` | Place Voltage source |
| `I` | Place Current source |
| `G` | Place Ground |
| `W` | Wire mode  (Enter = commit, Esc = cancel) |
| `Space` | Rotate 90° (rotates all selected components) |
| `F` | Flip (horizontal mirror on all selected components) |
| `E` | Open Properties dialog |
| `T` | Add net label |
| `M` | Toggle mouse mode |
| `+ / -` | Zoom in / out |
| `Del` | Delete selected element(s) or item at cursor |
| `:` / `Ctrl + P` | Open modern Command Palette |

---

## Multi-Element Selection & Clipboard

Vischem provides complete multi-element selection, group operations, and clipboard integration:

- **Selecting Multiple Elements**:
  - **Shift + Click / Ctrl + Click**: Click individual components, wires, or net labels to add or remove them from the selection set.
  - **Marquee Selection (Rubberband Box)**: Click and drag on empty canvas to draw a dashed selection rectangle; upon release, all components, wires, and net labels enclosed in or touching the box are selected.
  - **Select All**: Press `Ctrl+A` or type `:all` to select every component, wire, and net label on the schematic.
  - **Deselect**: Press `Escape`, click on empty canvas, or type `:deselect` to clear selection.
- **Group Drag & Drop**:
  - Dragging any selected element moves all selected components, wires, and net labels in unison with boundary and collision checks.
  - Shift-drag stretches unselected wire endpoints connected to the group.
- **Group Copy, Cut & Paste**:
  - `Ctrl+C` copies all selected elements to clipboard while preserving relative spacing and device sizing.
  - `Ctrl+V` pastes the entire group relative to cursor, auto-minting unique sequential labels (`M2`, `M3`, etc.).
  - `Ctrl+X` cuts all selected elements into clipboard.
- **Group Rotate, Flip & Delete**:
  - `Space` rotates all selected components simultaneously.
  - `F` flips all selected components horizontally.
  - `Del` deletes all selected components, wires, and labels in a single undoable action (`Ctrl+Z` fully restores them).

---

## Command Palette (`:` / `Ctrl+P`)

Press `:` (or `Ctrl+P`, or click **Cmd** in the toolbar) to open the floating **Command Palette**.

The redesigned palette features:
- **Clean Interface**: Zero clutter — all prompt headers above the input are removed, giving direct focus to your command.
- **Live Autocomplete**: Real-time fuzzy filtering of all commands, shorthands, and syntax templates with immediate previews.
- **Keyboard Navigation**: Use `↑` / `↓` to navigate suggestions or cycle through previous command history.
- **Tab Completion**: Press `Tab` to autocomplete the highlighted command name and cursor into argument position.
- **Direct Parameter Passing**: Place components, set values, and configure simulation directly in one command.

### Available Commands & Shorthands

| Command / Alias | Arguments | Description & Example |
|---|---|---|
| `:r` / `:res` / `:resistor` | `[val]` | Place resistor at cursor with value (e.g. `:r 10k`, `:r 4.7k`) |
| `:c` / `:cap` / `:capacitor` | `[val]` | Place capacitor at cursor with value (e.g. `:c 100p`, `:c 1u`) |
| `:l` / `:ind` / `:inductor` | `[val]` | Place inductor at cursor with value (e.g. `:l 10u`, `:l 1m`) |
| `:v` / `:vsrc` / `:dc` | `[val]` | Place voltage source at cursor with DC value (e.g. `:v 5V`, `:v 3.3V DC`) |
| `:i` / `:isrc` | `[val]` | Place current source at cursor with value (e.g. `:i 1m`, `:i 10u`) |
| `:g` / `:gnd` / `:ground` | — | Place ground symbol at cursor |
| `:nmos` / `:m` / `:mos` | `[w] [l]` | Place NMOS transistor with width & length (e.g. `:nmos 10u 0.18u`) |
| `:pmos` | `[w] [l]` | Place PMOS transistor with width & length (e.g. `:pmos 20u 0.18u`) |
| `:npn` / `:bjt` | `[model]` | Place NPN BJT with model (e.g. `:npn 2N2222`) |
| `:pnp` | `[model]` | Place PNP BJT with model (e.g. `:pnp 2N2907`) |
| `:in` / `:out` / `:inout` | `[name]` | Place port pin with custom net name (e.g. `:in VIN`, `:out VOUT`) |
| `:vdd` / `:vss` | `[name]` | Place power/ground rail pin (e.g. `:vdd VDD`, `:vss VSS`) |
| `:pin` | `[name] [type]` | Place port pin of specified type (e.g. `:pin CLK inout`) |
| `:w` / `:wire` | — | Enter interactive Wire drawing mode from cursor |
| `:lbl` / `:label` / `:t` | `<name>` | Place or rename net label at cursor (e.g. `:label CLK_IN`) |
| `:undo` / `:u` | — | Undo last change |
| `:redo` / `:U` | — | Redo last undone change |
| `:copy` / `:cp` | — | Copy selected element(s) |
| `:cut` / `:x` | — | Cut selected element(s) |
| `:paste` / `:p` | — | Paste clipboard element(s) |
| `:del` / `:delete` / `:rm` | — | Delete selected element(s) |
| `:rot` / `:rotate` | `[deg]` | Rotate selection or cursor component (e.g. `:rot 90`, `:rot 180`) |
| `:flip` / `:fl` | — | Flip / mirror selection horizontally |
| `:all` / `:sel` | — | Select all components, wires, and labels |
| `:deselect` / `:none` | — | Deselect all |
| `:pdk` | `[name] [corner]`| Switch PDK preset (e.g. `:pdk sky130 tt`, `:pdk gf180`, `:pdk none`) |
| `:corner` | `<corner>` | Switch active simulation corner (e.g. `:corner ss`, `:corner tt`) |
| `:models` | — | Open Model Manager dialog |
| `:sim` / `:analysis` | — | Open Simulation Settings dialog |
| `:run` | — | Run NGspice simulation |
| `:op` | — | Set simulation mode to DC Operating Point |
| `:tran` | `[tstop] [tstep]`| Configure transient simulation (e.g. `:tran 10u 1n`) |
| `:ac` | `[dec] [pts] [fstart] [fstop]` | Configure AC frequency sweep |
| `:dc` | `[src] [start] [stop] [step]` | Configure DC sweep |
| `:raw` / `:showraw` | — | Reveal NGspice `.raw` simulation data file |
| `:save` / `:w` | `[path]` | Save schematic JSON directly to path or open dialog |
| `:load` / `:open` | `[path]` | Load schematic JSON directly from path or open dialog |
| `:netlist` / `:nl` | `[path]` | Export SPICE netlist (.cir) |
| `:export` | `<png\|svg\|doc> [path]` | Export image or publication documentation diagram |
| `:zoom` / `:z` | `[pct\|+\|-\|fit]` | Adjust canvas zoom (e.g. `:zoom 150`, `:z +`, `:z fit`) |
| `:goto` / `:pos` | `<x> <y>` | Move cursor to grid coordinates (e.g. `:goto 10 15`) |
| `:mouse` / `:m` | — | Toggle mouse crosshair cursor mode |
| `:clear` / `:cls` | — | Clear schematic canvas |
| `:help` / `:?` | — | Show quick help summary |
| `:quit` / `:exit` / `:q` | — | Exit Vischem |

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
