# Spiritus — Autonomous Multi-Agent Disaster & Crisis Response Platform

**Challenge Track:** Advanced Multi-Agent Challenge (AI Agent Challenge 2K26)  
**Problem Statement:** **PS-03 — Disaster Management Agent**  
**Architecture:** Multi-Agent Swarm Orchestration with Autonomous Decide-Act-Observe Runtime & Self-Healing Critic  
**Evaluation Focus:** Real-time information processing, multi-agent coordination, risk assessment, dynamic evacuation routing, adversarial stress-testing, and actionable decision-making.

---

## Overview

**Spiritus** is an autonomous multi-agent disaster response platform built to handle complex, evolving humanitarian crises in real time. Designed for rapid emergency coordination, Spiritus ingests live global and regional environmental feeds (USGS Earthquakes, NASA EONET Wildfires, Open-Meteo Atmospheric Forecasts) and couples them with an in-memory tactical disaster state machine for local crisis management (Visakhapatnam Coastal Sector).

When natural disasters rupture critical infrastructure, Spiritus coordinates specialized autonomous agents to assess hazard severity, navigate safe evacuation transit corridors around blocked roads, allocate emergency shelter capacity, triage medical rescue queues, and resolve supply chain bottlenecks.

---

## Multi-Agent Swarm Architecture

Spiritus abandons brittle single-prompt chatbots in favor of an **autonomous multi-agent swarm with self-healing invariants**:

```
                                  ┌────────────────────────┐
                                  │   Human Incident Lead  │
                                  └───────────┬────────────┘
                                              │ Natural Language Directives
                                              ▼
                             ┌─────────────────────────────────┐
                             │    Lead Swarm Orchestrator      │
                             │  Task Decomposition & Strategy  │
                             └───────┬─────────────────┬───────┘
                                     │                 │
                ┌────────────────────┴───┐         ┌───┴────────────────────┐
                ▼                        ▼         ▼                        ▼
     ┌──────────────────────┐ ┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐
     │ Hazard Scout Agent   │ │ Evacuation Router  │ │ Logistics Coord.   │ │ Medical Triage     │
     │ Live USGS/EONET/Met  │ │ Road graph, closures│ │ Shelters, supplies │ │ Casualty & teams   │
     └──────────┬───────────┘ └──────────┬─────────┘ └──────────┬─────────┘ └──────────┬─────────┘
                │                        │                      │                      │
                └────────────────────────┼──────────────────────┴──────────────────────┘
                                         ▼
                             ┌─────────────────────────────────┐
                             │ Safety Critic & Invariant Auditor│
                             │  Vetoes unsafe plans & routes   │
                             └─────────────────┬───────────────┘
                                               │ Autonomous Replanning Trigger
                                               ▼
                             ┌─────────────────────────────────┐
                             │   Self-Healing Decision Stream  │
                             │   (SSE to Astra Observatory)    │
                             └─────────────────────────────────┘
```

1. **Lead Swarm Orchestrator:** Decomposes complex human queries into actionable domain tasks and delegates to specialists.
2. **Hazard & Situational Scout:** Ingests live seismic, wildfire, and meteorological telemetry to pinpoint hazard epicenters, flood zones, and deteriorating conditions.
3. **Evacuation & Transit Navigator:** Computes safe evacuation paths across regional road graphs, avoiding actively closed or inundated roads and calculating capacity-aware routing.
4. **Relief Logistics Coordinator:** Monitors open emergency shelters, real-time bed capacity, drinking water, rations, and medical supply depletion rates.
5. **Safety Critic & Invariant Auditor:** Continuously enforces safety invariants. If a bridge collapses or a shelter hits 100% saturation during an evacuation, the Critic **vetoes the plan**, injects constraint violations, and commands the swarm to autonomously replan an alternate corridor.

---

## 10 Mandatory Agent Capabilities (Evaluator Reference)

