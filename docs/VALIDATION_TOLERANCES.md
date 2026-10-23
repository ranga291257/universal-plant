# Validation tolerances (declared before pass/fail)

Engineering rationale: design-point duty is ~900 kW; steam ~1500 kg/h; level 2 m; temperature 75 °C. Tolerances cover correlation rounding, discrete PI lag, and 1 s Euler integration.

| Check | Metric | Pass criterion |
|---|---|---|
| Design duty (sensible+loss) | \|Q − 898 kW\| / 898 | ≤ 3% |
| Design steam | \|w − 1533 kg/h\| / 1533 | ≤ 5% |
| UA@50% vs demand | \|Q_UA − Q_need\| / Q_need | ≤ 10% (valve not exactly 50% after settle) |
| SS temperature | \|T − T_SP\| | ≤ 0.5 °C after settle |
| SS level | \|h − h_SP\| | ≤ 0.05 m after settle |
| SS mass balance | \|FI-101 − FI-102\| | ≤ 0.3 m³/h |
| Energy residual (EBAL closure) | \|CALC-EBAL\| | ≤ 40 kW (instrumental + transient; includes ambient loss in the tag) |
| Feed flow step (−10%) recovery | T back to SP | ≤ 0.8 °C within 90 min |
| Timestep sensitivity | \|T_1s − T_0.5s\| at t=1 h open-loop-ish settle | ≤ 0.3 °C |
| Repeatability | same seed IC | bitwise JSON match of IC file hash |

Integration: **dt = 1.0 s** (thermal τ ~ V·ρ·cp/UA_eff ≈ 6.28e3·4.18/10 ≈ 40+ min; hydraulic faster). Historian sample **10 s** (DCS scan); optional 60 s grid.
