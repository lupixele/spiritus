# Spiritus — Autonomous Disaster Response & Crisis Decision Platform

Spiritus is a high-performance autonomous AI crisis decision platform and operational workbench engineered for real-time disaster monitoring, multi-hazard risk assessment, and deterministic disaster response orchestration.

The system combines live public observation feeds (USGS seismic networks, NASA EONET active wildfire events, and Open-Meteo regional weather forecasts) with an authoritative, SQLite-backed operational exercise engine and an autonomous multi-agent decide-act-observe loop.

---

## Key Capabilities

1. **Live Public Disaster Observations:**
   - Real-time ingestion and in-memory caching of USGS M2.5+ earthquakes and NASA EONET active wildfire incidents.
   - Live Open-Meteo weather and wind forecasts for operational staging regions.
   - Strict provenance tagging on every record (`LIVE_PUBLIC_API` vs `SYNTHETIC_EXERCISE`), distinguishing empirical ground truth observations from predictive forecasts. Real field resource inventories are explicitly reported as `UNAVAILABLE` when no authenticated civil defense provider is present.

2. **Deterministic Operational Exercise Engine (`backend/disaster/`):**
   - SQLite-backed state machine modeling the Visakhapatnam (Vizag) M6.8 Coastal Earthquake response scenario.
   - Complete road network topology graph with per-segment status tracking (`normal`, `blocked`, `bridge_collapsed`, `hazardous`, `damaged`).
   - Designated relief shelters with live capacity, current occupancy, and medical/water ration tracking.
   - Triage-ranked rescue requests and operational resource rosters (NDRF SAR teams, mobile trauma units, potable water convoys).

3. **Deterministic Safety Invariants & Routing:**
   - Dijkstra-based evacuation pathfinding that strictly avoids blocked, collapsed, flooded, or hazardous road segments.
   - Capacity constraint enforcement that rejects routing evacuees to saturated or closed shelters.
   - Fail-closed guarantees: when a sector is severed from all open shelters, the system flags the zone as stranded and requests air evacuation or heavy clearance rather than inventing impassable routes.

4. **Incident Revision & Race Condition Protection:**
   - Authoritative monotonic incident revision counter (`revision: #N`).
   - Every road damage injection or shock bumps the revision.
   - Operational action commits enforce `expected_revision`; stale action proposals formulated against outdated observations are rejected (`STALE_REVISION_REJECTED`) to trigger autonomous re-evaluation.

5. **Ten Mandatory Operational Capabilities:**
   - `assess_regional_risk`: Composite risk scoring (0-100) and primary threat cause attribution.
   - `get_affected_population_aid`: Triage queries for trapped individuals and verified casualties.
   - `audit_road_network`: Structural auditing of impaired bridges and road corridors.
   - `query_shelter_capacity`: Open shelter capacities and remaining bed availability.
   - `prioritize_rescue_medical`: Deterministic ranking of urgent rescue operations.
   - `calculate_supply_shortfalls`: Shelter water, MRE ration, and trauma kit deficit calculation.
   - `compute_evacuation_route`: Shortest safe path computation with fail-closed safety.
   - `simulate_worsening_scenario`: Non-predictive conditional stress simulation (e.g. M5.5 aftershock structural cascade).
   - `recommend_resource_deployment`: Matching available field teams and supply convoys to prioritized needs.
   - `execute_simulated_dispatch`: Simulation-scoped execution of operational dispatch orders into SQLite.

6. **Visual Observatory Frontend (`backend/static/`):**
   - Professional dark/light observatory aesthetic derived from the Astra design system (`#080d12`, `#0d141a`, `#f5f3ee`, `#8df6bc`, `#ff7765`, `#f3c56b`).
   - Low-geometry 3D WebGL Earth globe (DPR capped at 1.0, 40x40 segments) with day/night texture blending and ocean specular highlights.
   - Automatic render throttling and page visibility pausing for low-end hardware efficiency.
   - Interactive 2D tactical SVG road network graph view for granular corridor damage inspection.
   - Judge operational shock controls: arbitrary road damage injection, shelter overflow shock, and one-click scenario reset.
   - Real-time Server-Sent Events (SSE) streaming trace displaying agent thoughts, tool invocations, and safety critic audits.

