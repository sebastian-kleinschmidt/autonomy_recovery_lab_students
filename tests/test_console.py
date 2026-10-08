"""Tests der Recovery Console: Ein Mensch uebernimmt die Agentensitzung ueber die Live-Oberflaeche."""

from __future__ import annotations

import json
import time
import unittest
from pathlib import Path

from autonomy_recovery_sim.engine import SimulationEngine
from autonomy_recovery_sim.live import LiveSimulation
from autonomy_recovery_sim.scenario import load_scenario
from autonomy_recovery_sim.simulation import run_scenario
from tests.test_commands import EVIDENCE_TOOLS, command

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return load_scenario(ROOT / f"autonomy_recovery_sim/scenarios/{name}.json")


def until_pending(engine: SimulationEngine) -> None:
    for _ in range(4000):
        if engine.pending_session is not None or engine.done:
            break
        engine.step()
    assert engine.pending_session is not None, "Konsole wurde nicht geoeffnet"


class ConsoleEngineTest(unittest.TestCase):
    def test_console_is_only_active_without_an_agent(self) -> None:
        self.assertTrue(SimulationEngine(load("hannover_frei"), console=True).console)
        self.assertFalse(SimulationEngine(load("hannover_frei")).console)
        self.assertFalse(SimulationEngine(load("hannover_frei"), agent=lambda s: None, console=True).console)
        # Batch und Einzellauf ohne Agent bleiben unveraendert: sie warten, statt zu blockieren.
        result = run_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        self.assertEqual(result.outcome, "waiting_for_agent")

    def test_time_stands_still_while_a_human_decides(self) -> None:
        engine = SimulationEngine(load("hannover_frei"), console=True)
        until_pending(engine)
        frozen, standstill = engine.time_s, engine.stationary_s
        for _ in range(50):
            engine.step()
        self.assertEqual(engine.time_s, frozen)
        self.assertEqual(engine.stationary_s, standstill)  # Denkzeit kostet nichts
        snapshot = engine.snapshot()["console"]
        self.assertTrue(snapshot["pending"])
        self.assertEqual(snapshot["max_tool_calls"], 14)

    def test_tools_are_recorded_and_evidence_can_be_gathered_at_once(self) -> None:
        engine = SimulationEngine(load("hannover_frei"), console=True)
        until_pending(engine)
        engine.console_tool("get_route_state")
        engine.console_gather_evidence()
        console = engine.snapshot()["console"]
        self.assertEqual(set(EVIDENCE_TOOLS) | {"get_route_state"}, set(console["called_tools"]))
        self.assertEqual(console["tool_calls"], 8)
        self.assertIn("detected", console["tool_results"]["get_blocker"])
        self.assertEqual(sum(e.event == "agent_tool_call" for e in engine.events), 8)
        engine.console_gather_evidence()  # idempotent: keine doppelten Aufrufe
        self.assertEqual(engine.snapshot()["console"]["tool_calls"], 8)

    def test_unknown_tool_and_budget_errors_are_reported_not_raised(self) -> None:
        engine = SimulationEngine(load("hannover_frei"), console=True)
        until_pending(engine)
        engine.console_tool("get_ground_truth")
        self.assertIn("Unbekanntes Werkzeug", engine.snapshot()["console"]["error"])
        for _ in range(20):
            engine.console_tool("get_blocker")
        self.assertIn("Werkzeugbudget", engine.snapshot()["console"]["error"])

    def test_rejection_keeps_the_session_open_and_shows_the_code(self) -> None:
        engine = SimulationEngine(load("hannover_durchgezogen"), console=True)
        until_pending(engine)
        engine.console_gather_evidence()
        engine.console_submit(command("NUDGE_AROUND_OBSTACLE", side="LEFT", max_longitudinal_distance_m=30))
        console = engine.snapshot()["console"]
        self.assertTrue(console["pending"])
        self.assertIn("CENTER_LINE_SOLID", console["error"])
        self.assertEqual(console["decision_attempts"], 1)
        self.assertEqual(engine.rejected_commands, 1)
        self.assertIsNone(engine.active)

    def test_missing_evidence_is_rejected(self) -> None:
        engine = SimulationEngine(load("hannover_frei"), console=True)
        until_pending(engine)
        engine.console_submit(command("NUDGE_AROUND_OBSTACLE", side="LEFT", max_longitudinal_distance_m=30))
        self.assertIn("Werkzeugevidenz", engine.snapshot()["console"]["error"])

    def test_valid_command_runs_time_resumes_and_the_run_is_marked_manual(self) -> None:
        engine = SimulationEngine(load("hannover_frei"), console=True)
        until_pending(engine)
        engine.console_gather_evidence()
        engine.console_submit(command("NUDGE_AROUND_OBSTACLE", side="LEFT", max_longitudinal_distance_m=35))
        self.assertIsNone(engine.pending_session)
        self.assertEqual(engine.agent_name, "manual")
        self.assertEqual(engine.agent_status, "manual")
        self.assertEqual(engine.active.request.command, "NUDGE_AROUND_OBSTACLE")
        self.assertEqual(engine.active.source, "manual")
        while not engine.done:
            engine.step()
        self.assertTrue(engine.liberated)
        self.assertFalse(engine.collision)
        self.assertEqual(engine.command_history[0]["source"], "manual")

    def test_a_new_deadlock_reopens_the_console(self) -> None:
        engine = SimulationEngine(load("hannover_durchgezogen"), console=True)
        until_pending(engine)
        engine.console_submit(command("WAIT", duration_s=5))
        self.assertIsNone(engine.pending_session)
        until_pending(engine)
        self.assertEqual(engine.snapshot()["console"]["session"], 2)
        self.assertEqual(engine.snapshot()["console"]["tool_calls"], 0)
        history = engine.console_snapshot()
        self.assertEqual(history["decision_attempts"], 0)

    def test_exhausted_decision_budget_falls_back_to_wait(self) -> None:
        engine = SimulationEngine(load("hannover_durchgezogen"), console=True)
        until_pending(engine)
        for _ in range(4):
            engine.console_submit({"command": "WAIT"})
        self.assertIsNone(engine.pending_session)
        self.assertEqual(engine.active.request.command, "WAIT")
        self.assertIn("Entscheidungsbudget", engine.agent_error)

    def test_manual_run_is_charged_like_an_agent_run(self) -> None:
        engine = SimulationEngine(load("hannover_frei"), console=True)
        until_pending(engine)
        engine.console_submit(command("REQUEST_REMOTE_ASSISTANCE", reason_code="NO_SAFE_RECOVERY"))
        while not engine.done:
            engine.step()
        costs = engine.costs()
        self.assertEqual(costs["remote_assistance_calls"], 1)
        self.assertEqual(costs["items_eur"]["remote_assistance"], 25.0)

    def test_catalog_lists_the_evidence_each_command_requires(self) -> None:
        engine = SimulationEngine(load("hannover_frei"), console=True)
        until_pending(engine)
        catalog = {e["command"]: e for e in engine.agent_observation["available_commands"]}
        self.assertEqual(catalog["WAIT"]["required_tools"], [])
        self.assertEqual(set(catalog["CHANGE_LANE"]["required_tools"]), set(EVIDENCE_TOOLS))


