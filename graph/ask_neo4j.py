#!/usr/bin/env python3
"""Silly NL → Cypher lab helper (local Ollama) + run against Neo4j.

Few-shots are loaded from graph/cypher_examples.cypher (all 20 lab queries).

  ./.venv/bin/python graph/ask_neo4j.py "What is directly connected to steam valve TV-101?"
  ./.venv/bin/python graph/ask_neo4j.py --dry-run "shortest path feed to product"
  ./.venv/bin/python graph/ask_neo4j.py "which controllers drive TV-101?"

Env: NEO4J_URI (default bolt://127.0.0.1:7687), NEO4J_USER, NEO4J_PASSWORD
     OLLAMA_HOST (default http://127.0.0.1:11434), OLLAMA_MODEL (default granite4.2:8b)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

GRAPH = Path(__file__).resolve().parent

SCHEMA = """
TK-101 engineering graph (Neo4j):
- Every asset is (:Node {id, kind, description, ...}). Kind also becomes a label:
  Boundary, Vessel, HeatExchanger, ControlValve, Port, Line, Controller,
  Instrument, Calc, CalcTerm, Document.
- Relationships (uppercase): PIPING, PART_OF, HEAT_TRANSFER, HEAT_LOSS,
  MEASURES, PV_INPUT, CASCADE_SP, OP_SIGNAL, DERIVED_FROM, DOCUMENTED_BY.
- Useful ids: FEED_SRC, PROD_SINK, STEAM_HDR, TK-101, E-101, TV-101, LV-101,
  TIC-101, FIC-201, LIC-101, TT-101, FT-201, LT-101, CALC-EBAL,
  DOC-PFD, DOC-PROCESS.

Rules for Cypher you write:
1. Prefer MATCH … RETURN. Read-only only (no CREATE/MERGE/DELETE/SET/DROP).
2. Filter assets with {id: '…'} on :Node (or kind labels).
3. Undirected neighbors: (a)-[r]-(b). Directed control: -[:OP_SIGNAL]-> etc.
4. Process path across vessels/valves: use [:PIPING|PART_OF*] — PIPING alone
   stops at nozzles (ports are PART_OF the equipment).
