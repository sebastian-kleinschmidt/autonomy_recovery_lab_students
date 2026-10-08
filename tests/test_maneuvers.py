"""Phasenmanoever mit Checkpoints: CREEP_FORWARD, PEEK_OUT, OVERTAKE, ABORT_TO_LANE, WAIT_FOR_GAP."""

from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from autonomy_recovery_sim.agent_session import AgentContractError, AgentSession
from autonomy_recovery_sim.commands import MANEUVER_EVIDENCE_TOOLS
from autonomy_recovery_sim.scenario import DifficultySpec, load_scenario
from autonomy_recovery_sim.simulation import run_scenario

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "autonomy_recovery_sim/scenarios"
WAIT = {"command": "WAIT", "parameters": {"duration_s": 10.0}, "reason": "warten"}
RESUME = {"command": "RESUME", "parameters": {}, "reason": "weiter"}
ABORT = {"command": "ABORT_TO_LANE", "parameters": {}, "reason": "zurueck"}
OVERTAKE = {
    "command": "OVERTAKE",
    "parameters": {"side": "LEFT", "max_longitudinal_distance_m": 40.0},
    "reason": "ueberholen",
}
PEEK = {"command": "PEEK_OUT", "parameters": {"side": "LEFT", "lateral_offset_m": 1.2}, "reason": "schauen"}


def load(name: str, guardrails: str = "strict"):
    scenario = load_scenario(SCENARIOS / f"hannover_{name}.json")
    # Vorsichtige Ablaeufe brauchen mehr Zeit als die Referenzloesung.
    return replace(scenario, difficulty=DifficultySpec(guardrails=guardrails), duration_s=90.0)


def phase(session: AgentSession) -> str:
    trigger = session.context.get("trigger", {})
    return str(trigger.get("phase") or trigger.get("type") or "DEADLOCK")  # type: ignore[union-attr]


def scripted(plan: dict[str, object], log: list[tuple[str, float]] | None = None):
    """Agent mit voller Evidenz, der je Ausloeser/Phase einen festen Befehl waehlt."""

    deadlocks = 0

    def agent(session: AgentSession):
        nonlocal deadlocks
        key = phase(session)
        if log is not None:
            log.append((key, float(session.context["time_s"])))  # type: ignore[arg-type]
        for tool in sorted(MANEUVER_EVIDENCE_TOOLS):
            session.call_tool(tool)
        if key == "DEADLOCK":
            deadlocks += 1
            # Nur die erste Blockade bekommt den geplanten Befehl, spaetere "LATER" (sonst WAIT).
            key = "DEADLOCK" if deadlocks == 1 else "LATER"
        choice = plan.get(key, WAIT)
        return choice(session) if callable(choice) else choice

    return agent


def commands(result) -> list[tuple[str, str]]:
    return [(item["command"], item["outcome"]) for item in result.commands]


class OvertakeTest(unittest.TestCase):
    def test_overtake_stops_beside_the_blocker_and_continues_on_resume(self) -> None:
        log: list[tuple[str, float]] = []
        result = run_scenario(load("frei"), agent=scripted({"DEADLOCK": OVERTAKE, "PULLED_OUT": RESUME}, log), agent_name="o")
        self.assertEqual([key for key, _ in log], ["DEADLOCK", "PULLED_OUT"])
        self.assertIn(("OVERTAKE", "OBSTACLE_PASSED"), commands(result))
        self.assertTrue(result.liberated)
        self.assertFalse(result.collision)

    def test_the_checkpoint_reveals_what_was_hidden_and_abort_returns_to_the_lane(self) -> None:
        seen = {}

        def at_checkpoint(session: AgentSession):
            seen["before"] = session.call_tool("get_visibility")
            return ABORT

        result = run_scenario(
            load("verdeckung_gegenverkehr"),
            agent=scripted({"DEADLOCK": OVERTAKE, "PULLED_OUT": at_checkpoint}),
            agent_name="a",
        )
        self.assertFalse(seen["before"]["sufficient"])
        self.assertIn(("OVERTAKE", "SUPERSEDED"), commands(result))
        self.assertIn(("ABORT_TO_LANE", "BACK_IN_LANE"), commands(result))
        self.assertFalse(result.collision)

    def test_overtake_after_peeking_makes_room_first(self) -> None:
        result = run_scenario(
            load("frei"), agent=scripted({"DEADLOCK": PEEK, "PEEKING": OVERTAKE, "PULLED_OUT": RESUME}), agent_name="p"
        )
        self.assertEqual(
            commands(result)[:3],
            [("PEEK_OUT", "SUPERSEDED"), ("RESUME", "MANEUVER_CONTINUED"), ("OVERTAKE", "OBSTACLE_PASSED")],
        )

    def test_the_clock_runs_while_the_agent_decides(self) -> None:
        result = run_scenario(load("frei"), agent=scripted({"DEADLOCK": OVERTAKE, "PULLED_OUT": RESUME}), agent_name="o")
        latency = [event for event in result.events if event.event == "decision_latency"]
        # Die sieben Belege am Checkpoint kosten je 0,2 s Bedenkzeit.
        self.assertAlmostEqual(latency[0].details["seconds"], 0.2 * len(MANEUVER_EVIDENCE_TOOLS))
        resumed = next(event for event in result.events if event.event == "command_started" and event.details["command"] == "RESUME")
        self.assertGreater(resumed.time_s, latency[0].time_s)


