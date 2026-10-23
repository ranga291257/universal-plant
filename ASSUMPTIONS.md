# Assumptions register

Inspired by Scott Duncan / HistorianRCA (CC BY 4.0) for the heated-tank design idea. real_plant simulator, historian, and digital twin are implemented in this repo.

| ID | Assumption | Rationale |
|---|---|---|
| A-01 | Fluid is water-like (ρ=1000 kg/m³, cp=4.18 kJ/kg·K); **non-reacting** | Purity indication is T-only; no invented kinetics. |
| A-02 | Dynamics engine is **Python ODEs** | Self-contained **real_plant simulator**; DWSIM is the **digital twin**, not the historian generator. |
| A-03 | Steam: `Tsat=100*(P_barg+1.013)^0.25`, `hfg=2500-2.4*Tsat` | Simple real_plant correlations (same form as the published design basis we were inspired by). |
| A-04 | Pressures as **barg** unless noted; absolute ≈ gauge + 1.013 bar | Consistent with design-basis writeup. |
| A-05 | Controllers are discrete PI at 10 s scan; no derivative; anti-windup by output clamp | Matches our PROCESS_DESCRIPTION. |
| A-06 | Valve positioner: first-order 3 s lag from OP to POS | Simplified actuator. |
| A-07 | Pilot duration 24 h; ~15–25 TK-101 tags; no neighbouring units | Pilot scope. |
| A-08 | Event taxonomy: equipment / instrument / operator / artifact / normal_disturbance | Defined for this challenge. |
| A-09 | Sensor noise and quality flags in the **measurement path only** | Conservation ODEs stay clean. |
| A-10 | Credit inspiration; do not claim identity with any external hidden simulator | Our generator lives in `challenge/`. |
| A-11 | `CALC-EBAL = CALC-DUTY − CALC-DUTY-PROC − Q_loss` so SS residual ≈ 0 | Intentional choice so EBAL is a closure residual. |

## Design choices (tracked)

| Item | This project |
|---|---|
| Reaction / purity AI | Optional T-only purity tag; no reaction heat |
| Neighbouring units | Omitted in pilot |
| Historian compression | Uncompressed pilot first |
| Ambient | Constant or mild daily for pilot |
| Duration | 24 h pilot |
