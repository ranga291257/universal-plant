# TK-101 Heated Hold Tank — Fault Diagnosis Challenge (Pilot)

You receive ~24 hours of historian data from a steam-heated agitated hold tank (TK-101). Find each **fault event**, estimate UTC start/end, diagnose the cause, and list evidence tags.

**Inspired by** Scott Duncan / HistorianRCA (CC BY 4.0). The dataset and plant model are **ours** — not that project’s hidden simulator or answer key.

## What to report

For each fault: `start_utc`, `end_utc`, `kind=fault`, free-text `root_cause`, `evidence_tags`.

**Not scored as faults** (if listed, use other `kind` values):

- deliberate operator setpoint changes with normal response
- instrument/historian artifacts (spikes, gaps, stuck values)
- normal feed/ambient disturbances

## Event taxonomy (this project)

| kind | Meaning |
|---|---|
| `fault` / equipment | Physical equipment or utility degradation |
| `instrument_fault` | Sensor/transmitter fault (separate category) |
| `operator_action` | Intentional SP/mode change |
| `historian_artifact` | Data-quality only |
| `normal_disturbance` | Legitimate process variation |

Scoring for this pilot (simple): +1 detection overlap, +2 correct cause, −1 false positive. Timing used as tie-break only.

## Files

See `PROCESS_DESCRIPTION.md`, `tags.csv`, `historian.parquet` / `historian_60s.parquet`, `submission_template.csv`, PFD SVG.
