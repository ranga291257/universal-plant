# universal-plant

Heated-tank **TK-101** lab: the **real_plant simulator** builds the historian; DWSIM is the **digital twin**; participants diagnose faults from the data.

**Inspired by** Scott Duncan / [HistorianRCA](https://github.com/ScottDuncanAI/HistorianRCA) (CC BY 4.0). real_plant simulator, historian, and digital twin are implemented in this repo.

## Architecture

| Layer | Role |
|---|---|
| **real_plant simulator** | `challenge/plant/` — first-principles ODEs + controllers (dynamic). Generates historian via `scripts/run_pilot.py`. |
| **digital twin** | DWSIM + `challenge/plant/dwsim_twin.py` — Simulate / Rate / Optimize / fouling detect. |
| **Challenge** | `participant/` package; answers in `private/` (organizers only). |

Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Quick start

```bash
pip install -r requirements.txt   # Python 3.12 recommended

python scripts/validate_baseline.py   # SS checks + baseline IC
python scripts/run_pilot.py           # 24 h historian + plots
python scripts/run_diagnostics.py     # baseline diagnostic score
python docs/pfd/build_pfd.py          # PFD SVG

# Digital twin (rate clean vs fouled → coil_fouling)
python scripts/dwsim_twin_modes.py demo
```

## Documentation map

| Doc | Purpose |
|---|---|
| [`ASSUMPTIONS.md`](ASSUMPTIONS.md) | Design choices |
| [`SOURCES.md`](SOURCES.md) | Attribution / inspiration links |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | real_plant vs digital twin, fouling, commands |
| [`docs/AS_BUILT_TWIN.md`](docs/AS_BUILT_TWIN.md) | As-built digital twin FS: modes, DOFs, UML |
| [`docs/VALIDATION_TOLERANCES.md`](docs/VALIDATION_TOLERANCES.md) | Pass/fail criteria |
| [`models/dwsim/NOTES.md`](models/dwsim/NOTES.md) | DWSIM files and limits |
| [`graph/README.md`](graph/README.md) | Engineering graph (internal) |
| [`participant/`](participant/) | Public challenge package |
| [`blind_eval/`](blind_eval/) | Solver workspace (no keys) |

## Working rules

1. **Roles:** the **real_plant simulator** builds the pilot historian. The **digital twin** (DWSIM) is for rate / optimize / checks — it does not rewrite the historian.
2. **Do not write** into `participant/`, `blind_eval/`, or `private/` unless packaging intentionally.
3. **Do not run** `validate_baseline.py` / `run_pilot.py` without need — they overwrite IC, historian, and plots.
4. **Do not change** real_plant physics in `challenge/plant/model.py` or `design.py` without intent — that changes the historian.

## Layout

| Path | Role |
|---|---|
| `challenge/` | real_plant simulator, faults, historian generator, diagnostics |
| `data/pilot/` | Generated pilot historian |
| `models/dwsim/` | DWSIM digital twin flowsheets |
| `docs/` | Architecture, validation, PFD |
| `graph/` | Internal equipment graph |
| `scripts/` | Entry points |
| `participant/` | Public package |
| `blind_eval/` | Blind solver copy |
| `private/` | Answer key (organizers) |
