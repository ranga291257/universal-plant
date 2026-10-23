#!/usr/bin/env python3
"""TK-101 engineering graph: build nodes and edges, then run structural checks.

real_plant topology: challenge/plant/model.py, docs/pfd/tk-101-hold-tank.svg, participant/tags.csv.
digital twin topology: models/dwsim/*.dwxmz, parsed directly from the archives.
Standard library only, so it runs without the project venv.

Run:  python3 graph/build_graph.py
Writes into graph/: nodes.csv, edges.csv, tk101_graph.json, dwsim_topology.csv, CHECK_REPORT.md
"""
from __future__ import annotations

import csv
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from pathlib import Path

GRAPH = Path(__file__).resolve().parent
ROOT = GRAPH.parent
sys.path.insert(0, str(ROOT))
from challenge.plant.design import DESIGN  # noqa: E402  pure-Python module, no numpy

TAGS_CSV = ROOT / "participant" / "tags.csv"
DWSIM_FILES = {
    "DWSIM steady-state (TK101_heated_tank.dwxmz)": ROOT / "models" / "dwsim" / "TK101_heated_tank.dwxmz",
    "DWSIM dynamic (TK101_heater_dynamic.dwxmz)": ROOT / "models" / "dwsim" / "TK101_heater_dynamic.dwxmz",
}

