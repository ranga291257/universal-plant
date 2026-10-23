# DWSIM models

The pilot historian is built by the **real_plant simulator** (`challenge/plant/`). DWSIM here is the **digital twin** for rate / optimize / checks — not a second historian generator. See [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) and as-built FS [`docs/AS_BUILT_TWIN.md`](../../docs/AS_BUILT_TWIN.md).

```bash
python scripts/dwsim_twin_modes.py demo
```

## Files

| File | Role |
|---|---|
| `TK101_twin_ss.dwxmz` | digital twin SS flowsheet (heater + tank) for rate / optimize |
| `twin_rated_baseline.json` / `twin_rated_fouled.json` | Rated knobs from historian windows |
| `twin_surrogate_doe.csv` | Optional ML DOE samples |
| `TK101_heated_tank.dwxmz` | SS HX topology cross-check (~75.8 °C, ~885 kW) |
| `TK101_heater_dynamic.dwxmz` | Dynamic open-loop heater; kickoff state `ss_design` |
| `TK101_heater_pf.dwxmz` | Experimental PF + LV-101 + SS Adjust `ADJ-LIC`; state `ss_level_balance` |

## digital twin vs real_plant physics

| Item | real_plant simulator | digital twin (DWSIM) |
|---|---|---|
| Coil | `UA_eff = UA_clean·R^(x−1)` | Twin rating uses same law on historian TV% + duty; flowsheet heater supplies energy/flash |
| Controls | TIC→FIC→TV, LIC→LV | SS: Adjust/specs; dyn PID not required for twin rate |
| Feed routing | Direct to tank + submerged coil | Heater-then-tank (or SS HX) simplification |
| Historian | Generated here | Never used as generator |

## Known limits

- Dual flow-spec dynamic file keeps level flat (no inventory response).
- PF/Kv path can move level but holdup restore to 2 m is unreliable via Dynamics Manager.
- MCP cannot create PID objects; Adjust ObjectData needs UI or XML patch.
- SS HX file routes feed through E-101 — intentional simplification, not submerged-coil identity.

## Dynamic kickoff (`TK101_heater_dynamic.dwxmz`)

1. Load file → restore state `ss_design` → optional solve → run schedule `pilot_rebuild`.
2. After a run, restore `ss_design` again before the next attempt.
3. Keep tank/heater `Initialize using Inlet Stream = 0` so restore is not wiped.
