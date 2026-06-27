"""
symbols/__init__.py
Central registry — import draw_symbol() from here.

Usage:
    from symbols import draw_symbol, DrawContext
    draw_symbol(ctx, comp.type)
"""

from .base     import DrawContext
from .passives import draw_R, draw_C, draw_L, draw_V, draw_I, draw_G
from .mosfets  import draw_NMOS, draw_PMOS
from .bjt      import draw_NPN, draw_PNP
from .pins     import (draw_PIN_IN, draw_PIN_OUT, draw_PIN_INOUT,
                       draw_PIN_VDD, draw_PIN_VSS)

# ── Registry: type-string → drawing function ──────────────────────────────────
_REGISTRY: dict = {
    # Passives
    "R":         draw_R,
    "C":         draw_C,
    "L":         draw_L,
    "V":         draw_V,
    "I":         draw_I,
    "G":         draw_G,
    # MOSFETs
    "NMOS":      draw_NMOS,
    "PMOS":      draw_PMOS,
    # BJTs
    "NPN":       draw_NPN,
    "PNP":       draw_PNP,
    # Port / pin symbols
    "PIN_IN":    draw_PIN_IN,
    "PIN_OUT":   draw_PIN_OUT,
    "PIN_INOUT": draw_PIN_INOUT,
    "PIN_VDD":   draw_PIN_VDD,
    "PIN_VSS":   draw_PIN_VSS,
}

KNOWN_TYPES: list = list(_REGISTRY.keys())


def draw_symbol(ctx: DrawContext, typ: str) -> None:
    """
    Draw the symbol for *typ* using *ctx*.
    Raises KeyError with a helpful message if the type is not registered.
    """
    fn = _REGISTRY.get(typ)
    if fn is None:
        raise KeyError(
            f"Unknown symbol type: '{typ}'  "
            f"(known: {', '.join(KNOWN_TYPES)})"
        )
    fn(ctx)
