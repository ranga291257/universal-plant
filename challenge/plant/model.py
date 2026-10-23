"""Dynamic heated-tank plant: mass + energy ODEs with steam coil and valves."""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any

from .controllers import ControlSuite
from .design import DESIGN, DesignBasis, hfg_kJ_kg, tsat_C, ua_eff_kW_K


@dataclass
class PlantParams:
    """Mutable physical parameters (faults inject here)."""

    ua_clean_kW_K: float = DESIGN.UA_clean_kW_K
    ua_multiplier: float = 1.0  # fouling: reduce this
    P_steam_barg: float = DESIGN.P_steam_barg
    UA_loss_W_K: float = DESIGN.UA_loss_W_K
    T_ambient_C: float = DESIGN.T_ambient_C
    Cv_m3_s: float = DESIGN.Cv_m3_s
    R: float = DESIGN.rangeability_R
    TV_travel_max_pct: float = 100.0  # travel limitation fault
    rho: float = DESIGN.rho_kg_m3
    cp: float = DESIGN.cp_kJ_kgK
    area_m2: float = DESIGN.area_m2


@dataclass
class PlantState:
    t_s: float = 0.0
    T_C: float = DESIGN.T_SP_C
    h_m: float = DESIGN.level_SP_m
    TV_pos_pct: float = 50.0
    LV_pos_pct: float = 50.0
    # true steam flow from energy (kg/h)
    steam_kg_h: float = DESIGN.design_steam_kg_h
    F_feed_m3_h: float = DESIGN.feed_m3_h
    T_feed_C: float = DESIGN.feed_T_C
    Q_coil_kW: float = DESIGN.design_duty_kW
    F_out_m3_h: float = DESIGN.feed_m3_h


def _positioner(pos: float, demand: float, dt: float, tau: float, travel_max: float) -> float:
    demand = min(max(demand, 0.0), travel_max)
    alpha = dt / (tau + dt)
    return pos + alpha * (demand - pos)


def coil_heat(params: PlantParams, T_C: float, x_tv: float) -> tuple[float, float, float, float]:
    """Return Q_kW, steam_kg_h, Tsat_C, UA_eff_kW_K."""
    Tsat = tsat_C(params.P_steam_barg)
    hfg = hfg_kJ_kg(Tsat)
    ua = ua_eff_kW_K(x_tv, params.ua_clean_kW_K * params.ua_multiplier, params.R)
    Q = max(ua * (Tsat - T_C), 0.0)
    steam = Q / hfg * 3600.0 if hfg > 1e-6 else 0.0
    return Q, steam, Tsat, ua


