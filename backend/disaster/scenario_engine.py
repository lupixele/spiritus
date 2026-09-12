"""Scenario Engine for Spiritus Operational Disaster Response Exercises.

Backed by SQLite for deterministic, durable exercise simulation.
Default Region: Visakhapatnam (Vizag) Coastal Earthquake Response.

Includes:
- Dynamic road segment damage/closure control for ANY road ID
- Incident revision tracking for race protection & stale commit rejection
- Deterministic Dijkstra routing with fail-closed safety
- Capacity checks and supply deficit analysis
- Explicit provenance: every record labeled SYNTHETIC_EXERCISE
"""
import heapq
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("spiritus.scenario")

DB_PATH = Path(__file__).parent / "exercise_state.db"


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_scenario_db(force: bool = False):
    """Initializes the SQLite schema and seeds Vizag disaster exercise data."""
    conn = get_db_connection()
    cur = conn.cursor()

    if force:
        cur.execute("DROP TABLE IF EXISTS road_edges")
        cur.execute("DROP TABLE IF EXISTS road_nodes")
        cur.execute("DROP TABLE IF EXISTS shelters")
        cur.execute("DROP TABLE IF EXISTS aid_requests")
        cur.execute("DROP TABLE IF EXISTS operational_resources")
        cur.execute("DROP TABLE IF EXISTS exercise_meta")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS exercise_meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS road_nodes (
        id TEXT PRIMARY KEY,
        name TEXT,
        lat REAL,
        lon REAL,
        hazard_risk REAL DEFAULT 0.0,
        provenance TEXT DEFAULT 'SYNTHETIC_EXERCISE'
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS road_edges (
        id TEXT PRIMARY KEY,
        source TEXT,
        target TEXT,
        name TEXT,
        distance_km REAL,
        capacity_veh_per_hr INTEGER,
        status TEXT DEFAULT 'normal', -- normal, blocked, hazardous, bridge_collapsed, flooded, damaged
        obstacle_reason TEXT,
        updated_at REAL DEFAULT 0.0,
        provenance TEXT DEFAULT 'SYNTHETIC_EXERCISE',
        FOREIGN KEY(source) REFERENCES road_nodes(id),
        FOREIGN KEY(target) REFERENCES road_nodes(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS shelters (
        id TEXT PRIMARY KEY,
        name TEXT,
        lat REAL,
        lon REAL,
        node_id TEXT,
        max_capacity INTEGER,
        current_occupancy INTEGER,
        status TEXT DEFAULT 'open', -- open, full, damaged, inaccessible
        medical_supplies_kits INTEGER,
        water_rations_days REAL,
        food_rations_days REAL,
        generator_power INTEGER DEFAULT 1,
        provenance TEXT DEFAULT 'SYNTHETIC_EXERCISE'
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS aid_requests (
        id TEXT PRIMARY KEY,
        node_id TEXT,
        location_desc TEXT,
        urgency TEXT, -- critical, high, medium, low
        status TEXT DEFAULT 'pending', -- pending, dispatched, resolved
        casualties_count INTEGER DEFAULT 0,
        trapped_count INTEGER DEFAULT 0,
        required_aid TEXT, -- 'medical,heavy_rescue', 'water,rations'
        assigned_team TEXT DEFAULT NULL,
        provenance TEXT DEFAULT 'SYNTHETIC_EXERCISE'
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS operational_resources (
        id TEXT PRIMARY KEY,
        name TEXT,
        type TEXT, -- 'search_and_rescue', 'medical_unit', 'supply_convoy', 'water_purification'
        status TEXT DEFAULT 'available', -- 'available', 'deployed', 'maintenance'
        assigned_to TEXT DEFAULT NULL,
        base_node_id TEXT,
        provenance TEXT DEFAULT 'SYNTHETIC_EXERCISE'
    )
    """)

    conn.commit()

    cur.execute("SELECT value FROM exercise_meta WHERE key='initialized'")
    row = cur.fetchone()
    if not row:
        _seed_vizag_baseline(conn)

    conn.close()


def _seed_vizag_baseline(conn: sqlite3.Connection):
    cur = conn.cursor()
    now = time.time()
    # Metadata & Revision tracking
    cur.execute("INSERT OR REPLACE INTO exercise_meta (key, value) VALUES ('initialized', '1')")
    cur.execute("INSERT OR REPLACE INTO exercise_meta (key, value) VALUES ('exercise_id', 'VIZAG-EQ-7.1-EX')")
    cur.execute("INSERT OR REPLACE INTO exercise_meta (key, value) VALUES ('title', 'Visakhapatnam Coastal Earthquake M6.8')")
    cur.execute("INSERT OR REPLACE INTO exercise_meta (key, value) VALUES ('badge', 'SYNTHETIC_EXERCISE_OPERATION')")
    cur.execute("INSERT OR REPLACE INTO exercise_meta (key, value) VALUES ('last_shock', 'none')")
    cur.execute("INSERT OR REPLACE INTO exercise_meta (key, value) VALUES ('revision', '1')")
    cur.execute("INSERT OR REPLACE INTO exercise_meta (key, value) VALUES ('last_updated', ?)", (str(now),))

    # Road Nodes in Vizag Urban Area
    nodes = [
        ("N1", "Vizag Port Area", 17.698, 83.292, 0.8, "SYNTHETIC_EXERCISE"),
        ("N2", "Beach Road Junction", 17.712, 83.324, 0.6, "SYNTHETIC_EXERCISE"),
        ("N3", "Jagadamba Center", 17.711, 83.301, 0.4, "SYNTHETIC_EXERCISE"),
        ("N4", "Gajuwaka Industrial Hub", 17.689, 83.218, 0.7, "SYNTHETIC_EXERCISE"),
        ("N5", "Madhurawada North", 17.820, 83.345, 0.2, "SYNTHETIC_EXERCISE"),
        ("N6", "Pendurthi Inland Transit", 17.780, 83.200, 0.1, "SYNTHETIC_EXERCISE"),
        ("N7", "RK Beachfront Prom", 17.718, 83.332, 0.9, "SYNTHETIC_EXERCISE"),
        ("N8", "Simhachalam Foothills", 17.766, 83.250, 0.2, "SYNTHETIC_EXERCISE"),
    ]
    cur.executemany("INSERT INTO road_nodes (id, name, lat, lon, hazard_risk, provenance) VALUES (?, ?, ?, ?, ?, ?)", nodes)

    # Road Edges
    edges = [
        ("E1", "N1", "N3", "Port Road Expressway", 4.2, 800, "normal", None, now, "SYNTHETIC_EXERCISE"),
        ("E2", "N3", "N1", "Port Road Expressway", 4.2, 800, "normal", None, now, "SYNTHETIC_EXERCISE"),
        ("E3", "N3", "N2", "Waltair Main Road", 3.1, 600, "normal", None, now, "SYNTHETIC_EXERCISE"),
        ("E4", "N2", "N3", "Waltair Main Road", 3.1, 600, "normal", None, now, "SYNTHETIC_EXERCISE"),
        ("E5", "N2", "N7", "Beach Coast Promenade", 1.8, 300, "hazardous", "Ground fissures reported", now, "SYNTHETIC_EXERCISE"),
        ("E6", "N7", "N2", "Beach Coast Promenade", 1.8, 300, "hazardous", "Ground fissures reported", now, "SYNTHETIC_EXERCISE"),
        ("E7", "N1", "N4", "Harbour Flyover Bridge", 7.5, 1000, "normal", None, now, "SYNTHETIC_EXERCISE"),
        ("E8", "N4", "N1", "Harbour Flyover Bridge", 7.5, 1000, "normal", None, now, "SYNTHETIC_EXERCISE"),
        ("E9", "N3", "N8", "BRTS Central Arterial", 6.8, 900, "normal", None, now, "SYNTHETIC_EXERCISE"),
        ("E10", "N8", "N3", "BRTS Central Arterial", 6.8, 900, "normal", None, now, "SYNTHETIC_EXERCISE"),
        ("E11", "N4", "N6", "Gajuwaka-Pendurthi Bypass", 9.2, 700, "normal", None, now, "SYNTHETIC_EXERCISE"),
        ("E12", "N6", "N4", "Gajuwaka-Pendurthi Bypass", 9.2, 700, "normal", None, now, "SYNTHETIC_EXERCISE"),
        ("E13", "N8", "N5", "Madhurawada Hills Transit", 8.4, 500, "normal", None, now, "SYNTHETIC_EXERCISE"),
        ("E14", "N5", "N8", "Madhurawada Hills Transit", 8.4, 500, "normal", None, now, "SYNTHETIC_EXERCISE"),
        ("E15", "N6", "N8", "West Valley Highway", 5.9, 650, "normal", None, now, "SYNTHETIC_EXERCISE"),
        ("E16", "N8", "N6", "West Valley Highway", 5.9, 650, "normal", None, now, "SYNTHETIC_EXERCISE"),
    ]
    cur.executemany("""
    INSERT INTO road_edges (id, source, target, name, distance_km, capacity_veh_per_hr, status, obstacle_reason, updated_at, provenance)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, edges)

    # Shelters
    shelters = [
        ("S1", "Andhra University Indoor Stadium", 17.724, 83.315, "N3", 1200, 750, "open", 250, 4.0, 3.5, 1, "SYNTHETIC_EXERCISE"),
        ("S2", "Swarna Bharathi Relief Arena", 17.708, 83.298, "N3", 1500, 1420, "open", 120, 2.0, 2.0, 1, "SYNTHETIC_EXERCISE"),
        ("S3", "Madhurawada Community Mega-Shelter", 17.822, 83.340, "N5", 2500, 400, "open", 400, 6.0, 5.0, 1, "SYNTHETIC_EXERCISE"),
        ("S4", "Pendurthi Civic Center", 17.782, 83.203, "N6", 1800, 300, "open", 180, 5.0, 4.5, 1, "SYNTHETIC_EXERCISE"),
    ]
    cur.executemany("""
    INSERT INTO shelters (id, name, lat, lon, node_id, max_capacity, current_occupancy, status, medical_supplies_kits, water_rations_days, food_rations_days, generator_power, provenance)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, shelters)

    # Aid Requests
    aid_requests = [
        ("REQ-01", "N1", "Collapsed cargo warehouse near Dock 4", "critical", "pending", 8, 14, "search_and_rescue,medical", None, "SYNTHETIC_EXERCISE"),
        ("REQ-02", "N7", "Beachfront hotel lobby partial collapse", "critical", "pending", 4, 9, "search_and_rescue,medical", None, "SYNTHETIC_EXERCISE"),
        ("REQ-03", "N4", "Residential colony power transformer failure", "medium", "pending", 0, 0, "power_generator,rations", None, "SYNTHETIC_EXERCISE"),
        ("REQ-04", "N3", "Elderly care clinic water pipeline rupture", "high", "pending", 1, 0, "potable_water,medical", None, "SYNTHETIC_EXERCISE"),
    ]
    cur.executemany("""
    INSERT INTO aid_requests (id, node_id, location_desc, urgency, status, casualties_count, trapped_count, required_aid, assigned_team, provenance)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, aid_requests)

    # Operational Resources
    resources = [
        ("SAR-ALPHA", "NDRF Search & Rescue Alpha", "search_and_rescue", "available", None, "N6", "SYNTHETIC_EXERCISE"),
        ("SAR-BRAVO", "NDRF Search & Rescue Bravo", "search_and_rescue", "available", None, "N5", "SYNTHETIC_EXERCISE"),
        ("MED-01", "KGH Emergency Trauma Mobile Unit", "medical_unit", "available", None, "N3", "SYNTHETIC_EXERCISE"),
        ("MED-02", "Naval Hospital Rapid Medical Squad", "medical_unit", "available", None, "N1", "SYNTHETIC_EXERCISE"),
        ("CONVOY-WATER-1", "District Potable Water Tanker Fleet (4x10kL)", "supply_convoy", "available", None, "N6", "SYNTHETIC_EXERCISE"),
        ("CONVOY-RATIONS-1", "Red Cross Emergency Food & MRE Supply", "supply_convoy", "available", None, "N8", "SYNTHETIC_EXERCISE"),
    ]
    cur.executemany("""
    INSERT INTO operational_resources (id, name, type, status, assigned_to, base_node_id, provenance)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, resources)

    conn.commit()


def bump_incident_revision(conn: sqlite3.Connection) -> int:
    """Increments the authoritative revision number for race condition protection."""
    cur = conn.cursor()
    cur.execute("SELECT value FROM exercise_meta WHERE key='revision'")
    row = cur.fetchone()
    curr_rev = int(row["value"]) if row and row["value"] else 1
    new_rev = curr_rev + 1
    cur.execute("UPDATE exercise_meta SET value = ? WHERE key='revision'", (str(new_rev),))
    cur.execute("UPDATE exercise_meta SET value = ? WHERE key='last_updated'", (str(time.time()),))
    return new_rev


def get_current_revision() -> int:
    """Reads current authoritative revision number."""
    init_scenario_db()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM exercise_meta WHERE key='revision'")
    row = cur.fetchone()
    rev = int(row["value"]) if row and row["value"] else 1
    conn.close()
    return rev


def set_road_status(road_id: str, status: str, reason: Optional[str] = None) -> Dict[str, Any]:
    """
    Judge or operator control to mark ANY road segment damaged, blocked, or normal.
    Updates authoritative incident revision to protect against stale plan commits.
    """
    init_scenario_db()
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM road_edges WHERE id = ?", (road_id,))
    edge = cur.fetchone()
    if not edge:
        conn.close()
        return {"success": False, "error": f"Road segment {road_id} not found."}

    now = time.time()
    cur.execute("""
    UPDATE road_edges
    SET status = ?, obstacle_reason = ?, updated_at = ?
    WHERE id = ?
    """, (status, reason or f"Damage reported: {status}", now, road_id))

    # Also match reverse direction if standard pair
    src, tgt = edge["source"], edge["target"]
    cur.execute("""
    UPDATE road_edges
    SET status = ?, obstacle_reason = ?, updated_at = ?
    WHERE source = ? AND target = ?
    """, (status, reason or f"Damage reported: {status}", now, tgt, src))

    new_rev = bump_incident_revision(conn)
    conn.commit()
    conn.close()

    return {
        "success": True,
        "road_id": road_id,
        "name": edge["name"],
        "status": status,
        "reason": reason or f"Damage reported: {status}",
        "revision": new_rev,
        "timestamp": now,
        "message": f"Road {road_id} ({edge['name']}) set to {status}. Authoritative revision bumped to {new_rev}."
    }


def get_exercise_summary() -> Dict[str, Any]:
    """Returns complete state of the synthetic exercise with revision."""
    init_scenario_db()
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT key, value FROM exercise_meta")
    meta = {r["key"]: r["value"] for r in cur.fetchall()}

    cur.execute("SELECT * FROM shelters")
    shelters = [dict(r) for r in cur.fetchall()]
    for s in shelters:
        s["remaining_capacity"] = max(0, s["max_capacity"] - s["current_occupancy"])
        s["occupancy_pct"] = round((s["current_occupancy"] / s["max_capacity"]) * 100, 1)

    cur.execute("SELECT * FROM road_edges WHERE status != 'normal'")
    disrupted_roads = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM road_edges")
    all_roads = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM road_nodes")
    nodes = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM aid_requests")
    requests = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM operational_resources")
    resources = [dict(r) for r in cur.fetchall()]

    conn.close()

    total_casualties = sum(r["casualties_count"] for r in requests)
    total_trapped = sum(r["trapped_count"] for r in requests)

    return {
        "badge": meta.get("badge", "SYNTHETIC_EXERCISE_OPERATION"),
        "exercise_id": meta.get("exercise_id", "VIZAG-EQ-7.1-EX"),
        "title": meta.get("title", "Visakhapatnam Coastal Earthquake M6.8"),
        "last_shock": meta.get("last_shock", "none"),
        "revision": int(meta.get("revision", 1)),
        "last_updated": float(meta.get("last_updated", 0.0)),
        "summary": {
            "total_shelters": len(shelters),
            "open_shelters": sum(1 for s in shelters if s["status"] == "open" and s["current_occupancy"] < s["max_capacity"]),
            "total_shelter_capacity": sum(s["max_capacity"] for s in shelters),
            "total_sheltered": sum(s["current_occupancy"] for s in shelters),
            "disrupted_road_segments": len(disrupted_roads),
            "reported_casualties": total_casualties,
            "reported_trapped": total_trapped,
            "active_aid_requests": len([r for r in requests if r["status"] == "pending"]),
            "available_resources": len([res for res in resources if res["status"] == "available"]),
        },
        "shelters": shelters,
        "disrupted_roads": disrupted_roads,
        "all_roads": all_roads,
        "nodes": nodes,
        "aid_requests": requests,
        "resources": resources,
    }


def find_safe_evacuation_route(origin_node_id: str, dest_shelter_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes deterministic shortest safe path on the road network using Dijkstra.
    Excludes any edges marked 'blocked', 'bridge_collapsed', 'flooded', 'damaged', or 'hazardous'.
    Validates that destination shelter is NOT at capacity.
    Fails closed if no safe route exists.
    """
    init_scenario_db()
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT value FROM exercise_meta WHERE key='revision'")
    rev_row = cur.fetchone()
    current_rev = int(rev_row["value"]) if rev_row and rev_row["value"] else 1

    # Get target shelter(s)
    if dest_shelter_id:
        cur.execute("SELECT * FROM shelters WHERE id = ?", (dest_shelter_id,))
        shelter = cur.fetchone()
        if not shelter:
            conn.close()
            return {
                "safe_route_found": False,
                "revision": current_rev,
                "reason": f"Shelter {dest_shelter_id} does not exist.",
                "status": "ROUTE_REJECTED_INVALID_TARGET",
            }
        if shelter["current_occupancy"] >= shelter["max_capacity"] or shelter["status"] != "open":
            conn.close()
            return {
                "safe_route_found": False,
                "revision": current_rev,
                "reason": f"Target shelter {shelter['name']} ({shelter['id']}) is FULL or CLOSED ({shelter['current_occupancy']}/{shelter['max_capacity']}). Routing rejected by capacity safety constraint.",
                "status": "ROUTE_REJECTED_SHELTER_FULL",
            }
        target_nodes = [(shelter["node_id"], shelter["id"], shelter["name"])]
    else:
        cur.execute("SELECT * FROM shelters WHERE status = 'open' AND current_occupancy < max_capacity")
        avail_shelters = cur.fetchall()
        if not avail_shelters:
            conn.close()
            return {
                "safe_route_found": False,
                "revision": current_rev,
                "reason": "No open shelters with remaining capacity exist in the region.",
                "status": "ROUTE_REJECTED_NO_CAPACITY",
            }
        target_nodes = [(s["node_id"], s["id"], s["name"]) for s in avail_shelters]

    # Build safe adjacency graph
    cur.execute("SELECT id, source, target, distance_km, name, status, obstacle_reason FROM road_edges")
    edges = cur.fetchall()
    conn.close()

    adj: Dict[str, List[Tuple[str, float, str, str, str]]] = {}
    blocked_encounters = []

    for e in edges:
        e_id, u, v, dist, name, status, reason = e["id"], e["source"], e["target"], e["distance_km"], e["name"], e["status"], e["obstacle_reason"]
        if status in ("blocked", "bridge_collapsed", "flooded", "damaged", "hazardous"):
            blocked_encounters.append(f"{e_id}: {name} ({u}->{v}): {status} ({reason or 'unsafe'})")
            continue
        adj.setdefault(u, []).append((v, dist, name, status, e_id))

    # Dijkstra from origin_node_id
    pq = [(0.0, origin_node_id, [origin_node_id], [], [])]
    visited = set()
    best_cost = {origin_node_id: 0.0}

    target_node_ids = {tn[0] for tn in target_nodes}
    target_map = {tn[0]: tn for tn in target_nodes}

    while pq:
        dist, curr, path, edge_names, edge_ids = heapq.heappop(pq)
        if curr in target_node_ids:
            target_info = target_map[curr]
            return {
                "safe_route_found": True,
                "revision": current_rev,
                "origin_node": origin_node_id,
                "destination_shelter_id": target_info[1],
                "destination_shelter_name": target_info[2],
                "arrival_node": curr,
                "distance_km": round(dist, 2),
                "path_nodes": path,
                "corridors": edge_names,
                "path_edges": edge_names,
                "edge_ids": edge_ids,
                "closure_invariants_checked": len(blocked_encounters),
                "status": "APPROVED_SAFE_CORRIDOR",
            }

        if curr in visited:
            continue
        visited.add(curr)

        for neighbor, edge_dist, e_name, _, e_id in adj.get(curr, []):
            new_dist = dist + edge_dist
            if neighbor not in best_cost or new_dist < best_cost[neighbor]:
                best_cost[neighbor] = new_dist
                heapq.heappush(pq, (new_dist, neighbor, path + [neighbor], edge_names + [e_name], edge_ids + [e_id]))

    return {
        "safe_route_found": False,
        "revision": current_rev,
        "origin_node": origin_node_id,
        "reason": f"No safe traversable path exists from {origin_node_id} to designated open shelters without violating road closures or hazard perimeters.",
        "blocked_edges_evaluated": blocked_encounters,
        "status": "ROUTE_REJECTED_FAIL_CLOSED",
        "action_required": "FLAG_STRANDED_AREA_REQUEST_AIRLIFT_OR_HEAVY_CLEARANCE",
    }


def commit_exercise_action_with_race_protection(request_id: str, resource_id: str, expected_revision: Optional[int] = None) -> Dict[str, Any]:
    """
    Commits an operational action to the exercise state.
    Protects against race conditions: if expected_revision does not match current authoritative revision,
    rejects stale commit and forces replanning.
    """
    init_scenario_db()
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT value FROM exercise_meta WHERE key='revision'")
    rev_row = cur.fetchone()
    current_rev = int(rev_row["value"]) if rev_row and rev_row["value"] else 1

    if expected_revision is not None and expected_revision != current_rev:
        conn.close()
        return {
            "success": False,
            "error": "STALE_REVISION_REJECTED",
            "message": f"Incident state updated during reasoning (current rev {current_rev} != expected {expected_revision}). Re-evaluation required.",
            "current_revision": current_rev,
            "expected_revision": expected_revision,
        }

    # Verify request existence and status
    cur.execute("SELECT * FROM aid_requests WHERE id = ?", (request_id,))
    req = cur.fetchone()
    if not req:
        conn.close()
        return {
            "success": False,
            "error": "REQUEST_NOT_FOUND",
            "message": f"Aid request {request_id} does not exist.",
            "current_revision": current_rev,
        }
    if req["status"] != "pending":
        conn.close()
        return {
            "success": False,
            "error": "REQUEST_ALREADY_RESOLVED",
            "message": f"Aid request {request_id} has already been dispatched or resolved.",
            "current_revision": current_rev,
        }

    # Verify resource existence and availability
    cur.execute("SELECT * FROM operational_resources WHERE id = ?", (resource_id,))
    res = cur.fetchone()
    if not res:
        conn.close()
        return {
            "success": False,
            "error": "RESOURCE_NOT_FOUND",
            "message": f"Resource {resource_id} does not exist in operational inventory.",
            "current_revision": current_rev,
        }
    if res["status"] != "available":
        conn.close()
        return {
            "success": False,
            "error": "RESOURCE_NOT_AVAILABLE",
            "message": f"Resource {resource_id} is currently {res['status']} (assigned to {res['assigned_to']}).",
            "current_revision": current_rev,
        }

    cur.execute("UPDATE aid_requests SET status = 'dispatched', assigned_team = ? WHERE id = ?", (resource_id, request_id))
    cur.execute("UPDATE operational_resources SET status = 'deployed', assigned_to = ? WHERE id = ?", (request_id, resource_id))

    new_rev = bump_incident_revision(conn)
    conn.commit()
    conn.close()

    return {
        "success": True,
        "status": "DISPATCH_COMMITTED_IN_SIMULATION",
        "request_id": request_id,
        "resource_id": resource_id,
        "revision": new_rev,
        "badge": "SYNTHETIC_EXERCISE_OPERATION",
    }


def inject_scenario_shock(shock_type: str) -> Dict[str, Any]:
    """Injects dynamic chaos/shock into the SQLite operational scenario and bumps revision."""
    init_scenario_db()
    conn = get_db_connection()
    cur = conn.cursor()

    result = {}
    if shock_type == "bridge_collapse":
        cur.execute("""
        UPDATE road_edges
        SET status = 'bridge_collapsed', obstacle_reason = 'Critical structural fracture post-aftershock'
        WHERE id IN ('E7', 'E8')
        """)
        cur.execute("UPDATE exercise_meta SET value = 'bridge_collapse' WHERE key = 'last_shock'")
        result = {
            "shock": "bridge_collapse",
            "impact": "Harbour Flyover Bridge (E7/E8 connecting N1 Port and N4 Gajuwaka) severed.",
            "enforcement": "Routing algorithm must reject Harbour Flyover.",
        }

    elif shock_type == "shelter_overflow":
        cur.execute("""
        UPDATE shelters
        SET current_occupancy = max_capacity, status = 'full'
        WHERE id IN ('S1', 'S2')
        """)
        cur.execute("UPDATE exercise_meta SET value = 'shelter_overflow' WHERE key = 'last_shock'")
        result = {
            "shock": "shelter_overflow",
            "impact": "AU Stadium (S1) and Swarna Bharathi (S2) at 100% capacity.",
            "enforcement": "Critic will reject any dispatch of evacuees to central shelters. Rerouting north/west required.",
        }

    elif shock_type == "supply_shortage":
        cur.execute("""
        UPDATE shelters
        SET water_rations_days = 0.5, medical_supplies_kits = 10
        WHERE id = 'S2'
        """)
        cur.execute("UPDATE exercise_meta SET value = 'supply_shortage' WHERE key = 'last_shock'")
        result = {
            "shock": "supply_shortage",
            "impact": "Swarna Bharathi Relief Arena water reserves drop to 0.5 days; emergency triage kits depleted to 10.",
            "enforcement": "Immediate supply convoy prioritization required.",
        }
    else:
        result = {"error": f"Unknown shock type: {shock_type}"}

    new_rev = bump_incident_revision(conn)
    result["revision"] = new_rev
    conn.commit()
    conn.close()
    return result


def reset_scenario_to_baseline():
    """Resets the exercise database to initial clean Vizag state."""
    init_scenario_db(force=True)
    return {"status": "reset_complete", "exercise": "VIZAG-EQ-7.1-EX", "revision": 1}