# ---------------------------------------------------------------- nodes
# (id, kind, description, attributes)
NODES = [
    # boundaries
    ("FEED_SRC", "boundary", "Feed supply", {"F_m3_h": DESIGN.feed_m3_h, "T_C": DESIGN.feed_T_C}),
    ("STEAM_HDR", "boundary", "Steam header", {"P_barg": DESIGN.P_steam_barg}),
    ("COND_RET", "boundary", "Condensate return", {}),
    ("PROD_SINK", "boundary", "Product to downstream", {}),
    ("AMBIENT", "boundary", "Ambient air", {"T_C": DESIGN.T_ambient_C}),
    # equipment
    ("TK-101", "vessel", "Hold tank", {"diameter_m": DESIGN.diameter_m, "height_m": DESIGN.height_m,
                                       "level_SP_m": DESIGN.level_SP_m, "working_volume_m3": round(DESIGN.working_volume_m3, 2)}),
    ("E-101", "heat_exchanger", "Steam coil (submerged in TK-101 per PFD and Python model)",
     {"UA_clean_kW_K": DESIGN.UA_clean_kW_K, "R_rangeability": DESIGN.rangeability_R}),
    ("TV-101", "control_valve", "Steam control valve", {"positioner_tau_s": DESIGN.positioner_tau_s}),
    ("LV-101", "control_valve", "Outlet control valve (gravity outflow)", {"Cv_m3_s": DESIGN.Cv_m3_s}),
    # ports
    ("TK-101.N_FEED", "port", "Feed nozzle", {"parent": "TK-101"}),
    ("TK-101.N_OUT", "port", "Outlet nozzle", {"parent": "TK-101"}),
    ("E-101.S_IN", "port", "Steam inlet", {"parent": "E-101"}),
    ("E-101.C_OUT", "port", "Condensate outlet", {"parent": "E-101"}),
    ("TV-101.IN", "port", "Inlet", {"parent": "TV-101"}),
    ("TV-101.OUT", "port", "Outlet", {"parent": "TV-101"}),
    ("LV-101.IN", "port", "Inlet", {"parent": "LV-101"}),
    ("LV-101.OUT", "port", "Outlet", {"parent": "LV-101"}),
    # lines (line numbers match docs/pfd/tk-101-hold-tank.svg)
    ("L-FEED", "line", "Feed line", {"line_number": "1001"}),
    ("L-STM-SUP", "line", "Steam supply to TV-101", {"line_number": "2001"}),
    ("L-STM-COIL", "line", "Steam from TV-101 to coil", {"line_number": "2002"}),
    ("L-COND", "line", "Condensate line", {"line_number": "2003"}),
    ("L-PROD-1", "line", "Vessel outlet to LV-101", {"line_number": "1002"}),
    ("L-PROD-2", "line", "Product line after LV-101", {"line_number": "1003"}),
    # controllers
    ("TIC-101", "controller", "Temperature controller, reverse, AUTO",
     {"Kc": DESIGN.tic_Kc, "Ti_min": DESIGN.tic_Ti_min, "mode": "AUTO"}),
    ("FIC-201", "controller", "Steam flow controller, reverse, CAS (remote SP from TIC-101)",
     {"Kc": DESIGN.fic_Kc, "Ti_min": DESIGN.fic_Ti_min, "mode": "CAS"}),
    ("LIC-101", "controller", "Level controller, direct, AUTO",
     {"Kc": DESIGN.lic_Kc, "Ti_min": DESIGN.lic_Ti_min, "mode": "AUTO"}),
    # measurement elements that feed controllers (on PFD; historised under controller .PV)
    ("TT-101", "instrument", "Tank temperature transmitter (TIC-101.PV)",
     {"historised_as": "TIC-101.PV"}),
    ("FT-201", "instrument", "Steam flow transmitter (FIC-201.PV)",
     {"historised_as": "FIC-201.PV"}),
    ("LT-101", "instrument", "Tank level transmitter (LIC-101.PV)",
     {"historised_as": "LIC-101.PV"}),
    # tagged instruments and valve positions
    ("TI-100", "instrument", "Feed temperature", {}),
    ("FI-101", "instrument", "Feed flow", {}),
    ("TI-102", "instrument", "Product temperature", {}),
    ("FI-102", "instrument", "Product flow", {}),
    ("PI-201", "instrument", "Steam header pressure", {}),
    ("TI-201", "instrument", "Steam saturation temperature", {}),
    ("TI-202", "instrument", "Condensate temperature", {}),
    ("TI-901", "instrument", "Ambient temperature", {}),
    ("TV-101.POS", "instrument", "Steam valve position (indication)", {}),
    ("LV-101.POS", "instrument", "Outlet valve position (indication)", {}),
    # calculated tags and indications
    ("CALC-DUTY", "calc", "Steam-side coil duty", {}),
    ("CALC-DUTY-PROC", "calc", "Process-side sensible duty", {}),
    ("CALC-EBAL", "calc", "Energy balance gap (duty - process - ambient loss)", {}),
    ("CALC-APPROACH", "calc", "Steam-to-bulk approach", {}),
    ("CALC-UA", "calc", "Back-calculated coil UA", {}),
    ("CALC-MBAL", "calc", "Mass balance residual", {}),
    ("AI-101", "calc", "Purity indication (temperature correlation only)", {}),
    ("Q-LOSS-CALC", "calc_term", "Ambient loss term UA_loss x (T_tank - T_amb); not a tag",
     {"UA_W_K": DESIGN.UA_loss_W_K, "T_amb_C": DESIGN.T_ambient_C}),
    # engineering documents (paths relative to repo root)
    ("DOC-PFD", "document", "Conceptual PFD SVG",
     {"path": "docs/pfd/tk-101-hold-tank.svg", "revision": "1"}),
    ("DOC-PROCESS", "document", "Process description (participant package)",
     {"path": "participant/PROCESS_DESCRIPTION.md"}),
]

