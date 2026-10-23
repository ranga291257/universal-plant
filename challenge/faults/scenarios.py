"""Fault / event definitions. Physical faults change PlantParams; sensors change measurement path."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from challenge.plant.model import PlantParams, PlantState
from challenge.plant.controllers import ControlSuite


class EventTaxonomy(str, Enum):
    equipment_fault = "equipment_fault"
    instrument_fault = "instrument_fault"
    operator_action = "operator_action"
    historian_artifact = "historian_artifact"
    normal_disturbance = "normal_disturbance"


@dataclass
class ScenarioEvent:
    event_id: str
    kind: EventTaxonomy
    start_s: float
    end_s: float  # when cause removed
    recovery_s: float | None = None  # process recovered (for docs)
    description: str = ""
    parameter: str = ""
    magnitude: float = 0.0
    profile: str = "step"  # step | ramp
    expected_consequences: str = ""
    competing_explanations: str = ""
    uniquely_distinguishable: bool = True
    evidence_tags: list[str] = field(default_factory=list)

    def active(self, t_s: float) -> bool:
        return self.start_s <= t_s < self.end_s


# Pilot: coil UA fouling — 40% reduction for 4 hours after 8 h of normal
FOULING_UA_PILOT = ScenarioEvent(
    event_id="E001",
    kind=EventTaxonomy.equipment_fault,
    start_s=8 * 3600,
    end_s=12 * 3600,
    recovery_s=14 * 3600,
    description="Coil fouling: UA_clean multiplier reduced to 0.6 (40% fouling)",
    parameter="ua_multiplier",
    magnitude=0.6,
    profile="step",
    expected_consequences=(
        "Temperature held near SP by cascade; steam flow and/or TV-101 open further; "
        "CALC-UA falls; CALC-APPROACH may rise if duty same but effective UA lower."
    ),
    competing_explanations=(
        "Steam header pressure drop (PI-201/TI-201 would move); "
        "TT bias (redundant TI-102 vs TIC; steam would not need to rise for true T)."
    ),
    uniquely_distinguishable=True,
    evidence_tags=["CALC-UA", "FIC-201.PV", "TV-101.POS", "PI-201", "TIC-101.PV", "TI-201"],
)


def apply_event(
    event: ScenarioEvent | None,
    t_s: float,
    params: PlantParams,
    state: PlantState,
    ctrl: ControlSuite,
    sensor_bias: dict[str, float],
) -> None:
    """Mutate params / setpoints / sensor_bias according to active events."""
    # Reset defaults each call for step faults that only apply while active
    params.ua_multiplier = 1.0
    # (steam P and travel left as-is unless events set them; caller may reset)

    if event is None or not event.active(t_s):
        return

    if event.parameter == "ua_multiplier":
        params.ua_multiplier = event.magnitude
    elif event.parameter == "P_steam_barg":
        params.P_steam_barg = event.magnitude
    elif event.parameter == "TV_travel_max_pct":
        params.TV_travel_max_pct = event.magnitude
    elif event.parameter == "TIC-101.SP":
        ctrl.tic.SP = event.magnitude
    elif event.parameter == "LIC-101.SP":
        ctrl.lic.SP = event.magnitude
    elif event.parameter == "F_feed_m3_h":
        state.F_feed_m3_h = event.magnitude
    elif event.parameter == "T_feed_C":
        state.T_feed_C = event.magnitude
    elif event.parameter == "TIC-101.bias":
        sensor_bias["TIC-101.PV"] = event.magnitude