class PeekTest(unittest.TestCase):
    def test_peek_keeps_its_distance_and_stops_at_a_checkpoint(self) -> None:
        log: list[tuple[str, float]] = []
        result = run_scenario(load("frei"), agent=scripted({"DEADLOCK": PEEK, "PEEKING": ABORT}, log), agent_name="p")
        self.assertEqual(log[1][0], "PEEKING")
        self.assertIn(("ABORT_TO_LANE", "BACK_IN_LANE"), commands(result))
        self.assertFalse(result.collision)

    def test_peek_respects_a_solid_center_line(self) -> None:
        result = run_scenario(load("durchgezogen"), agent=scripted({"DEADLOCK": PEEK}), agent_name="p")
        self.assertIn("CENTER_LINE_SOLID", result.agent_error or "")


class GapAndCreepTest(unittest.TestCase):
    def test_wait_for_gap_lets_oncoming_traffic_pass_first(self) -> None:
        gap = {
            "command": "WAIT_FOR_GAP",
            "parameters": {
                "min_gap_s": 8.0,
                "timeout_s": 40.0,
                "then": "NUDGE_AROUND_OBSTACLE",
                "side": "LEFT",
                "max_longitudinal_distance_m": 40.0,
            },
            "reason": "Luecke abwarten",
        }
        result = run_scenario(load("gegenverkehr"), agent=scripted({"DEADLOCK": gap}), agent_name="g")
        self.assertEqual(
            commands(result)[:2], [("WAIT_FOR_GAP", "GAP_FOUND"), ("NUDGE_AROUND_OBSTACLE", "OBSTACLE_PASSED")]
        )
        self.assertEqual(result.commands[1]["source"], "wait_for_gap")
        self.assertFalse(result.collision)

    def test_wait_for_gap_checks_the_follow_up_up_front(self) -> None:
        gap = {
            "command": "WAIT_FOR_GAP",
            "parameters": {"min_gap_s": 8.0, "timeout_s": 20.0, "then": "OVERTAKE", "side": "LEFT", "max_longitudinal_distance_m": 40.0},
            "reason": "Luecke",
        }
        result = run_scenario(load("durchgezogen"), agent=scripted({"DEADLOCK": gap}), agent_name="g")
        self.assertIn("CENTER_LINE_SOLID", result.agent_error or "")

    def test_creep_stops_short_of_the_obstacle(self) -> None:
        creep = {"command": "CREEP_FORWARD", "parameters": {"max_distance_m": 5.0}, "reason": "vortasten"}
        result = run_scenario(load("frei"), agent=scripted({"DEADLOCK": creep, "LATER": creep}), agent_name="c")
        self.assertIn(("CREEP_FORWARD", "OBSTACLE_REACHED"), commands(result))
        self.assertFalse(result.collision)

    def test_abort_is_refused_when_already_in_lane(self) -> None:
        sessions: list[AgentSession] = []

        def agent(session: AgentSession):
            sessions.append(session)
            return WAIT

        run_scenario(load("frei"), agent=agent, agent_name="w")
        fresh = AgentSession(sessions[0]._tools, time_s=0.0, stopped_for_s=5.0)
        with self.assertRaises(AgentContractError) as caught:
            fresh.submit_decision(ABORT)
        self.assertIn("ALREADY_IN_LANE", str(caught.exception))



class TurnAroundTest(unittest.TestCase):
    def turn(self, method: str) -> dict[str, object]:
        return {"command": "TURN_AROUND", "parameters": {"method": method}, "reason": "wenden"}

    def test_three_point_turn_ends_rerouted_facing_the_other_way(self) -> None:
        result = run_scenario(load("umgekippter_lkw"), agent=scripted({"DEADLOCK": self.turn("THREE_POINT")}), agent_name="t")
        finished = next(e for e in result.events if e.event == "command_finished" and e.details["command"] == "TURN_AROUND")
        self.assertEqual(finished.details["outcome"], "TURNED_AROUND")
        self.assertGreaterEqual(finished.details["moves"], 2)
        self.assertEqual(result.outcome, "rerouted")
        self.assertFalse(result.collision)
        self.assertGreater(result.trajectory[-1]["d_m"], 0.0, "endet in der Gegenspur")

    def test_u_turn_needs_a_wide_road(self) -> None:
        result = run_scenario(load("umgekippter_lkw"), agent=scripted({"DEADLOCK": self.turn("U_TURN")}), agent_name="t")
        self.assertIn("ROAD_TOO_NARROW_FOR_U_TURN", result.agent_error or "")

    def test_oncoming_traffic_blocks_the_turn_in_strict_and_crashes_it_in_off(self) -> None:
        strict = run_scenario(load("gegenverkehr"), agent=scripted({"DEADLOCK": self.turn("THREE_POINT")}), agent_name="t")
        self.assertIn("ONCOMING_TOO_CLOSE", strict.agent_error or "")
        advisory = run_scenario(
            load("gegenverkehr", "advisory"), agent=scripted({"DEADLOCK": self.turn("THREE_POINT")}), agent_name="t"
        )
        self.assertEqual(advisory.outcome, "rerouted")
        self.assertFalse(advisory.collision, "der Ausfuehrer wartet mitten in der Wende")
        blind = run_scenario(
            load("gegenverkehr", "off"),
            agent=lambda session: self.turn("THREE_POINT") if session.context["commands_used"] == 0 else WAIT,
            agent_name="t",
        )
        self.assertTrue(blind.collision)


if __name__ == "__main__":
    unittest.main()