# ---------------------------------------------------------------- edges
# (src, dst, edge_type, attributes)
EDGES = [
    # process piping, upstream -> downstream
    ("FEED_SRC", "L-FEED", "piping", {}),
    ("L-FEED", "TK-101.N_FEED", "piping", {}),
    ("STEAM_HDR", "L-STM-SUP", "piping", {}),
    ("L-STM-SUP", "TV-101.IN", "piping", {}),
    ("TV-101.OUT", "L-STM-COIL", "piping", {}),
    ("L-STM-COIL", "E-101.S_IN", "piping", {}),
    ("E-101.C_OUT", "L-COND", "piping", {}),
    ("L-COND", "COND_RET", "piping", {}),
    ("TK-101.N_OUT", "L-PROD-1", "piping", {}),
    ("L-PROD-1", "LV-101.IN", "piping", {}),
    ("LV-101.OUT", "L-PROD-2", "piping", {}),
    ("L-PROD-2", "PROD_SINK", "piping", {}),
    # ports belong to equipment
    ("TK-101.N_FEED", "TK-101", "part_of", {}),
    ("TK-101.N_OUT", "TK-101", "part_of", {}),
    ("E-101.S_IN", "E-101", "part_of", {}),
    ("E-101.C_OUT", "E-101", "part_of", {}),
    ("TV-101.IN", "TV-101", "part_of", {}),
    ("TV-101.OUT", "TV-101", "part_of", {}),
    ("LV-101.IN", "LV-101", "part_of", {}),
    ("LV-101.OUT", "LV-101", "part_of", {}),
    # energy coupling
    ("E-101", "TK-101", "heat_transfer",
     {"law": "UA_eff = UA_clean * R**(x_TV - 1)", "UA_clean_kW_K": DESIGN.UA_clean_kW_K, "R": DESIGN.rangeability_R}),
    ("TK-101", "AMBIENT", "heat_loss", {"UA_W_K": DESIGN.UA_loss_W_K}),
    # measurements
    ("TI-100", "L-FEED", "measures", {}),
    ("FI-101", "L-FEED", "measures", {}),
    ("TI-102", "L-PROD-2", "measures", {}),
    ("FI-102", "L-PROD-2", "measures", {}),
    ("PI-201", "L-STM-SUP", "measures", {}),
    ("TI-201", "L-STM-SUP", "measures", {}),
    ("TI-202", "L-COND", "measures", {}),
    ("TI-901", "AMBIENT", "measures", {}),
    ("TV-101.POS", "TV-101", "measures", {}),
    ("LV-101.POS", "LV-101", "measures", {}),
    ("TT-101", "TK-101", "measures", {"variable": "bulk temperature"}),
    ("FT-201", "L-STM-SUP", "measures", {"variable": "steam mass flow"}),
    ("LT-101", "TK-101", "measures", {"variable": "level"}),
    # control loops
    ("TT-101", "TIC-101", "pv_input", {"variable": "TK-101 temperature"}),
    ("TIC-101", "FIC-201", "cascade_sp", {"scale": "FIC-201.SP [kg/h] = 30 x TIC-101.OP [%]"}),
    ("FT-201", "FIC-201", "pv_input", {"variable": "steam flow to coil"}),
    ("FIC-201", "TV-101", "op_signal", {}),
    ("LT-101", "LIC-101", "pv_input", {"variable": "TK-101 level"}),
    ("LIC-101", "LV-101", "op_signal", {}),
    # calculated tags and their inputs
    ("FT-201", "CALC-DUTY", "derived_from", {}),
    ("TI-201", "CALC-DUTY", "derived_from", {}),
    ("FI-101", "CALC-DUTY-PROC", "derived_from", {}),
    ("TI-100", "CALC-DUTY-PROC", "derived_from", {}),
    ("TI-102", "CALC-DUTY-PROC", "derived_from", {}),
    ("CALC-DUTY", "CALC-EBAL", "derived_from", {}),
    ("CALC-DUTY-PROC", "CALC-EBAL", "derived_from", {}),
    ("Q-LOSS-CALC", "CALC-EBAL", "derived_from", {}),
    ("TI-201", "CALC-APPROACH", "derived_from", {}),
    ("TI-102", "CALC-APPROACH", "derived_from", {}),
    ("CALC-DUTY", "CALC-UA", "derived_from", {}),
    ("TI-201", "CALC-UA", "derived_from", {}),
    ("TI-102", "CALC-UA", "derived_from", {}),
    ("FI-101", "CALC-MBAL", "derived_from", {}),
    ("FI-102", "CALC-MBAL", "derived_from", {}),
    ("TT-101", "AI-101", "derived_from", {}),
    ("TI-102", "Q-LOSS-CALC", "derived_from", {}),
    ("TI-901", "Q-LOSS-CALC", "derived_from", {}),
    # document links
    ("TK-101", "DOC-PFD", "documented_by", {}),
    ("E-101", "DOC-PFD", "documented_by", {}),
    ("TV-101", "DOC-PFD", "documented_by", {}),
    ("LV-101", "DOC-PFD", "documented_by", {}),
    ("TK-101", "DOC-PROCESS", "documented_by", {}),
    ("E-101", "DOC-PROCESS", "documented_by", {}),
    ("TV-101", "DOC-PROCESS", "documented_by", {}),
    ("LV-101", "DOC-PROCESS", "documented_by", {}),
]

