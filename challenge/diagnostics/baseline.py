"""Deterministic diagnostic baseline: balances, residuals, change detection."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class DetectedEvent:
    start_utc: str
    end_utc: str
    kind: str
    root_cause: str
    evidence_tags: str
    notes: str = ""


def _ua_clean_est(df: pd.DataFrame, R: float = 50.0) -> pd.Series:
    """Back-calculate clean UA [kW/K] from CALC-UA [W/K] and valve position."""
    x = (df["TV-101.POS"].clip(1.0, 99.0) / 100.0)
    ua_eff_kW = df["CALC-UA"] / 1000.0
    return ua_eff_kW / (R ** (x - 1.0))


def run_diagnostics(historian_path: Path, baseline_hours: float = 6.0) -> list[DetectedEvent]:
    df = pd.read_parquet(historian_path) if historian_path.suffix == ".parquet" else pd.read_csv(historian_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df["UA_clean_est"] = _ua_clean_est(df)

    t0 = df.index.min()
    base = df.loc[t0 : t0 + pd.Timedelta(hours=baseline_hours)]
    ua0 = float(base["UA_clean_est"].median())
    tv0 = float(base["TV-101.POS"].median())
    steam0 = float(base["FIC-201.PV"].median())
    pi0 = float(base["PI-201"].median())

    # Fouling: estimated clean UA drops while steam header pressure stays put
    thresh = ua0 * 0.85
    low = df["UA_clean_est"] < thresh
    events: list[DetectedEvent] = []

    s = low.astype(int)
    changes = s.diff().fillna(float(s.iloc[0]))
    starts = df.index[changes == 1].tolist()
    if int(s.iloc[0]) == 1:
        starts = [df.index[0]] + starts
    ends = df.index[changes == -1].tolist()
    if int(s.iloc[-1]) == 1:
        ends = ends + [df.index[-1]]

    # Merge segments separated by short gaps (< 45 min)
    segments: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for a, b in zip(starts, ends):
        if (b - a) < pd.Timedelta(minutes=15):
            continue
        if segments and (a - segments[-1][1]) < pd.Timedelta(minutes=45):
            segments[-1] = (segments[-1][0], b)
        else:
            segments.append((a, b))

    for a, b in segments:
        if (b - a) < pd.Timedelta(minutes=30):
            continue
        window = df.loc[a:b]
        tv_up = float(window["TV-101.POS"].median()) > tv0 + 3.0
        steam_ok = abs(float(window["FIC-201.PV"].median()) - steam0) / max(steam0, 1) < 0.15
        pi_stable = abs(float(window["PI-201"].median()) - pi0) < 0.25
        if tv_up and pi_stable:
            cause = (
                "E-101 coil fouling / reduced clean UA "
                "(valve opens to hold duty; steam pressure unchanged)"
            )
        elif not pi_stable:
            cause = "Steam supply pressure change or heat-transfer degradation - check PI-201"
        else:
            cause = "Reduced coil heat-transfer capability (UA)"
        events.append(
            DetectedEvent(
                start_utc=a.strftime("%Y-%m-%dT%H:%M:%SZ"),
                end_utc=b.strftime("%Y-%m-%dT%H:%M:%SZ"),
                kind="fault",
                root_cause=cause,
                evidence_tags="TV-101.POS;FIC-201.PV;CALC-UA;PI-201;TIC-101.PV;TI-201",
                notes=(
                    f"UA_clean_est baseline={ua0:.1f} kW/K; thresh={thresh:.1f}; "
                    f"tv_up={tv_up}; steam_ok={steam_ok}; pi_stable={pi_stable}"
                ),
            )
        )
    return events


def events_to_submission(events: list[DetectedEvent], path: Path) -> None:
    rows = [
        {
            "start_utc": e.start_utc,
            "end_utc": e.end_utc,
            "kind": e.kind,
            "root_cause": e.root_cause,
            "evidence_tags": e.evidence_tags,
            "notes": e.notes,
        }
        for e in events
    ]
    pd.DataFrame(rows).to_csv(path, index=False)
