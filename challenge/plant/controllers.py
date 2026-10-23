"""Discrete PI controllers with output clamping (anti-windup)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PIController:
    name: str
    Kc: float
    Ti_min: float
    action: str  # "direct" or "reverse"
    op_min: float = 0.0
    op_max: float = 100.0
    mode: int = 1  # 0 MAN, 1 AUTO, 2 CAS
    SP: float = 0.0
    OP: float = 50.0
    integral: float = 0.0
    man_OP: float = 50.0

    def update(self, PV: float, dt_s: float, remote_SP: float | None = None) -> float:
        if self.mode == 2 and remote_SP is not None:
            self.SP = remote_SP
        if self.mode == 0:
            self.OP = min(max(self.man_OP, self.op_min), self.op_max)
            return self.OP

        # direct (LIC): level high → open; reverse (TIC/FIC): PV high → reduce OP
        err = (PV - self.SP) if self.action == "direct" else (self.SP - PV)

        Ti_s = max(self.Ti_min * 60.0, 1e-6)
        p = self.Kc * err
        self.integral += self.Kc * err * dt_s / Ti_s
        raw = p + self.integral
        # clamp and freeze integral when saturated (simple anti-windup)
        if raw > self.op_max:
            self.OP = self.op_max
            if err > 0:
                self.integral -= self.Kc * err * dt_s / Ti_s
        elif raw < self.op_min:
            self.OP = self.op_min
            if err < 0:
                self.integral -= self.Kc * err * dt_s / Ti_s
        else:
            self.OP = raw
        return self.OP


@dataclass
class ControlSuite:
    tic: PIController
    fic: PIController
    lic: PIController
    steam_flow_max_kg_h: float = 3000.0

    @classmethod
    def from_design(cls, d) -> "ControlSuite":
        tic = PIController("TIC-101", d.tic_Kc, d.tic_Ti_min, "reverse", mode=1, SP=d.T_SP_C, OP=50.0)
        fic = PIController("FIC-201", d.fic_Kc, d.fic_Ti_min, "reverse", mode=2, SP=1500.0, OP=50.0)
        lic = PIController("LIC-101", d.lic_Kc, d.lic_Ti_min, "direct", mode=1, SP=d.level_SP_m, OP=50.0)
        return cls(tic=tic, fic=fic, lic=lic, steam_flow_max_kg_h=d.steam_flow_max_kg_h)

    def step(self, T_meas: float, steam_meas_kg_h: float, level_meas: float, dt_s: float) -> dict[str, float]:
        # Master TIC → FIC SP
        tic_op = self.tic.update(T_meas, dt_s)
        fic_sp = (tic_op / 100.0) * self.steam_flow_max_kg_h
        fic_op = self.fic.update(steam_meas_kg_h, dt_s, remote_SP=fic_sp if self.fic.mode == 2 else None)
        lic_op = self.lic.update(level_meas, dt_s)
        return {
            "TIC-101.OP": tic_op,
            "TIC-101.SP": self.tic.SP,
            "TIC-101.MODE": float(self.tic.mode),
            "FIC-201.SP": self.fic.SP,
            "FIC-201.OP": fic_op,
            "FIC-201.MODE": float(self.fic.mode),
            "LIC-101.OP": lic_op,
            "LIC-101.SP": self.lic.SP,
            "LIC-101.MODE": float(self.lic.mode),
            "TV_demand": fic_op,
            "LV_demand": lic_op,
        }
