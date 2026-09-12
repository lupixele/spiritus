"""FastAPI Server for Spiritus — Problem-Agnostic Autonomous Agent Platform & Workbench."""
import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.adversarial import adversarial_manager
from agent.loop import run_agent_loop
from agent.orchestrator import MultiAgentOrchestrator
from core.sessions import SessionStore
from core.tools import (
    CalculatorTool,
    DatasetLookupTool,
    KeyValueStoreTool,
    ToolRegistry,
)
from core.disaster_tools import (
    LiveDisasterFeedTool,
    RegionalRiskAssessmentTool,
    AffectedPopulationAidTool,
    RoadNetworkAuditTool,
    ShelterCapacityTool,
    RescuePrioritizationTool,
    SupplyShortfallsTool,
    EvacuationRouteTool,
    ScenarioSimulationTool,
    ResourceDeploymentTool,
    ExecuteDispatchTool,
)
from disaster.live_feeds import get_all_disaster_feeds
from disaster.scenario_engine import (
    get_exercise_summary,
    init_scenario_db,
    inject_scenario_shock,
    reset_scenario_to_baseline,
)

logger = logging.getLogger("spiritus.app")
PROJECT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = PROJECT_DIR / "config.json"
STATIC_DIR = PROJECT_DIR / "static"

app = FastAPI(
    title="Spiritus — Autonomous Agent Workbench",
    description="Problem-Agnostic Autonomous AI Agent Platform with Multi-Agent Swarm Orchestration & Self-Healing",
    version="1.0.0",
)

