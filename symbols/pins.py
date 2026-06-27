"""
symbols/pins.py
Port / Pin symbols for schematic boundaries.

  PIN_IN    → input flag (right-pointing chevron)
  PIN_OUT   → output flag (left-pointing chevron)
  PIN_INOUT → bidirectional flag (both-sided chevron)
  PIN_VDD   → power rail (VDD)
  PIN_VSS   → power rail (VSS / GND equivalent)

All symbols have a single connection pin at the origin (0, 0).
The net name is stored in comp.value and rendered as the flag label.
"""

from .base import DrawContext
import math


def draw_PIN_IN(ctx: DrawContext):
    """Input port: chevron/arrow pointing RIGHT (into circuit)."""
    S = ctx.S
    hw = S * 0.38   # half-width of flag
    hh = S * 0.22   # half-height
    tip = S * 0.16  # arrow tip indent

    # Flag body: pentagon pointing right
    pts = [
        (-hw,    hh),
        (0,      hh),
        (tip,    0),
        (0,     -hh),
        (-hw,   -hh),
    ]
    for i in range(len(pts)):
        ctx.line(*pts[i], *pts[(i+1) % len(pts)])

    # Connection line from right tip to origin
    ctx.line(tip, 0, S * 0.5, 0)
    ctx.pin(S * 0.5, 0)


def draw_PIN_OUT(ctx: DrawContext):
    """Output port: chevron/arrow pointing LEFT (out of circuit)."""
    S = ctx.S
    hw = S * 0.38
    hh = S * 0.22
    tip = -S * 0.16

    pts = [
        (hw,   hh),
        (0,    hh),
        (tip,  0),
        (0,   -hh),
        (hw,  -hh),
    ]
    for i in range(len(pts)):
        ctx.line(*pts[i], *pts[(i+1) % len(pts)])

    ctx.line(tip, 0, -S * 0.5, 0)
    ctx.pin(-S * 0.5, 0)


def draw_PIN_INOUT(ctx: DrawContext):
    """Bidirectional port: chevron both sides (diamond)."""
    S = ctx.S
    hw = S * 0.42
    hh = S * 0.22

    pts = [
        (-hw,  0),
        (0,   -hh),
        (hw,   0),
        (0,    hh),
    ]
    for i in range(len(pts)):
        ctx.line(*pts[i], *pts[(i+1) % len(pts)])

    ctx.pin(0, 0)


def draw_PIN_VDD(ctx: DrawContext):
    """VDD power pin — vertical line with horizontal bar on top."""
    S = ctx.S
    ctx.line(0, S * 0.45, 0, 0)      # vertical stem up to pin
    ctx.line(0, 0, 0, -S * 0.2)      # short lead to rail
    ctx.line(-S * 0.32, -S * 0.2, S * 0.32, -S * 0.2)   # horizontal bar
    ctx.pin(0, S * 0.45)


def draw_PIN_VSS(ctx: DrawContext):
    """VSS power pin — vertical line with three descending bars (like GND)."""
    S = ctx.S
    ctx.line(0, -S * 0.45, 0, 0)
    ctx.line(0, 0, 0, S * 0.2)
    ctx.line(-S * 0.32, S * 0.20,  S * 0.32, S * 0.20)
    ctx.line(-S * 0.21, S * 0.33,  S * 0.21, S * 0.33)
    ctx.line(-S * 0.09, S * 0.46,  S * 0.09, S * 0.46)
    ctx.pin(0, -S * 0.45)
