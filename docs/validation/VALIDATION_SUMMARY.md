# Validation summary (pilot)

| Gate | Result |
|---|---|
| Design duty / steam independent calc | PASS (err < 0.1%) |
| Settled SS T, level, mass balance | PASS |
| Feed step recovery | PASS |
| Timestep 1 s vs 0.5 s | PASS |
| MCP SS flash_tp + session | PASS (dynamics absent — documented) |
| 24 h pilot export | PASS (8640 samples @ 10 s) |
| UA fouling physical signature | PASS (TV ~50% → ~63%; UA_clean_est 72 → 43) |
| Diagnostic baseline score | **3/3** (detect + cause) |

Plots: `docs/validation/plots/pilot_overview.png`, `pilot_fault_zoom.png`.