session_store = SessionStore()
_active_agent_runs: Dict[str, asyncio.Task] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_cache_control_header(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def load_config() -> Dict[str, Any]:
    import os
    env_key = os.environ.get("HERMES_CUSTOM_OMNIROUTE_API_KEY") or os.environ.get("AUTO_API_KEY") or ""
    cfg = {
        "provider_url": "https://omniroute.lupixele.online/v1",
        "api_key": env_key,
        "active_model": "antigravity/gemini-3.8-flash-tiered",
        "custom_models": [
            "antigravity/gemini-3.8-flash-tiered",
            "auto/best-fast",
            "gpt-4o-mini",
        ],
        "max_steps": 8,
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                cfg.update(saved)
                if not cfg.get("api_key") and env_key:
                    cfg["api_key"] = env_key
        except Exception:
            pass
    return cfg


def save_config(cfg: Dict[str, Any]):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def create_agent_registry() -> ToolRegistry:
    """
    Primary tool registry factory with all general and disaster operational capabilities.
    """
    registry = ToolRegistry()
    # General utilities
    registry.register(CalculatorTool())
    registry.register(DatasetLookupTool())
    registry.register(KeyValueStoreTool())

    # Disaster Operational Tools (10 Mandatory Capabilities)
    registry.register(LiveDisasterFeedTool())
    registry.register(RegionalRiskAssessmentTool())
    registry.register(AffectedPopulationAidTool())
    registry.register(RoadNetworkAuditTool())
    registry.register(ShelterCapacityTool())
    registry.register(RescuePrioritizationTool())
    registry.register(SupplyShortfallsTool())
    registry.register(EvacuationRouteTool())
    registry.register(ScenarioSimulationTool())
    registry.register(ResourceDeploymentTool())
    registry.register(ExecuteDispatchTool())
    return registry


# --------------------------------------------------------------------
# Request / Response Schemas
# --------------------------------------------------------------------
class ConfigUpdateRequest(BaseModel):
    provider_url: Optional[str] = None
    api_key: Optional[str] = None
    active_model: Optional[str] = None
    custom_models: Optional[List[str]] = None
    max_steps: Optional[int] = None


class StreamRequest(BaseModel):
    instruction: str
    session_id: Optional[str] = None
    model: Optional[str] = None
    multi_agent: Optional[bool] = False
    context: Optional[Dict[str, Any]] = None


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class CancelRequest(BaseModel):
    session_id: Optional[str] = None
    run_id: Optional[str] = None


class AdversarialInjectRequest(BaseModel):
    scenario_id: str
    payload: Optional[Dict[str, Any]] = None


# --------------------------------------------------------------------
# System & Config Endpoints
# --------------------------------------------------------------------
@app.get("/api/config")
def get_config():
    cfg = load_config()
    api_key = cfg.get("api_key", "")
    return {
        "provider_url": cfg.get("provider_url", "https://omniroute.lupixele.online/v1"),
        "active_model": cfg.get("active_model", "antigravity/gemini-3.8-flash-tiered"),
        "custom_models": cfg.get("custom_models", []),
        "max_steps": cfg.get("max_steps", 8),
        "has_api_key": bool(api_key.strip()),
        "api_key_masked": (
            (api_key[:3] + "..." + api_key[-4:])
            if len(api_key) > 7
            else ("••••••••" if api_key else "")
        ),
    }


@app.post("/api/config")
def update_config(req: ConfigUpdateRequest):
    cfg = load_config()
    if req.provider_url is not None:
        cfg["provider_url"] = req.provider_url.strip()
    if req.api_key is not None:
        key_candidate = req.api_key.strip()
        if key_candidate and not key_candidate.startswith("••") and "..." not in key_candidate:
            cfg["api_key"] = key_candidate
        elif key_candidate == "":
            cfg["api_key"] = ""
    if req.active_model is not None:
        cfg["active_model"] = req.active_model.strip()
    if req.custom_models is not None:
        cfg["custom_models"] = req.custom_models
    if req.max_steps is not None:
        cfg["max_steps"] = max(1, min(req.max_steps, 25))
    save_config(cfg)
    return {"status": "success", "config": get_config()}


# --------------------------------------------------------------------
# Session Endpoints
# --------------------------------------------------------------------
@app.get("/api/sessions")
def list_sessions():
    return session_store.list_sessions()


@app.post("/api/sessions")
def create_session(req: CreateSessionRequest):
    new_id = f"session_{uuid.uuid4().hex[:12]}"
    new_sess = {
        "id": new_id,
        "title": req.title or "New Session",
        "created_at": time.time(),
        "updated_at": time.time(),
        "turns": [],
    }
    session_store.save_session(new_sess)
    return new_sess


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    sess = session_store.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    deleted = session_store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "id": session_id}


# --------------------------------------------------------------------
# Adversarial Stress Testing Endpoints
# --------------------------------------------------------------------
@app.get("/api/adversarial/presets")
def get_adversarial_presets():
    return adversarial_manager.list_presets()


@app.get("/api/adversarial/status")
def get_adversarial_status():
    return adversarial_manager.get_status()


@app.post("/api/adversarial/inject")
def inject_adversarial_scenario(req: AdversarialInjectRequest):
    return adversarial_manager.inject(req.scenario_id, payload=req.payload)


@app.post("/api/adversarial/reset")
def reset_adversarial_scenarios():
    return adversarial_manager.reset()


# --------------------------------------------------------------------
# Cancellation Endpoint
# --------------------------------------------------------------------
@app.post("/api/agent/cancel")
def cancel_agent_run(req: CancelRequest):
    cancelled = False
    if req.run_id and req.run_id in _active_agent_runs:
        task = _active_agent_runs[req.run_id]
        if not task.done():
            task.cancel()
            cancelled = True
    elif req.session_id and req.session_id in _active_agent_runs:
        task = _active_agent_runs[req.session_id]
        if not task.done():
            task.cancel()
            cancelled = True
    return {"status": "cancelled" if cancelled else "not_running", "run_id": req.run_id, "session_id": req.session_id}


# --------------------------------------------------------------------
# Agent Streaming Endpoint (SSE)
# --------------------------------------------------------------------
@app.post("/api/agent/stream")
async def stream_agent(req: StreamRequest):
    cfg = load_config()
    model_to_use = (req.model or cfg.get("active_model", "")).strip()
    if not model_to_use:
        raise HTTPException(status_code=400, detail="No model configured.")

    session_id = req.session_id or f"session_{uuid.uuid4().hex[:12]}"
    active_session = session_store.get_session(session_id)
    if not active_session:
        active_session = {
            "id": session_id,
            "title": req.instruction[:36] + ("..." if len(req.instruction) > 36 else ""),
            "created_at": time.time(),
            "updated_at": time.time(),
            "turns": [],
        }
        session_store.save_session(active_session)

    user_turn = {
        "id": f"turn_u_{uuid.uuid4().hex[:8]}",
        "role": "user",
        "timestamp": time.time(),
        "content": req.instruction,
    }
    session_store.append_turn(session_id, user_turn)

    registry = create_agent_registry()
    provider_url = cfg.get("provider_url", "https://omniroute.lupixele.online/v1")
    api_key = cfg.get("api_key", "")
    max_steps = int(cfg.get("max_steps", 8))
    run_id = f"run_{uuid.uuid4().hex[:8]}"

    async def event_generator():
        assistant_turn_id = f"turn_a_{uuid.uuid4().hex[:8]}"
        tool_records: List[Dict[str, Any]] = []
        full_thoughts: List[str] = []
        final_answer_text = ""
        plan_artifact: Optional[Dict[str, Any]] = None
        converged = False

        current_task = asyncio.current_task()
        if current_task:
            _active_agent_runs[run_id] = current_task
            _active_agent_runs[session_id] = current_task

        try:
            if req.multi_agent:
                orchestrator = MultiAgentOrchestrator(
                    registry=registry,
                    provider_url=provider_url,
                    api_key=api_key,
                    model=model_to_use,
                    max_steps_per_agent=max_steps,
                )
                runner_generator = orchestrator.run(
                    instruction=req.instruction,
                    session_id=session_id,
                    run_id=run_id,
                    prior_turns=active_session.get("turns", []),
                    context=req.context,
                )
            else:
                runner_generator = run_agent_loop(
                    instruction=req.instruction,
                    registry=registry,
                    provider_url=provider_url,
                    api_key=api_key,
                    model=model_to_use,
                    session_id=session_id,
                    run_id=run_id,
                    prior_turns=active_session.get("turns", []),
                    max_steps=max_steps,
                    context=req.context,
                )

            async for event in runner_generator:
                ev_type = event.get("type")
                if ev_type == "tool_call" and event.get("status") in ("success", "error", "completed", "failed"):
                    tool_records.append(event)
                elif ev_type == "thought":
                    full_thoughts.append(event.get("content", ""))
                elif ev_type == "final_answer":
                    final_answer_text = event.get("content", "")
                elif ev_type == "plan_artifact":
                    plan_artifact = event
                elif ev_type == "done":
                    converged = bool(event.get("converged", False))

                yield f"data: {json.dumps(event)}\n\n"

            # Persist assistant turn
            assistant_turn = {
                "id": assistant_turn_id,
                "role": "assistant",
                "timestamp": time.time(),
                "content": final_answer_text,
                "status": "completed" if converged else "incomplete",
                "thoughts": "\n".join(full_thoughts),
                "tools": tool_records,
                "artifact": plan_artifact,
            }
            session_store.append_turn(session_id, assistant_turn)

        except asyncio.CancelledError:
            cancelled_event = {
                "type": "done",
                "session_id": session_id,
                "run_id": run_id,
                "cancelled": True,
                "converged": False,
            }
            yield f"data: {json.dumps(cancelled_event)}\n\n"
        except Exception as e:
            err_event = {
                "type": "error",
                "session_id": session_id,
                "run_id": run_id,
                "message": f"Server stream exception: {str(e)}",
            }
            yield f"data: {json.dumps(err_event)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'converged': False})}\n\n"
        finally:
            _active_agent_runs.pop(run_id, None)
            _active_agent_runs.pop(session_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --------------------------------------------------------------------
# Disaster Domain & Operational Exercise Endpoints
# --------------------------------------------------------------------
class ExerciseShockRequest(BaseModel):
    shock_type: str  # bridge_collapse, shelter_overflow, supply_shortage


class RoadDamageRequest(BaseModel):
    road_id: str
    status: str = "blocked"  # blocked, damaged, hazardous, normal
    reason: Optional[str] = None


class ExerciseActionRequest(BaseModel):
    request_id: str
    resource_id: str
    expected_revision: Optional[int] = None


@app.get("/api/feeds/disasters")
async def get_disaster_feeds(lat: float = Query(17.6868), lon: float = Query(83.2185)):
    return await get_all_disaster_feeds(lat=lat, lon=lon)


@app.get("/api/exercise/state")
def get_current_exercise_state():
    return get_exercise_summary()


@app.post("/api/exercise/reset")
def reset_exercise_endpoint():
    return reset_scenario_to_baseline()


@app.post("/api/exercise/shock")
def inject_shock_endpoint(req: ExerciseShockRequest):
    return inject_scenario_shock(req.shock_type)


@app.post("/api/exercise/road_status")
def set_road_status_endpoint(req: RoadDamageRequest):
    from disaster.scenario_engine import set_road_status
    res = set_road_status(req.road_id, req.status, req.reason)
    return res


@app.post("/api/exercise/action")
async def execute_action_endpoint(req: ExerciseActionRequest):
    dispatch_tool = ExecuteDispatchTool()
    res = await dispatch_tool.run(
        request_id=req.request_id,
        resource_id=req.resource_id,
        expected_revision=req.expected_revision,
    )
    return res.output if res.success else {"error": res.error or res.output.get("message", "Commit rejected")}


# --------------------------------------------------------------------
# Static Files & SPA Route
# --------------------------------------------------------------------
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def get_root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Spiritus Autonomous Agent Backend Running", "docs": "/docs"}
