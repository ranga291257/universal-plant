"""real_plant steady-state Simulate / Rate / Optimize (algebraic Adjust DOFs).

LIC → level SP + Fin=Fout → LV%; TIC → T SP → TV% from coil law.
See docs/ARCHITECTURE.md. For the digital twin path use dwsim_twin.py.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .design import DESIGN, DesignBasis, hfg_kJ_kg, tsat_C, ua_eff_kW_K
from .model import PlantParams

DEFAULT_BASELINE_PATH = Path(__file__).resolve().parent / "rated_baseline.json"
DEFAULT_HISTORIAN = (
    Path(__file__).resolve().parents[2] / "data" / "pilot" / "historian.csv"
)

# Acceptance (plan)
TOL_T_C = 1.0
TOL_LV_PCT = 5.0
UA_MULT_BOUNDS = (0.5, 1.2)
UA_LOSS_BOUNDS = (100.0, 2000.0)  # W/K
CV_BOUNDS = (0.002, 0.02)  # m3/s per sqrt(m)


@dataclass
class SSFactors:
    """DOE / boundary factors (Mode 1 inputs; Mode 2 frozen from plant)."""

    feed_m3_h: float = DESIGN.feed_m3_h
    feed_T_C: float = DESIGN.feed_T_C
    T_SP_C: float = DESIGN.T_SP_C
    level_SP_m: float = DESIGN.level_SP_m
    P_steam_barg: float = DESIGN.P_steam_barg
    T_ambient_C: float = DESIGN.T_ambient_C


@dataclass
class SSResult:
    """Solved steady state with DOFs closed."""

    T_C: float
    h_m: float
    TV_pct: float
    LV_pct: float
    steam_kg_h: float
    Q_coil_kW: float
    Q_proc_kW: float
    Q_loss_kW: float
    CALC_EBAL: float
    UA_eff_kW_K: float
    F_out_m3_h: float
    factors: dict[str, float] = field(default_factory=dict)
    params: dict[str, float] = field(default_factory=dict)
    ok: bool = True
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def _clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


def solve_ss(
    params: PlantParams | None = None,
    factors: SSFactors | None = None,
    d: DesignBasis = DESIGN,
) -> SSResult:
    """Algebraic SS: fix level and temperature SPs; Adjust TV% and LV%."""
    params = params or PlantParams()
    f = factors or SSFactors()
    # Allow factors to override steam P / ambient on the params copy used for coil
    p = replace(
        params,
        P_steam_barg=f.P_steam_barg,
        T_ambient_C=f.T_ambient_C,
    )

    h = _clamp(f.level_SP_m, 0.05, d.height_m - 0.05)
    T = f.T_SP_C
    F_m3_s = f.feed_m3_h / 3600.0

    # LIC Adjust: Fin = Fout → LV opening
    denom = p.Cv_m3_s * math.sqrt(h)
    if denom <= 1e-12:
        return SSResult(
            T, h, 50.0, 50.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            asdict(f), asdict(p), False, "Cv or level too small for LV solve",
        )
    x_lv = F_m3_s / denom
    LV_pct = 100.0 * x_lv
    if LV_pct < 0.0 or LV_pct > 100.0:
        # Still report; mark soft failure for capacity
        ok_lv = False
        msg_lv = f"LV% {LV_pct:.1f} outside 0-100 (Cv capacity)"
    else:
        ok_lv = True
        msg_lv = ""

    Tsat = tsat_C(p.P_steam_barg)
    hfg = hfg_kJ_kg(Tsat)
    Q_proc = p.rho * p.cp * F_m3_s * (T - f.feed_T_C)
    Q_loss = p.UA_loss_W_K * (T - p.T_ambient_C) / 1000.0
    Q_need = Q_proc + Q_loss
    approach = Tsat - T
    if approach <= 0.1:
        return SSResult(
            T, h, 100.0, LV_pct, 0.0, Q_need, Q_proc, Q_loss, 0.0, 0.0,
            f.feed_m3_h, asdict(f), asdict(p), False, "Tsat - T too small",
        )

    ua_needed = Q_need / approach
    ua_max = p.ua_clean_kW_K * p.ua_multiplier  # at x=1, R^(0)=1
    ua_min = ua_eff_kW_K(0.0, p.ua_clean_kW_K * p.ua_multiplier, p.R)

    def ua_of(x: float) -> float:
        return ua_eff_kW_K(x, p.ua_clean_kW_K * p.ua_multiplier, p.R)

    # TIC Adjust: find x_tv in [0,1] so ua(x)*(Tsat-T) = Q_need
    if ua_needed > ua_max * 1.001:
        x_tv = 1.0
        ok_tv = False
        msg_tv = "UA at full open insufficient for duty"
    elif ua_needed < ua_min:
        x_tv = 0.0
        ok_tv = True
        msg_tv = ""
    else:
        # ua = ua_clean*mult * R^(x-1) → x = 1 + ln(ua/ua_base)/ln(R)
        ua_base = p.ua_clean_kW_K * p.ua_multiplier
        x_tv = 1.0 + math.log(ua_needed / ua_base) / math.log(p.R)
        x_tv = _clamp(x_tv, 0.0, 1.0)
        ok_tv = True
        msg_tv = ""

    TV_pct = 100.0 * x_tv
    ua = ua_of(x_tv)
    Q = ua * approach
    steam = Q / hfg * 3600.0 if hfg > 1e-6 else 0.0
    ebal = Q - Q_proc - Q_loss

    ok = ok_lv and ok_tv
    message = "; ".join(m for m in (msg_lv, msg_tv) if m)
    return SSResult(
        T_C=T,
        h_m=h,
        TV_pct=TV_pct,
        LV_pct=LV_pct,
        steam_kg_h=steam,
        Q_coil_kW=Q,
        Q_proc_kW=Q_proc,
        Q_loss_kW=Q_loss,
        CALC_EBAL=ebal,
        UA_eff_kW_K=ua,
        F_out_m3_h=f.feed_m3_h,
        factors=asdict(f),
        params={
            "ua_multiplier": p.ua_multiplier,
            "UA_loss_W_K": p.UA_loss_W_K,
            "Cv_m3_s": p.Cv_m3_s,
            "ua_clean_kW_K": p.ua_clean_kW_K,
            "P_steam_barg": p.P_steam_barg,
        },
        ok=ok,
        message=message,
    )


def simulate(
    factors: SSFactors | dict[str, float] | None = None,
    params: PlantParams | None = None,
) -> SSResult:
    """Mode 1: design (or given) params; vary feeds/SPs."""
    if isinstance(factors, dict):
        factors = SSFactors(**{k: factors[k] for k in SSFactors.__dataclass_fields__ if k in factors})
    return solve_ss(params=params or PlantParams(), factors=factors or SSFactors())


def _window_mask(df: pd.DataFrame, start_s: float, end_s: float, t0: pd.Timestamp) -> pd.Series:
    elapsed = (pd.to_datetime(df["timestamp"], utc=True) - t0).dt.total_seconds()
    return (elapsed >= start_s) & (elapsed < end_s)


def average_ss_window(
    historian_path: Path | str = DEFAULT_HISTORIAN,
    start_s: float = 3600.0,
    end_s: float = 7200.0,
) -> dict[str, float]:
    """Mean tags over [start_s, end_s) from run start (SS-detected by caller)."""
    df = pd.read_csv(historian_path)
    t0 = pd.to_datetime(df["timestamp"].iloc[0], utc=True)
    m = _window_mask(df, start_s, end_s, t0)
    w = df.loc[m]
    if len(w) < 5:
        raise ValueError(f"SS window [{start_s},{end_s}) has only {len(w)} rows")
    keys = [
        "TIC-101.PV", "TIC-101.SP", "LIC-101.PV", "LIC-101.SP",
        "TV-101.POS", "LV-101.POS", "FI-101", "TI-100", "FI-102",
        "PI-201", "TI-901", "FIC-201.PV", "CALC-DUTY", "CALC-EBAL",
    ]
    out: dict[str, float] = {"n_rows": float(len(w)), "start_s": start_s, "end_s": end_s}
    for k in keys:
        if k in w.columns:
            out[k] = float(w[k].mean())
    # flatness diagnostics
    out["TIC-101.PV_std"] = float(w["TIC-101.PV"].std())
    out["LIC-101.PV_std"] = float(w["LIC-101.PV"].std())
    return out


def _meas_to_factors(meas: dict[str, float]) -> SSFactors:
    return SSFactors(
        feed_m3_h=meas.get("FI-101", DESIGN.feed_m3_h),
        feed_T_C=meas.get("TI-100", DESIGN.feed_T_C),
        T_SP_C=meas.get("TIC-101.SP", DESIGN.T_SP_C),
        level_SP_m=meas.get("LIC-101.SP", DESIGN.level_SP_m),
        P_steam_barg=meas.get("PI-201", DESIGN.P_steam_barg),
        T_ambient_C=meas.get("TI-901", DESIGN.T_ambient_C),
    )


def _rating_residuals(
    x: np.ndarray,
    factors: SSFactors,
    meas: dict[str, float],
    base: PlantParams,
) -> float:
    ua_m, ua_loss, cv = float(x[0]), float(x[1]), float(x[2])
    p = replace(base, ua_multiplier=ua_m, UA_loss_W_K=ua_loss, Cv_m3_s=cv)
    # Rate against measured tank T (not SP) so fouled-but-controlled cases still fit
    f = replace(factors, T_SP_C=meas.get("TIC-101.PV", factors.T_SP_C),
                level_SP_m=meas.get("LIC-101.PV", factors.level_SP_m))
    r = solve_ss(p, f)
    e_T = (r.T_C - meas["TIC-101.PV"]) ** 2  # ~0 by construction if using PV as SP
    e_TV = ((r.TV_pct - meas["TV-101.POS"]) / 100.0) ** 2
    e_LV = ((r.LV_pct - meas["LV-101.POS"]) / 100.0) ** 2
    e_steam = 0.0
    if "FIC-201.PV" in meas and r.steam_kg_h > 1.0:
        e_steam = ((r.steam_kg_h - meas["FIC-201.PV"]) / DESIGN.design_steam_kg_h) ** 2
    return e_TV + e_LV + 0.25 * e_steam + 0.01 * e_T


def rate(
    historian_path: Path | str = DEFAULT_HISTORIAN,
    start_s: float = 3600.0,
    end_s: float = 7200.0,
    baseline_path: Path | str = DEFAULT_BASELINE_PATH,
    write: bool = True,
) -> dict[str, Any]:
    """Mode 2: fit ua_multiplier, UA_loss_W_K, Cv_m3_s to an SS window; save baseline."""
    meas = average_ss_window(historian_path, start_s, end_s)
    factors = _meas_to_factors(meas)
    base = PlantParams(
        P_steam_barg=factors.P_steam_barg,
        T_ambient_C=factors.T_ambient_C,
    )
    x0 = np.array([1.0, DESIGN.UA_loss_W_K, DESIGN.Cv_m3_s])
    bounds = [UA_MULT_BOUNDS, UA_LOSS_BOUNDS, CV_BOUNDS]
    res = minimize(
        _rating_residuals,
        x0,
        args=(factors, meas, base),
        method="L-BFGS-B",
        bounds=bounds,
    )
    ua_m, ua_loss, cv = (float(v) for v in res.x)
    params = replace(base, ua_multiplier=ua_m, UA_loss_W_K=ua_loss, Cv_m3_s=cv)
    # Predict at measured T/h for metrics
    f_pred = replace(
        factors,
        T_SP_C=meas["TIC-101.PV"],
        level_SP_m=meas["LIC-101.PV"],
    )
    pred = solve_ss(params, f_pred)
    metrics = {
        "T_err_C": abs(pred.T_C - meas["TIC-101.PV"]),
        "TV_err_pct": abs(pred.TV_pct - meas["TV-101.POS"]),
        "LV_err_pct": abs(pred.LV_pct - meas["LV-101.POS"]),
        "steam_err_kg_h": abs(pred.steam_kg_h - meas.get("FIC-201.PV", pred.steam_kg_h)),
        "pass_T": abs(pred.T_C - meas["TIC-101.PV"]) <= TOL_T_C,
        "pass_LV": abs(pred.LV_pct - meas["LV-101.POS"]) <= TOL_LV_PCT,
        "optimizer_success": bool(res.success),
        "objective": float(res.fun),
    }
    # Physical bounds check
    metrics["pass_bounds"] = (
        UA_MULT_BOUNDS[0] <= ua_m <= UA_MULT_BOUNDS[1]
        and UA_LOSS_BOUNDS[0] <= ua_loss <= UA_LOSS_BOUNDS[1]
        and CV_BOUNDS[0] <= cv <= CV_BOUNDS[1]
    )
    metrics["pass"] = metrics["pass_T"] and metrics["pass_LV"] and metrics["pass_bounds"]

    payload = {
        "mode": "rate",
        "knobs": {
            "ua_multiplier": ua_m,
            "UA_loss_W_K": ua_loss,
            "Cv_m3_s": cv,
        },
        "factors": asdict(factors),
        "meas_window": meas,
        "prediction": pred.as_dict(),
        "metrics": metrics,
        "historian": str(historian_path),
        "window_s": [start_s, end_s],
    }
    if write:
        path = Path(baseline_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))
        payload["baseline_path"] = str(path)
    return payload


def load_baseline(path: Path | str = DEFAULT_BASELINE_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def params_from_baseline(baseline: dict[str, Any] | None = None,
                         path: Path | str = DEFAULT_BASELINE_PATH) -> PlantParams:
    b = baseline or load_baseline(path)
    k = b["knobs"]
    f = b.get("factors", {})
    return PlantParams(
        ua_multiplier=k["ua_multiplier"],
        UA_loss_W_K=k["UA_loss_W_K"],
        Cv_m3_s=k["Cv_m3_s"],
        P_steam_barg=f.get("P_steam_barg", DESIGN.P_steam_barg),
        T_ambient_C=f.get("T_ambient_C", DESIGN.T_ambient_C),
    )


def holdout(
    historian_path: Path | str = DEFAULT_HISTORIAN,
    baseline_path: Path | str = DEFAULT_BASELINE_PATH,
    start_s: float = 10800.0,
    end_s: float = 14400.0,
) -> dict[str, Any]:
    """Predict a second SS window with frozen rated knobs (no re-tune)."""
    baseline = load_baseline(baseline_path)
    params = params_from_baseline(baseline)
    meas = average_ss_window(historian_path, start_s, end_s)
    factors = _meas_to_factors(meas)
    f_pred = replace(
        factors,
        T_SP_C=meas["TIC-101.PV"],
        level_SP_m=meas["LIC-101.PV"],
    )
    pred = solve_ss(params, f_pred)
    metrics = {
        "T_err_C": abs(pred.T_C - meas["TIC-101.PV"]),
        "TV_err_pct": abs(pred.TV_pct - meas["TV-101.POS"]),
        "LV_err_pct": abs(pred.LV_pct - meas["LV-101.POS"]),
        "steam_err_kg_h": abs(pred.steam_kg_h - meas.get("FIC-201.PV", pred.steam_kg_h)),
        "pass_T": abs(pred.T_C - meas["TIC-101.PV"]) <= TOL_T_C,
        "pass_LV": abs(pred.LV_pct - meas["LV-101.POS"]) <= TOL_LV_PCT,
    }
    metrics["pass"] = metrics["pass_T"] and metrics["pass_LV"]
    return {
        "mode": "holdout",
        "window_s": [start_s, end_s],
        "meas_window": meas,
        "prediction": pred.as_dict(),
        "knobs": baseline["knobs"],
        "metrics": metrics,
    }


def check_outlier(
    meas: dict[str, float],
    params: PlantParams,
    tol_T: float = TOL_T_C,
    tol_TV: float = 10.0,
    tol_LV: float = TOL_LV_PCT,
) -> dict[str, Any]:
    """Reconciliation: flag measurement if model disagrees beyond tolerance."""
    factors = _meas_to_factors(meas)
    f_pred = replace(
        factors,
        T_SP_C=meas.get("TIC-101.PV", factors.T_SP_C),
        level_SP_m=meas.get("LIC-101.PV", factors.level_SP_m),
    )
    pred = solve_ss(params, f_pred)
    errs = {
        "T_err_C": abs(pred.T_C - meas.get("TIC-101.PV", pred.T_C)),
        "TV_err_pct": abs(pred.TV_pct - meas.get("TV-101.POS", pred.TV_pct)),
        "LV_err_pct": abs(pred.LV_pct - meas.get("LV-101.POS", pred.LV_pct)),
    }
    flags = {
        "T": errs["T_err_C"] > tol_T,
        "TV": errs["TV_err_pct"] > tol_TV,
        "LV": errs["LV_err_pct"] > tol_LV,
    }
    return {
        "outlier": any(flags.values()),
        "flags": flags,
        "errors": errs,
        "prediction": pred.as_dict(),
    }


def project(
    params: PlantParams,
    factors: SSFactors | None = None,
    **factor_overrides: float,
) -> SSResult:
    """What-if projection on rated (or given) params."""
    f = factors or SSFactors()
    if factor_overrides:
        f = replace(f, **{k: v for k, v in factor_overrides.items() if k in SSFactors.__dataclass_fields__})
    # param overrides via ua_multiplier etc.
    p = params
    for k in ("ua_multiplier", "UA_loss_W_K", "Cv_m3_s"):
        if k in factor_overrides:
            p = replace(p, **{k: factor_overrides[k]})
    return solve_ss(p, f)


def optimize(
    baseline_path: Path | str = DEFAULT_BASELINE_PATH,
    feed_max_m3_h: float = 25.0,
    TV_max_pct: float = 90.0,
    LV_max_pct: float = 90.0,
) -> dict[str, Any]:
    """Mode 3: maximize feed on rated knobs subject to valve headroom; benefit vs baseline."""
    baseline = load_baseline(baseline_path)
    params = params_from_baseline(baseline)
    f0 = SSFactors(**{k: baseline["factors"][k] for k in SSFactors.__dataclass_fields__
                      if k in baseline["factors"]})
    base_ss = solve_ss(params, f0)

    def feasible(feed: float) -> tuple[bool, SSResult]:
        r = solve_ss(params, replace(f0, feed_m3_h=feed))
        ok = (
            r.ok
            and 0.0 <= r.TV_pct <= TV_max_pct
            and 0.0 <= r.LV_pct <= LV_max_pct
        )
        return ok, r

    # Maximize feed by bisection
    lo, hi = f0.feed_m3_h, feed_max_m3_h
    best = base_ss
    if not feasible(lo)[0]:
        return {
            "mode": "optimize",
            "ok": False,
            "message": "baseline feed infeasible under valve limits",
            "baseline": base_ss.as_dict(),
        }
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        ok, r = feasible(mid)
        if ok:
            lo = mid
            best = r
        else:
            hi = mid

    benefit = {
        "delta_feed_m3_h": best.factors["feed_m3_h"] - base_ss.factors["feed_m3_h"],
        "delta_steam_kg_h": best.steam_kg_h - base_ss.steam_kg_h,
        "delta_Q_coil_kW": best.Q_coil_kW - base_ss.Q_coil_kW,
    }
    return {
        "mode": "optimize",
        "ok": True,
        "objective": "maximize_feed_m3_h",
        "constraints": {"TV_max_pct": TV_max_pct, "LV_max_pct": LV_max_pct},
        "baseline": base_ss.as_dict(),
        "optimized": best.as_dict(),
        "benefit": benefit,
        "knobs": baseline["knobs"],
    }


def run_demo(
    historian_path: Path | str = DEFAULT_HISTORIAN,
    baseline_path: Path | str = DEFAULT_BASELINE_PATH,
) -> dict[str, Any]:
    """
    End-to-end demo on pilot historian:
      rate on clean SS [1h,2h), hold-out [3h,4h),
      also report fouled window [10h,11h) as outlier/projection check.
    Event E001 fouling starts at 28800 s (8 h).
    """
    sim = simulate()
    rated = rate(historian_path, 3600.0, 7200.0, baseline_path, write=True)
    ho = holdout(historian_path, baseline_path, 10800.0, 14400.0)
    # Fouled regime: expect hold-out style prediction with clean knobs to fail TV match
    fouled_meas = average_ss_window(historian_path, 36000.0, 39600.0)
    params_clean = params_from_baseline(rated)
    outlier = check_outlier(fouled_meas, params_clean)
    # Re-rate on fouled window for diagnostic knob (ua_multiplier should drop)
    rated_fouled = rate(
        historian_path, 36000.0, 39600.0,
        Path(baseline_path).with_name("rated_baseline_fouled.json"),
        write=True,
    )
    opt = optimize(baseline_path)
    proj = project(
        params_from_baseline(rated),
        SSFactors(**rated["factors"]),
        feed_m3_h=18.0,
        ua_multiplier=0.6,
    )
    return {
        "simulate_design": sim.as_dict(),
        "rate_clean": {
            "knobs": rated["knobs"],
            "metrics": rated["metrics"],
            "path": rated.get("baseline_path"),
        },
        "holdout_clean": {"metrics": ho["metrics"], "window_s": ho["window_s"]},
        "fouled_outlier_vs_clean_knobs": outlier,
        "rate_fouled": {
            "knobs": rated_fouled["knobs"],
            "metrics": rated_fouled["metrics"],
        },
        "optimize": {
            "benefit": opt.get("benefit"),
            "optimized_feed": opt.get("optimized", {}).get("factors", {}).get("feed_m3_h"),
        },
        "project_feed18_ua06": proj.as_dict(),
    }
