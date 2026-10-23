"""Design basis for TK-101 non-reacting water hold tank.

Inspired by Scott Duncan / HistorianRCA (CC BY 4.0) for the heated-tank design idea.
Numbers and departures are owned by this project — see ASSUMPTIONS.md.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DesignBasis:
    # Geometry
    diameter_m: float = 2.0
    height_m: float = 4.0
    area_m2: float = math.pi  # π * 1^2

    # Nominal operating point
    feed_m3_h: float = 15.0
    feed_T_C: float = 25.0
    T_SP_C: float = 75.0
    level_SP_m: float = 2.0
    working_volume_m3: float = 2.0 * math.pi  # 6.283...

    # Fluid (water-like)
    rho_kg_m3: float = 1000.0
    cp_kJ_kgK: float = 4.18

    # Steam header (gauge)
    P_steam_barg: float = 6.0
    UA_clean_kW_K: float = 72.0
    rangeability_R: float = 50.0
    UA_loss_W_K: float = 500.0
    T_ambient_C: float = 20.0

    # Outlet valve: F_out = Cv * x * sqrt(h); Cv in m3/s per unit opening per m^0.5
    Cv_m3_s: float = 0.0059

    # Controllers (Kc as %output / eng unit; Ti in minutes)
    tic_Kc: float = 4.5  # % / degC → maps to FIC SP via OP
    tic_Ti_min: float = 15.0
    fic_Kc: float = 0.015  # % / (kg/h)
    fic_Ti_min: float = 1.0
    lic_Kc: float = 200.0  # % / m
    lic_Ti_min: float = 10.0
    steam_flow_max_kg_h: float = 3000.0

    # Timing
    scan_s: float = 10.0
    positioner_tau_s: float = 3.0

    # Design-point references
    design_duty_kW: float = 898.0
    design_steam_kg_h: float = 1533.0
    design_TV_pct: float = 50.0
    design_LV_pct: float = 50.0


DESIGN = DesignBasis()


def tsat_C(P_barg: float) -> float:
    """Plant correlation: Tsat [°C] = 100 * (P_barg + 1.013)^0.25."""
    return 100.0 * (P_barg + 1.013) ** 0.25


def hfg_kJ_kg(Tsat_C: float) -> float:
    """Plant correlation: hfg [kJ/kg] = 2500 - 2.4 * Tsat."""
    return 2500.0 - 2.4 * Tsat_C


def ua_eff_kW_K(x_tv: float, ua_clean: float = DESIGN.UA_clean_kW_K, R: float = DESIGN.rangeability_R) -> float:
    """Effective coil UA [kW/K] = UA_clean * R^(x-1), x in 0..1."""
    x = min(max(x_tv, 0.0), 1.0)
    return ua_clean * (R ** (x - 1.0))


def design_duty_independent(d: DesignBasis = DESIGN) -> dict[str, float]:
    """Independent SS energy check at design (sensible + loss)."""
    F = d.feed_m3_h / 3600.0  # m3/s
    Q_sens_kW = d.rho_kg_m3 * d.cp_kJ_kgK * F * (d.T_SP_C - d.feed_T_C)
    Q_loss_kW = d.UA_loss_W_K * (d.T_SP_C - d.T_ambient_C) / 1000.0
    Q_coil_kW = Q_sens_kW + Q_loss_kW
    Tsat = tsat_C(d.P_steam_barg)
    hfg = hfg_kJ_kg(Tsat)
    w_steam_kg_h = Q_coil_kW / hfg * 3600.0
    ua_at_50 = ua_eff_kW_K(0.5)
    approach = Tsat - d.T_SP_C
    Q_from_ua = ua_at_50 * approach
    return {
        "Q_sens_kW": Q_sens_kW,
        "Q_loss_kW": Q_loss_kW,
        "Q_coil_kW": Q_coil_kW,
        "Tsat_C": Tsat,
        "hfg_kJ_kg": hfg,
        "w_steam_kg_h": w_steam_kg_h,
        "UA_eff_50_kW_K": ua_at_50,
        "Q_from_UA_at_50pct_kW": Q_from_ua,
        "ref_duty_kW": d.design_duty_kW,
        "ref_steam_kg_h": d.design_steam_kg_h,
    }
