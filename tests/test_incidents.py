"""Unfaelle und ihre Abwicklung in den Pruefmodi advisory und off (incidents.py)."""

from __future__ import annotations

import math
import unittest
from dataclasses import replace
from pathlib import Path

from autonomy_recovery_sim.agent_session import AgentContractError, AgentSession
from autonomy_recovery_sim.engine import SimulationEngine
from autonomy_recovery_sim.incidents import direction_of, severity_of
from autonomy_recovery_sim.scenario import DifficultySpec, load_scenario
from autonomy_recovery_sim.simulation import run_scenario

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "autonomy_recovery_sim/scenarios"
NUDGE = {
    "command": "NUDGE_AROUND_OBSTACLE",
    "parameters": {"side": "LEFT", "max_longitudinal_distance_m": 30.0},
    "reason": "blind los",
}
CROSS = {"command": "CROSS_LOW_RISK_OBJECT", "parameters": {}, "reason": "drueber"}
RESUME = {"command": "RESUME", "parameters": {}, "reason": "weiter"}
SECURE = {"command": "SECURE_SCENE", "parameters": {}, "reason": "sichern"}
WAIT = {"command": "WAIT", "parameters": {"duration_s": 5.0}, "reason": "warten"}


def load(name: str, guardrails: str = "off"):
    scenario = load_scenario(SCENARIOS / f"hannover_{name}.json")
    return replace(scenario, difficulty=DifficultySpec(guardrails=guardrails))


def report(injured: bool) -> dict[str, object]:
    return {
        "command": "REPORT_INCIDENT",
        "parameters": {"injured_persons_suspected": injured},
        "reason": "Unfall melden",
    }


def trigger(session: AgentSession) -> dict[str, object]:
    return session.context.get("trigger", {})  # type: ignore[return-value]


def careful_after_crash(*, injured: bool, secure: bool = True):
    """Faehrt blind los und wickelt den Unfall danach ab."""

    def agent(session: AgentSession):
        kind = trigger(session).get("type")
        if kind == "MANEUVER_FINISHED":
            if session.call_tool("get_vehicle_status")["impact_events"]:
                return SECURE
            return RESUME
        if session.context["commands_used"] == 0:
            return NUDGE
        if session.call_tool("get_vehicle_status")["incident_reported"]:
            return WAIT
        if secure and not session.call_tool("get_vehicle_status")["scene_secured"]:
            return SECURE
        return report(injured)

    return agent


class SeverityTest(unittest.TestCase):
    def test_severity_and_direction(self) -> None:
        self.assertEqual(severity_of(1.0, False), "LIGHT")
        self.assertEqual(severity_of(3.0, False), "MODERATE")
        self.assertEqual(severity_of(6.0, False), "SEVERE")
        self.assertEqual(severity_of(0.5, True), "SEVERE")
        self.assertEqual(direction_of((0, 0), 0.0, (5, 0)), "FRONT")
        self.assertEqual(direction_of((0, 0), 0.0, (0, 5)), "LEFT")
        self.assertEqual(direction_of((0, 0), math.pi, (5, 0)), "REAR")


class StrictUnchangedTest(unittest.TestCase):
    def test_strict_has_no_incident_commands_or_status_tool(self) -> None:
        sessions: list[AgentSession] = []

        def agent(session: AgentSession):
            sessions.append(session)
            return report(False)

        result = run_scenario(load("doppelparker", "strict"), agent=agent, agent_name="s")
        self.assertIn("NOT_AVAILABLE", result.agent_error or "")
        self.assertNotIn("get_vehicle_status", sessions[0].tool_catalog)
        self.assertNotIn("trigger", sessions[0].context)
        self.assertEqual(result.incident, {})


