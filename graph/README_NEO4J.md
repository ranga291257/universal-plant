# Neo4j learning lab (Neo4j Desktop, no Docker)

CSV/JSON under `graph/` are the **source of truth**. Neo4j Desktop is a teaching sandbox so you can ask connection questions in Cypher.

## 1. Install and start Neo4j Desktop

1. Download [Neo4j Desktop](https://neo4j.com/download/) and install it.
2. Create a project named **TK-101 Lab**.
3. **Add** → **Local DBMS** (or Create a Local DBMS). Name it e.g. `tk101`.
4. Set a password you will remember (example below uses `tk101lab`).
5. Click **Start** on the DBMS.
6. Click **Open** → **Neo4j Browser**.

Bolt URI is usually:

```text
neo4j://127.0.0.1:7687
```

(or `bolt://127.0.0.1:7687`). Confirm under the DBMS details in Desktop.

## 2. Python driver

From the repo root (venv recommended):

```bash
pip install neo4j
# or: pip install -r requirements.txt
```

## 3. Rebuild CSV (optional) and load

```bash
python graph/build_graph.py

export NEO4J_PASSWORD=tk101lab   # same password as the DBMS
python graph/load_neo4j.py --wipe
```

Flags / env:

| Name | Default |
|---|---|
| `NEO4J_URI` / `--uri` | `neo4j://127.0.0.1:7687` |
| `NEO4J_USER` / `--user` | `neo4j` |
| `NEO4J_PASSWORD` / `--password` | (required) |
| `--wipe` | delete all nodes before load |

Successful load prints node and relationship counts.

## 4. Run teaching queries

In Neo4j Browser, open [`cypher_examples.cypher`](cypher_examples.cypher) and paste **one** Cypher block at a time (not the `//` English comments — Browser only accepts Cypher).

Start with queries **1–10**; **11–20** cover shared docs, allShortestPaths, calc DAGs, loop motifs, heat maps.

### Silly NL → Cypher (local Ollama)

If you prefer English, `ask_neo4j.py` asks Ollama for Cypher and runs it (read-only). Few-shots come from the same `cypher_examples.cypher` file.

```bash
# Neo4j up (Desktop or: docker start tk101-neo4j)
export NEO4J_PASSWORD=tk101lab
export NEO4J_URI=bolt://127.0.0.1:7687   # use bolt:// for Docker single-instance

./.venv/bin/python graph/ask_neo4j.py "What is directly connected to steam valve TV-101?"
./.venv/bin/python graph/ask_neo4j.py "which controllers drive TV-101?"
./.venv/bin/python graph/ask_neo4j.py --dry-run "shortest path feed to product"
```

Default model: `granite4.2:8b` (`OLLAMA_MODEL` / `--model`). Requires `ollama serve` with that model pulled.

## 5. After you change the graph

Edit `build_graph.py` → run `python graph/build_graph.py` → reload with `--wipe`.

## Alternate: Aura Free

You can point the same loader at an Aura Free instance by setting `NEO4J_URI` to the Aura connection string. This lab is documented for **Desktop** only.
