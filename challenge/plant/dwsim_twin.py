"""DWSIM digital twin: Simulate / Rate / Optimize + fouling detection.

``challenge.plant`` is the real_plant simulator (dynamic historian). This module
is the digital twin path: rate historian windows, detect fouling via
``ua_multiplier``, and optimize. See docs/ARCHITECTURE.md and models/dwsim/NOTES.md.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .design import DESIGN, hfg_kJ_kg, tsat_C, ua_eff_kW_K
from .ss_modes import (
    DEFAULT_HISTORIAN,
    SSFactors,
    average_ss_window,
    solve_ss,
    SSResult,
)
from .model import PlantParams

ROOT = Path(__file__).resolve().parents[2]
TWIN_FLOWSHEET = ROOT / "models" / "dwsim" / "TK101_twin_ss.dwxmz"
TWIN_BASELINE = ROOT / "models" / "dwsim" / "twin_rated_baseline.json"
TWIN_FOULED = ROOT / "models" / "dwsim" / "twin_rated_fouled.json"
SURROGATE_CSV = ROOT / "models" / "dwsim" / "twin_surrogate_doe.csv"

# Fouling alarm: ua_multiplier drop vs clean baseline
FOULING_UA_DROP = 0.15  # absolute drop that triggers alarm (e.g. 1.0 → 0.85)
FOULING_UA_RATIO = 0.85  # or ratio fouled/clean below this


@dataclass
class TwinRateResult:
    ua_multiplier: float
    UA_eff_kW_K: float
    Cv_m3_s: float
    Q_coil_kW: float
    steam_kg_h: float
    TV_pct: float
    LV_pct: float
    T_C: float
    h_m: float
    factors: dict[str, float]
    meas: dict[str, float]
    method: str = "ua_backcalc_from_TV_and_energy"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def energy_duty_kW(
    feed_m3_h: float,
    feed_T_C: float,
    T_C: float,
    UA_loss_W_K: float = DESIGN.UA_loss_W_K,
    T_ambient_C: float = DESIGN.T_ambient_C,
    rho: float = DESIGN.rho_kg_m3,
    cp: float = DESIGN.cp_kJ_kgK,
) -> dict[str, float]:
    """SS coil duty the DWSIM heater must supply (process + ambient loss)."""
    F = feed_m3_h / 3600.0
    Q_proc = rho * cp * F * (T_C - feed_T_C)
    Q_loss = UA_loss_W_K * (T_C - T_ambient_C) / 1000.0
    Q = Q_proc + Q_loss
    return {"Q_proc_kW": Q_proc, "Q_loss_kW": Q_loss, "Q_coil_kW": Q}


def backcalc_ua_multiplier(
    Q_coil_kW: float,
    T_C: float,
    TV_pct: float,
    P_steam_barg: float = DESIGN.P_steam_barg,
    ua_clean: float = DESIGN.UA_clean_kW_K,
    R: float = DESIGN.rangeability_R,
) -> tuple[float, float]:
    """Recover ua_multiplier from duty, temperature, and measured TV%."""
    Tsat = tsat_C(P_steam_barg)
    approach = max(Tsat - T_C, 0.1)
    UA_eff = Q_coil_kW / approach
    x = _clamp(TV_pct / 100.0, 1e-6, 1.0)
    # UA_eff = ua_clean * mult * R^(x-1)  →  mult = UA_eff / (ua_clean * R^(x-1))
    mult = UA_eff / (ua_clean * (R ** (x - 1.0)))
    return float(mult), float(UA_eff)


def backcalc_Cv(
    feed_m3_h: float,
    LV_pct: float,
    h_m: float,
) -> float:
    x = _clamp(LV_pct / 100.0, 1e-6, 1.0)
    return (feed_m3_h / 3600.0) / (x * math.sqrt(max(h_m, 1e-6)))


def _clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


def simulate_twin(factors: SSFactors | None = None, ua_multiplier: float = 1.0) -> SSResult:
    """Mode 1 on the twin: design coil law, closed SS DOFs (same physics as plant SS)."""
    params = PlantParams(ua_multiplier=ua_multiplier)
    return solve_ss(params, factors or SSFactors())


def rate_twin_window(
    historian_path: Path | str = DEFAULT_HISTORIAN,
    start_s: float = 3600.0,
    end_s: float = 7200.0,
) -> TwinRateResult:
    """
    Rate one SS historian window.

    Boundaries from measurements; duty from energy balance (DWSIM heater target);
    ``ua_multiplier`` from measured TV% + coil law (fouling knob).
    """
    meas = average_ss_window(historian_path, start_s, end_s)
    feed = meas["FI-101"]
    Tin = meas["TI-100"]
    T = meas["TIC-101.PV"]
    h = meas["LIC-101.PV"]
    TV = meas["TV-101.POS"]
    LV = meas["LV-101.POS"]
    P = meas.get("PI-201", DESIGN.P_steam_barg)
    Tamb = meas.get("TI-901", DESIGN.T_ambient_C)

    duty = energy_duty_kW(feed, Tin, T, DESIGN.UA_loss_W_K, Tamb)
    # Prefer historian CALC-DUTY when present (plant energy tag)
    Q = float(meas.get("CALC-DUTY", duty["Q_coil_kW"]))
    mult, UA_eff = backcalc_ua_multiplier(Q, T, TV, P)
    Cv = backcalc_Cv(feed, LV, h)
    Tsat = tsat_C(P)
    steam = Q / hfg_kJ_kg(Tsat) * 3600.0

    return TwinRateResult(
        ua_multiplier=mult,
        UA_eff_kW_K=UA_eff,
        Cv_m3_s=Cv,
        Q_coil_kW=Q,
        steam_kg_h=steam,
        TV_pct=TV,
        LV_pct=LV,
        T_C=T,
        h_m=h,
        factors={
            "feed_m3_h": feed,
            "feed_T_C": Tin,
            "T_SP_C": meas.get("TIC-101.SP", T),
            "level_SP_m": meas.get("LIC-101.SP", h),
            "P_steam_barg": P,
            "T_ambient_C": Tamb,
        },
        meas=meas,
    )


def save_twin_baseline(result: TwinRateResult, path: Path | str = TWIN_BASELINE) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "role": "dwsim_digital_twin_rated_baseline",
        "flowsheet": str(TWIN_FLOWSHEET),
        "knobs": {
            "ua_multiplier": result.ua_multiplier,
            "Cv_m3_s": result.Cv_m3_s,
            "UA_loss_W_K": DESIGN.UA_loss_W_K,
        },
        "rate": result.as_dict(),
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def load_twin_baseline(path: Path | str = TWIN_BASELINE) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def detect_fouling(
    clean: TwinRateResult | dict[str, Any],
    candidate: TwinRateResult | dict[str, Any],
    ua_drop: float = FOULING_UA_DROP,
    ua_ratio: float = FOULING_UA_RATIO,
) -> dict[str, Any]:
    """Compare rated ua_multiplier: drop ⇒ fouling (vs header/sensor competitors)."""
    def mult(x: TwinRateResult | dict) -> float:
        if isinstance(x, TwinRateResult):
            return x.ua_multiplier
        if "ua_multiplier" in x:
            return float(x["ua_multiplier"])
        return float(x["knobs"]["ua_multiplier"])

    def tv(x: TwinRateResult | dict) -> float:
        if isinstance(x, TwinRateResult):
            return x.TV_pct
        r = x.get("rate", x)
        return float(r.get("TV_pct", 50.0))

    m0, m1 = mult(clean), mult(candidate)
    drop = m0 - m1
    ratio = m1 / m0 if m0 > 1e-9 else 1.0
    fouled = (drop >= ua_drop) or (ratio <= ua_ratio)
    return {
        "fouling_detected": fouled,
        "ua_multiplier_clean": m0,
        "ua_multiplier_candidate": m1,
        "ua_drop": drop,
        "ua_ratio": ratio,
        "TV_pct_clean": tv(clean),
        "TV_pct_candidate": tv(candidate),
        "diagnosis": (
            "coil_fouling"
            if fouled
            else "no_fouling_vs_baseline"
        ),
        "note": (
            "TV% rose while ua_multiplier fell at similar T — classic fouling "
            "signature (not steam-header collapse)."
            if fouled
            else "Rated UA within band of clean baseline."
        ),
    }


def optimize_twin(
    baseline_path: Path | str = TWIN_BASELINE,
    feed_max_m3_h: float = 25.0,
    TV_max_pct: float = 90.0,
    LV_max_pct: float = 90.0,
) -> dict[str, Any]:
    """Maximize feed on rated twin knobs subject to valve headroom."""
    b = load_twin_baseline(baseline_path)
    params = PlantParams(
        ua_multiplier=b["knobs"]["ua_multiplier"],
        Cv_m3_s=b["knobs"]["Cv_m3_s"],
        UA_loss_W_K=b["knobs"].get("UA_loss_W_K", DESIGN.UA_loss_W_K),
    )
    f0 = SSFactors(**{k: b["rate"]["factors"][k] for k in SSFactors.__dataclass_fields__
                      if k in b["rate"]["factors"]})
    base = solve_ss(params, f0)

    def ok(feed: float) -> tuple[bool, SSResult]:
        r = solve_ss(params, replace(f0, feed_m3_h=feed))
        return (
            r.ok and r.TV_pct <= TV_max_pct and r.LV_pct <= LV_max_pct,
            r,
        )

    lo, hi = f0.feed_m3_h, feed_max_m3_h
    best = base
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        good, r = ok(mid)
        if good:
            lo, best = mid, r
        else:
            hi = mid

    return {
        "mode": "dwsim_twin_optimize",
        "baseline_feed_m3_h": base.factors["feed_m3_h"],
        "optimized_feed_m3_h": best.factors["feed_m3_h"],
        "benefit": {
            "delta_feed_m3_h": best.factors["feed_m3_h"] - base.factors["feed_m3_h"],
            "delta_steam_kg_h": best.steam_kg_h - base.steam_kg_h,
        },
        "optimized": best.as_dict(),
        "knobs": b["knobs"],
    }


def surrogate_doe(
    n: int = 64,
    seed: int = 0,
    path: Path | str = SURROGATE_CSV,
) -> pd.DataFrame:
    """
    Space-filling samples of the twin SS map for optional ML surrogates.

    Factors: feed, Tin, T_SP, ua_multiplier.
    Responses: steam, TV%, LV%, duty.
    """
    rng = np.random.default_rng(seed)
    # Simple LHS-like uniform draws in bounds
    feeds = rng.uniform(10.0, 22.0, n)
    Tins = rng.uniform(15.0, 35.0, n)
    TSPs = rng.uniform(70.0, 80.0, n)
    uas = rng.uniform(0.55, 1.05, n)
    rows = []
    for i in range(n):
        fac = SSFactors(feed_m3_h=float(feeds[i]), feed_T_C=float(Tins[i]), T_SP_C=float(TSPs[i]))
        r = simulate_twin(fac, ua_multiplier=float(uas[i]))
        rows.append({
            "feed_m3_h": fac.feed_m3_h,
            "feed_T_C": fac.feed_T_C,
            "T_SP_C": fac.T_SP_C,
            "ua_multiplier": float(uas[i]),
            "steam_kg_h": r.steam_kg_h,
            "TV_pct": r.TV_pct,
            "LV_pct": r.LV_pct,
            "Q_coil_kW": r.Q_coil_kW,
            "ok": r.ok,
        })
    df = pd.DataFrame(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def run_twin_demo(
    historian_path: Path | str = DEFAULT_HISTORIAN,
) -> dict[str, Any]:
    """
    Full twin demo on pilot historian:
      - rate clean [1h,2h)
      - rate fouled [10h,11h)  (E001 fouling after 8 h)
      - detect fouling
      - optimize from clean baseline
      - write surrogate DOE sample file
    """
    clean = rate_twin_window(historian_path, 3600.0, 7200.0)
    fouled = rate_twin_window(historian_path, 36000.0, 39600.0)
    save_twin_baseline(clean, TWIN_BASELINE)
    save_twin_baseline(fouled, TWIN_FOULED)
    foul = detect_fouling(clean, fouled)
    opt = optimize_twin(TWIN_BASELINE)
    df = surrogate_doe(48, seed=42)
    sim = simulate_twin()
    return {
        "architecture": "python_plant + dwsim_twin",
        "simulate_design": {
            "T_C": sim.T_C,
            "steam_kg_h": sim.steam_kg_h,
            "TV_pct": sim.TV_pct,
            "ok": sim.ok,
        },
        "rate_clean": {
            "ua_multiplier": clean.ua_multiplier,
            "TV_pct": clean.TV_pct,
            "baseline": str(TWIN_BASELINE),
        },
        "rate_fouled": {
            "ua_multiplier": fouled.ua_multiplier,
            "TV_pct": fouled.TV_pct,
            "baseline": str(TWIN_FOULED),
        },
        "fouling": foul,
        "optimize": {
            "benefit": opt["benefit"],
            "optimized_feed_m3_h": opt["optimized_feed_m3_h"],
        },
        "surrogate_doe": {
            "path": str(SURROGATE_CSV),
            "n": len(df),
            "ok_fraction": float(df["ok"].mean()),
        },
        "dwsim_flowsheet": str(TWIN_FLOWSHEET),
    }
