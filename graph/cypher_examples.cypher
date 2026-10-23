// TK-101 Neo4j learning lab — paste into Neo4j Browser one block at a time.
// CSV is the source of truth; this DB is for asking connection questions.
// Basics (1–10) then richer patterns (11–20). ask_neo4j.py loads this whole file.

// ---------------------------------------------------------------------------
// 1) How many nodes of each kind?
// ---------------------------------------------------------------------------
MATCH (n:Node)
RETURN n.kind AS kind, count(*) AS n
ORDER BY n DESC;

// ---------------------------------------------------------------------------
// 2) What is directly connected to steam valve TV-101? (neighbors)
// ---------------------------------------------------------------------------
MATCH (v:Node {id: 'TV-101'})-[r]-(x:Node)
RETURN type(r) AS rel, startNode(r).id AS from_id, endNode(r).id AS to_id,
       x.kind AS other_kind, x.description AS other
ORDER BY rel, from_id, to_id;

// ---------------------------------------------------------------------------
// 3) Shortest process path from feed supply to product sink
//    PIPING alone stops at nozzles; include PART_OF to cross vessel/valve ports
// ---------------------------------------------------------------------------
MATCH (a:Node {id: 'FEED_SRC'}), (b:Node {id: 'PROD_SINK'})
MATCH p = shortestPath((a)-[:PIPING|PART_OF*]-(b))
RETURN [n IN nodes(p) | n.id] AS path_ids, length(p) AS hops;

// ---------------------------------------------------------------------------
// 4) Temperature cascade: TIC-101 → (cascade SP) → FIC-201 → (OP) → TV-101
// ---------------------------------------------------------------------------
MATCH path = (tic:Node {id: 'TIC-101'})-[:CASCADE_SP|OP_SIGNAL*1..3]->(v:ControlValve)
RETURN [n IN nodes(path) | n.id] AS chain, [r IN relationships(path) | type(r)] AS rels;

// ---------------------------------------------------------------------------
// 5) Level loop: which transmitter feeds LIC-101, and which valve does it move?
// ---------------------------------------------------------------------------
MATCH (lt)-[:PV_INPUT]->(lic:Node {id: 'LIC-101'})-[:OP_SIGNAL]->(lv)
RETURN lt.id AS transmitter, lic.id AS controller, lv.id AS valve;

// ---------------------------------------------------------------------------
// 6) Instruments that MEASURE the tank TK-101
// ---------------------------------------------------------------------------
MATCH (i:Instrument)-[:MEASURES]->(t:Node {id: 'TK-101'})
RETURN i.id AS instrument, i.description AS description;

// ---------------------------------------------------------------------------
// 7) Energy calc: what does CALC-EBAL derive from?
// ---------------------------------------------------------------------------
MATCH (src)-[:DERIVED_FROM]->(c:Node {id: 'CALC-EBAL'})
RETURN src.id AS input, src.kind AS kind, src.description AS description;

// ---------------------------------------------------------------------------
// 8) Documents that cover LV-101
// ---------------------------------------------------------------------------
MATCH (e:Node {id: 'LV-101'})-[:DOCUMENTED_BY]->(d:Document)
RETURN d.id AS doc, d.path AS path, d.description AS description;

// ---------------------------------------------------------------------------
// 9) Blast radius: everything within 2 hops of coil E-101
// ---------------------------------------------------------------------------
MATCH (e:Node {id: 'E-101'})-[*1..2]-(x:Node)
RETURN DISTINCT x.id AS id, x.kind AS kind, x.description AS description
ORDER BY kind, id;

// ---------------------------------------------------------------------------
// 10) Picture: neighborhood of TK-101 (limit size for Browser)
// ---------------------------------------------------------------------------
MATCH p = (t:Node {id: 'TK-101'})-[*1..2]-(x)
RETURN p
LIMIT 50;

// ---------------------------------------------------------------------------
// 11) Valves that share documents
// ---------------------------------------------------------------------------
MATCH (a:ControlValve)-[:DOCUMENTED_BY]->(d:Document)<-[:DOCUMENTED_BY]-(b:ControlValve)
WHERE a.id < b.id
WITH a, b, collect(d.id) AS shared_docs
RETURN a.id AS valve_a, b.id AS valve_b, shared_docs, size(shared_docs) AS n_shared
ORDER BY n_shared DESC, valve_a;

