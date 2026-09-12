# Spiritus API Contracts & Operational Schema

This document defines the live backend endpoints, data contracts, and SSE event streaming formats for the Spiritus Disaster Decision & Operational Response platform.

The backend server is running persistently on:
`http://127.0.0.1:8420`

---

## 1. Public Live Feeds API

### `GET /api/feeds/disasters?lat=17.6868&lon=83.2185`
Fetches cached live public hazard observations and weather forecasts.

**Response Schema:**
```json
{
  "timestamp": 1789191243.62,
  "earthquakes": {
    "source": "USGS M2.5+ Day",
    "fetched_at": 1789191236.72,
    "stale": false,
    "status": "live",
    "type": "observation",
    "count": 42,
    "events": [
      {
        "id": "aka2026sbnvva",
        "title": "M 2.9 - 47 km E of Pedro Bay, Alaska",
        "mag": 2.9,
        "place": "47 km E of Pedro Bay, Alaska",
        "time": 1789189704724,
        "lat": 59.823,
        "lon": -153.262,
        "depth": 130.6,
        "category": "earthquake",
        "significance": 129
      }
    ]
  },
  "wildfires": {
    "source": "NASA EONET Wildfires",
    "fetched_at": 1789191240.10,
    "stale": false,
    "status": "live",
    "type": "observation",
    "count": 7084,
    "events": [
      {
        "id": "EONET_1234",
        "title": "Wildfire - North Ridge",
        "category": "wildfire",
        "lat": 34.12,
        "lon": -118.45,
        "date": "2026-09-12T04:30:00Z"
      }
    ]
  },
  "weather": {
    "source": "Open-Meteo API",
    "fetched_at": 1789191241.00,
    "stale": false,
    "status": "live",
    "type": "forecast",
    "location": { "lat": 17.6868, "lon": 83.2185 },
    "temperature": 28.5,
    "windspeed": 12.4,
    "winddirection": 180,
    "weathercode": 1
  },
  "live_resource_inventories": {
    "status": "UNAVAILABLE",
    "note": "No authoritative real-world civil defense API provider configured for live field teams. Exercise operational mode must be used for simulated resource tracking."
  }
}
```

---

## 2. Operational Exercise State API (SQLite Durable Store)

Default region: Visakhapatnam (Vizag) M6.8 Coastal Earthquake Response.

### `GET /api/exercise/state`
Returns the complete operational scenario state including roads, shelters, aid requests, resources, and authoritative incident revision.

