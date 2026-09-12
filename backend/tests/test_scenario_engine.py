"""Dedicated comprehensive tests for the Spiritus SQLite scenario engine,
Dijkstra evacuation pathfinding, optimistic concurrency race protection,
arbitrary road status manipulation, and operational shocks.
"""
import unittest
from disaster.scenario_engine import (
    bump_incident_revision,
    commit_exercise_action_with_race_protection,
    find_safe_evacuation_route,
    get_current_revision,
    get_db_connection,
    get_exercise_summary,
    init_scenario_db,
    inject_scenario_shock,
    reset_scenario_to_baseline,
    set_road_status,
)


class TestScenarioEngineDedicated(unittest.TestCase):
    def setUp(self):
        reset_scenario_to_baseline()

    def test_database_initialization_and_metadata(self):
        summary = get_exercise_summary()
        self.assertEqual(summary["badge"], "SYNTHETIC_EXERCISE_OPERATION")
        self.assertEqual(summary["exercise_id"], "VIZAG-EQ-7.1-EX")
        self.assertEqual(summary["revision"], 1)
        self.assertIn("summary", summary)
        self.assertEqual(len(summary["nodes"]), 8)
        self.assertEqual(len(summary["all_roads"]), 16)
        self.assertEqual(len(summary["shelters"]), 4)
        self.assertGreater(len(summary["aid_requests"]), 0)
        self.assertGreater(len(summary["resources"]), 0)

    def test_arbitrary_road_status_updates(self):
        # Initial status of E9 (BRTS Central Arterial N3 -> N8)
        initial_rev = get_current_revision()
        self.assertEqual(initial_rev, 1)

        # Set E9 to damaged
        res = set_road_status("E9", "damaged", reason="Debris from collapsed hoarding")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "damaged")
        self.assertEqual(res["road_id"], "E9")
        self.assertEqual(res["revision"], 2)

        # Verify reverse edge E10 (N8 -> N3) is also updated
        summary = get_exercise_summary()
        e10 = next(r for r in summary["all_roads"] if r["id"] == "E10")
        self.assertEqual(e10["status"], "damaged")
        self.assertEqual(e10["obstacle_reason"], "Debris from collapsed hoarding")

        # Set non-existent road ID
        bad_res = set_road_status("E999_NONEXISTENT", "blocked")
        self.assertFalse(bad_res["success"])
        self.assertIn("not found", bad_res["error"])

    def test_dijkstra_safe_routing_nearest_shelter(self):
        # Route from Vizag Port (N1) to nearest open non-full shelter
        route = find_safe_evacuation_route("N1")
        self.assertTrue(route["safe_route_found"])
        self.assertEqual(route["status"], "APPROVED_SAFE_CORRIDOR")
        self.assertIn("path_nodes", route)
        self.assertIn("edge_ids", route)
        self.assertGreater(route["distance_km"], 0.0)
        self.assertIn(route["destination_shelter_id"], ["S1", "S2", "S3", "S4"])

    def test_dijkstra_safe_routing_specific_shelter(self):
        # Route specifically to Madhurawada Mega-Shelter (S3 at N5)
        route = find_safe_evacuation_route("N3", "S3")
        self.assertTrue(route["safe_route_found"])
        self.assertEqual(route["destination_shelter_id"], "S3")
        self.assertEqual(route["destination_shelter_name"], "Madhurawada Community Mega-Shelter")
        self.assertEqual(route["path_nodes"][-1], "N5")

    def test_routing_rejects_invalid_shelter(self):
        res = find_safe_evacuation_route("N1", "S_DOES_NOT_EXIST")
        self.assertFalse(res["safe_route_found"])
        self.assertEqual(res["status"], "ROUTE_REJECTED_INVALID_TARGET")

    def test_routing_rejects_full_shelter(self):
        # Manually update S1 to full
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE shelters SET current_occupancy = max_capacity WHERE id = 'S1'")
        conn.commit()
        conn.close()

        res = find_safe_evacuation_route("N3", "S1")
        self.assertFalse(res["safe_route_found"])
        self.assertEqual(res["status"], "ROUTE_REJECTED_SHELTER_FULL")
        self.assertIn("full", res["reason"].lower())

    def test_routing_fails_closed_when_stranded(self):
        # Node N1 connects to N3 via E1/E2 and to N4 via E7/E8
        # Block both routes
        set_road_status("E1", "blocked", reason="Fissure")
        set_road_status("E7", "bridge_collapsed", reason="Bridge collapsed")

        res = find_safe_evacuation_route("N1")
        self.assertFalse(res["safe_route_found"])
        self.assertEqual(res["status"], "ROUTE_REJECTED_FAIL_CLOSED")
        self.assertEqual(res["action_required"], "FLAG_STRANDED_AREA_REQUEST_AIRLIFT_OR_HEAVY_CLEARANCE")

    def test_inject_scenario_shocks(self):
        # Shock 1: bridge_collapse
        s1 = inject_scenario_shock("bridge_collapse")
        self.assertEqual(s1["shock"], "bridge_collapse")
        summary1 = get_exercise_summary()
        e7 = next(r for r in summary1["all_roads"] if r["id"] == "E7")
        self.assertEqual(e7["status"], "bridge_collapsed")
        self.assertGreater(summary1["revision"], 1)

        # Shock 2: shelter_overflow
        s2 = inject_scenario_shock("shelter_overflow")
        self.assertEqual(s2["shock"], "shelter_overflow")
        summary2 = get_exercise_summary()
        shelter_s1 = next(s for s in summary2["shelters"] if s["id"] == "S1")
        self.assertEqual(shelter_s1["remaining_capacity"], 0)

        # Shock 3: supply_shortage
        s3 = inject_scenario_shock("supply_shortage")
        self.assertEqual(s3["shock"], "supply_shortage")
        summary3 = get_exercise_summary()
        shelter_s2 = next(s for s in summary3["shelters"] if s["id"] == "S2")
        self.assertLessEqual(shelter_s2["water_rations_days"], 0.8)
        self.assertLessEqual(shelter_s2["medical_supplies_kits"], 20)

        # Unknown shock
        s_unknown = inject_scenario_shock("meteor_strike")
        self.assertIn("error", s_unknown)
        self.assertIn("Unknown shock", s_unknown["error"])

    def test_race_condition_protection_flow(self):
        # Committing with valid revision succeeds
        current_rev = get_current_revision()
        res_ok = commit_exercise_action_with_race_protection(
            request_id="REQ-01",
            resource_id="SAR-ALPHA",
            expected_revision=current_rev,
        )
        self.assertTrue(res_ok["success"])
        self.assertEqual(res_ok["revision"], current_rev + 1)
        self.assertEqual(res_ok["resource_id"], "SAR-ALPHA")

        # Committing another action with stale revision must fail
        res_stale = commit_exercise_action_with_race_protection(
            request_id="REQ-02",
            resource_id="MED-BRAVO",
            expected_revision=current_rev,  # Stale, should be current_rev + 1
        )
        self.assertFalse(res_stale["success"])
        self.assertEqual(res_stale["error"], "STALE_REVISION_REJECTED")

        # Committing using an already deployed resource must fail
        new_rev = get_current_revision()
        res_deployed = commit_exercise_action_with_race_protection(
            request_id="REQ-02",
            resource_id="SAR-ALPHA",  # Already deployed
            expected_revision=new_rev,
        )
        self.assertFalse(res_deployed["success"])
        self.assertEqual(res_deployed["error"], "RESOURCE_NOT_AVAILABLE")

        # Committing for an already dispatched request must fail
        res_dup_req = commit_exercise_action_with_race_protection(
            request_id="REQ-01",  # Already dispatched
            resource_id="MED-BRAVO",
            expected_revision=new_rev,
        )
        self.assertFalse(res_dup_req["success"])
        self.assertEqual(res_dup_req["error"], "REQUEST_ALREADY_RESOLVED")

        # Invalid resource or request
        res_bad_res = commit_exercise_action_with_race_protection("REQ-03", "NONEXISTENT", expected_revision=new_rev)
        self.assertFalse(res_bad_res["success"])
        self.assertEqual(res_bad_res["error"], "RESOURCE_NOT_FOUND")

        res_bad_req = commit_exercise_action_with_race_protection("NONEXISTENT", "MED-BRAVO", expected_revision=new_rev)
        self.assertFalse(res_bad_req["success"])
        self.assertEqual(res_bad_req["error"], "REQUEST_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
