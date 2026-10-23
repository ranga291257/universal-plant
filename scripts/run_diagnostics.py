#!/usr/bin/env python3
"""Run deterministic diagnostic baseline on pilot (dev) and score vs private key."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from challenge.diagnostics.baseline import events_to_submission, run_diagnostics

DEV_HIST = ROOT / "data" / "pilot" / "historian.parquet"
KEY = ROOT / "private" / "answer_key.csv"
OUT_SUB = ROOT / "docs" / "validation" / "diagnostic_submission_dev.csv"
OUT_REP = ROOT / "docs" / "validation" / "diagnostic_report.md"
BLIND_SUB = ROOT / "blind_eval" / "submission_from_baseline.csv"


def overlap(a0, a1, b0, b1) -> bool:
    return a0 <= b1 and b0 <= a1


def main() -> int:
    events = run_diagnostics(DEV_HIST, baseline_hours=6.0)
    OUT_SUB.parent.mkdir(parents=True, exist_ok=True)
    events_to_submission(events, OUT_SUB)
    events_to_submission(events, BLIND_SUB)

    key = pd.read_csv(KEY)
    score = 0
    lines = ["# Diagnostic baseline report (dev seed)", "", f"Detected events: {len(events)}", ""]
    # Greedy longest-overlap one-to-one matching
    pairs = []
    for ei, e in enumerate(events):
        e0 = pd.Timestamp(e.start_utc)
        e1 = pd.Timestamp(e.end_utc)
        for ki, row in key.iterrows():
            k0 = pd.Timestamp(row["start_utc"])
            k1 = pd.Timestamp(row["end_utc"]) + pd.Timedelta(hours=6)
            if overlap(e0, e1, k0, k1):
                ov = (min(e1, k1) - max(e0, k0)).total_seconds()
                pairs.append((ov, ei, ki))
    pairs.sort(reverse=True)
    used_e, used_k = set(), set()
    matches = {}
    for ov, ei, ki in pairs:
        if ei in used_e or ki in used_k:
            continue
        used_e.add(ei)
        used_k.add(ki)
        matches[ei] = ki
    for ei, e in enumerate(events):
        if ei not in matches:
            score -= 1
            lines.append(f"- FALSE POSITIVE {e.start_utc} .. {e.end_utc}")
        else:
            row = key.loc[matches[ei]]
            score += 1
            cause_ok = "fouling" in e.root_cause.lower() or "UA" in e.root_cause
            if cause_ok:
                score += 2
            lines.append(
                f"- MATCH {row['event_id']}: detected {e.start_utc}..{e.end_utc}; cause_ok={cause_ok}"
            )
    for ki, row in key.iterrows():
        if ki not in used_k:
            lines.append(f"- MISSED {row['event_id']}")
    lines += ["", f"**Score = {score}** ( +1 detect, +2 cause, -1 FP )", ""]
    OUT_REP.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
