# TK-101 engineering graph (internal)

Nodes/edges for equipment, lines, instruments, loops, and documents. Built from the real_plant simulator, PFD, and tags. Not part of the participant package.

| File | Role |
|---|---|
| `build_graph.py` | Build graph + structural checks |
| `verify_against_historian.py` | Check relationships on normal baseline |
| `nodes.csv`, `edges.csv`, `tk101_graph.json` | Graph data (source of truth) |
| `CHECK_REPORT.md`, `HISTORIAN_CHECK.md` | Last check outputs |
| `load_neo4j.py` | Optional load into Neo4j |
| `ask_neo4j.py` | NL → Cypher via local Ollama, then run |
| `cypher_examples.cypher` | All lab Cypher queries (1–20) |
| `README_NEO4J.md` | Neo4j lab setup |

```bash
python graph/build_graph.py
./.venv/bin/python graph/verify_against_historian.py
```

## Schema (kinds / edge types)

**Node kinds:** `boundary`, `vessel`, `heat_exchanger`, `control_valve`, `port`, `line`, `controller`, `instrument`, `calc`, `calc_term`, `document`

**Edge types:** `piping`, `part_of`, `heat_transfer`, `heat_loss`, `measures`, `pv_input`, `cascade_sp`, `op_signal`, `derived_from`, `documented_by`

## Neo4j learning lab

Edit the CSV (via `build_graph.py`), then reload Neo4j if you use it. See [`README_NEO4J.md`](README_NEO4J.md).

Status: C01–C11 and historian V1–V4 currently PASS. DWSIM topology differences (feed-through HX vs submerged coil) are documented in `models/dwsim/NOTES.md`.
