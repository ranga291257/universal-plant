#!/usr/bin/env python3
"""Sample the digital-twin SS map for optional ML surrogates."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from challenge.plant.dwsim_twin import SURROGATE_CSV, surrogate_doe  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("-n", type=int, default=128)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=Path, default=SURROGATE_CSV)
    args = p.parse_args()
    df = surrogate_doe(args.n, args.seed, args.out)
    print(f"wrote {args.out} rows={len(df)} ok_fraction={df['ok'].mean():.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
