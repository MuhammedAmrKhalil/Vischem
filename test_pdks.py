#!/usr/bin/env python3
"""
Vischem PDK Integration Tests
Tests PDK detection, resolution, ModelConfig presets, and netlist emission.
Runs headless without requiring a display server.
"""

import sys
import os

# Add Vischem directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from editor.pdk import detect_installed_pdks, resolve_pdk, format_pdk_dim
from editor.netlist import ModelConfig, generate, parse_model_file_corners


class DummyComp:
    def __init__(self, t, gx, gy, label, value="", rot=0):
        self.type = t
        self.gx = gx
        self.gy = gy
        self.label = label
        self.value = value
        self.rot = rot
        self.flip = False
        self.model_name = None
        self.bulk_net = "0"
        self.mos_w = None
        self.mos_l = None


def test_pdk_detection():
    print("Testing PDK detection...")
    pdks = detect_installed_pdks()
    print(f"Found PDKs: {list(pdks.keys())}")
    for name in ("gf180", "sky130", "ihp"):
        assert name in pdks, f"PDK '{name}' should be detected!"
        res = resolve_pdk(name)
        assert res is not None, f"Failed to resolve PDK '{name}'"
        assert os.path.isfile(res.lib_file), f"Lib file not found: {res.lib_file}"
        print(f"  [OK] {res.display_name} -> {res.lib_file}")


def test_model_config_presets():
    print("\nTesting ModelConfig presets...")
    for name, expected_corner, expected_nmos in [
        ("gf180", "typical", "nfet_03v3"),
        ("sky130", "tt", "sky130_fd_pr__nfet_01v8"),
        ("ihp", "mos_tt", "sg13_lv_nmos"),
    ]:
        cfg = ModelConfig(pdk_name=name)
        assert cfg.corner == expected_corner, f"Expected {expected_corner}, got {cfg.corner}"
        assert cfg.device_models["NMOS"]["name"] == expected_nmos
        assert os.path.isfile(cfg.file_path)
        print(f"  [OK] {name}: corner={cfg.corner}, nmos={cfg.device_models['NMOS']['name']}")


def test_dim_formatting():
    print("\nTesting dimension formatting...")
    # Sky130 uses scale=1.0u, so 2u -> 2, 180n -> 0.18
    assert format_pdk_dim("2u", "sky130") == "2"
    assert format_pdk_dim("180n", "sky130") == "0.18"
    assert format_pdk_dim("0.15u", "sky130") == "0.15"

    # GF180 and IHP retain explicit units
    assert format_pdk_dim("2u", "gf180") == "2u"
    assert format_pdk_dim("280n", "gf180") == "280n"
    assert format_pdk_dim("2u", "ihp") == "2u"
    print("  [OK] Dimension formatting matches PDK expectations.")


def test_netlist_generation():
    print("\nTesting netlist generation with PDK...")
    # Create simple NMOS and BJT components
    nmos = DummyComp("NMOS", 5, 5, "M1")
    nmos.mos_w = "2u"
    nmos.mos_l = "180n"
    bjt = DummyComp("NPN", 10, 10, "Q1")
    
    # Sky130
    cfg_sky = ModelConfig(pdk_name="sky130")
    res_sky = generate([nmos], [], model_config=cfg_sky)
    cir_sky = res_sky.netlist
    assert "XM1" in cir_sky, "Should prepend X for PDK subcircuit"
    assert "sky130_fd_pr__nfet_01v8" in cir_sky
    assert "W=2 L=0.18" in cir_sky
    print("  [OK] Sky130 netlist verified.")

    # IHP
    cfg_ihp = ModelConfig(pdk_name="ihp")
    res_ihp = generate([nmos, bjt], [], model_config=cfg_ihp)
    cir_ihp = res_ihp.netlist
    assert "XM1" in cir_ihp
    assert "XQ1" in cir_ihp
    assert "sg13_lv_nmos" in cir_ihp
    assert "npn13G2" in cir_ihp
    # IHP BJT should have 4 terminals (c b e bn)
    for line in cir_ihp.splitlines():
        if "XQ1" in line:
            tokens = line.split()
            # tokens: XQ1 collector base emitter substrate model_name
            assert len(tokens) >= 6, f"Expected 4-terminal BJT line, got: {line}"
    print("  [OK] IHP netlist and 4-terminal BJT verified.")


if __name__ == "__main__":
    test_pdk_detection()
    test_model_config_presets()
    test_dim_formatting()
    test_netlist_generation()
    print("\nALL PDK INTEGRATION TESTS PASSED SUCCESSFULLY!")