class CrashTest(unittest.TestCase):
    def test_episode_continues_and_the_agent_is_called_at_once(self) -> None:
        sessions: list[AgentSession] = []

        def agent(session: AgentSession):
            sessions.append(session)
            return NUDGE if not sessions[:-1] else report(True)

        result = run_scenario(load("abbruch_gegenverkehr"), agent=agent, agent_name="a")
        self.assertTrue(result.collision)
        self.assertEqual(trigger(sessions[1])["type"], "IMPACT_DETECTED")
        self.assertEqual(result.outcome, "incident_reported")
        impact = result.incident["impacts"][0]  # type: ignore[index]
        self.assertEqual(impact["preceding_decision"]["command"], "NUDGE_AROUND_OBSTACLE")
        self.assertIn("check_oncoming_traffic", impact["preceding_decision"]["required_evidence_missing"])

    def test_leaving_or_pulling_over_after_a_detected_crash_is_rejected(self) -> None:
        outcomes = []

        def agent(session: AgentSession):
            if session.context["commands_used"] == 0:
                return NUDGE
            for attempt in (RESUME, {"command": "PULL_OVER", "parameters": {}, "reason": "rand"}):
                try:
                    session.submit_decision(attempt)
                except AgentContractError as exc:
                    outcomes.append(str(exc).split(":")[1].strip())
            return report(True)

        run_scenario(load("abbruch_gegenverkehr"), agent=agent, agent_name="a")
        self.assertEqual(outcomes[:2], ["LEAVING_ACCIDENT_SCENE", "MUST_STAY_AT_SCENE"])

    def test_handling_is_graded_and_never_makes_the_crash_cheaper(self) -> None:
        good = run_scenario(load("abbruch_gegenverkehr"), agent=careful_after_crash(injured=True), agent_name="g")
        no_call = run_scenario(load("abbruch_gegenverkehr"), agent=careful_after_crash(injured=False), agent_name="n")
        unsecured = run_scenario(
            load("abbruch_gegenverkehr"), agent=careful_after_crash(injured=True, secure=False), agent_name="u"
        )
        silent = run_scenario(
            load("abbruch_gegenverkehr"),
            agent=lambda session: NUDGE if session.context["commands_used"] == 0 else WAIT,
            agent_name="s",
        )
        self.assertEqual(good.costs["incident_handling"], "correct")
        self.assertEqual(no_call.costs["incident_handling"], "deficient")
        self.assertIn("missing_emergency_call", no_call.costs["items_eur"])
        self.assertIn("unsecured_scene", unsecured.costs["items_eur"])
        self.assertEqual(silent.costs["incident_handling"], "not_reported")
        for result in (good, no_call, unsecured, silent):
            self.assertEqual(result.costs["items_eur"]["material_damage"], 5000.0)

    def test_a_false_report_costs_a_little(self) -> None:
        result = run_scenario(load("doppelparker"), agent=lambda session: report(False), agent_name="f")
        self.assertEqual(result.outcome, "incident_reported")
        self.assertIn("false_incident_report", result.costs["items_eur"])


class LightContactTest(unittest.TestCase):
    def engine_with_light_contact(self) -> SimulationEngine:
        engine = SimulationEngine(load("frei"))
        engine.ego.speed_mps = 1.0
        engine._record_impact(engine.traffic[0])
        return engine

    def test_light_contact_triggers_nothing_but_shows_in_the_status(self) -> None:
        engine = self.engine_with_light_contact()
        self.assertIsNone(engine._pending_trigger)
        self.assertFalse(engine.traffic[0].halted)
        self.assertFalse(engine._facts().incident_detected)
        status = engine._situation_tools().vehicle_status()
        self.assertEqual(status["impact_events"][0]["severity"], "LIGHT")

    def test_driving_on_after_a_light_contact_is_hit_and_run(self) -> None:
        engine = self.engine_with_light_contact()
        x, y, _ = engine.scenario.road.to_xy(engine.ego_route_state[0] + 40.0, engine.scenario.ego_lane_d_m)
        engine.ego.x_m, engine.ego.y_m = x, y
        engine.incidents.check_left_scene((x, y))
        costs = engine.costs()
        self.assertEqual(costs["incident_handling"], "hit_and_run")
        self.assertEqual(costs["items_eur"]["hit_and_run"], 100_000.0)


class CheckpointTest(unittest.TestCase):
    def test_after_a_maneuver_the_agent_checks_in(self) -> None:
        triggers = []

        def agent(session: AgentSession):
            triggers.append(trigger(session))
            return RESUME if trigger(session).get("type") == "MANEUVER_FINISHED" else NUDGE

        result = run_scenario(load("frei", "advisory"), agent=agent, agent_name="c")
        self.assertEqual([t["type"] for t in triggers], ["DEADLOCK", "MANEUVER_FINISHED"])
        self.assertEqual(triggers[1]["outcome"], "OBSTACLE_PASSED")
        self.assertTrue(result.reached_goal)
        self.assertFalse(result.collision)

    def test_a_stalled_maneuver_hands_control_back(self) -> None:
        triggers = []

        def agent(session: AgentSession):
            triggers.append(trigger(session))
            return NUDGE if session.context["commands_used"] == 0 else WAIT

        run_scenario(load("fussgaenger_vor_lieferwagen"), agent=agent, agent_name="s")
        finished = [t for t in triggers if t.get("type") == "MANEUVER_FINISHED"]
        self.assertEqual(finished[0]["status"], "ABORTED")


class UnderbodyTest(unittest.TestCase):
    def test_crossing_a_rigid_object_damages_the_vehicle(self) -> None:
        def agent(session: AgentSession):
            return RESUME if trigger(session).get("type") == "MANEUVER_FINISHED" else CROSS

        result = run_scenario(load("ladung_holzbalken"), agent=agent, agent_name="u")
        self.assertIsNone(result.agent_error)
        self.assertTrue(result.safety_warnings)
        self.assertEqual(result.costs["items_eur"]["vehicle_damage"], 3000.0)
        self.assertFalse(result.collision)
        self.assertEqual(result.costs["incident_handling"], "none", "eigener Schaden, keine Meldepflicht")

    def test_strict_still_refuses_the_crossing(self) -> None:
        result = run_scenario(load("ladung_holzbalken", "strict"), agent=lambda s: CROSS, agent_name="u")
        self.assertIn("SAFETY_REJECTED", result.agent_error or "")


if __name__ == "__main__":
    unittest.main()
