# Baseline validation report

## Independent design duty
- `Q_sens_kW` = 870.8333
- `Q_loss_kW` = 27.5000
- `Q_coil_kW` = 898.3333
- `Tsat_C` = 162.7331
- `hfg_kJ_kg` = 2109.4405
- `w_steam_kg_h` = 1533.1079
- `UA_eff_50_kW_K` = 10.1823
- `Q_from_UA_at_50pct_kW` = 893.3283
- `ref_duty_kW` = 898.0000
- `ref_steam_kg_h` = 1533.0000
- duty relative error 0.0371% => PASS
- steam relative error 0.0070% => PASS

## Settled SS (3 h)
- T=75.000 degC (err 0.000) => PASS
- h=2.000 m (err 0.000) => PASS
- steam=1533.1 kg/h, TV=50.1%, LV=49.9%
- CALC-MBAL=0.000 => PASS
- CALC-EBAL=-0.00 kW (closure; loss term=27.50 kW already subtracted)
- |CALC-EBAL| <= 40 kW => PASS

## Feed -10% for 90 min
- T=75.001 => PASS

## Timestep sensitivity 1s vs 0.5s (1 h)
- dT=0.0000 => PASS

## IC saved `challenge/plant/baseline_ic.json`
- sha256[:16]=6f953296220bb788