# Every tag in participant/tags.csv maps to a node id: the tag itself, or its controller.
CONTROLLERS = {"TIC-101", "FIC-201", "LIC-101"}


def tag_to_node(tag: str, node_ids: set[str]) -> str | None:
    if tag in node_ids:
        return tag
    base = tag.split(".")[0]
    return base if base in CONTROLLERS else None


# ---------------------------------------------------------------- helpers
def collapse(directed: set[tuple[str, str]], is_pass) -> set[tuple[str, str]]:
    """Contract pass-through nodes (lines, interior streams) into direct links between endpoints."""
    succ: dict[str, set[str]] = defaultdict(set)
    for a, b in directed:
        succ[a].add(b)
    out: set[tuple[str, str]] = set()
    for start in {a for a, _ in directed}:
        if is_pass(start):
            continue
        queue, seen = deque(succ[start]), set()
        while queue:
            n = queue.popleft()
            if n in seen:
                continue
            seen.add(n)
            if is_pass(n):
                queue.extend(succ[n])
            else:
                out.add((start, n))
    return out


def parse_dwsim(path: Path) -> set[tuple[str, str]]:
    """Return unit-to-unit links (streams contracted), with boundary streams named like the graph."""
    with zipfile.ZipFile(path) as z:
        xml_name = next(n for n in z.namelist() if n.endswith(".xml"))
        root = ET.fromstring(z.read(xml_name))
    graphic = root.find("GraphicObjects")
    id_to_tag = {g.findtext("Name"): g.findtext("Tag") for g in graphic}
    obj_type = {g.findtext("Tag"): g.findtext("ObjectType") for g in graphic}

    directed: set[tuple[str, str]] = set()
    for g in graphic:
        tag = g.findtext("Tag")
        for c in g.findall("OutputConnectors/Connector"):
            if c.get("IsAttached") == "true":
                directed.add((tag, id_to_tag.get(c.get("AttachedToObjID"))))
        for c in g.findall("InputConnectors/Connector"):
            if c.get("IsAttached") == "true":
                directed.add((id_to_tag.get(c.get("AttachedFromObjID")), tag))
    directed = {(a, b) for a, b in directed if a and b and obj_type.get(a) != "EnergyStream"
                and obj_type.get(b) != "EnergyStream"}

    streams = {t for t, typ in obj_type.items() if typ == "MaterialStream"}
    units = {t for t, typ in obj_type.items() if typ not in ("MaterialStream", "EnergyStream")}
    boundary_name = {"FEED": "FEED_SRC", "STEAM": "STEAM_HDR", "CONDENSATE": "COND_RET", "PRODUCT": "PROD_SINK"}

    interior, renamed = set(), {}
    for s in streams:
        ups = [a for a, b in directed if b == s and a in units]
        downs = [b for a, b in directed if a == s and b in units]
        if ups and downs:
            interior.add(s)
        else:
            renamed[s] = boundary_name.get(s, s)
    edges = set()
    for a, b in directed:
        edges.add((renamed.get(a, a), renamed.get(b, b)))
    return collapse(edges, is_pass=lambda n: n in interior)


