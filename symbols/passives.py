"""
symbols/passives.py
Passive component symbols: Resistor, Capacitor, Inductor,
Voltage Source, Current Source, Ground.

All symbols are drawn in local coordinates:
  horizontal components  → pins at (-S, 0) and (+S, 0)
  vertical   components  → pins at (0, -S) and (0, +S)
  ground                 → single pin at (0, 0)
"""

import math
from .base import DrawContext


def draw_R(ctx: DrawContext):
    """Resistor — IEC zigzag style."""
    S = ctx.S
    ctx.line(-S, 0, -S * .5, 0)
    pts = [
        (-S * .5, 0), (-S * .38, -S * .22), (-S * .19, S * .22),
        (0, -S * .22), (S * .19, S * .22), (S * .38, -S * .22),
        (S * .5, 0)
    ]
    for i in range(len(pts) - 1):
        ctx.line(*pts[i], *pts[i + 1])
    ctx.line(S * .5, 0, S, 0)
    ctx.pin(-S, 0)
    ctx.pin(S, 0)


def draw_C(ctx: DrawContext):
    """Capacitor — two parallel plates."""
    S = ctx.S
    ctx.line(-S, 0, -S * .12, 0)
    ctx.line(-S * .12, -S * .32, -S * .12, S * .32)
    ctx.line(S * .12, -S * .32, S * .12, S * .32)
    ctx.line(S * .12, 0, S, 0)
    ctx.pin(-S, 0)
    ctx.pin(S, 0)


def draw_L(ctx: DrawContext):
    """Inductor — four upward bumps."""
    S  = ctx.S
    r  = S * 0.115
    cx_list = [-3 * r, -r, r, 3 * r]
    ctx.line(-S, 0, -4 * r, 0)
    ctx.line(4 * r, 0, S, 0)
    for bx in cx_list:
        ctx.arc(bx, 0, r, r, math.pi, 0)
    ctx.pin(-S, 0)
    ctx.pin(S, 0)


def draw_V(ctx: DrawContext):
    """
    Voltage Source — circle with + / − markings.
    Pins: top = + (0, -S), bottom = − (0, +S).
    """
    S = ctx.S
    r = S * .38
    ctx.line(0, -S, 0, -r)
    ctx.line(0,  r, 0,  S)
    ctx.circle(0, 0, r)
    # + symbol (top half)
    ctx.line(-S * .10, -S * .18, S * .10, -S * .18)
    ctx.line(0, -S * .27, 0, -S * .09)
    # − symbol (bottom half)
    ctx.line(-S * .10, S * .18, S * .10, S * .18)
    ctx.pin(0, -S)
    ctx.pin(0,  S)


def draw_I(ctx: DrawContext):
    """
    Current Source — circle with upward arrow.
    Conventional current flows from − (bottom) to + (top).
    """
    S  = ctx.S
    r  = S * .38
    ctx.line(0, -S, 0, -r)
    ctx.line(0,  r, 0,  S)
    ctx.circle(0, 0, r)
    # Arrow shaft
    ctx.line(0, S * .22, 0, -S * .12)
    # Arrowhead (pointing up)
    ah = -S * .12
    ctx.line(0, ah, -S * .09, ah + S * .16)
    ctx.line(0, ah,  S * .09, ah + S * .16)
    ctx.pin(0, -S)
    ctx.pin(0,  S)


def draw_G(ctx: DrawContext):
    """
    Ground — three descending horizontal bars.
    Single pin at (0, 0).
    """
    S = ctx.S
    ctx.line(0, 0, 0, S * .20)
    ctx.line(-S * .36, S * .20,  S * .36, S * .20)
    ctx.line(-S * .23, S * .35,  S * .23, S * .35)
    ctx.line(-S * .10, S * .50,  S * .10, S * .50)
    ctx.pin(0, 0)