**Response Schema:**
```json
{
  "badge": "SYNTHETIC_EXERCISE_OPERATION",
  "exercise_id": "VIZAG-EQ-7.1-EX",
  "title": "Visakhapatnam Coastal Earthquake M6.8",
  "last_shock": "none",
  "revision": 3,
  "last_updated": 1789191250.0,
  "summary": {
    "total_shelters": 4,
    "open_shelters": 2,
    "total_shelter_capacity": 7000,
    "total_sheltered": 3400,
    "disrupted_road_segments": 1,
    "reported_casualties": 13,
    "reported_trapped": 23,
    "active_aid_requests": 3,
    "available_resources": 5
  },
  "shelters": [
    {
      "id": "S1",
      "name": "Andhra University Indoor Stadium",
      "lat": 17.724,
      "lon": 83.315,
      "node_id": "N3",
      "max_capacity": 1200,
      "current_occupancy": 750,
      "remaining_capacity": 450,
      "occupancy_pct": 62.5,
      "status": "open",
      "medical_supplies_kits": 250,
      "water_rations_days": 4.0,
      "food_rations_days": 3.5,
      "generator_power": 1,
      "provenance": "SYNTHETIC_EXERCISE"
    },
    {
      "id": "S2",
      "name": "Swarna Bharathi Relief Arena",
      "lat": 17.708,
      "lon": 83.298,
      "node_id": "N3",
      "max_capacity": 1500,
      "current_occupancy": 1420,
      "remaining_capacity": 80,
      "occupancy_pct": 94.7,
      "status": "open",
      "medical_supplies_kits": 120,
      "water_rations_days": 2.0,
      "food_rations_days": 2.0,
      "generator_power": 1,
      "provenance": "SYNTHETIC_EXERCISE"
    },
    {
      "id": "S3",
      "name": "Madhurawada Community Mega-Shelter",
      "lat": 17.822,
      "lon": 83.340,
      "node_id": "N5",
      "max_capacity": 2500,
      "current_occupancy": 400,
      "remaining_capacity": 2100,
      "occupancy_pct": 16.0,
      "status": "open",
      "medical_supplies_kits": 400,
      "water_rations_days": 6.0,
      "food_rations_days": 5.0,
      "generator_power": 1,
      "provenance": "SYNTHETIC_EXERCISE"
    },
    {
      "id": "S4",
      "name": "Pendurthi Civic Center",
      "lat": 17.782,
      "lon": 83.203,
      "node_id": "N6",
      "max_capacity": 1800,
      "current_occupancy": 300,
      "remaining_capacity": 1500,
      "occupancy_pct": 16.7,
      "status": "open",
      "medical_supplies_kits": 180,
      "water_rations_days": 5.0,
      "food_rations_days": 4.5,
      "generator_power": 1,
      "provenance": "SYNTHETIC_EXERCISE"
    }
  ],
  "nodes": [
    { "id": "N1", "name": "Vizag Port Area", "lat": 17.698, "lon": 83.292, "hazard_risk": 0.8 },
    { "id": "N2", "name": "Beach Road Junction", "lat": 17.712, "lon": 83.324, "hazard_risk": 0.6 },
    { "id": "N3", "name": "Jagadamba Center", "lat": 17.711, "lon": 83.301, "hazard_risk": 0.4 },
    { "id": "N4", "name": "Gajuwaka Industrial Hub", "lat": 17.689, "lon": 83.218, "hazard_risk": 0.7 },
    { "id": "N5", "name": "Madhurawada North", "lat": 17.820, "lon": 83.345, "hazard_risk": 0.2 },
    { "id": "N6", "name": "Pendurthi Inland Transit", "lat": 17.780, "lon": 83.200, "hazard_risk": 0.1 },
    { "id": "N7", "name": "RK Beachfront Prom", "lat": 17.718, "lon": 83.332, "hazard_risk": 0.9 },
    { "id": "N8", "name": "Simhachalam Foothills", "lat": 17.766, "lon": 83.250, "hazard_risk": 0.2 }
  ],
  "all_roads": [
    { "id": "E1", "source": "N1", "target": "N3", "name": "Port Road Expressway", "distance_km": 4.2, "status": "normal" },
    { "id": "E3", "source": "N3", "target": "N2", "name": "Waltair Main Road", "distance_km": 3.1, "status": "normal" },
    { "id": "E5", "source": "N2", "target": "N7", "name": "Beach Coast Promenade", "distance_km": 1.8, "status": "hazardous", "obstacle_reason": "Ground fissures reported" },
    { "id": "E7", "source": "N1", "target": "N4", "name": "Harbour Flyover Bridge", "distance_km": 7.5, "status": "normal" },
    { "id": "E9", "source": "N3", "target": "N8", "name": "BRTS Central Arterial", "distance_km": 6.8, "status": "normal" },
    { "id": "E11", "source": "N4", "target": "N6", "name": "Gajuwaka-Pendurthi Bypass", "distance_km": 9.2, "status": "normal" },
    { "id": "E13", "source": "N8", "target": "N5", "name": "Madhurawada Hills Transit", "distance_km": 8.4, "status": "normal" },
    { "id": "E15", "source": "N6", "target": "N8", "name": "West Valley Highway", "distance_km": 5.9, "status": "normal" }
  ],
  "aid_requests": [
    { "id": "REQ-01", "node_id": "N1", "location_desc": "Collapsed cargo warehouse near Dock 4", "urgency": "critical", "status": "pending", "casualties_count": 8, "trapped_count": 14 },
    { "id": "REQ-02", "node_id": "N7", "location_desc": "Beachfront hotel lobby partial collapse", "urgency": "critical", "status": "pending", "casualties_count": 4, "trapped_count": 9 },
    { "id": "REQ-03", "node_id": "N4", "location_desc": "Residential colony power transformer failure", "urgency": "medium", "status": "pending", "casualties_count": 0, "trapped_count": 0 },
    { "id": "REQ-04", "node_id": "N3", "location_desc": "Elderly care clinic water pipeline rupture", "urgency": "high", "status": "pending", "casualties_count": 1, "trapped_count": 0 }
  ],
  "resources": [
    { "id": "SAR-ALPHA", "name": "NDRF Search & Rescue Alpha", "type": "search_and_rescue", "status": "available", "base_node_id": "N6" },
    { "id": "SAR-BRAVO", "name": "NDRF Search & Rescue Bravo", "type": "search_and_rescue", "status": "available", "base_node_id": "N5" },
    { "id": "MED-01", "name": "KGH Emergency Trauma Mobile Unit", "type": "medical_unit", "status": "available", "base_node_id": "N3" },
    { "id": "MED-02", "name": "Naval Hospital Rapid Medical Squad", "type": "medical_unit", "status": "available", "base_node_id": "N1" },
    { "id": "CONVOY-WATER-1", "name": "District Potable Water Tanker Fleet (4x10kL)", "type": "supply_convoy", "status": "available", "base_node_id": "N6" },
    { "id": "CONVOY-RATIONS-1", "name": "Red Cross Emergency Food & MRE Supply", "type": "supply_convoy", "status": "available", "base_node_id": "N8" }
  ]
}
```