def real_plant_links() -> set[tuple[str, str]]:
    """Same unit-to-unit view as the DWSIM files: piping contracted, ports mapped to equipment."""
    node_kind = {n[0]: n[1] for n in NODES}
    port_parent = {n[0]: n[3]["parent"] for n in NODES if n[1] == "port"}
    directed = set()
    for a, b, typ, _ in EDGES:
        if typ == "piping":
            a2 = port_parent.get(a, a)
            b2 = port_parent.get(b, b)
            directed.add((a2, b2))
        if typ == "heat_transfer":
            directed.add((a, b))
    lines = {n for n, k in node_kind.items() if k == "line"}
    return collapse(directed, is_pass=lambda n: n in lines)


# ---------------------------------------------------------------- checks
def build_indexes():
    node_kind = {n[0]: n[1] for n in NODES}
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for a, b, typ, attrs in EDGES:
        incoming[b].append((a, typ))
        outgoing[a].append((b, typ))
    return node_kind, incoming, outgoing


def derived_ancestors(node: str, incoming, seen=None) -> set[str]:
    """Every node that feeds `node` through derived_from edges, directly or indirectly."""
    seen = set() if seen is None else seen
    for a, t in incoming[node]:
        if t == "derived_from" and a not in seen:
            seen.add(a)
            derived_ancestors(a, incoming, seen)
    return seen


def upstream_leaves(node: str, incoming, node_kind, seen=None) -> set[str]:
    """Walk derived_from edges backwards and return the measurement leaves."""
    seen = seen or set()
    if node in seen:
        return set()
    seen.add(node)
    parents = [a for a, t in incoming[node] if t == "derived_from"]
    if not parents:
        return {node}
    leaves: set[str] = set()
    for p in parents:
        leaves |= upstream_leaves(p, incoming, node_kind, seen)
    return leaves


