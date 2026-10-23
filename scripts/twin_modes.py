#!/usr/bin/env python3
"""CLI for TK-101 Simulate / Rate / Optimize (steady-state twin modes)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from challenge.plant.ss_modes import (  # noqa: E402
    DEFAULT_BASELINE_PATH,
    DEFAULT_HISTORIAN,
    SSFactors,
    holdout,
    optimize,
    project,
    params_from_baseline,
    rate,
    run_demo,
    simulate,
)


def main() -> int:
    p = argparse.ArgumentParser(description="TK-101 SS twin: simulate | rate | holdout | optimize | demo")
    p.add_argument(
        "mode",
        choices=["simulate", "rate", "holdout", "optimize", "project", "demo"],
    )
    p.add_argument("--historian", type=Path, default=DEFAULT_HISTORIAN)
    p.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE_PATH)
    p.add_argument("--start-s", type=float, default=3600.0, help="rate/holdout window start")
    p.add_argument("--end-s", type=float, default=7200.0, help="rate/holdout window end")
    p.add_argument("--feed", type=float, default=None)
    p.add_argument("--T-SP", type=float, default=None, dest="T_SP")
    p.add_argument("--level-SP", type=float, default=None, dest="level_SP")
    p.add_argument("--ua-multiplier", type=float, default=None)
    args = p.parse_args()

    if args.mode == "simulate":
        fac = SSFactors()
        if args.feed is not None:
            fac.feed_m3_h = args.feed
        if args.T_SP is not None:
            fac.T_SP_C = args.T_SP
        if args.level_SP is not None:
            fac.level_SP_m = args.level_SP
        out = simulate(fac).as_dict()
    elif args.mode == "rate":
        out = rate(args.historian, args.start_s, args.end_s, args.baseline, write=True)
    elif args.mode == "holdout":
        out = holdout(args.historian, args.baseline, args.start_s, args.end_s)
    elif args.mode == "optimize":
        out = optimize(args.baseline)
    elif args.mode == "project":
        params = params_from_baseline(path=args.baseline)
        kw = {}
        if args.feed is not None:
            kw["feed_m3_h"] = args.feed
        if args.T_SP is not None:
            kw["T_SP_C"] = args.T_SP
        if args.ua_multiplier is not None:
            kw["ua_multiplier"] = args.ua_multiplier
        out = project(params, **kw).as_dict()
    else:
        out = run_demo(args.historian, args.baseline)

    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
