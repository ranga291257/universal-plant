#!/usr/bin/env python3
"""DWSIM digital twin CLI: simulate | rate | fouling | optimize | demo."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from challenge.plant.dwsim_twin import (  # noqa: E402
    TWIN_BASELINE,
    TWIN_FOULED,
    detect_fouling,
    optimize_twin,
    rate_twin_window,
    run_twin_demo,
    save_twin_baseline,
    simulate_twin,
)
from challenge.plant.ss_modes import SSFactors  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="DWSIM twin Simulate/Rate/Fouling/Optimize")
    p.add_argument(
        "mode",
        choices=["simulate", "rate", "fouling", "optimize", "demo"],
    )
    p.add_argument("--start-s", type=float, default=3600.0)
    p.add_argument("--end-s", type=float, default=7200.0)
    p.add_argument("--fouled-start-s", type=float, default=36000.0)
    p.add_argument("--fouled-end-s", type=float, default=39600.0)
    p.add_argument("--feed", type=float, default=None)
    p.add_argument("--ua-multiplier", type=float, default=1.0)
    args = p.parse_args()

    if args.mode == "simulate":
        fac = SSFactors()
        if args.feed is not None:
            fac.feed_m3_h = args.feed
        out = simulate_twin(fac, ua_multiplier=args.ua_multiplier).as_dict()
    elif args.mode == "rate":
        r = rate_twin_window(start_s=args.start_s, end_s=args.end_s)
        path = save_twin_baseline(r, TWIN_BASELINE)
        out = {"saved": str(path), "rate": r.as_dict()}
    elif args.mode == "fouling":
        clean = rate_twin_window(start_s=args.start_s, end_s=args.end_s)
        fouled = rate_twin_window(start_s=args.fouled_start_s, end_s=args.fouled_end_s)
        save_twin_baseline(clean, TWIN_BASELINE)
        save_twin_baseline(fouled, TWIN_FOULED)
        out = {
            "clean": {"ua_multiplier": clean.ua_multiplier, "TV_pct": clean.TV_pct},
            "fouled": {"ua_multiplier": fouled.ua_multiplier, "TV_pct": fouled.TV_pct},
            "detection": detect_fouling(clean, fouled),
        }
    elif args.mode == "optimize":
        out = optimize_twin(TWIN_BASELINE)
    else:
        out = run_twin_demo()

    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