Spiritus directly addresses the 10 mandatory evaluation questions through specialized agent tools:

| # | Mandatory Question | Specialized Tool & Source | Autonomous Agent Action |
|---|---|---|---|
| **1** | **Highest Risk Areas & Causes** | `RegionalRiskAssessmentTool` + USGS / Open-Meteo | Computes risk index, seismic intensity, and wind/rain exposure per sector. |
| **2** | **Affected Areas Needing Immediate Aid** | `AffectedPopulationAidTool` | Ranks impacted zones by exposed population, structural damage, and urgency. |
| **3** | **Blocked or Unsafe Roads** | `RoadNetworkAuditTool` | Audits road network; flags impassable corridors (debris, flood, bridge failure). |
| **4** | **Open Shelters & Available Capacity** | `ShelterCapacityTool` | Tracks total vs available beds across all operational cyclone/emergency shelters. |
| **5** | **Immediate Rescue & Medical Assistance** | `RescueMedicalTriageTool` | Evaluates casualty severity (P1 Critical to P3 Stable) and dispatches teams. |
| **6** | **Food, Water & Medical Shortages** | `SupplyShortfallAuditTool` | Calculates supply burn rates; flags depots with critical deficit warnings. |
| **7** | **Safe Evacuation Corridors** | `EvacuationRoutingTool` | Generates verified routes strictly avoiding closed roads and full shelters. |
| **8** | **Escalating Scenario Forecast** | `EscalatingScenarioTool` + Open-Meteo | Models aftershock probability, storm surge progression, and secondary risk. |
| **9** | **Resource Deployment Recommendations** | `ResourceDeploymentTool` | Recommends optimal allocation of NDRF teams, ambulances, and supply trucks. |
| **10**| **Top 3 Immediate Actions** | `TopPriorityActionsTool` | Generates prioritized, high-impact executive directives for incident commanders. |

---

## Data Taxonomy & Architecture: Real vs Simulated

To ensure total scientific integrity, Spiritus clearly labels the provenance of all data:

- **Live Macro Observation Layer:** Real-time GeoJSON streams from **USGS Earthquake Hazards Program** (`2.5_day.geojson`), **NASA EONET** (`wildfires open`), and **Open-Meteo API** (hourly precipitation, wind speed, pressure).
- **Static Infrastructure Layer:** Real geographic locations of gazetted cyclone shelters, hospitals, and transit nodes in the coastal Andhra Pradesh / Visakhapatnam corridor.
- **Dynamic Operational State Machine:** High-fidelity in-memory SQLite state tracking live shelter occupancy percentages, road damage reports, medical triage queues, and supply depletion.
- **Adversarial Chaos Engine:** Allows evaluators to inject real-time curveballs (e.g., bridge collapse, shelter saturation, supply depletion) and witness instantaneous multi-agent self-healing.

---

## Interactive Astra 3D Globe & Crisis Workbench

The user interface brings the power of **Astra's 3D Earth Observatory** together with an **executive AI crisis workspace**:
- **Astra 3D WebGL Earth:** Rendered with Three.js, displaying global seismic epicenters and wildfire clusters with day/night terminator lighting.
- **Interactive Multi-Agent Chat:** Direct natural-language dialogue with the agent swarm, rendering live tool execution pills, agent handoff cards, and self-healing trace logs.
- **Tactical Scenario Matrix:** Quick access to the 10 core capability audits, live telemetry gauges, and 1-click adversarial stress controls.
- **Dual Theme Support:** True dark mode (Astra graphite `#080d12` with subtle translucent surfaces) and high-contrast professional light mode.

---

## Quickstart

```bash
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Run backend test suite (18 unit & integration tests)
cd backend && python -m unittest discover -s tests

# 3. Launch Spiritus Crisis Workbench
python -m uvicorn app:app --host 127.0.0.1 --port 8420
```

Open **`http://127.0.0.1:8420`** in your browser.
