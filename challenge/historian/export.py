"""Simulate plant and export UTC historian (wide CSV/Parquet + long format + tags)."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from challenge.faults.scenarios import ScenarioEvent, apply_event
from challenge.plant.controllers import ControlSuite
from challenge.plant.design import DESIGN
from challenge.plant.model import PlantParams, PlantState, load_from_dict, settle_to_steady, state_to_dict, step_plant


TAG_DICTIONARY = [
    {"tag": "TIC-101.PV", "description": "Tank temperature", "units": "degC", "role": "PV"},
    {"tag": "TIC-101.SP", "description": "Tank temperature setpoint", "units": "degC", "role": "SP"},
    {"tag": "TIC-101.OP", "description": "TIC output (steam flow demand %)", "units": "%", "role": "OP"},
    {"tag": "TIC-101.MODE", "description": "TIC mode 0MAN 1AUTO 2CAS", "units": "-", "role": "MODE"},
    {"tag": "FIC-201.PV", "description": "Steam flow to coil", "units": "kg/h", "role": "PV"},
    {"tag": "FIC-201.SP", "description": "Steam flow setpoint", "units": "kg/h", "role": "SP"},
    {"tag": "FIC-201.OP", "description": "Steam valve demand", "units": "%", "role": "OP"},
    {"tag": "FIC-201.MODE", "description": "FIC mode", "units": "-", "role": "MODE"},
    {"tag": "LIC-101.PV", "description": "Tank level", "units": "m", "role": "PV"},
    {"tag": "LIC-101.SP", "description": "Level setpoint", "units": "m", "role": "SP"},
    {"tag": "LIC-101.OP", "description": "Outlet valve demand", "units": "%", "role": "OP"},
    {"tag": "LIC-101.MODE", "description": "LIC mode", "units": "-", "role": "MODE"},
    {"tag": "TV-101.POS", "description": "Steam valve position", "units": "%", "role": "IND"},
    {"tag": "LV-101.POS", "description": "Outlet valve position", "units": "%", "role": "IND"},
    {"tag": "FI-101", "description": "Feed flow", "units": "m3/h", "role": "IND"},
    {"tag": "TI-100", "description": "Feed temperature", "units": "degC", "role": "IND"},
    {"tag": "FI-102", "description": "Product flow", "units": "m3/h", "role": "IND"},
    {"tag": "TI-102", "description": "Product temperature", "units": "degC", "role": "IND"},
    {"tag": "PI-201", "description": "Steam header pressure", "units": "barg", "role": "IND"},
    {"tag": "TI-201", "description": "Steam saturation temperature", "units": "degC", "role": "IND"},
    {"tag": "TI-202", "description": "Condensate return temperature", "units": "degC", "role": "IND"},
    {"tag": "TI-901", "description": "Ambient temperature", "units": "degC", "role": "IND"},
    {"tag": "AI-101", "description": "Product purity (T-correlation)", "units": "%", "role": "IND"},
    {"tag": "CALC-DUTY", "description": "Steam-side coil duty", "units": "kW", "role": "CALC"},
    {"tag": "CALC-DUTY-PROC", "description": "Process-side sensible duty", "units": "kW", "role": "CALC"},
    {"tag": "CALC-EBAL", "description": "Energy balance gap (duty - process - ambient loss)", "units": "kW", "role": "CALC"},
    {"tag": "CALC-APPROACH", "description": "Steam-to-bulk approach", "units": "K", "role": "CALC"},
    {"tag": "CALC-UA", "description": "Back-calculated coil UA", "units": "W/K", "role": "CALC"},
    {"tag": "CALC-MBAL", "description": "Mass balance residual", "units": "m3/h", "role": "CALC"},
]

PUBLIC_TAGS = [r["tag"] for r in TAG_DICTIONARY]


@dataclass
class HistorianConfig:
    start_utc: datetime = datetime(2024, 6, 1, 6, 0, 0, tzinfo=timezone.utc)
    duration_h: float = 24.0
    dt_s: float = 1.0
    sample_s: float = 10.0
    seed: int = 42
    noise: bool = True
    missing_frac: float = 0.001


def _add_noise(rng: np.random.Generator, tag: str, value: float) -> float:
    # rough % of span noise by class
    spans = {
        "TIC-101.PV": 120.0,
        "LIC-101.PV": 4.0,
        "FIC-201.PV": 3000.0,
        "FI-101": 30.0,
        "FI-102": 30.0,
        "TI-100": 60.0,
        "TI-102": 120.0,
        "PI-201": 12.0,
        "TV-101.POS": 100.0,
        "LV-101.POS": 100.0,
    }
    sigma_frac = {
        "TIC-101.PV": 0.0008,
        "LIC-101.PV": 0.0022,
        "FIC-201.PV": 0.006,
        "default": 0.0015,
    }
    span = spans.get(tag, 100.0)
    sig = sigma_frac.get(tag, sigma_frac["default"]) * span
    if tag.endswith(".MODE") or tag.endswith(".SP"):
        return value
    if tag.startswith("CALC-"):
        return value
    return float(value + rng.normal(0.0, sig))


def simulate_and_export(
    out_dir: Path,
    event: ScenarioEvent | None,
    ic_path: Path | None,
    cfg: HistorianConfig,
) -> pd.DataFrame:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(cfg.seed)

    if ic_path and Path(ic_path).exists():
        data = json.loads(Path(ic_path).read_text(encoding="utf-8"))
        state, params, ctrl = load_from_dict(data)
    else:
        state, params, ctrl, _ = settle_to_steady(hours=3.0, dt_s=cfg.dt_s)

    # Scenario clock starts at 0 regardless of settle time stored in IC
    state.t_s = 0.0

    # Keep clean copies of baseline feed for restoration after disturbances
    base_params = PlantParams(**asdict(params))

    n_steps = int(cfg.duration_h * 3600 / cfg.dt_s)
    sample_every = max(int(cfg.sample_s / cfg.dt_s), 1)
    rows: list[dict] = []
    sensor_bias: dict[str, float] = {}

    for i in range(n_steps):
        t = state.t_s if i else 0.0
        # restore physical defaults then apply active event
        params.ua_multiplier = 1.0
        params.P_steam_barg = base_params.P_steam_barg
        params.TV_travel_max_pct = 100.0
        sensor_bias.clear()
        if event:
            apply_event(event, state.t_s, params, state, ctrl, sensor_bias)

        # measurement path (true + bias); noise added at sample
        meas = {
            "TIC-101.PV": state.T_C + sensor_bias.get("TIC-101.PV", 0.0),
            "FIC-201.PV": state.steam_kg_h + sensor_bias.get("FIC-201.PV", 0.0),
            "LIC-101.PV": state.h_m + sensor_bias.get("LIC-101.PV", 0.0),
        }
        state, tags = step_plant(state, params, ctrl, cfg.dt_s, meas=meas)

        if i % sample_every == 0:
            ts = cfg.start_utc + timedelta(seconds=state.t_s)
            # Build measured snapshot from true tags + PV overrides
            snap = dict(tags)
            snap["TIC-101.PV"] = meas["TIC-101.PV"]
            snap["FIC-201.PV"] = meas["FIC-201.PV"]
            snap["LIC-101.PV"] = meas["LIC-101.PV"]
            row: dict = {"timestamp": ts}
            quality = {}
            for tag in PUBLIC_TAGS:
                val = snap.get(tag, float("nan"))
                if cfg.noise and isinstance(val, (int, float)) and np.isfinite(val):
                    val = _add_noise(rng, tag, float(val))
                q = 0
                if cfg.missing_frac > 0 and rng.random() < cfg.missing_frac:
                    val = float("nan")
                    q = 2
                row[tag] = val
                quality[f"{tag}__q"] = q
            row.update(quality)
            rows.append(row)

    wide = pd.DataFrame(rows)
    # public wide without quality columns in main parquet; quality in side file
    qcols = [c for c in wide.columns if c.endswith("__q")]
    pub = wide[["timestamp"] + PUBLIC_TAGS].copy()
    qual = wide[["timestamp"] + qcols].copy()

    pub.to_csv(out_dir / "historian.csv", index=False)
    pub.to_parquet(out_dir / "historian.parquet", index=False)
    # 60s grid
    pub60 = pub.set_index("timestamp").resample("60s").mean().reset_index()
    pub60.to_parquet(out_dir / "historian_60s.parquet", index=False)
    qual.to_parquet(out_dir / "historian_quality.parquet", index=False)

    long_rows = []
    for _, r in pub.iterrows():
        for tag in PUBLIC_TAGS:
            v = r[tag]
            q = 2 if (isinstance(v, float) and not np.isfinite(v)) else 0
            long_rows.append({"tag": tag, "timestamp": r["timestamp"], "value": v, "quality": q})
    long_df = pd.DataFrame(long_rows)
    long_df.to_parquet(out_dir / "historian_long.parquet", index=False)

    pd.DataFrame(TAG_DICTIONARY).to_csv(out_dir / "tags.csv", index=False)

    meta = {
        "start_utc": cfg.start_utc.isoformat(),
        "duration_h": cfg.duration_h,
        "dt_s": cfg.dt_s,
        "sample_s": cfg.sample_s,
        "seed": cfg.seed,
        "event": asdict(event) if event else None,
        "engine": "python_ode_plant",
        "mcp": "properties_crosscheck_only",
    }
    # serialize enum
    if meta["event"] and "kind" in meta["event"]:
        meta["event"]["kind"] = event.kind.value  # type: ignore
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    return pub
