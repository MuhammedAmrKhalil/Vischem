"""
symbols/mosfets.py
MOSFET symbols — Razavi "Design of Analog CMOS Integrated Circuits"

Both NMOS and PMOS share the same body structure:
  Gate lead → gate bar (vertical)
  Three horizontal body dashes (oxide region)
  Vertical D/S rail
  Drain tap + lead
  Source tap + lead   ← arrow lives here, direction sets N vs P type

NMOS:
  • No gate bubble
  • Drain TOP   (0, -S)
  • Source BOTTOM (0, +S)
  • Arrow on source tap pointing INWARD →  (into channel = N-type)

PMOS:
  • Gate inversion bubble
  • Source TOP   (0, -S)   ← VDD side
  • Drain BOTTOM (0, +S)
  • Arrow on source tap pointing OUTWARD ←  (away from channel = P-type)
"""

from .base import DrawContext


def draw_NMOS(ctx: DrawContext):
    """
    Enhancement NMOS.
    Gate left · Drain top · Source bottom.
    Arrow on source tap pointing RIGHT (inward, into channel).
    """
    S = ctx.S

    # Gate lead + vertical gate bar (no bubble for NMOS)
    ctx.line(-S, 0, -S * .46, 0)
    ctx.line(-S * .46, -S * .44, -S * .46, S * .44)

    # Three horizontal body dashes (no arrow on these)
    for dy in (-S * .26, 0, S * .26):
        ctx.line(-S * .32, dy, -S * .08, dy)

    # Vertical D/S rail
    ctx.line(-S * .08, -S * .26, -S * .08, S * .26)

    # Drain tap → up  (top pin)
    ctx.line(-S * .08, -S * .26,  0, -S * .26)
    ctx.line(0, -S * .26,          0, -S)

    # Source tap → down  (bottom pin)
    ctx.line(-S * .22, S * .26, -S * .08, S * .26)   # shaft (arrow part)
    ctx.line(-S * .08, S * .26,  0,        S * .26)   # continues to rail
    ctx.line(0,         S * .26,  0,        S)         # lead down

    # Arrow on source tap — tip at body side, pointing INWARD (right = N-type)
    ctx.line(-S * .08, S * .26, -S * .17, S * .19)
    ctx.line(-S * .08, S * .26, -S * .17, S * .33)

    ctx.pin(-S, 0)    # gate
    ctx.pin(0, -S)    # drain  (top)
    ctx.pin(0,  S)    # source (bottom)


def draw_PMOS(ctx: DrawContext):
    """
    Enhancement PMOS.
    Gate left (with inversion bubble) · Source TOP · Drain bottom.
    Arrow on source tap pointing OUTWARD (left, away from channel = P-type).
    """
    S  = ctx.S
    br = S * .075   # gate bubble radius

    # Gate lead + inversion bubble + vertical gate bar
    ctx.line(-S, 0, -S * .55, 0)
    ctx.circle(-S * .47, 0, br, n=22)
    ctx.line(-S * .39, -S * .44, -S * .39, S * .44)

    # Three horizontal body dashes
    for dy in (-S * .26, 0, S * .26):
        ctx.line(-S * .25, dy, -S * .08, dy)

    # Vertical D/S rail
    ctx.line(-S * .08, -S * .26, -S * .08, S * .26)

    # Source tap → up  (top pin)
    ctx.line(-S * .08, -S * .26, -S * .22, -S * .26)  # shaft (arrow part)
    ctx.line(-S * .08, -S * .26,  0,        -S * .26)  # continues to rail
    ctx.line(0,        -S * .26,  0,        -S)         # lead up

    # Arrow on source tap — tip away from body, pointing OUTWARD (left = P-type)
    ctx.line(-S * .22, -S * .26, -S * .13, -S * .19)
    ctx.line(-S * .22, -S * .26, -S * .13, -S * .33)

    # Drain tap → down  (bottom pin)
    ctx.line(-S * .08, S * .26,  0, S * .26)
    ctx.line(0,         S * .26,  0, S)

    ctx.pin(-S, 0)    # gate
    ctx.pin(0, -S)    # source (top)
    ctx.pin(0,  S)    # drain  (bottom)
