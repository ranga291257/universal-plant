#!/usr/bin/env python3
"""Validate heated-tank baseline; save IC JSON."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from challenge.plant.design import DESIGN, design_duty_independent
from challenge.plant.model import settle_to_steady, state_to_dict, step_plant, PlantState, PlantParams
from challenge.plant.controllers import ControlSuite

OUT = ROOT / "challenge" / "plant" / "baseline_ic.json"
REPORT = ROOT / "docs" / "validation" / "baseline_report.md"


def main() -> int:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Baseline validation report", ""]
    fails = 0

    duty = design_duty_independent()
    lines.append("## Independent design duty")
    for k, v in duty.items():
        lines.append(f"- `{k}` = {v:.4f}")
    err_q = abs(duty["Q_coil_kW"] - DESIGN.design_duty_kW) / DESIGN.design_duty_kW
    err_w = abs(duty["w_steam_kg_h"] - DESIGN.design_steam_kg_h) / DESIGN.design_steam_kg_h
    ok_q = err_q <= 0.03
    ok_w = err_w <= 0.05
    lines.append(f"- duty relative error {err_q:.4%} => {'PASS' if ok_q else 'FAIL'}")
    lines.append(f"- steam relative error {err_w:.4%} => {'PASS' if ok_w else 'FAIL'}")
    fails += (not ok_q) + (not ok_w)

    print("Settling 3 h ...")
    state, params, ctrl, tags = settle_to_steady(hours=3.0, dt_s=1.0)
    dT = abs(state.T_C - DESIGN.T_SP_C)
    dh = abs(state.h_m - DESIGN.level_SP_m)
    mbal = abs(tags["CALC-MBAL"])
    ok_T = dT <= 0.5
    ok_h = dh <= 0.05
    ok_m = mbal <= 0.3
    lines += [
        "",
        "## Settled SS (3 h)",
        f"- T={state.T_C:.3f} degC (err {dT:.3f}) => {'PASS' if ok_T else 'FAIL'}",
        f"- h={state.h_m:.3f} m (err {dh:.3f}) => {'PASS' if ok_h else 'FAIL'}",
        f"- steam={state.steam_kg_h:.1f} kg/h, TV={state.TV_pos_pct:.1f}%, LV={state.LV_pos_pct:.1f}%",
        f"- CALC-MBAL={mbal:.3f} => {'PASS' if ok_m else 'FAIL'}",
        f"- CALC-EBAL={tags['CALC-EBAL']:.2f} kW (closure; loss term={duty['Q_loss_kW']:.2f} kW already subtracted)",
    ]
    ok_ebal = abs(tags["CALC-EBAL"]) <= 40.0
    lines.append(f"- |CALC-EBAL| <= 40 kW => {'PASS' if ok_ebal else 'FAIL'}")
    fails += (not ok_T) + (not ok_h) + (not ok_m) + (not ok_ebal)

    # Feed step
    state2, params2, ctrl2, _ = settle_to_steady(hours=2.0, dt_s=1.0)
    state2.F_feed_m3_h = 13.5
    for _ in range(int(90 * 60)):
        state2, tags2 = step_plant(state2, params2, ctrl2, 1.0)
    ok_rec = abs(state2.T_C - DESIGN.T_SP_C) <= 0.8
    lines += ["", "## Feed -10% for 90 min", f"- T={state2.T_C:.3f} => {'PASS' if ok_rec else 'FAIL'}"]
    fails += not ok_rec

    # Timestep sensitivity
    def settle_dt(dt):
        st, pr, ct, _ = settle_to_steady(hours=1.0, dt_s=dt)
        return st.T_C

    # lighter: integrate 1800 s from same IC
    st_a, p_a, c_a, _ = settle_to_steady(hours=1.5, dt_s=1.0)
    st_b = PlantState(**{**state_to_dict(st_a, p_a, c_a)["state"]})
    # compare one more hour at 1s vs 0.5s from identical dict
    data = state_to_dict(st_a, p_a, c_a)
    from challenge.plant.model import load_from_dict

    s1, p1, c1 = load_from_dict(json.loads(json.dumps(data)))
    s2, p2, c2 = load_from_dict(json.loads(json.dumps(data)))
    for _ in range(3600):
        s1, _ = step_plant(s1, p1, c1, 1.0)
    for _ in range(7200):
        s2, _ = step_plant(s2, p2, c2, 0.5)
    d_ts = abs(s1.T_C - s2.T_C)
    ok_ts = d_ts <= 0.3
    lines += ["", "## Timestep sensitivity 1s vs 0.5s (1 h)", f"- dT={d_ts:.4f} => {'PASS' if ok_ts else 'FAIL'}"]
    fails += not ok_ts

    # Save IC
    payload = state_to_dict(state, params, ctrl)
    text = json.dumps(payload, indent=2)
    OUT.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode()).hexdigest()[:16]
    lines += ["", f"## IC saved `{OUT.relative_to(ROOT)}`", f"- sha256[:16]={digest}"]

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nFAILS={fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
