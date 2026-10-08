"""Tests der High-Level-Befehle: Registry, Regelpruefung, Ausfuehrung und Kosten."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from autonomy_recovery_sim.agent_session import AgentSession
from autonomy_recovery_sim.commands import COMMAND_NAMES, COMMANDS, CommandError, decision_schema, parse_command
from autonomy_recovery_sim.dynamics import Control, Vehicle, step_vehicle
from autonomy_recovery_sim.engine import SimulationEngine
from autonomy_recovery_sim.models import ActorSpec, ActorState, CommandRequest, EgoState, WorldFacts
from autonomy_recovery_sim.policy import heuristic_agent
from autonomy_recovery_sim.rules import check_command
from autonomy_recovery_sim.scenario import AssistanceSpec, MissionSpec, RouteSpec, load_scenario
from autonomy_recovery_sim.simulation import run_scenario
from autonomy_recovery_sim.tools import SituationTools

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "autonomy_recovery_sim/scenarios"
EVIDENCE_TOOLS = (
    "get_blocker",
    "get_center_marking",
    "check_oncoming_traffic",
    "check_rear_traffic",
    "check_vulnerable_road_users",
    "get_lateral_clearance",
    "get_visibility",
)
TODO_COMMANDS = {
    "WAIT",
    "REPLAN_ROUTE",
    "REVERSE_SHORT",
    "PULL_OVER",
    "NUDGE_AROUND_OBSTACLE",
    "CHANGE_LANE",
    "AVOID_TEMPORARY_OBSTRUCTION",
    "CROSS_LOW_RISK_OBJECT",
    "REQUEST_REMOTE_ASSISTANCE",
    "ABORT_MISSION",
    "SAFE_STOP",
    "RETURN_HOME",
    "DROP_PASSENGER",
    "REQUEST_ADDITIONAL_INFORMATION",
    "ESCALATE_TO_RULE_ENGINE",
    "RESUME",
    "SECURE_SCENE",
    "REPORT_INCIDENT",
    "CREEP_FORWARD",
    "PEEK_OUT",
    "OVERTAKE",
    "ABORT_TO_LANE",
    "WAIT_FOR_GAP",
    "TURN_AROUND",
}


def command(name: str, reason: str = "Test", **parameters: object) -> dict[str, object]:
    return {"command": name, "parameters": parameters, "reason": reason}


def scripted(*steps: dict[str, object], sessions: list[AgentSession] | None = None):
    """Agent, der pro Deadlock-Sitzung den naechsten Befehl liefert (danach WAIT)."""
    queue = list(steps)

    def policy(session: AgentSession):
        if sessions is not None:
            sessions.append(session)
        for tool in EVIDENCE_TOOLS:
            session.call_tool(tool)
        return queue.pop(0) if queue else command("WAIT", duration_s=5.0)

    return policy


def run(scenario, *steps: dict[str, object], sessions: list[AgentSession] | None = None):
    return run_scenario(scenario, agent=scripted(*steps, sessions=sessions), agent_name="script")


def load(name: str):
    return load_scenario(SCENARIOS / f"{name}.json")


def situation(*actors: ActorSpec, ego_s: float = 82.0, facts: WorldFacts | None = None, scenario=None):
    scenario = scenario or load("hannover_frei")
    return SituationTools(
        scenario,
        EgoState(ego_s, -1.75, 0.0, 4.71, 1.99),
        tuple(ActorState.from_spec(actor) for actor in actors),
        None,
        facts or WorldFacts(),
    )


BLOCKER = ActorSpec("blocker", "car", 92.0, -1.75, 0.0, 1, 4.5, 1.8)


class RegistryTest(unittest.TestCase):
    def test_registry_offers_exactly_the_documented_commands(self) -> None:
        self.assertEqual(set(COMMAND_NAMES), TODO_COMMANDS)
        self.assertEqual(len(COMMAND_NAMES), 24)

    def test_registry_offers_no_actuator_or_trajectory_commands(self) -> None:
        for forbidden in ("set_steering_angle", "set_throttle", "follow_raw_waypoints", "teleport_vehicle"):
            self.assertNotIn(forbidden.upper(), COMMAND_NAMES)

    def test_committed_json_schema_matches_the_registry(self) -> None:
        committed = json.loads((ROOT / "autonomy_recovery_sim/schemas/agent_decision.schema.json").read_text("utf8"))
        self.assertEqual(committed, decision_schema())

    def test_commands_are_documented(self) -> None:
        documentation = (ROOT / "autonomy_recovery_sim/COMMANDS.md").read_text("utf8")
        for name in COMMAND_NAMES:
            self.assertIn(f"`{name}`", documentation)

    def test_defaults_are_filled_and_bounds_are_enforced(self) -> None:
        request = parse_command(command("REPLAN_ROUTE"))
        self.assertEqual(request.parameters, {"avoid_current_segment": True})
        self.assertEqual(parse_command(command("PULL_OVER")).parameters, {"side_preference": "RIGHT"})
        self.assertEqual(
            parse_command(command("CROSS_LOW_RISK_OBJECT")).parameters,
            {"max_speed_mps": 1.0},
        )
        for payload in (
            command("REVERSE_SHORT", max_distance_m=9.0),
            command("REVERSE_SHORT"),
            command("NUDGE_AROUND_OBSTACLE", side="UP", max_longitudinal_distance_m=20),
            command("REQUEST_REMOTE_ASSISTANCE", reason_code="BORED"),
            command("WAIT", duration_s=0),
        ):
            with self.subTest(payload=payload), self.assertRaises(CommandError) as raised:
                parse_command(payload)
            self.assertEqual(raised.exception.code, "INVALID_ARGUMENT")

    def test_catalog_is_part_of_the_session_context(self) -> None:
        tools = situation(BLOCKER)
        catalog = AgentSession(tools, time_s=0.0, stopped_for_s=0.0).context["available_commands"]
        # Im Pruefmodus strict fehlen die Befehle der Unfallabwicklung.
        self.assertEqual(
            {entry["command"] for entry in catalog},
            TODO_COMMANDS - {"SECURE_SCENE", "REPORT_INCIDENT"},
        )
        self.assertTrue(all(COMMANDS[e["command"]].summary == e["description"] for e in catalog))


class RuleEngineTest(unittest.TestCase):
    def check(self, request: dict[str, object], tools: SituationTools) -> str | None:
        try:
            check_command(parse_command(request), tools=tools, facts=tools.facts)
        except CommandError as error:
            return error.detail.split(":")[0] + "@" + error.code
        return None

    def test_solid_center_line_blocks_a_left_nudge(self) -> None:
        tools = situation(BLOCKER, scenario=load("hannover_durchgezogen"))
        nudge = command("NUDGE_AROUND_OBSTACLE", side="LEFT", max_longitudinal_distance_m=30)
        self.assertEqual(self.check(nudge, tools), "CENTER_LINE_SOLID@RULE_REJECTED")
        right = command("NUDGE_AROUND_OBSTACLE", side="RIGHT", max_longitudinal_distance_m=30)
        self.assertEqual(
            self.check(right, tools),
            "SHOULDER_PASSING_NOT_ALLOWED@RULE_REJECTED",
        )

    def test_shoulder_passing_policy_does_not_forbid_pulling_over(self) -> None:
        scenario = load("hannover_leitstelle_offline")
        tools = situation(BLOCKER, facts=WorldFacts(shoulder_m=scenario.shoulder_m), scenario=scenario)
        right = command("NUDGE_AROUND_OBSTACLE", side="RIGHT", max_longitudinal_distance_m=30)
        self.assertEqual(
            self.check(right, tools),
            "SHOULDER_PASSING_NOT_ALLOWED@RULE_REJECTED",
        )
        self.assertIsNone(self.check(command("PULL_OVER"), tools))

    def test_narrow_road_has_no_safe_passing_side(self) -> None:
        scenario = load("hannover_schmal")
        blocker = scenario.actors[0]
        tools = situation(blocker, facts=WorldFacts(shoulder_m=scenario.shoulder_m), scenario=scenario)
        left = command("NUDGE_AROUND_OBSTACLE", side="LEFT", max_longitudinal_distance_m=30)
        right = command("NUDGE_AROUND_OBSTACLE", side="RIGHT", max_longitudinal_distance_m=30)
        self.assertEqual(self.check(left, tools), "ROAD_FULLY_BLOCKED@SAFETY_REJECTED")
        self.assertEqual(
            self.check(right, tools),
            "SHOULDER_PASSING_NOT_ALLOWED@RULE_REJECTED",
        )

    def test_right_nudge_needs_shoulder_space(self) -> None:
        tools = situation(BLOCKER, facts=WorldFacts(shoulder_m=0.5))
        right = command("NUDGE_AROUND_OBSTACLE", side="RIGHT", max_longitudinal_distance_m=30)
        self.assertEqual(self.check(right, tools), "NO_SHOULDER_SPACE@SAFETY_REJECTED")

    def test_lane_change_never_uses_the_oncoming_lane(self) -> None:
        tools = situation(BLOCKER)
        self.assertEqual(
            self.check(command("CHANGE_LANE", direction="LEFT"), tools),
            "LANE_OPPOSITE_DIRECTION@RULE_REJECTED",
        )
        self.assertEqual(
            self.check(command("CHANGE_LANE", direction="RIGHT"), tools), "NO_ADJACENT_LANE@NOT_AVAILABLE"
        )

    def test_lane_change_rejects_an_occupied_target_lane(self) -> None:
        lane = ({"side": "RIGHT", "direction": "SAME", "available": True},)
        facts = WorldFacts(adjacent_lanes=lane)
        free = situation(BLOCKER, facts=facts)
        self.assertIsNone(self.check(command("CHANGE_LANE", direction="RIGHT"), free))
        neighbour = ActorSpec("neighbour", "car", 84.0, -5.25, 0.0, 1, 4.5, 1.8)
        busy = situation(BLOCKER, neighbour, facts=facts)
        self.assertEqual(
            self.check(command("CHANGE_LANE", direction="RIGHT"), busy),
            "TARGET_LANE_OCCUPIED@SAFETY_REJECTED",
        )

    def test_avoid_requires_a_matching_small_obstruction(self) -> None:
        bin_actor = ActorSpec("bin", "trash_bin", 92.0, -2.9, 0.0, 1, 0.8, 0.7)
        tools = situation(bin_actor)
        good = command("AVOID_TEMPORARY_OBSTRUCTION", obstruction_type="TRASH_BIN", side="LEFT", max_lateral_offset_m=1.0)
        self.assertIsNone(self.check(good, tools))
        wrong = command("AVOID_TEMPORARY_OBSTRUCTION", obstruction_type="CONSTRUCTION_BEACON", side="LEFT", max_lateral_offset_m=1.0)
        self.assertEqual(self.check(wrong, tools), "OBSTRUCTION_TYPE_MISMATCH@NOT_AVAILABLE")
        tight = command("AVOID_TEMPORARY_OBSTRUCTION", obstruction_type="TRASH_BIN", side="RIGHT", max_lateral_offset_m=0.5)
        self.assertEqual(self.check(tight, tools), "OFFSET_EXCEEDS_LIMIT@SAFETY_REJECTED")
        self.assertEqual(
            self.check(command("AVOID_TEMPORARY_OBSTRUCTION", obstruction_type="TRASH_BIN", side="LEFT", max_lateral_offset_m=1.0), situation(BLOCKER)),
            "OBSTRUCTION_TYPE_MISMATCH@NOT_AVAILABLE",
        )

    def test_cross_low_risk_object_accepts_only_a_confident_soft_low_profile(self) -> None:
        safe = load("hannover_ladung_karton").actors[0]
        request = command("CROSS_LOW_RISK_OBJECT")
        self.assertIsNone(self.check(request, situation(safe)))
        assert safe.obstacle_profile is not None
        variants = (
            (replace(safe, obstacle_profile=None), "OBSTACLE_PROFILE_UNKNOWN@SAFETY_REJECTED"),
            (
                replace(safe, obstacle_profile=replace(safe.obstacle_profile, assessment_confidence=0.8)),
                "OBJECT_CLASSIFICATION_UNCERTAIN@SAFETY_REJECTED",
            ),
            (
                replace(safe, obstacle_profile=replace(safe.obstacle_profile, height_m=0.2)),
                "OBJECT_TOO_HIGH@SAFETY_REJECTED",
            ),
            (
                replace(
                    safe,
                    obstacle_profile=replace(
                        safe.obstacle_profile, material="WOOD", deformability="LOW"
                    ),
                ),
                "OBJECT_NOT_DEFORMABLE@SAFETY_REJECTED",
            ),
            (
                replace(safe, obstacle_profile=replace(safe.obstacle_profile, sharp_edges=True)),
                "SHARP_EDGES_DETECTED@SAFETY_REJECTED",
            ),
            (
                replace(safe, obstacle_profile=replace(safe.obstacle_profile, liquid=True)),
                "LIQUID_HAZARD_DETECTED@SAFETY_REJECTED",
            ),
        )
        for actor, expected in variants:
            with self.subTest(expected=expected):
                self.assertEqual(self.check(request, situation(actor)), expected)
        low_visibility = replace(load("hannover_ladung_karton"), visibility_m=10.0)
        self.assertEqual(
            self.check(request, situation(safe, scenario=low_visibility)),
            "VISIBILITY_INSUFFICIENT@SAFETY_REJECTED",
        )

    def test_pull_over_only_to_the_right_and_only_with_a_shoulder(self) -> None:
        tools = situation(BLOCKER)
        self.assertIsNone(self.check(command("PULL_OVER"), tools))
        self.assertEqual(
            self.check(command("PULL_OVER", side_preference="LEFT"), tools),
            "PULL_OVER_LEFT_NOT_ALLOWED@RULE_REJECTED",
        )
        narrow = situation(BLOCKER, facts=WorldFacts(shoulder_m=1.0))
        self.assertEqual(self.check(command("PULL_OVER"), narrow), "NO_SAFE_HALT_POSITION@NOT_AVAILABLE")

    def test_reverse_needs_a_clear_rear(self) -> None:
        follower = ActorSpec("follower", "car", 77.0, -1.75, 0.0, 1, 4.5, 1.8)
        self.assertEqual(
            self.check(command("REVERSE_SHORT", max_distance_m=3.0), situation(BLOCKER, follower)),
            "REAR_NOT_CLEAR@SAFETY_REJECTED",
        )
        self.assertIsNone(self.check(command("REVERSE_SHORT", max_distance_m=3.0), situation(BLOCKER)))

    def test_mission_commands_check_their_preconditions(self) -> None:
        empty = situation(BLOCKER, facts=WorldFacts(passengers_on_board=0, hub_available=False))
        self.assertEqual(self.check(command("DROP_PASSENGER"), empty), "NO_PASSENGER_ON_BOARD@NOT_AVAILABLE")
        self.assertEqual(self.check(command("RETURN_HOME"), empty), "HUB_UNREACHABLE@NOT_AVAILABLE")

    def test_maneuvers_need_the_seven_evidence_tools(self) -> None:
        session = AgentSession(situation(BLOCKER), time_s=0.0, stopped_for_s=0.0)
        with self.assertRaisesRegex(CommandError, "Werkzeugevidenz"):
            session.submit_decision(command("NUDGE_AROUND_OBSTACLE", side="LEFT", max_longitudinal_distance_m=30))
        # Nicht-Manoever brauchen keine Evidenz.
        self.assertEqual(session.submit_decision(command("WAIT", duration_s=5)).command, "WAIT")


class ExecutionTest(unittest.TestCase):
    def test_wait_ends_early_when_the_pedestrian_group_has_crossed(self) -> None:
        result = run_scenario(SCENARIOS / "hannover_fussgaengergruppe.json", agent=heuristic_agent, agent_name="baseline")
        self.assertEqual(result.command, "WAIT")
        self.assertEqual(result.outcome, "resolved")
        self.assertTrue(result.reached_goal)
        self.assertFalse(result.collision)
        wait = result.commands[0]
        self.assertEqual(wait["outcome"], "PATH_CLEARED")
        self.assertLess(wait["elapsed_s"], 10.0)
        self.assertEqual(result.costs["remote_assistance_calls"], 0)

    def test_crossing_actor_moves_sideways_and_stays_on_its_lane_position(self) -> None:
        engine = SimulationEngine(load("hannover_fussgaengergruppe"))
        start_d = engine._actor_states()[0].d_m
        while engine.time_s < 30.0:
            engine.step()
        end = engine._actor_states()[0]
        self.assertAlmostEqual(start_d, -1.75, places=1)
        self.assertAlmostEqual(end.d_m, 6.0, places=1)
        self.assertAlmostEqual(end.s_m, 92.0, delta=0.5)

    def test_replan_route_reroutes_and_charges_the_detour(self) -> None:
        result = run_scenario(SCENARIOS / "hannover_baustelle_umleitung.json", agent=heuristic_agent, agent_name="baseline")
        self.assertEqual(result.outcome, "rerouted")
        self.assertEqual(result.costs["items_eur"]["detour"], 90.0)  # 180 s * 0,50 EUR/s
        self.assertFalse(result.reached_goal)

    def test_replan_route_fails_without_blocked_route_or_alternative(self) -> None:
        free = load("hannover_frei")
        result = run(free, command("REPLAN_ROUTE"))
        self.assertEqual((result.commands[0]["status"], result.commands[0]["outcome"]), ("FAILED", "ROUTE_NOT_BLOCKED"))
        dead_end = replace(free, route=RouteSpec(blocked=True, alternative_available=False))
        result = run(dead_end, command("REPLAN_ROUTE"))
        self.assertEqual(result.commands[0]["outcome"], "NO_ALTERNATIVE_ROUTE")
        same = replace(free, route=RouteSpec(blocked=True))
        result = run(same, command("REPLAN_ROUTE", avoid_current_segment=False))
        self.assertEqual(result.commands[0]["outcome"], "NO_CHANGE_SAME_ROUTE")

    def test_reverse_then_replan(self) -> None:
        result = run_scenario(SCENARIOS / "hannover_sackgasse.json", agent=heuristic_agent, agent_name="baseline")
        self.assertEqual([c["command"] for c in result.commands], ["REVERSE_SHORT", "REPLAN_ROUTE"])
        self.assertEqual(result.outcome, "rerouted")
        self.assertFalse(result.collision)
        premature = run(load("hannover_sackgasse"), command("REPLAN_ROUTE"))
        self.assertEqual(premature.commands[0]["outcome"], "NO_MANEUVER_SPACE")

    def test_reverse_moves_the_vehicle_backwards_by_the_requested_distance(self) -> None:
        scenario = load("hannover_frei")
        result = run(scenario, command("REVERSE_SHORT", max_distance_m=2.0))
        reverse = result.commands[0]
        self.assertEqual(reverse["outcome"], "DISTANCE_REACHED")
        started = next(e for e in result.events if e.event == "command_started")
        before = next(p for p in result.trajectory if p["time_s"] >= started.time_s)
        after = next(
            p for p in result.trajectory
            if p["time_s"] >= started.time_s + reverse["elapsed_s"]
        )
        self.assertGreater(before["s_m"] - after["s_m"], 1.9)
        self.assertLess(before["s_m"] - after["s_m"], 3.5)

    def test_dynamics_support_reverse_gear_only_on_request(self) -> None:
        vehicle = Vehicle(0.0, 0.0, 0.0, 0.0)
        for _ in range(20):
            step_vehicle(vehicle, Control(throttle=1.0, reverse=True), 0.1)
        self.assertLess(vehicle.speed_mps, 0.0)
        self.assertLess(vehicle.x_m, 0.0)
        forward = Vehicle(0.0, 0.0, 0.0, 0.0)
        step_vehicle(forward, Control(brake=1.0), 0.1)
        self.assertEqual(forward.speed_mps, 0.0)

    def test_pull_over_then_drop_is_safe_and_cheap(self) -> None:
        result = run(load("hannover_frei"), command("PULL_OVER"), command("DROP_PASSENGER"))
        self.assertEqual([c["outcome"] for c in result.commands], ["PULLED_OVER", "PASSENGERS_DROPPED_SAFE"])
        self.assertEqual(result.outcome, "passenger_dropped")
        self.assertNotIn("personal_injury", result.costs["items_eur"])
        self.assertLess(result.costs["total_eur"], 100.0)
        self.assertFalse(result.collision)

    def test_dropping_passengers_in_the_lane_is_the_most_expensive_outcome(self) -> None:
        unsafe = run(load("hannover_frei"), command("DROP_PASSENGER"))
        self.assertEqual(unsafe.commands[0]["outcome"], "PASSENGERS_ENDANGERED")
        self.assertEqual(unsafe.costs["passengers_injured"], 1)
        self.assertGreaterEqual(unsafe.costs["items_eur"]["personal_injury"], 100_000.0)
        self.assertEqual(unsafe.costs["customer_satisfaction"], 0.0)
        for name in ("SAFE_STOP", "ABORT_MISSION", "RETURN_HOME"):
            other = run(load("hannover_frei"), command(name, reason_code="UNRECOVERABLE_BLOCKAGE") if name != "RETURN_HOME" else command(name))
            self.assertGreater(unsafe.costs["total_eur"], other.costs["total_eur"] * 10)

    def test_nudge_passes_on_the_shoulder_side(self) -> None:
        result = run(load("hannover_frei"), command("NUDGE_AROUND_OBSTACLE", side="RIGHT", max_longitudinal_distance_m=35))
        self.assertEqual(result.outcome, "liberated")
        self.assertTrue(result.reached_goal)
        self.assertFalse(result.collision)
        self.assertLess(min(p["d_m"] for p in result.trajectory), -3.5)  # ueber die Fahrbahngrenze

    def test_change_lane_moves_permanently_to_the_adjacent_lane(self) -> None:
        result = run_scenario(SCENARIOS / "hannover_doppelparker.json", agent=heuristic_agent, agent_name="baseline")
        self.assertEqual(result.command, "CHANGE_LANE")
        self.assertEqual(result.outcome, "liberated")
        self.assertTrue(result.reached_goal)
        self.assertFalse(result.collision)
        self.assertAlmostEqual(result.trajectory[-1]["d_m"], -5.25, delta=0.4)

    def test_avoid_temporary_obstruction_stays_left_of_the_center_line(self) -> None:
        result = run_scenario(SCENARIOS / "hannover_muelltonne.json", agent=heuristic_agent, agent_name="baseline")
        self.assertEqual(result.command, "AVOID_TEMPORARY_OBSTRUCTION")
        self.assertEqual(result.outcome, "liberated")
        self.assertFalse(result.collision)
        left_edge = max(p["d_m"] for p in result.trajectory) + 1.99 / 2.0
        self.assertLess(left_edge, 0.0)

    def test_cross_low_risk_object_uses_the_certified_straight_skill(self) -> None:
        result = run_scenario(
            SCENARIOS / "hannover_ladung_karton.json",
            agent=heuristic_agent,
            agent_name="baseline",
        )
        self.assertEqual(result.command, "CROSS_LOW_RISK_OBJECT")
        self.assertEqual(result.outcome, "liberated")
        self.assertTrue(result.reached_goal)
        self.assertFalse(result.collision)
        self.assertTrue(any(event.event == "low_risk_object_crossed" for event in result.events))

    def test_dynamic_hazard_aborts_a_lane_change(self) -> None:
        scenario = load("hannover_doppelparker")
        # Ein schnelles Fahrzeug naht von hinten in der Zielspur, sobald das Manoever laeuft.
        fast = ActorSpec("fast", "car", 40.0, -5.25, 0.0, 1, 4.5, 1.8, motion_start_time_s=0.0, target_speed_mps=6.0)
        scenario = replace(scenario, actors=scenario.actors + (fast,))
        result = run(scenario, command("CHANGE_LANE", direction="RIGHT"))
        self.assertFalse(result.collision)

    def test_remote_assistance_costs_money_and_resolves_the_blockage(self) -> None:
        result = run_scenario(SCENARIOS / "hannover_leitstelle.json", agent=heuristic_agent, agent_name="baseline")
        self.assertEqual(result.outcome, "remote_resolved")
        self.assertEqual(result.costs["remote_assistance_calls"], 1)
        self.assertEqual(result.costs["items_eur"]["remote_assistance"], 25.0)
        self.assertTrue(result.reached_goal)
        self.assertEqual(result.commands[-1]["command"], "REQUEST_REMOTE_ASSISTANCE")

    def test_unavailable_remote_assistance_fails_and_the_agent_can_fall_back(self) -> None:
        scenario = replace(load("hannover_frei"), remote_assistance=AssistanceSpec(available=False))
        result = run(scenario, command("REQUEST_REMOTE_ASSISTANCE", reason_code="NO_SAFE_RECOVERY"), command("SAFE_STOP", reason_code="NO_SAFE_RECOVERY"))
        self.assertEqual(result.commands[0]["outcome"], "REMOTE_ASSISTANCE_UNAVAILABLE")
        self.assertEqual(result.outcome, "safe_stopped")
        self.assertEqual(result.costs["remote_assistance_calls"], 1)

    def test_safe_stop_is_cheaper_after_pulling_over(self) -> None:
        in_lane = run(load("hannover_frei"), command("SAFE_STOP", reason_code="SAFETY_CONCERN"))
        on_edge = run(load("hannover_frei"), command("PULL_OVER"), command("SAFE_STOP", reason_code="SAFETY_CONCERN"))
        self.assertEqual(in_lane.outcome, "safe_stopped")
        self.assertIn("blocking_traffic", in_lane.costs["items_eur"])
        self.assertNotIn("blocking_traffic", on_edge.costs["items_eur"])
        self.assertLess(on_edge.costs["total_eur"], in_lane.costs["total_eur"])

    def test_abort_mission_strands_passengers_but_not_an_empty_vehicle(self) -> None:
        loaded = run(load("hannover_frei"), command("ABORT_MISSION", reason_code="UNRECOVERABLE_BLOCKAGE"))
        empty_scenario = replace(load("hannover_frei"), mission=MissionSpec("EMPTY_REPOSITIONING", passengers=0))
        empty = run(empty_scenario, command("ABORT_MISSION", reason_code="UNRECOVERABLE_BLOCKAGE"))
        self.assertEqual(loaded.outcome, "mission_aborted")
        self.assertIn("stranded_passengers", loaded.costs["items_eur"])
        self.assertNotIn("stranded_passengers", empty.costs["items_eur"])
        self.assertIsNone(empty.costs["customer_satisfaction"])

    def test_return_home_upsets_passengers(self) -> None:
        loaded = run(load("hannover_frei"), command("RETURN_HOME"))
        empty = run(replace(load("hannover_frei"), mission=MissionSpec("EMPTY_REPOSITIONING", passengers=0)), command("RETURN_HOME"))
        self.assertEqual(loaded.outcome, "returned_home")
        self.assertEqual(loaded.costs["customer_satisfaction"], 0.1)
        self.assertGreater(loaded.costs["total_eur"], empty.costs["total_eur"])

    def test_additional_information_reaches_the_next_session(self) -> None:
        sessions: list[AgentSession] = []
        run(
            load("hannover_frei"),
            command("REQUEST_ADDITIONAL_INFORMATION", topic="MOTION_REASSESSMENT", duration_s=3),
            command("WAIT", duration_s=5),
            sessions=sessions,
        )
        self.assertEqual(sessions[0].context["additional_information"], [])
        gathered = sessions[1].context["additional_information"]
        self.assertEqual(gathered[0]["topic"], "MOTION_REASSESSMENT")
        self.assertTrue(gathered[0]["result"]["blocker_still_present"])

    def test_escalation_delegates_to_the_rule_engine(self) -> None:
        result = run(load("hannover_frei"), command("ESCALATE_TO_RULE_ENGINE"))
        self.assertEqual([c["command"] for c in result.commands[:2]], ["ESCALATE_TO_RULE_ENGINE", "NUDGE_AROUND_OBSTACLE"])
        self.assertEqual(result.commands[1]["source"], "rule_engine")
        self.assertEqual(result.command, "NUDGE_AROUND_OBSTACLE")  # erster inhaltlicher Befehl
        self.assertEqual(result.outcome, "liberated")
        self.assertEqual(result.costs["items_eur"]["rule_engine"], 1.0)

    def test_rule_engine_never_calls_remote_assistance(self) -> None:
        scenario = load("hannover_leitstelle")
        result = run(scenario, *[command("ESCALATE_TO_RULE_ENGINE")] * 8)
        self.assertEqual(result.costs["remote_assistance_calls"], 0)

    def test_only_one_command_is_active_and_the_budget_ends_the_loop(self) -> None:
        scenario = replace(load("hannover_durchgezogen"), max_commands=2, duration_s=80.0)
        engine = SimulationEngine(scenario, agent=scripted(), agent_name="script")
        active_counts = set()
        while not engine.done:
            engine.step()
            active_counts.add(engine.active is not None)
        self.assertEqual(len(engine.commands), 2)
        self.assertTrue(any(e.event == "command_budget_exhausted" for e in engine.events))

    def test_repeated_failures_are_visible_to_the_agent(self) -> None:
        histories: list[dict[str, object]] = []
        steps = [command("REPLAN_ROUTE"), command("WAIT", duration_s=5)]

        def watching(session: AgentSession):
            histories.append(session.call_tool("get_recovery_history"))
            return steps.pop(0) if steps else command("WAIT", duration_s=5)

        run_scenario(load("hannover_frei"), agent=watching, agent_name="watching")
        self.assertEqual(histories[0]["attempts"], [])
        self.assertEqual(histories[1]["attempts"][0]["outcome"], "ROUTE_NOT_BLOCKED")
        self.assertIn("REPLAN_ROUTE_ALREADY_FAILED", histories[1]["repetition_warnings"])

    def test_rejected_attempts_are_counted_as_costs(self) -> None:
        def stubborn(session: AgentSession):
            for tool in EVIDENCE_TOOLS:
                session.call_tool(tool)
            for _ in range(2):
                try:
                    session.submit_decision(command("CHANGE_LANE", direction="LEFT"))
                except CommandError:
                    pass
            return session.submit_decision(command("WAIT", duration_s=5))

        result = run_scenario(load("hannover_frei"), agent=stubborn, agent_name="stubborn")
        self.assertGreaterEqual(result.costs["rejected_commands"], 2)
        self.assertIn("rejected_commands", result.costs["items_eur"])

    def test_cost_ranking_matches_the_evaluation_metric(self) -> None:
        from autonomy_recovery_sim.costs import DEFAULT_COST_MODEL as model

        self.assertGreater(model.personal_injury_eur, model.material_damage_eur)
        self.assertGreater(model.material_damage_eur, model.remote_assistance_call_eur * 10)
        self.assertGreater(model.remote_assistance_call_eur, model.standstill_eur_per_s)

    def test_collision_is_charged_as_damage_or_injury(self) -> None:
        engine = SimulationEngine(load("hannover_fussgaengergruppe"))
        group = engine.traffic[0].vehicle
        engine.ego.x_m, engine.ego.y_m = group.x_m, group.y_m  # Ego steht auf der Gruppe
        engine.step()
        self.assertTrue(engine.collision)
        self.assertTrue(engine.collision_with_vulnerable)
        self.assertGreaterEqual(engine.costs()["items_eur"]["personal_injury"], 100_000.0)

        car_engine = SimulationEngine(load("hannover_frei"))
        blocker = car_engine.traffic[0].vehicle
        car_engine.ego.x_m, car_engine.ego.y_m = blocker.x_m, blocker.y_m
        car_engine.step()
        self.assertTrue(car_engine.collision)
        self.assertEqual(car_engine.costs()["items_eur"]["material_damage"], 5_000.0)

    def test_freie_fahrt_triggers_no_recovery(self) -> None:
        result = run_scenario(SCENARIOS / "hannover_freie_fahrt.json", agent=heuristic_agent, agent_name="baseline")
        self.assertEqual(result.command, "NONE")
        self.assertEqual(result.outcome, "not_triggered")
        self.assertTrue(result.command_correct)
        self.assertEqual(result.costs["total_eur"], 0.0)

    def test_result_and_snapshot_are_json_serializable(self) -> None:
        engine = SimulationEngine(load("hannover_frei"), agent=heuristic_agent, agent_name="baseline")
        for _ in range(400):
            engine.step()
        json.dumps(engine.snapshot())
        result = run_scenario(SCENARIOS / "hannover_frei.json", agent=heuristic_agent, agent_name="baseline")
        json.dumps(result.to_dict())


if __name__ == "__main__":
    unittest.main()