5. Return small columns (ids, kinds, type(r), path id lists). LIMIT 50 if graph viz.
6. Output ONLY one Cypher statement. No markdown fences, no commentary.
"""

COOKBOOK = GRAPH / "cypher_examples.cypher"

# Numbered header on its own line: "// 3) Title" or "// C7) Title"
HEADER_RE = re.compile(r"(?m)^//\s*(?:[A-Z])?(\d+)\)\s+(.+?)\s*$")
SEP_RE = re.compile(r"(?m)^// -{5,}\s*$")


def parse_cookbook(path: Path) -> list[tuple[str, str]]:
    """Return (english_title, cypher) pairs from a cookbook .cypher file."""
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        hm = HEADER_RE.match(lines[i])
        if not hm:
            i += 1
            continue
        title = hm.group(2).strip()
        i += 1
        # skip continuation // comments and the ---- separator
        while i < len(lines) and (
            lines[i].strip().startswith("//") or not lines[i].strip()
        ):
            i += 1
        body: list[str] = []
        while i < len(lines):
            if HEADER_RE.match(lines[i]) or SEP_RE.match(lines[i]):
                break
            if lines[i].strip().startswith("//"):
                i += 1
                continue
            body.append(lines[i])
            i += 1
        cypher = "\n".join(body).strip().rstrip(";").strip()
        if cypher and title:
            out.append((title, cypher))
    return out


def score_example(question: str, title: str, cypher: str) -> int:
    q = question.lower()
    blob = f"{title}\n{cypher}".lower()
    score = 0
    # tag / id hits
    for tok in re.findall(r"[A-Z]{1,4}-\d{2,3}|FEED_SRC|PROD_SINK|STEAM_HDR|CALC-[A-Z]+|DOC-[A-Z]+", question):
        if tok.lower() in blob:
            score += 5
    for word in re.findall(r"[a-z]{4,}", q):
        if word in blob:
            score += 1
    # pattern hints
    hints = {
        "neighbor": "-[r]-",
        "path": "shortestpath",
        "cascade": "cascade_sp",
        "document": "documented_by",
        "measure": "measures",
        "derive": "derived_from",
        "blast": "*1..2",
        "controller": "controller",
        "steam": "steam",
    }
    for w, frag in hints.items():
        if w in q and frag in blob:
            score += 3
    return score


def select_few_shots(
    question: str,
    examples: list[tuple[str, str]],
    *,
    max_n: int = 6,
) -> list[tuple[str, str]]:
    if len(examples) <= max_n:
        return examples
    ranked = sorted(
        examples,
        key=lambda pair: score_example(question, pair[0], pair[1]),
        reverse=True,
    )
    # always keep a couple of high-value basics if present
    prefer = []
    for title, cypher in examples:
        t = title.lower()
        if "neighbors" in t or "piping|part_of" in cypher.lower() or "shortest process path" in t:
            prefer.append((title, cypher))
    chosen: list[tuple[str, str]] = []
    seen: set[str] = set()
    for pair in prefer + ranked:
        if pair[0] in seen:
            continue
        chosen.append(pair)
        seen.add(pair[0])
        if len(chosen) >= max_n:
            break
    return chosen


def extract_cypher(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I).strip()
    text = re.sub(r"^```(?:cypher)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text).strip()
    blocks = re.findall(
        r"(?is)\bMATCH\b.*?\bRETURN\b.+?(?=(?:\n\s*\n|\Z))",
        text,
    )
    if blocks:
        cand = max(blocks, key=len).strip()
        if ";" in cand:
            cand = cand.split(";", 1)[0].strip()
        return cand
    m = re.search(r"(?is)\bMATCH\b.+", text)
    if m:
        cand = m.group(0).strip()
        if ";" in cand:
            cand = cand.split(";", 1)[0].strip()
        lines = []
        for line in cand.splitlines():
            if lines and re.match(r"(?i)^(thus|so |but |we |the |according)", line.strip()):
                break
            lines.append(line)
        return "\n".join(lines).strip()
    return text.strip()


def ollama_cypher(
    question: str,
    model: str,
    host: str,
    few_shot: list[tuple[str, str]],
) -> str:
    examples = "\n\n".join(f"Q: {q}\nCypher:\n{c}" for q, c in few_shot)
    prompt = (
        "Convert the question to read-only Neo4j Cypher for the TK-101 graph.\n"
        "Follow the example style closely (relationship types, PIPING|PART_OF for "
        "process paths through ports).\n"
        "Output ONLY Cypher. First word must be MATCH. No markdown, no commentary.\n\n"
        f"{SCHEMA}\n\nExamples from the lab cookbook:\n{examples}\n\n"
        f"Q: {question}\nCypher:\n"
    )
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.0, "num_predict": 350},
        }
    ).encode()
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        raise SystemExit(f"Ollama not reachable at {host}: {e}") from e
    text = (data.get("response") or data.get("thinking") or "").strip()
    return extract_cypher(text)


FORBIDDEN = re.compile(
    r"(?i)\b(CREATE|MERGE|DELETE|DETACH|SET|DROP|REMOVE|LOAD\s+CSV|CALL\s+dbms)\b"
)


def run_cypher(uri: str, user: str, password: str, cypher: str):
    from neo4j import GraphDatabase

    if FORBIDDEN.search(cypher):
        raise SystemExit(f"Refusing non-read Cypher:\n{cypher}")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
        with driver.session() as session:
            result = session.run(cypher)
            rows = [dict(r) for r in result]
            keys = list(result.keys())
    finally:
        driver.close()
    return keys, rows


def main() -> int:
    p = argparse.ArgumentParser(description="NL → Cypher (Ollama) → Neo4j")
    p.add_argument("question", nargs="+", help="Natural language question")
    p.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "granite4.2:8b"))
    p.add_argument("--ollama", default=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"))
    p.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687"))
    p.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    p.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD", "tk101lab"))
    p.add_argument("--dry-run", action="store_true", help="Print Cypher only; do not run")
    p.add_argument("--max-shots", type=int, default=8, help="Max cookbook examples in prompt")
    p.add_argument("--list-shots", action="store_true", help="Show selected few-shots and exit")
    args = p.parse_args()
    question = " ".join(args.question).strip()

    examples = parse_cookbook(COOKBOOK)
    if not examples:
        print(f"No cookbook examples found in {COOKBOOK}", file=sys.stderr)
        return 2
    few = select_few_shots(question, examples, max_n=args.max_shots)

    print(f"# question: {question}")
    print(f"# model:    {args.model}")
    print(f"# shots:    {len(few)}/{len(examples)} from cookbook")
    if args.list_shots:
        for t, c in few:
            print(f"  - {t}")
            print(f"    {c.splitlines()[0]}...")
        return 0

    cypher = ollama_cypher(question, args.model, args.ollama, few)
    if not cypher:
        print("LLM returned empty Cypher", file=sys.stderr)
        return 1
    print("--- cypher ---")
    print(cypher)
    print("---")
    if args.dry_run:
        return 0

    try:
        keys, rows = run_cypher(args.uri, args.user, args.password, cypher)
    except Exception as e:
        print(f"# neo4j error: {e}", file=sys.stderr)
        return 1
    print(f"# rows: {len(rows)}")
    if not rows:
        return 0
    widths = {k: max(len(k), *(len(str(r.get(k))) for r in rows)) for k in keys}
    print(" | ".join(k.ljust(widths[k]) for k in keys))
    print("-+-".join("-" * widths[k] for k in keys))
    for r in rows:
        print(" | ".join(str(r.get(k, "")).ljust(widths[k]) for k in keys))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