def run_checks():
    node_kind, incoming, outgoing = build_indexes()
    node_ids = set(node_kind)
    results = []

    # C01 tag coverage
    with TAGS_CSV.open(newline="", encoding="utf-8") as f:
        tags = [r["tag"] for r in csv.DictReader(f)]
    unmapped = [t for t in tags if tag_to_node(t, node_ids) is None]
    results.append(("C01", "Every tag in participant/tags.csv maps to a graph node",
                    "PASS" if not unmapped else "FAIL",
                    f"{len(tags) - len(unmapped)}/{len(tags)} mapped" + (f"; unmapped: {unmapped}" if unmapped else "")))

    # C02 every port is part of one equipment item and connected to exactly one line
    bad = []
    for n, k in node_kind.items():
        if k != "port":
            continue
        piping = [1 for a, t in incoming[n] if t == "piping"] + [1 for b, t in outgoing[n] if t == "piping"]
        if len(piping) != 1 or not any(t == "part_of" for _, t in outgoing[n]):
            bad.append(n)
    ports = [n for n, k in node_kind.items() if k == "port"]
    results.append(("C02", "Every equipment port belongs to one item and has exactly one connection",
                    "PASS" if not bad else "FAIL",
                    f"{len(ports) - len(bad)}/{len(ports)} ports OK" + (f"; problems: {bad}" if bad else "")))

    # C03 every line has one upstream end and one downstream end
    lines = [n for n, k in node_kind.items() if k == "line"]
    bad = []
    for n in lines:
        ins = [a for a, t in incoming[n] if t == "piping"]
        outs = [b for b, t in outgoing[n] if t == "piping"]
        if len(ins) != 1 or len(outs) != 1:
            bad.append(n)
    results.append(("C03", "Every line has exactly one upstream and one downstream end",
                    "PASS" if not bad else "FAIL",
                    f"{len(lines) - len(bad)}/{len(lines)} lines OK" + (f"; problems: {bad}" if bad else "")))

    # C04 every controller's PV comes from a tagged element
    ctrls = [n for n, k in node_kind.items() if k == "controller"]
    gaps = []
    for c in ctrls:
        src = [a for a, t in incoming[c] if t == "pv_input"]
        for s in src:
            if node_kind[s] == "unassigned_element":
                gaps.append(f"{c} PV from {s}")
    results.append(("C04", "Every controller PV is a tagged measurement element",
                    "GAP" if gaps else "PASS",
                    "; ".join(gaps) if gaps else "all PVs tagged"))

    # C05 controller output reaches a final element (cascade allowed)
    bad = []
    for c in ctrls:
        seen, frontier, reached = set(), [c], False
        while frontier:
            n = frontier.pop()
            for b, t in outgoing[n]:
                if t in ("cascade_sp", "op_signal"):
                    if node_kind[b] == "control_valve":
                        reached = True
                    frontier.append(b)
        if not reached:
            bad.append(c)
    results.append(("C05", "Every controller output reaches a control valve (cascade allowed)",
                    "PASS" if not bad else "FAIL",
                    "all controllers reach a valve: TIC-101 -> FIC-201 -> TV-101; LIC-101 -> LV-101" if not bad
                    else f"no path from {bad}"))

    # C06 every control valve has an operating signal and piping in and out
    valves = [n for n, k in node_kind.items() if k == "control_valve"]
    bad = []
    for v in valves:
        has_op = any(t == "op_signal" for _, t in incoming[v])
        ports_v = [p for p in ports if p.startswith(v + ".")]
        piping_ok = all(any(t == "piping" for _, t in incoming[p]) or any(t == "piping" for _, t in outgoing[p])
                        for p in ports_v)
        if not (has_op and piping_ok and len(ports_v) == 2):
            bad.append(v)
    results.append(("C06", "Every control valve has an operating signal and piping in and out",
                    "PASS" if not bad else "FAIL", f"{len(valves) - len(bad)}/{len(valves)} valves OK"))

    # C07 tank mass balance: inflow and outflow are both measured
    inflow_meas = any(a == "FI-101" and b == "L-FEED" and t == "measures" for a, b, t, _ in EDGES)
    outflow_meas = any(a == "FI-102" and t == "measures" for a, b, t, _ in EDGES)
    results.append(("C07", "TK-101 mass balance: inflow and outflow flows are measured",
                    "PASS" if inflow_meas and outflow_meas else "FAIL",
                    "FI-101 on feed, FI-102 on product (no branch between LV-101 and FI-102)"))

    # C08 every calculated tag traces back to tagged measurements only
    gaps = []
    for n, k in node_kind.items():
        if k != "calc":
            continue
        leaves = upstream_leaves(n, incoming, node_kind)
        untagged = sorted(x for x in leaves if node_kind.get(x) == "unassigned_element")
        if untagged:
            gaps.append(f"{n} <- {untagged}")
    results.append(("C08", "Every calculated tag traces to tagged measurements",
                    "GAP" if gaps else "PASS",
                    "; ".join(gaps) if gaps else "all calc inputs traceable"))

    # C09 energy terms present for TK-101
    heat_in = [a for a, t in incoming["TK-101"] if t == "heat_transfer"]
    heat_out = [b for b, t in outgoing["TK-101"] if t == "heat_loss"]
    results.append(("C09", "TK-101 energy balance has steam heat input and ambient loss",
                    "PASS" if heat_in and heat_out else "FAIL",
                    f"in: {heat_in}; out: {heat_out}"))

    # C10 line numbers on drawing
    node_attrs = {n[0]: n[3] for n in NODES}
    missing = [n for n in lines if node_attrs[n].get("line_number") is None]
    results.append(("C10", "Every line carries a line number",
                    "GAP" if missing else "PASS",
                    f"{len(missing)}/{len(lines)} lines have no line number on the drawing"))

    # C11 CALC-EBAL includes the ambient loss term (steam heat in = process sensible + loss)
    ebal_inputs = derived_ancestors("CALC-EBAL", incoming)
    loss_missing = "Q-LOSS-CALC" not in ebal_inputs
    results.append(("C11", "CALC-EBAL includes every energy term on TK-101 (steam heat in, ambient loss out)",
                    "FAIL" if loss_missing else "PASS",
                    "CALC-EBAL = CALC-DUTY - CALC-DUTY-PROC has no ambient-loss input, so at steady state it reads "
                    "the loss (about 27.5 kW), not a closure error; see HISTORIAN_CHECK.md V4" if loss_missing
                    else "ambient loss is an input"))

    return results


