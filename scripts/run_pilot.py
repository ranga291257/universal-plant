#!/usr/bin/env python3
"""Run 24 h pilot with UA fouling fault; export historian + plots."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from challenge.faults.scenarios import FOULING_UA_PILOT
from challenge.historian.export import HistorianConfig, simulate_and_export

OUT = ROOT / "data" / "pilot"
PLOTS = ROOT / "docs" / "validation" / "plots"
IC = ROOT / "challenge" / "plant" / "baseline_ic.json"


def main() -> int:
    PLOTS.mkdir(parents=True, exist_ok=True)
    cfg = HistorianConfig(duration_h=24.0, dt_s=1.0, sample_s=10.0, seed=42, noise=True)
    print("Simulating 24 h pilot ...")
    df = simulate_and_export(OUT, FOULING_UA_PILOT, IC if IC.exists() else None, cfg)
    print(f"Wrote {OUT} rows={len(df)}")

    # Plots
    d = df.set_index("timestamp")
    fig, axs = plt.subplots(4, 1, figsize=(11, 9), sharex=True)
    d["TIC-101.PV"].plot(ax=axs[0], label="TIC-101.PV")
    d["TIC-101.SP"].plot(ax=axs[0], label="SP", linestyle="--")
    axs[0].set_ylabel("°C")
    axs[0].legend(loc="upper right")
    axs[0].set_title("Pilot: UA fouling 08:00–12:00 h from start")

    d["FIC-201.PV"].plot(ax=axs[1], label="steam kg/h")
    d["TV-101.POS"].plot(ax=axs[1], label="TV-101.POS %", secondary_y=False)
    axs[1].legend(loc="upper right")
    axs[1].set_ylabel("kg/h or %")

    d["CALC-UA"].plot(ax=axs[2], label="CALC-UA")
    axs[2].set_ylabel("W/K")
    axs[2].legend()

    d["CALC-EBAL"].plot(ax=axs[3], label="CALC-EBAL")
    d["LIC-101.PV"].plot(ax=axs[3], label="level m", secondary_y=True)
    axs[3].legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(PLOTS / "pilot_overview.png", dpi=120)
    plt.close(fig)

    # Zoom around fault
    t0 = d.index.min()
    fault_start = t0 + pd.Timedelta(hours=7)
    fault_end = t0 + pd.Timedelta(hours=13)
    z = d.loc[fault_start:fault_end]
    fig, axs = plt.subplots(3, 1, figsize=(11, 7), sharex=True)
    z["CALC-UA"].plot(ax=axs[0])
    axs[0].set_ylabel("CALC-UA W/K")
    z["FIC-201.PV"].plot(ax=axs[1])
    axs[1].set_ylabel("Steam kg/h")
    z["TV-101.POS"].plot(ax=axs[2])
    axs[2].set_ylabel("TV %")
    fig.suptitle("Fault window (±1 h)")
    fig.tight_layout()
    fig.savefig(PLOTS / "pilot_fault_zoom.png", dpi=120)
    plt.close(fig)
    print(f"Plots → {PLOTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
