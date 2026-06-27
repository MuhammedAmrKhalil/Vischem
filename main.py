#!/usr/bin/env python3
"""
Vischem  v0.1
Visual Schematic Editor for analog / mixed-signal circuit design.
Targets NGspice for simulation.

Usage
-----
    python main.py

Requirements
------------
    Python 3.10+
    Pillow  (optional — for PNG/JPEG/BMP and documentation image export)
        pip install pillow

    NGspice (optional — for running the exported .cir netlist)
        https://ngspice.sourceforge.io
"""

import sys
import os

# ── Ensure project root is on sys.path so all packages resolve ────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── Python version guard ───────────────────────────────────────────────────────
if sys.version_info < (3, 10):
    sys.exit(
        f"Vischem requires Python 3.10 or newer.\n"
        f"You are running Python {sys.version}.\n"
        "Please upgrade: https://www.python.org/downloads/"
    )

# ── Optional dependency check (Pillow) ────────────────────────────────────────
try:
    import PIL  # noqa: F401
    _PILLOW = True
except ImportError:
    _PILLOW = False

# ── Tkinter availability guard ────────────────────────────────────────────────
try:
    import tkinter as tk
except ImportError:
    sys.exit(
        "Tkinter is not available.\n"
        "On Linux: sudo apt install python3-tk\n"
        "On macOS: install Python from python.org (includes Tk)\n"
        "On Windows: reinstall Python and tick 'tcl/tk' in the installer."
    )

# ── Launch ─────────────────────────────────────────────────────────────────────
def main():
    from editor.app import Editor

    root = tk.Tk()
    root.title("Vischem  v0.1")

    # Set a reasonable minimum window size
    root.minsize(900, 600)

    # Centre the window on screen
    root.update_idletasks()
    w, h = 1280, 800
    x = (root.winfo_screenwidth()  - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    app = Editor(root)  # noqa: F841

    if not _PILLOW:
        app._status(
            "Pillow not installed — image export disabled.  "
            "Run:  pip install pillow",
            "#f59e0b")

    root.mainloop()


if __name__ == "__main__":
    main()
