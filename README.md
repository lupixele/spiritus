# Spiritus — Problem-Agnostic Autonomous Agent Harness & Workbench

Spiritus is a lightweight, competition-grade autonomous AI agent platform and developer workbench built on FastAPI, multi-agent swarm orchestration, and an adaptive decide-act-observe runtime.

## Key Capabilities

1. **Problem-Agnostic Tool Registry (`core/tools.py`):**
   - Clean `Tool` protocol.
   - Register any domain tool in ~10 lines of Python.
   - Built-in safe AST `CalculatorTool`, `DatasetLookupTool`, and persistent `KeyValueStoreTool`.

2. **Multi-Agent Swarm Orchestration (`agent/orchestrator.py`):**
   - **Lead Orchestrator:** Mission strategy & task decomposition.
   - **Domain Execution Specialist:** Dynamic tool calling with strict observational grounding.
   - **Safety Critic & Invariant Auditor:** Invariant verification against disruptions, saturation limits, or policy shifts.
   - **Self-Healing Loop:** Autonomous correction and replanning when the Critic detects safety violations.

3. **Adversarial Chaos Injection (`agent/adversarial.py`):**
   - Pre-built stress scenarios (API 503 Outages, Capacity Bottlenecks, Emergency Policy Shocks).
   - Inoculates the agent against surprise curveballs injected by hackathon evaluators.

4. **Industrial "Precision Monolith" UI (`backend/static/`):**
   - Zero-bundle vanilla SPA (HTML5, CSS3, ES2022).
   - Kimi/Linear warm obsidian aesthetic (`#121212`).
   - Live SSE event streaming (tool calls, thoughts, artifacts, swarm handoffs, critic evaluations).
   - 1-click Adversarial Shock injection and reset directly in the composer.

5. **1-Click Live Demonstration & Cloudflare Tunnel (`run_demo.py` / `run_demo.bat`):**
   - Auto-boots FastAPI on port 8000.
   - Generates an ephemeral `trycloudflare.com` HTTPS link with zero credential setup.

## Quickstart

```bash
# 1. Run tests
cd backend && python -m unittest discover -s tests

# 2. Launch live demo + tunnel
python run_demo.py
```