class ConsoleLiveTest(unittest.TestCase):
    def test_live_actions_round_trip_and_state_is_json(self) -> None:
        live = LiveSimulation(load("hannover_frei"))
        live.command({"action": "start"})
        for _ in range(4000):
            if live.engine.pending_session is not None:
                break
            live.engine.step()
        state = live.command({"action": "console_evidence"})
        json.dumps(state)
        self.assertEqual(len(state["console"]["called_tools"]), 7)
        state = live.command({"action": "console_tool", "name": "get_mission_context"})
        self.assertIn("get_mission_context", state["console"]["tool_results"])
        state = live.command(
            {"action": "console_submit", "payload": command("NUDGE_AROUND_OBSTACLE", side="LEFT", max_longitudinal_distance_m=35)}
        )
        self.assertFalse(state["console"]["pending"])
        self.assertEqual(state["agent"]["name"], "manual")
        self.assertEqual(state["active_command"], "NUDGE_AROUND_OBSTACLE")

    def test_console_actions_without_a_session_are_harmless(self) -> None:
        live = LiveSimulation(load("hannover_frei"))
        state = live.command({"action": "console_submit", "payload": command("WAIT", duration_s=5)})
        self.assertFalse(state["console"]["pending"])
        self.assertEqual(state["time_s"], 0.0)

    def test_malformed_console_payloads_are_rejected_as_bad_requests(self) -> None:
        live = LiveSimulation(load("hannover_frei"))
        with self.assertRaises(ValueError):
            live.command({"action": "console_submit", "payload": "WAIT"})
        with self.assertRaises(ValueError):
            live.command({"action": "console_tool", "name": "get_blocker", "arguments": []})

    def test_console_is_not_offered_when_an_agent_is_connected(self) -> None:
        from autonomy_recovery_sim.policy import heuristic_agent

        live = LiveSimulation(load("hannover_frei"), agent=heuristic_agent, agent_name="baseline")
        self.assertFalse(live.snapshot()["console"]["enabled"])

    def test_slow_motion_slows_the_simulation_clock(self) -> None:
        def simulated_seconds(factor: float, wall_s: float = 0.6) -> float:
            live = LiveSimulation(load("hannover_frei"))
            live.command({"action": "start", "speed_factor": factor})
            live.start_worker()
            try:
                time.sleep(wall_s)
            finally:
                live.stop_worker()
            return live.snapshot()["time_s"]

        normal = simulated_seconds(1.0)
        slow = simulated_seconds(0.25)
        self.assertGreater(normal, 0.3)
        self.assertLess(slow, 0.5 * normal)  # vor der Korrektur liefen 0,25x und 1x gleich schnell


if __name__ == "__main__":
    unittest.main()
