"""Comprehensive tests for Spiritus disaster domain tools, SQLite scenario engine,
arbitrary road damage control, race condition protection, and ten mandatory capabilities.
"""
import asyncio
import os
import unittest

from core.disaster_tools import (
    AffectedPopulationAidTool,
    EvacuationRouteTool,
    ExecuteDispatchTool,
    LiveDisasterFeedTool,
    RegionalRiskAssessmentTool,
    RescuePrioritizationTool,
    ResourceDeploymentTool,
    RoadNetworkAuditTool,
    ScenarioSimulationTool,
    ShelterCapacityTool,
    SupplyShortfallsTool,
)
from disaster.live_feeds import (
    fetch_earthquakes,
    fetch_regional_weather,
    fetch_wildfires,
    get_all_disaster_feeds,
)
from disaster.scenario_engine import (
    commit_exercise_action_with_race_protection,
    find_safe_evacuation_route,
    get_current_revision,
    get_exercise_summary,
    init_scenario_db,
    inject_scenario_shock,
    reset_scenario_to_baseline,
    set_road_status,
)
from agent.orchestrator import MultiAgentOrchestrator
from core.tools import ToolRegistry


class TestDisasterDomainAndEngine(unittest.TestCase):
    def setUp(self):
        reset_scenario_to_baseline()

    def test_01_scenario_initialization_and_summary(self):
        summary = get_exercise_summary()
        self.assertEqual(summary["badge"], "SYNTHETIC_EXERCISE_OPERATION")
        self.assertEqual(summary["exercise_id"], "VIZAG-EQ-7.1-EX")
        self.assertEqual(summary["revision"], 1)
        self.assertGreaterEqual(len(summary["shelters"]), 4)
        self.assertGreaterEqual(len(summary["all_roads"]), 10)
        self.assertGreaterEqual(summary["summary"]["reported_casualties"], 10)
        self.assertGreaterEqual(summary["summary"]["reported_trapped"], 20)

    def test_02_ten_capabilities_tools_registry(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 1. LiveDisasterFeedTool
        feed_tool = LiveDisasterFeedTool()
        r1 = loop.run_until_complete(feed_tool.run(feed_type="all"))
        self.assertTrue(r1.success)
        self.assertIn("earthquakes", r1.output)
        self.assertIn("wildfires", r1.output)
        self.assertIn("weather", r1.output)
        self.assertEqual(r1.output["live_resource_inventories"]["status"], "UNAVAILABLE")

        # 2. RegionalRiskAssessmentTool
        risk_tool = RegionalRiskAssessmentTool()
        r2 = loop.run_until_complete(risk_tool.run(region="Vizag Urban Area"))
        self.assertTrue(r2.success)
        self.assertIn("composite_risk_score", r2.output)
        self.assertIn(r2.output["risk_tier"], ["CRITICAL", "ELEVATED", "MODERATE"])

        # 3. AffectedPopulationAidTool
        aid_tool = AffectedPopulationAidTool()
        r3 = loop.run_until_complete(aid_tool.run(urgency_filter="critical"))
        self.assertTrue(r3.success)
        self.assertGreaterEqual(r3.output["total_trapped_persons"], 1)
        self.assertEqual(r3.output["provenance"], "SYNTHETIC_EXERCISE")

        # 4. RoadNetworkAuditTool
        road_tool = RoadNetworkAuditTool()
        r4 = loop.run_until_complete(road_tool.run())
        self.assertTrue(r4.success)
        self.assertGreater(r4.output["total_monitored_segments"], 0)

        # 5. ShelterCapacityTool
        shelter_tool = ShelterCapacityTool()
        r5 = loop.run_until_complete(shelter_tool.run())
        self.assertTrue(r5.success)
        self.assertGreater(r5.output["total_capacity_remaining"], 0)

        # 6. RescuePrioritizationTool
        rescue_tool = RescuePrioritizationTool()
        r6 = loop.run_until_complete(rescue_tool.run())
        self.assertTrue(r6.success)
        missions = r6.output["ranked_rescue_missions"]
        self.assertGreater(len(missions), 0)
        self.assertGreaterEqual(missions[0]["priority_score"], missions[-1]["priority_score"])

        # 7. SupplyShortfallsTool
        supply_tool = SupplyShortfallsTool()
        r7 = loop.run_until_complete(supply_tool.run())
        self.assertTrue(r7.success)
        self.assertIn("supply_deficits", r7.output)

        # 8. EvacuationRouteTool (Deterministic safe route from Port N1)
        route_tool = EvacuationRouteTool()
        r8 = loop.run_until_complete(route_tool.run(origin_node="N1"))
        self.assertTrue(r8.success)
        self.assertTrue(r8.output["safe_route_found"])
        self.assertIn("path_nodes", r8.output)

        # 9. ScenarioSimulationTool
        sim_tool = ScenarioSimulationTool()
        r9 = loop.run_until_complete(sim_tool.run(event_type="aftershock_m5_5"))
        self.assertTrue(r9.success)
        self.assertEqual(r9.output["scenario_tag"], "NON_PREDICTIVE_STRESS_SIMULATION")

        # 10. ResourceDeploymentTool & ExecuteDispatchTool
        deploy_tool = ResourceDeploymentTool()
        r10 = loop.run_until_complete(deploy_tool.run())
        self.assertTrue(r10.success)
        self.assertGreater(len(r10.output["top_three_actions"]), 0)

        dispatch_tool = ExecuteDispatchTool()
        r11 = loop.run_until_complete(dispatch_tool.run(request_id="REQ-01", resource_id="SAR-ALPHA", expected_revision=1))
        self.assertTrue(r11.success)
        self.assertEqual(r11.output["status"], "DISPATCH_COMMITTED_IN_SIMULATION")

        loop.close()

    def test_03_arbitrary_road_closure_and_fail_closed_stranded_area(self):
        # Port N1 connects only via E1/E2 to N3, and E7/E8 to N4
        # Verify initial safe path exists
        initial_route = find_safe_evacuation_route("N1")
        self.assertTrue(initial_route["safe_route_found"])

        # Close E1 (Port Road Expressway)
        res1 = set_road_status("E1", "blocked", reason="Overpass fissure")
        self.assertTrue(res1["success"])
        self.assertEqual(res1["revision"], 2)

        # Still traversable via E7 (Harbour Flyover) to N4 -> N6 -> S4
        alt_route = find_safe_evacuation_route("N1")
        self.assertTrue(alt_route["safe_route_found"])
        self.assertIn("N4", alt_route["path_nodes"])

        # Now close E7 (Harbour Flyover Bridge) as well
        res2 = set_road_status("E7", "bridge_collapsed", reason="Structural pier snapped")
        self.assertTrue(res2["success"])
        self.assertEqual(res2["revision"], 3)

        # Now N1 is completely cut off: algorithm must fail closed and flag stranded area
        stranded_route = find_safe_evacuation_route("N1")
        self.assertFalse(stranded_route["safe_route_found"])
        self.assertEqual(stranded_route["status"], "ROUTE_REJECTED_FAIL_CLOSED")
        self.assertEqual(stranded_route["action_required"], "FLAG_STRANDED_AREA_REQUEST_AIRLIFT_OR_HEAVY_CLEARANCE")

    def test_04_race_protection_stale_commit_rejection(self):
        # Observer reads state at revision 1
        rev = get_current_revision()
        self.assertEqual(rev, 1)

        # Road status change bumps revision to 2
        set_road_status("E3", "hazardous", reason="Fissure")
        new_rev = get_current_revision()
        self.assertEqual(new_rev, 2)

        # Attempting to commit plan prepared for stale revision 1 must be REJECTED
        res = commit_exercise_action_with_race_protection(
            request_id="REQ-02",
            resource_id="SAR-BRAVO",
            expected_revision=1,  # STALE
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "STALE_REVISION_REJECTED")

        # Committing with matching revision succeeds
        res_ok = commit_exercise_action_with_race_protection(
            request_id="REQ-02",
            resource_id="SAR-BRAVO",
            expected_revision=2,
        )
        self.assertTrue(res_ok["success"])
        self.assertEqual(res_ok["revision"], 3)

    def test_05_shelter_capacity_rejection(self):
        # Overflow shelters S1 and S2
        shock = inject_scenario_shock("shelter_overflow")
        self.assertEqual(shock["shock"], "shelter_overflow")

        # Routing specifically to S1 should be REJECTED with capacity reason
        route_to_s1 = find_safe_evacuation_route("N3", "S1")
        self.assertFalse(route_to_s1["safe_route_found"])
        self.assertIn("FULL", route_to_s1["reason"])

        # Generic routing should find open non-full shelter (S3 or S4)
        route_any = find_safe_evacuation_route("N3")
        self.assertTrue(route_any["safe_route_found"])
        self.assertIn(route_any["destination_shelter_id"], ["S3", "S4"])

    def test_06_critic_safety_audit(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        orchestrator = MultiAgentOrchestrator(registry=ToolRegistry())

        # Inject shelter overflow shock
        inject_scenario_shock("shelter_overflow")

        # A plan proposing sending evacuees to AU Stadium (which is S1, full)
        bad_plan = {
            "columns": ["Action", "Destination", "Notes"],
            "rows": [["Evacuate 300 residents", "Andhra University Indoor Stadium", "Direct arrival"]],
        }
        audit = loop.run_until_complete(orchestrator.audit_plan_safety(bad_plan))
        self.assertFalse(audit["approved"])
        self.assertTrue(any(v["type"] == "SHELTER_OVERCAPACITY_VIOLATION" for v in audit["violations"]))

        # A safe plan routing to Madhurawada Mega-Shelter
        safe_plan = {
            "columns": ["Action", "Destination", "Notes"],
            "rows": [["Evacuate 300 residents", "Madhurawada Community Mega-Shelter", "Divert via bypass"]],
        }
        audit_safe = loop.run_until_complete(orchestrator.audit_plan_safety(safe_plan))
        self.assertTrue(audit_safe["approved"])

        loop.close()


if __name__ == "__main__":
    unittest.main()
