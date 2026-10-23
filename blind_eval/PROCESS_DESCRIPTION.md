# TK-101 Process Description (Pilot)

Non-reacting water hold tank heated by a submerged steam coil.  
**Inspired by** Scott Duncan / HistorianRCA (CC BY 4.0). This description is for **our** plant model; see project `ASSUMPTIONS.md`.

## Equipment

- **TK-101**: D = 2.0 m, height 4.0 m, well mixed; level SP 2.0 m (V ≈ 6.28 m³); residence time ≈ 25 min at 15 m³/h.
- **E-101**: steam coil; equal-percentage effective UA: `UA_eff = UA_clean * R^(x-1)` with UA_clean = 72 kW/K, R = 50.
- **TV-101**: steam valve; **LV-101**: gravity outlet valve, `F_out = Cv * x * sqrt(h)`, Cv = 0.0059 m³/s.
- Feed not controlled by this unit (FI-101, TI-100).

## Design point

| Quantity | Value |
|---|---|
| Feed | 15 m³/h @ 25 °C |
| T_SP | 75 °C |
| Steam header | 6.0 barg |
| Duty / steam | ~898 kW / ~1533 kg/h |
| Valve mid-travel | ~50% |
| Heat loss | 500 W/K |

Steam correlations: `Tsat=100*(P_barg+1.013)^0.25` °C; `hfg=2500-2.4*Tsat` kJ/kg.

## Control

- **TIC-101** (AUTO, reverse) → **FIC-201** (CAS) → TV-101
- **LIC-101** (AUTO, direct) → LV-101
- FIC-201.SP [kg/h] = 30 × TIC-101.OP [%]
- Scan 10 s; PI only

## Calculated tags

| Tag | Definition |
|---|---|
| `CALC-DUTY` | Coil duty (kW) |
| `CALC-DUTY-PROC` | Sensible heat to raise feed to tank T (kW) |
| `CALC-APPROACH` | Tsat − tank T (°C) |
| `CALC-UA` | Apparent UA from duty / approach |
| `CALC-MBAL` | Feed − outlet volumetric flow |
| `CALC-EBAL` | `CALC-DUTY − CALC-DUTY-PROC − UA_loss×(T−T_amb)/1000` (kW) — closure residual (~0 at SS) |

## Simplification

No hydrolysis reaction heat; purity `AI-101` uses a T-only correlation for indication only.
