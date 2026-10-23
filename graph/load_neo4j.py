#!/usr/bin/env python3
"""Load graph/nodes.csv and graph/edges.csv into a local Neo4j DBMS (Neo4j Desktop).

Requires: pip install neo4j
Env (or flags):
  NEO4J_URI      default neo4j://127.0.0.1:7687
  NEO4J_USER     default neo4j
  NEO4J_PASSWORD required (Desktop DBMS password)

Example:
  export NEO4J_PASSWORD=tk101lab
  python graph/load_neo4j.py --wipe
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

GRAPH = Path(__file__).resolve().parent

KIND_LABEL = {
    "boundary": "Boundary",
    "vessel": "Vessel",
    "heat_exchanger": "HeatExchanger",
    "control_valve": "ControlValve",
    "port": "Port",
    "line": "Line",
    "controller": "Controller",
    "instrument": "Instrument",
    "calc": "Calc",
    "calc_term": "CalcTerm",
    "document": "Document",
}


def kind_to_label(kind: str) -> str:
    return KIND_LABEL.get(kind, "".join(p.capitalize() for p in kind.replace("-", "_").split("_")))


def load_rows():
    with (GRAPH / "nodes.csv").open(newline="", encoding="utf-8") as f:
        nodes = list(csv.DictReader(f))
    with (GRAPH / "edges.csv").open(newline="", encoding="utf-8") as f:
        edges = list(csv.DictReader(f))
    return nodes, edges


def main() -> int:
    p = argparse.ArgumentParser(description="Load TK-101 engineering graph into Neo4j")
    p.add_argument("--uri", default=os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687"))
    p.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    p.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"))
    p.add_argument("--wipe", action="store_true", help="DETACH DELETE all nodes before load")
    args = p.parse_args()
    if not args.password:
        print("Set NEO4J_PASSWORD or pass --password (Neo4j Desktop DBMS password).", file=sys.stderr)
        return 2

    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("Install the driver: pip install neo4j", file=sys.stderr)
        return 2

    nodes, edges = load_rows()
    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    try:
        driver.verify_connectivity()
    except Exception as e:
        print(f"Cannot connect to {args.uri}: {e}", file=sys.stderr)
        print("Start the DBMS in Neo4j Desktop and check URI/password.", file=sys.stderr)
        return 1

    with driver.session() as session:
        if args.wipe:
            session.run("MATCH (n) DETACH DELETE n")
            print("Wiped database.")

        for row in nodes:
            attrs = json.loads(row["attributes_json"] or "{}")
            label = kind_to_label(row["kind"])
            props = {
                "id": row["id"],
                "kind": row["kind"],
                "description": row["description"],
            }
            for k, v in attrs.items():
                if isinstance(v, (str, int, float, bool)) or v is None:
                    props[k] = v
                else:
                    props[k] = json.dumps(v)
            session.run(
                f"MERGE (n:Node {{id: $id}}) "
                f"SET n:{label}, n += $props",
                id=row["id"],
                props=props,
            )

        for row in edges:
            rel = row["edge_type"].upper()
            rel = "".join(c if c.isalnum() or c == "_" else "_" for c in rel)
            eattrs = json.loads(row["attributes_json"] or "{}")
            flat = {}
            for k, v in eattrs.items():
                if isinstance(v, (str, int, float, bool)) or v is None:
                    flat[k] = v
                else:
                    flat[k] = json.dumps(v)
            session.run(
                f"MATCH (a:Node {{id: $src}}), (b:Node {{id: $dst}}) "
                f"MERGE (a)-[r:{rel}]->(b) "
                f"SET r += $props",
                src=row["src"],
                dst=row["dst"],
                props=flat,
            )

        n_count = session.run("MATCH (n:Node) RETURN count(n) AS c").single()["c"]
        r_count = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        print(f"Loaded nodes={n_count} relationships={r_count}")
        print("Open Neo4j Browser and try graph/cypher_examples.cypher")

    driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