---

## System Architecture

```
Spiritus Platform
├── backend/
│   ├── app.py                      # FastAPI application & REST/SSE routing
│   ├── config.json                 # Model & provider configuration (untracked)
│   ├── API_CONTRACTS.md            # Comprehensive API specification
│   ├── core/
│   │   ├── tools.py                # Abstract Tool protocol & baseline tools
│   │   ├── disaster_tools.py       # 10 Mandatory crisis operational capabilities
│   │   └── sessions.py             # Session state store
│   ├── disaster/
│   │   ├── live_feeds.py           # USGS, NASA EONET, Open-Meteo adapters
│   │   └── scenario_engine.py      # SQLite-backed Vizag exercise engine
│   ├── agent/
│   │   ├── loop.py                 # Autonomous decide-act-observe agent loop
│   │   ├── orchestrator.py         # Multi-agent orchestrator & safety critic
│   │   ├── adversarial.py          # Chaos injection manager
│   │   └── prompt.py               # System prompts & grounding constraints
│   ├── static/
│   │   ├── index.html              # Precision observatory workbench UI
│   │   ├── style.css               # Astra-derived tokens (Dark & Light themes)
│   │   ├── app.js                  # Frontend controller & SSE stream consumer
│   │   ├── globe.js                # Three.js low-geometry visual observatory globe
│   │   ├── geo.js                  # Spherical coordinates & distance math
│   │   ├── vendor/                 # Three.js vendor bundle & MIT license
│   │   └── assets/                 # Earth day/night/specular textures
│   └── tests/
│       ├── test_scenario_engine.py # Dedicated SQLite engine & routing tests
│       ├── test_disaster_domain.py # 10 Capabilities & critic audit tests
│       ├── test_live_feeds_unit.py # Live feed caching & offline fallback tests
│       ├── test_tools.py           # Baseline tool execution tests
│       ├── test_adversarial.py     # Chaos injection tests
│       └── test_api.py             # FastAPI endpoint integration tests
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Requirements installed via `pip install -r backend/requirements.txt`:
  - `fastapi`
  - `uvicorn`
  - `httpx`
  - `pydantic`

### Running Tests

Execute the comprehensive test suite from the `backend/` directory:

```bash
cd backend
python -m unittest discover -s tests
```

All 28 unit and integration tests validate the deterministic routing, race condition protection, shelter capacity bounds, live feed caching, safety critic invariants, and baseline tool executions.

### Running the Workbench Server

Start the persistent Spiritus server:

```bash
cd backend
python -m uvicorn app:app --host 127.0.0.1 --port 8420
```

Open your browser at `http://127.0.0.1:8420/` to access the interactive Disaster Decision & Operational Response Workbench.

---

## Data Sources & Legal Attribution

- **Earthquake Feeds:** United States Geological Survey (USGS) Earthquake Hazards Program (`earthquake.usgs.gov`). Public domain.
- **Wildfire Observations:** NASA Earth Observatory Natural Event Gateway (EONET v3) (`eonet.gsfc.nasa.gov`). Public domain NASA open data.
- **Weather & Forecasts:** Open-Meteo Weather API (`open-meteo.com`). Open data under Creative Commons Attribution 4.0 International (CC BY 4.0).
- **Three.js:** JavaScript 3D Library by Ricardo Cabello (Mr.doob) and Three.js authors. MIT License (`backend/static/vendor/THREE_LICENSE`).
- **Earth Planetary Textures:** NASA Visible Earth / Blue Marble project imagery. Public domain.
