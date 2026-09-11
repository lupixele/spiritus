"""Domain-Agnostic Adversarial Chaos & Resilience Engine for Spiritus.

Enables live injection of real-world edge cases (API failures, service timeouts,
resource bottlenecks, constraint shifts) to demonstrate autonomous error recovery,
truthful fallbacks, and multi-agent self-healing under competition stress.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("spiritus.adversarial")


class AdversarialManager:
    def __init__(self):
        self.simulated_api_outages: Set[str] = set()
        self.active_scenarios: List[str] = []
        self.injected_constraints: Dict[str, Any] = {}

    def is_outage_active(self, service: str) -> bool:
        return service.lower() in self.simulated_api_outages

    def get_status(self) -> Dict[str, Any]:
        return {
            "chaos_active": bool(self.active_scenarios or self.simulated_api_outages or self.injected_constraints),
            "simulated_outages": list(self.simulated_api_outages),
            "active_scenarios": list(self.active_scenarios),
            "injected_constraints": dict(self.injected_constraints),
        }

    def list_presets(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "SERVICE_OUTAGE_HTTP503",
                "title": "Primary External API Outage (HTTP 503)",
                "severity": "HIGH",
                "description": "Simulates failure of external data source. Verifies graceful fallback without crashing.",
            },
            {
                "id": "RESOURCE_BOTTLENECK",
                "title": "Severe Resource / Capacity Bottleneck",
                "severity": "CRITICAL",
                "description": "Simulates saturation of critical operational bottlenecks. Forces rerouting or rescheduling.",
            },
            {
                "id": "CONSTRAINT_INVERSION",
                "title": "Dynamic Constraint Inversion / Emergency Policy",
                "severity": "HIGH",
                "description": "Injects an emergency policy directive invalidating previous assumptions, triggering replanning.",
            },
        ]

    def inject(self, scenario_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        sc_id = scenario_id.upper()
        if sc_id == "SERVICE_OUTAGE_HTTP503":
            self.simulated_api_outages.add("external_service")
            self.active_scenarios.append("SERVICE_OUTAGE_HTTP503")
            return {
                "status": "injected",
                "scenario": "SERVICE_OUTAGE_HTTP503",
                "details": "External service calls will simulate 503 timeout. Adapters should engage local cache fallback.",
            }
        elif sc_id == "RESOURCE_BOTTLENECK":
            self.active_scenarios.append("RESOURCE_BOTTLENECK")
            self.injected_constraints["capacity_ceiling"] = 0.15  # 85% reduction
            return {
                "status": "injected",
                "scenario": "RESOURCE_BOTTLENECK",
                "details": "Resource capacity reduced to 15%. Multi-agent planner must distribute loads.",
            }
        elif sc_id == "CONSTRAINT_INVERSION":
            self.active_scenarios.append("CONSTRAINT_INVERSION")
            self.injected_constraints["emergency_lockdown"] = True
            return {
                "status": "injected",
                "scenario": "CONSTRAINT_INVERSION",
                "details": "Emergency policy active. Direct execution restricted; Critic safety veto armed.",
            }
        else:
            self.active_scenarios.append(sc_id)
            if payload:
                self.injected_constraints[sc_id] = payload
            return {"status": "injected", "scenario": sc_id, "payload": payload}

    def reset(self) -> Dict[str, Any]:
        self.simulated_api_outages.clear()
        self.active_scenarios.clear()
        self.injected_constraints.clear()
        return {
            "status": "reset",
            "message": "All adversarial conditions and simulated outages cleared.",
        }


adversarial_manager = AdversarialManager()