def step_plant(
    state: PlantState,
    params: PlantParams,
    ctrl: ControlSuite,
    dt_s: float,
    meas: dict[str, float] | None = None,
    d: DesignBasis = DESIGN,
) -> tuple[PlantState, dict[str, float]]:
    """One integration step. Controllers use `meas` if provided (sensor faults)."""
    m = meas or {}
    T_meas = m.get("TIC-101.PV", state.T_C)
    steam_meas = m.get("FIC-201.PV", state.steam_kg_h)
    level_meas = m.get("LIC-101.PV", state.h_m)

    outs = ctrl.step(T_meas, steam_meas, level_meas, dt_s)
    state.TV_pos_pct = _positioner(
        state.TV_pos_pct, outs["TV_demand"], dt_s, d.positioner_tau_s, params.TV_travel_max_pct
    )
    state.LV_pos_pct = _positioner(
        state.LV_pos_pct, outs["LV_demand"], dt_s, d.positioner_tau_s, 100.0
    )

    x_tv = state.TV_pos_pct / 100.0
    x_lv = state.LV_pos_pct / 100.0
    Q, steam, Tsat, ua = coil_heat(params, state.T_C, x_tv)
    state.Q_coil_kW = Q
    state.steam_kg_h = steam

    F_feed = state.F_feed_m3_h / 3600.0
    F_out = params.Cv_m3_s * x_lv * math.sqrt(max(state.h_m, 1e-6))
    state.F_out_m3_h = F_out * 3600.0

    V = params.area_m2 * max(state.h_m, 1e-6)
    # Mass / level
    dh = (F_feed - F_out) / params.area_m2 * dt_s
    state.h_m = min(max(state.h_m + dh, 0.05), d.height_m - 0.05)

    # Energy
    Q_loss_kW = params.UA_loss_W_K * (state.T_C - params.T_ambient_C) / 1000.0
    dT = (
        params.rho * params.cp * F_feed * (state.T_feed_C - state.T_C)
        + Q
        - Q_loss_kW
    ) / (params.rho * params.cp * V) * dt_s
    state.T_C = state.T_C + dT
    state.t_s += dt_s

    tags = {
        **outs,
        "TIC-101.PV_true": state.T_C,
        "LIC-101.PV_true": state.h_m,
        "FIC-201.PV_true": state.steam_kg_h,
        "TV-101.POS": state.TV_pos_pct,
        "LV-101.POS": state.LV_pos_pct,
        "FI-101": state.F_feed_m3_h,
        "TI-100": state.T_feed_C,
        "FI-102": state.F_out_m3_h,
        "TI-102": state.T_C,
        "PI-201": params.P_steam_barg,
        "TI-201": Tsat,
        "TI-202": Tsat - 5.0,
        "TI-901": params.T_ambient_C,
        "Q_coil_kW": Q,
        "UA_eff_kW_K": ua,
        "CALC-DUTY": Q,
        "CALC-DUTY-PROC": state.F_feed_m3_h / 3600.0 * params.rho * params.cp * (state.T_C - state.T_feed_C),
        "CALC-APPROACH": Tsat - state.T_C,
        "CALC-UA": (1000.0 * Q / max(Tsat - state.T_C, 0.1)),
        "CALC-MBAL": state.F_feed_m3_h - state.F_out_m3_h,
        "AI-101": 99.4 - 0.02 * (state.T_C - 78.0) ** 2,
    }
    # Closure residual: steam duty − process sensible − ambient loss (≈ 0 at SS).
    tags["CALC-EBAL"] = tags["CALC-DUTY"] - tags["CALC-DUTY-PROC"] - Q_loss_kW
    return state, tags


def settle_to_steady(
    hours: float = 2.0,
    dt_s: float = 1.0,
    d: DesignBasis = DESIGN,
) -> tuple[PlantState, PlantParams, ControlSuite, dict[str, float]]:
    params = PlantParams()
    state = PlantState()
    ctrl = ControlSuite.from_design(d)
    # Initialize FIC SP / OP near design steam
    ctrl.fic.SP = d.design_steam_kg_h
    ctrl.tic.OP = 100.0 * d.design_steam_kg_h / d.steam_flow_max_kg_h
    ctrl.tic.integral = ctrl.tic.OP
    ctrl.fic.OP = 50.0
    ctrl.fic.integral = 50.0
    ctrl.lic.OP = 50.0
    ctrl.lic.integral = 50.0
    tags: dict[str, float] = {}
    n = int(hours * 3600 / dt_s)
    for _ in range(n):
        state, tags = step_plant(state, params, ctrl, dt_s, d=d)
    return state, params, ctrl, tags


def state_to_dict(state: PlantState, params: PlantParams, ctrl: ControlSuite) -> dict[str, Any]:
    return {
        "state": asdict(state),
        "params": asdict(params),
        "ctrl": {
            "tic": asdict(ctrl.tic),
            "fic": asdict(ctrl.fic),
            "lic": asdict(ctrl.lic),
            "steam_flow_max_kg_h": ctrl.steam_flow_max_kg_h,
        },
    }


def load_from_dict(data: dict[str, Any]) -> tuple[PlantState, PlantParams, ControlSuite]:
    from .controllers import PIController

    state = PlantState(**data["state"])
    params = PlantParams(**data["params"])
    c = data["ctrl"]
    ctrl = ControlSuite(
        tic=PIController(**c["tic"]),
        fic=PIController(**c["fic"]),
        lic=PIController(**c["lic"]),
        steam_flow_max_kg_h=c["steam_flow_max_kg_h"],
    )
    return state, params, ctrl
