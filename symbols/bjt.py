"""
symbols/bjt.py
Bipolar Junction Transistor symbols: NPN and PNP.
Symbol style follows Razavi "Design of Analog CMOS Integrated Circuits".

Pin layout (unrotated):
  Base      → left    (-S, 0)
  Collector → top     ( 0, -S)
  Emitter   → bottom  ( 0, +S)

NPN: emitter arrow points AWAY from base bar (outward / conventional current out).
PNP: emitter arrow points TOWARD base bar  (inward  / conventional current in).
"""

import math
from .base import DrawContext


def draw_NPN(ctx: DrawContext):
    """
    NPN BJT — Razavi style.

    Structure:
      Circle boundary
      Base lead (left) → vertical base bar
      Collector diagonal (top-right)
      Emitter  diagonal (bottom-right) with outward arrow
    """
    S = ctx.S
    R = S * .42        # circle radius

    # 1. Circle
    ctx.circle(0, 0, R, n=52)

    # 2. Base lead + vertical bar
    ctx.line(-S, 0, -S * .30, 0)
    ctx.line(-S * .30, -S * .38, -S * .30, S * .38)

    # 3. Collector (upper diagonal)
    ctx.line(-S * .30, -S * .22, 0, -S)

    # 4. Emitter (lower diagonal)
    ctx.line(-S * .30, S * .22, 0, S)

    # 5. Emitter arrowhead — outward (NPN), 58% along emitter line
    ex1, ey1 = -S * .30, S * .22
    ex2, ey2 =  0,        S
    t         = 0.58
    mx  = ex1 + (ex2 - ex1) * t
    my  = ey1 + (ey2 - ey1) * t
    ang = math.atan2(ey2 - ey1, ex2 - ex1)
    ctx.arrow_head(mx, my, ang)

    ctx.pin(-S, 0)
    ctx.pin(0, -S)
    ctx.pin(0,  S)


def draw_PNP(ctx: DrawContext):
    """
    PNP BJT — Razavi style.

    Same as NPN but collector and emitter are swapped,
    and the emitter arrow points INWARD (toward the base bar).
    """
    S = ctx.S
    R = S * .42

    # 1. Circle
    ctx.circle(0, 0, R, n=52)

    # 2. Base lead + vertical bar
    ctx.line(-S, 0, -S * .30, 0)
    ctx.line(-S * .30, -S * .38, -S * .30, S * .38)

    # 3. Emitter goes UP-right for PNP (top terminal is emitter)
    ctx.line(-S * .30, -S * .22, 0, -S)

    # 4. Collector goes DOWN-right
    ctx.line(-S * .30, S * .22, 0, S)

    # 5. Emitter arrowhead — INWARD (PNP), 42% along emitter line
    #    The emitter is the upper diagonal: from (-0.3S, -0.22S) → (0, -S)
    ex1, ey1 = -S * .30, -S * .22
    ex2, ey2 =  0,        -S
    t         = 0.42
    mx  = ex1 + (ex2 - ex1) * t
    my  = ey1 + (ey2 - ey1) * t
    # Arrow points BACKWARD along the line (toward base = inward)
    ang = math.atan2(ey1 - ey2, ex1 - ex2)   # reversed direction
    ctx.arrow_head(mx, my, ang)

    ctx.pin(-S, 0)
    ctx.pin(0, -S)
    ctx.pin(0,  S)
