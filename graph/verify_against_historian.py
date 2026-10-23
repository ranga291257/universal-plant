#!/usr/bin/env python3
"""Check the graph's stated relationships against the normal-baseline historian window.

Uses participant/historian_60s.parquet (the public pilot file) and only the first 6 h,
which participant/README.md describes as normal baseline. Read-only: writes a report, nothing else.

Run with the project venv:  ./.venv/bin/python graph/verify_against_historian.py
Writes: graph/HISTORIAN_CHECK.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

GRAPH = Path(__file__).resolve().parent
ROOT = GRAPH.parent
sys.path.insert(0, str(ROOT))
from challenge.plant.design import DESIGN  # noqa: E402

DATA = ROOT / "participant" / "historian_60s.parquet"
REPORT = GRAPH / "HISTORIAN_CHECK.md"
BASELINE_H = 6.0


def hfg_kJ_kg(tsat_c):
    return 2500.0 - 2.4 * tsat_c


def main() -> None:
    df = pd.read_parquet(DATA)
    ts = pd.to_datetime(df["timestamp"]) if "timestamp" in df.columns else df.index.to_series()
    t0 = ts.iloc[0]
    win = df[(ts - t0) <= pd.Timedelta(hours=BASELINE_H)].copy()
    rows = []

    # V1 mass balance: CALC-MBAL is noise-free; the residual against the two flow meters should be meter noise only
    resid1 = win["CALC-MBAL"] - (win["FI-101"] - win["FI-102"])
    noise1 = (win["FI-101"].std() ** 2 + win["FI-102"].std() ** 2) ** 0.5
    ok1 = abs(resid1.mean()) < 0.01 and abs(resid1.std() / noise1 - 1) < 0.2
    rows.append(("V1", "CALC-MBAL = FI-101 - FI-102 (graph: CALC-MBAL derived_from FI-101, FI-102)",
                 f"residual mean {resid1.mean():+.4f}, std {resid1.std():.4f} m3/h; "
                 f"flow-meter noise predicts {noise1:.4f} m3/h",
                 "PASS" if ok1 else "CHECK"))

    # V2 cascade: the model holds FIC-201.SP = 30 x TIC-101.OP exactly (residual 0.0000 kg/h in a 10-min model run).
    # The export adds noise to the OP tag only (sigma 0.15 %), so the residual should scatter by 30 x std(OP).
    resid2 = win["FIC-201.SP"] - 30.0 * win["TIC-101.OP"]
    op_sigma = 30.0 * win["TIC-101.OP"].std()
    ok2 = abs(resid2.mean()) < 0.5 and abs(resid2.std() / op_sigma - 1) < 0.2
    rows.append(("V2", "FIC-201.SP = 30 x TIC-101.OP (graph: cascade_sp, 30 kg/h per %)",
                 f"residual mean {resid2.mean():+.3f}, std {resid2.std():.3f} kg/h; "
                 f"OP noise predicts 30 x std(OP) = {op_sigma:.3f} kg/h",
                 "PASS (scatter is OP noise)" if ok2 else "CHECK"))

    # V3 steam duty: CALC-DUTY vs steam flow * hfg (graph: CALC-DUTY derived from FIC-201.PV and TI-201)
    tsat = win["TI-201"]
    duty_from_steam = win["FIC-201.PV"] * hfg_kJ_kg(tsat) / 3600.0
    ratio = win["CALC-DUTY"] / duty_from_steam
    rows.append(("V3", "CALC-DUTY = FIC-201.PV x hfg(TI-201) / 3600 (tags.csv: steam-side duty)",
                 f"median ratio {ratio.median():.4f}, p5-p95 {ratio.quantile(0.05):.4f}-{ratio.quantile(0.95):.4f}",
                 "PASS" if abs(ratio.median() - 1.0) < 0.02 else "CHECK"))

    # V4 energy balance: CALC-EBAL = CALC-DUTY - CALC-DUTY-PROC - Q_loss (graph C11).
    # At steady state the closure residual should be near zero (noise / accumulation).
    ebal_mean = win["CALC-EBAL"].mean()
    ebal_std = win["CALC-EBAL"].std()
    loss_kW = DESIGN.UA_loss_W_K * (win["TIC-101.PV"].mean() - DESIGN.T_ambient_C) / 1000.0
    ok4 = abs(ebal_mean) < 5.0
    rows.append(("V4", "CALC-EBAL closes the energy balance (duty - process - ambient loss)",
                 f"mean CALC-EBAL {ebal_mean:.2f} kW (std {ebal_std:.2f}); ambient loss for reference = {loss_kW:.2f} kW",
                 "PASS" if ok4 else "CHECK"))

    # V5 setpoints and PVs in baseline
    rows.append(("V5", "Baseline operating point (design basis 75 C, 2.0 m, 6 barg)",
                 f"TIC PV {win['TIC-101.PV'].mean():.2f} C; LIC PV {win['LIC-101.PV'].mean():.3f} m; "
                 f"PI-201 {win['PI-201'].mean():.2f} barg",
                 "INFO"))

    # V6 product temperature vs tank temperature (graph: TI-102 is on the product line)
    d_t = (win["TI-102"] - win["TIC-101.PV"]).abs()
    rows.append(("V6", "TI-102 (product line) reads the same as the tank temperature TIC-101.PV",
                 f"mean |TI-102 - TIC-101.PV| = {d_t.mean():.3f} C",
                 "INFO"))

    lines = ["# Historian check of graph relationships", "",
             f"Source: `participant/historian_60s.parquet`, first {BASELINE_H:.0f} h from {t0} ({len(win)} samples).",
             "Read-only check; does not change any project file.", "",
             "| ID | Relationship in graph | Result | Status |", "|---|---|---|---|"]
    lines += [f"| {i} | {r} | {res} | **{s}** |" for i, r, res, s in rows]
    lines += ["", "PASS = relationship holds in the data. CHECK = relationship does not hold; investigate before",
              "trusting the graph. INFO = reported values, no pass/fail rule.", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    for i, r, res, s in rows:
        print(f"{i} {s:5s} {r}\n      {res}")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