// ---------------------------------------------------------------------------
// 12) Every controller → valve chain (cascade allowed)
// ---------------------------------------------------------------------------
MATCH (c:Controller)
MATCH p = (c)-[:CASCADE_SP|OP_SIGNAL*1..4]->(v:ControlValve)
RETURN c.id AS controller, v.id AS valve,
       [n IN nodes(p) | n.id] AS chain, length(p) AS hops
ORDER BY hops, controller;

// ---------------------------------------------------------------------------
// 13) Integrity: instruments with no MEASURES edge (expect 0 rows)
// ---------------------------------------------------------------------------
MATCH (i:Instrument)
WHERE NOT (i)-[:MEASURES]->()
RETURN i.id AS orphan_instrument, i.description AS description
ORDER BY i.id;

// ---------------------------------------------------------------------------
// 14) Ultimate tagged inputs that feed CALC-EBAL (walk DERIVED_FROM)
// ---------------------------------------------------------------------------
MATCH (leaf)-[:DERIVED_FROM*1..5]->(root:Node {id: 'CALC-EBAL'})
WHERE NOT ( ()-[:DERIVED_FROM]->(leaf) )
RETURN DISTINCT leaf.id AS ultimate_input, leaf.kind AS kind, leaf.description AS description
ORDER BY kind, ultimate_input;

// ---------------------------------------------------------------------------
// 15) Nodes on all shortest FEED → PROD process paths (PIPING|PART_OF)
// ---------------------------------------------------------------------------
MATCH (a:Node {id: 'FEED_SRC'}), (b:Node {id: 'PROD_SINK'})
MATCH p = allShortestPaths((a)-[:PIPING|PART_OF*]-(b))
UNWIND nodes(p) AS n
WITH n.id AS id, n.kind AS kind, count(*) AS on_paths
RETURN id, kind, on_paths
ORDER BY on_paths DESC, id;

// ---------------------------------------------------------------------------
// 16) Equipment grouped by document paths
// ---------------------------------------------------------------------------
MATCH (e)-[:DOCUMENTED_BY]->(d:Document)
WHERE d.path STARTS WITH 'docs/' OR d.path STARTS WITH 'participant/'
RETURN e.id AS equipment, e.kind AS kind,
       collect(DISTINCT d.id) AS docs, collect(DISTINCT d.path) AS paths
ORDER BY kind, equipment;

// ---------------------------------------------------------------------------
// 17) Steam header → TV-101 path AND controllers that drive that valve
// ---------------------------------------------------------------------------
MATCH steam = shortestPath(
  (h:Node {id: 'STEAM_HDR'})-[:PIPING|PART_OF*]-(v:Node {id: 'TV-101'})
)
MATCH (c:Controller)-[:CASCADE_SP|OP_SIGNAL*1..3]->(v)
RETURN [n IN nodes(steam) | n.id] AS steam_path,
       collect(DISTINCT c.id) AS driving_controllers;

// ---------------------------------------------------------------------------
// 18) Loop motif: transmitter → controller → valve (+ what transmitter measures)
// ---------------------------------------------------------------------------
MATCH (tx:Instrument)-[:PV_INPUT]->(c:Controller)-[:OP_SIGNAL|CASCADE_SP*1..3]->(v:ControlValve)
OPTIONAL MATCH (tx)-[:MEASURES]->(target)
RETURN tx.id AS transmitter, c.id AS controller, v.id AS valve,
       collect(DISTINCT target.id) AS measures,
       collect(DISTINCT target.kind) AS target_kinds
ORDER BY controller, transmitter;

// ---------------------------------------------------------------------------
// 19) Heat in / heat out on TK-101 (map projections)
// ---------------------------------------------------------------------------
MATCH (t:Node {id: 'TK-101'})
OPTIONAL MATCH (hx)-[ht:HEAT_TRANSFER]->(t)
OPTIONAL MATCH (t)-[hl:HEAT_LOSS]->(amb)
RETURN t.id AS tank,
       collect(DISTINCT {hx: hx.id, law: ht.law, UA: ht.UA_clean_kW_K}) AS heat_in,
       collect(DISTINCT {sink: amb.id, UA_W_K: hl.UA_W_K}) AS heat_out;

// ---------------------------------------------------------------------------
// 20) Neighborhood of FIC-201 with edge direction
// ---------------------------------------------------------------------------
MATCH (n:Node {id: 'FIC-201'})-[r]-(x:Node)
RETURN x.id AS neighbor, x.kind AS kind, type(r) AS rel,
       CASE WHEN startNode(r).id = n.id THEN 'out' ELSE 'in' END AS direction,
       x.description AS description
ORDER BY kind, neighbor;