---

## 3. Operational Shock & Judge Controls

### `POST /api/exercise/road_status`
Sets the condition of any road segment (bidirectional) and increments authoritative revision.
```json
{
  "road_id": "E7",
  "status": "bridge_collapsed",
  "reason": "Structural pier sheared"
}
```
**Response:**
```json
{
  "success": true,
  "road_id": "E7",
  "name": "Harbour Flyover Bridge",
  "status": "bridge_collapsed",
  "reason": "Structural pier sheared",
  "revision": 4,
  "timestamp": 1789191255.2,
  "message": "Road E7 (Harbour Flyover Bridge) set to bridge_collapsed. Authoritative revision bumped to 4."
}
```

### `POST /api/exercise/shock`
Injects pre-packaged disaster shocks (`bridge_collapse`, `shelter_overflow`, `supply_shortage`).
```json
{
  "shock_type": "shelter_overflow"
}
```

### `POST /api/exercise/reset`
Resets the exercise SQLite database back to clean baseline state (Revision #1).

---

## 4. Action Commit & Race Condition Protection

### `POST /api/exercise/action`
Executes an operational dispatch order into SQLite scenario store.
If `expected_revision` does not match authoritative revision, the commit is rejected with `STALE_REVISION_REJECTED`.
```json
{
  "request_id": "REQ-01",
  "resource_id": "SAR-ALPHA",
  "expected_revision": 4
}
```
**Success Response:**
```json
{
  "status": "DISPATCH_COMMITTED_IN_SIMULATION",
  "request_id": "REQ-01",
  "resource_id": "SAR-ALPHA",
  "revision": 5,
  "badge": "SYNTHETIC_EXERCISE_OPERATION"
}
```
**Stale Rejection Response:**
```json
{
  "error": "Incident state updated during reasoning (current rev 4 != expected 2). Re-evaluation required."
}
```

---

## 5. Real-Time Autonomous Agent SSE Stream

### `POST /api/agent/stream`
Executes autonomous LLM agent loop using real configured model (`antigravity/gemini-3.8-flash-tiered`) and domain tools.

**Request Payload:**
```json
{
  "instruction": "Evaluate situation and recommend top actions",
  "model": "antigravity/gemini-3.8-flash-tiered",
  "multi_agent": true,
  "max_steps": 8
}
```

**SSE Event Types Emitted:**
- `tool_call`: When an agent invokes a domain tool.
- `tool_result`: Tool execution output and observation data.
- `critic_audit`: Safety critic validation (`approved` or `rejected` with violations).
- `thought`: Agent step reasoning text.
- `final_answer`: Completed synthesized resolution.
- `done`: Final convergence marker.

---

## 6. Ten Registered Operational Capabilities

1. `assess_regional_risk`: Composite risk calculation (0-100) + threat causes.
2. `get_affected_population_aid`: Casualties and trapped individuals query.
3. `audit_road_network`: Impaired corridors and bridge status.
4. `query_shelter_capacity`: Open shelters, occupancy, remaining beds.
5. `prioritize_rescue_medical`: Deterministic triage ranking.
6. `calculate_supply_shortfalls`: Water, MRE, medical kit deficits.
7. `compute_evacuation_route`: Dijkstra corridor excluding closed edges and full shelters (fails closed with stranded area flag).
8. `simulate_worsening_scenario`: Non-predictive stress simulation for secondary cascades.
9. `recommend_resource_deployment`: Matching SAR teams and convoys to priority requests.
10. `get_live_disaster_feed`: Real-time USGS, EONET, and Open-Meteo observations.