def cross_model():
    auth = real_plant_links()
    rows = []
    summary = []
    for label, path in DWSIM_FILES.items():
        dw = parse_dwsim(path)
        rows.append((label, "only in DWSIM", sorted(dw - auth)))
        rows.append((label, "only in real_plant", sorted(auth - dw)))
        rows.append((label, "in both", sorted(dw & auth)))
        summary.append((label, dw))
    return auth, summary, rows


# ---------------------------------------------------------------- outputs
def write_outputs(results, auth, summary, rows):
    with (GRAPH / "nodes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "kind", "description", "attributes_json"])
        for n in NODES:
            w.writerow([n[0], n[1], n[2], json.dumps(n[3], sort_keys=True)])

    with (GRAPH / "edges.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["src", "dst", "edge_type", "attributes_json"])
        for a, b, t, attrs in EDGES:
            w.writerow([a, b, t, json.dumps(attrs, sort_keys=True)])

    (GRAPH / "tk101_graph.json").write_text(json.dumps({
        "nodes": [{"id": n[0], "kind": n[1], "description": n[2], "attributes": n[3]} for n in NODES],
        "edges": [{"src": a, "dst": b, "type": t, "attributes": attrs} for a, b, t, attrs in EDGES],
    }, indent=2), encoding="utf-8")

    with (GRAPH / "dwsim_topology.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "relation", "from", "to"])
        for label, rel, pairs in rows:
            for a, b in pairs:
                w.writerow([label, rel, a, b])

    lines = ["# TK-101 graph: check report", "",
             "Generated by `graph/build_graph.py`. Status: **PASS** = rule holds; **GAP** = the drawing or tag set",
             "does not yet say enough to check the rule; **FAIL** = the model is internally inconsistent.", "",
             "| ID | Rule | Status | Detail |", "|---|---|---|---|"]
    for cid, rule, status, detail in results:
        lines.append(f"| {cid} | {rule} | **{status}** | {detail} |")

    lines += ["", "## Cross-model topology (unit-to-unit links, streams contracted)", "",
              "Authoritative (Python model + PFD):", ""]
    lines += [f"- `{a}` -> `{b}`" for a, b in sorted(auth)]
    for label, dw in summary:
        lines += ["", f"### {label}", ""]
        only_dw = sorted(dw - auth)
        only_auth = sorted(auth - dw)
        lines.append(f"- Only in DWSIM: {only_dw if only_dw else 'none'}")
        lines.append(f"- Only in real_plant: {only_auth if only_auth else 'none'}")
        lines.append(f"- In both: {len(dw & auth)} link(s)")
    lines += ["",
              "### Reading the differences",
              "",
              "- **Feed routing (steady-state file):** DWSIM sends the feed through E-101 before the tank. The Python model and the PFD have the feed enter the tank directly, with the steam coil submerged. The same tag `E-101` names a different physical item in each model. `models/dwsim/NOTES.md` does not list this in its fidelity table.",
              "- **Dynamic file:** DWSIM replaces the steam coil with an inline heater (`HTR-101`) and has no steam valve, outlet valve, or controllers. `NOTES.md` documents the missing controllers and steam side.",
              "- The steady-state DWSIM file has no ambient heat loss, so the heat-loss link is excluded from the comparison.", ""]
    (GRAPH / "CHECK_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    results = run_checks()
    auth, summary, rows = cross_model()
    write_outputs(results, auth, summary, rows)
    for cid, rule, status, detail in results:
        print(f"{cid} {status:5s} {rule} :: {detail}")
    for label, dw in summary:
        print(f"{label}: only-DWSIM={sorted(dw - auth)} only-auth={sorted(auth - dw)}")
    print(f"Wrote outputs to {GRAPH}")


if __name__ == "__main__":
    main()
