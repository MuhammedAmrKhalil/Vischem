"""
symbols/base.py
DrawContext — shared drawing helpers passed to every symbol drawer.
All coordinates are in local space (origin = component center).
The context handles the rotation transform and canvas calls.
"""

import math
import tkinter as tk

# ── Shared colour tokens (imported by all symbol files) ──────────────────────
COMP_C  = "#9fb0c8"   # normal symbol stroke
SEL_C   = "#e8edf5"   # selected symbol stroke
PIN_C   = "#1d9e52"   # pin dot normal
PIN_SEL = "#fbbf24"   # pin dot selected
LBL_C   = "#2d3f55"   # reference label normal
LBL_SEL = "#fbbf24"   # reference label selected
VAL_C   = "#7c83f5"   # value text


class DrawContext:
    """
    Wraps a Tkinter Canvas and provides coordinate-transformed
    drawing primitives for symbol files.

    Parameters
    ----------
    cv   : tk.Canvas
    ox   : int   canvas-pixel x of component centre
    oy   : int   canvas-pixel y of component centre
    S    : int   grid size in pixels (= GS from editor)
    rot  : int   rotation in degrees (0 / 90 / 180 / 270)
    sel  : bool  True when the cursor is on this component
    """

    def __init__(self, cv: tk.Canvas, ox: int, oy: int,
                 S: int, rot: int, sel: bool):
        self.cv   = cv
        self.ox   = ox
        self.oy   = oy
        self.S    = S
        self.sel  = sel

        rad       = math.radians(rot)
        self._cr  = math.cos(rad)
        self._sr  = math.sin(rad)

        self.col  = SEL_C   if sel else COMP_C
        self.pinc = PIN_SEL if sel else PIN_C
        self.lblc = LBL_SEL if sel else LBL_C

    # ── Coordinate transform ───────────────────────────────────────────────
    def T(self, x: float, y: float) -> tuple[float, float]:
        """Local (x, y) → canvas (px, py)."""
        return (self.ox + x * self._cr - y * self._sr,
                self.oy + x * self._sr + y * self._cr)

    # ── Primitives ─────────────────────────────────────────────────────────
    def line(self, x1, y1, x2, y2, color=None, w=1.8):
        self.cv.create_line(
            *self.T(x1, y1), *self.T(x2, y2),
            fill=color or self.col, width=w,
            capstyle=tk.ROUND, joinstyle=tk.ROUND)

    def arc(self, cx, cy, rx, ry, a0, a1, n=24, color=None, w=1.8):
        """Polyline approximation of an elliptical arc."""
        step = (a1 - a0) / n
        pts  = [self.T(cx + rx * math.cos(a0 + i * step),
                       cy + ry * math.sin(a0 + i * step))
                for i in range(n + 1)]
        for i in range(len(pts) - 1):
            self.cv.create_line(
                *pts[i], *pts[i + 1],
                fill=color or self.col, width=w, capstyle=tk.ROUND)

    def circle(self, cx, cy, r, n=36, color=None, w=1.8):
        self.arc(cx, cy, r, r, 0, 2 * math.pi, n, color, w)

    def arrow_head(self, mx, my, ang, al=None, av=None):
        """
        Draw a two-line arrowhead at point (mx, my) pointing in direction ang.
        al = arrowhead length, av = arrowhead half-width.
        """
        S  = self.S
        al = al if al is not None else S * 0.11
        av = av if av is not None else S * 0.07
        self.line(mx, my,
                  mx - al * math.cos(ang) + av * math.sin(ang),
                  my - al * math.sin(ang) - av * math.cos(ang))
        self.line(mx, my,
                  mx - al * math.cos(ang) - av * math.sin(ang),
                  my - al * math.sin(ang) + av * math.cos(ang))

    def pin(self, px, py):
        x0, y0 = self.T(px, py)
        r = 3
        self.cv.create_oval(x0 - r, y0 - r, x0 + r, y0 + r,
                            fill=self.pinc, outline="")

    def label(self, text, lx, ly, color=None):
        x0, y0 = self.T(lx, ly)
        self.cv.create_text(x0, y0, text=text,
                            fill=color or self.lblc,
                            font=("Courier", 8, "bold"),
                            anchor="center")

    def value(self, text, lx, ly):
        x0, y0 = self.T(lx, ly)
        self.cv.create_text(x0, y0, text=text,
                            fill=VAL_C,
                            font=("Courier", 7),
                            anchor="center")
