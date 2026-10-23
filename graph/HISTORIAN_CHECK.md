# Historian check of graph relationships

Source: `participant/historian_60s.parquet`, first 6 h from 2024-06-01 06:00:00+00:00 (361 samples).
Read-only check; does not change any project file.

| ID | Relationship in graph | Result | Status |
|---|---|---|---|
| V1 | CALC-MBAL = FI-101 - FI-102 (graph: CALC-MBAL derived_from FI-101, FI-102) | residual mean -0.0002, std 0.0272 m3/h; flow-meter noise predicts 0.0271 m3/h | **PASS** |
| V2 | FIC-201.SP = 30 x TIC-101.OP (graph: cascade_sp, 30 kg/h per %) | residual mean -0.057, std 1.871 kg/h; OP noise predicts 30 x std(OP) = 1.871 kg/h | **PASS (scatter is OP noise)** |
| V3 | CALC-DUTY = FIC-201.PV x hfg(TI-201) / 3600 (tags.csv: steam-side duty) | median ratio 1.0003, p5-p95 0.9923-1.0076 | **PASS** |
| V4 | CALC-EBAL closes the energy balance (duty - process - ambient loss) | mean CALC-EBAL -0.00 kW (std 0.00); ambient loss for reference = 27.50 kW | **PASS** |
| V5 | Baseline operating point (design basis 75 C, 2.0 m, 6 barg) | TIC PV 75.00 C; LIC PV 2.000 m; PI-201 6.00 barg | **INFO** |
| V6 | TI-102 (product line) reads the same as the tank temperature TIC-101.PV | mean |TI-102 - TIC-101.PV| = 0.068 C | **INFO** |

PASS = relationship holds in the data. CHECK = relationship does not hold; investigate before
trusting the graph. INFO = reported values, no pass/fail rule.
