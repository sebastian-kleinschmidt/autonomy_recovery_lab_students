"""Schwierigkeit (Block ``difficulty``): Laden, Pruefmodi und Wirkung auf den Ausfuehrer."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from autonomy_recovery_sim.agent_session import AgentContractError, AgentSession
from autonomy_recovery_sim.commands import CommandError
from autonomy_recovery_sim.models import ActorSpec, CommandRequest, WorldFacts
from autonomy_recovery_sim.rules import WAIVABLE_SAFETY_CHECKS, check_command
from autonomy_recovery_sim.scenario import DifficultySpec, load_scenario
from autonomy_recovery_sim.simulation import run_scenario
from tests.test_commands import BLOCKER, situation

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "autonomy_recovery_sim/scenarios"
NUDGE_LEFT = {
    "command": "NUDGE_AROUND_OBSTACLE",
    "parameters": {"side": "LEFT", "max_longitudinal_distance_m": 30.0},
    "reason": "Losfahren ohne Lagepruefung",
}


def load(name: str, guardrails: str | None = None):
    scenario = load_scenario(SCENARIOS / f"{name}.json")
    if guardrails is None:
        return scenario
    return replace(scenario, difficulty=DifficultySpec(guardrails=guardrails))


def blind(session: AgentSession) -> dict[str, object]:
    """Agent, der ohne ein einziges Werkzeug sofort links vorbeifaehrt."""
    return NUDGE_LEFT


class LoadingTest(unittest.TestCase):
    def write_variant(self, folder: str, **difficulty: object) -> Path:
        data = json.loads((SCENARIOS / "hannover_frei.json").read_text("utf8"))
        for key in ("map_file", "context_file"):
            if key in data["road"]:
                data["road"][key] = str((SCENARIOS / data["road"][key]).resolve())
        data["difficulty"] = difficulty
        path = Path(folder) / "variant.json"
        path.write_text(json.dumps(data), encoding="utf8")
        return path

    def test_without_block_every_shipped_scenario_keeps_the_previous_behaviour(self) -> None:
        for path in sorted(SCENARIOS.glob("*.json")):
            with self.subTest(path.name):
                self.assertEqual(load_scenario(path).difficulty, DifficultySpec())

    def test_block_is_loaded_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            spec = load_scenario(self.write_variant(folder, level="C", guardrails="advisory")).difficulty
            self.assertEqual(spec, DifficultySpec(level="C", guardrails="advisory"))
            for bad in ({"level": "E"}, {"guardrails": "lax"}, {"perception_model": "magic"}, {"noise": 1}):
                with self.subTest(bad), self.assertRaises(ValueError):
                    load_scenario(self.write_variant(folder, **bad))

    def test_agent_sees_the_difficulty(self) -> None:
        sessions: list[AgentSession] = []

        def observe(session: AgentSession):
            sessions.append(session)
            return {"command": "WAIT", "parameters": {"duration_s": 5.0}, "reason": "beobachten"}

        run_scenario(load("hannover_doppelparker", "advisory"), agent=observe, agent_name="o")
        self.assertEqual(
            sessions[0].context["difficulty"],
            {"level": "A", "guardrails": "advisory", "perception_model": "exact"},
        )


class RuleLevelTest(unittest.TestCase):
    def test_waivable_findings_become_warnings_others_stay_rejections(self) -> None:
        lane = ({"side": "RIGHT", "direction": "SAME", "available": True},)
        neighbour = ActorSpec("neighbour", "car", 84.0, -5.25, 0.0, 1, 4.5, 1.8)
        busy = situation(BLOCKER, neighbour, facts=WorldFacts(adjacent_lanes=lane))
        change = CommandRequest("CHANGE_LANE", {"direction": "RIGHT"}, "t")
        with self.assertRaises(CommandError):
            check_command(change, tools=busy, facts=busy.facts)
        warnings: list[str] = []
        check_command(change, tools=busy, facts=busy.facts, warnings=warnings)
        self.assertEqual([w.split(":")[0] for w in warnings], ["TARGET_LANE_OCCUPIED"])

        narrow = situation(BLOCKER, facts=WorldFacts(shoulder_m=0.5))
        right = CommandRequest("NUDGE_AROUND_OBSTACLE", {"side": "RIGHT", "max_longitudinal_distance_m": 30.0}, "t")
        with self.assertRaises(CommandError) as caught:
            check_command(right, tools=narrow, facts=narrow.facts, warnings=[])
        self.assertTrue(caught.exception.detail.startswith("NO_SHOULDER_SPACE"))
        self.assertNotIn("NO_SHOULDER_SPACE", WAIVABLE_SAFETY_CHECKS)


class GuardrailTest(unittest.TestCase):
    def test_strict_rejects_a_maneuver_without_evidence(self) -> None:
        result = run_scenario(load("hannover_abbruch_gegenverkehr"), agent=blind, agent_name="blind")
        self.assertIn("SAFETY_REJECTED", result.agent_error or "")
        self.assertFalse(result.collision)
        self.assertEqual(result.safety_warnings, [])

    def test_advisory_accepts_with_warning_and_the_executor_still_aborts(self) -> None:
        result = run_scenario(load("hannover_abbruch_gegenverkehr", "advisory"), agent=blind, agent_name="blind")
        self.assertIsNone(result.agent_error)
        self.assertTrue(result.safety_warnings[0].startswith("MISSING_EVIDENCE"))
        self.assertEqual(result.abort_reason, "oncoming_traffic")
        self.assertFalse(result.collision)
        accepted = [e for e in result.agent_trace if e["type"] == "decision_attempt" and e["accepted"]]
        # Nach dem stabilisierten Abbruch entscheidet der Agent erneut; die erste Warnung zaehlt.
        self.assertEqual(accepted[0]["warnings"], result.safety_warnings[: len(accepted[0]["warnings"])])

    def test_off_has_no_predictive_abort_so_the_blind_agent_crashes(self) -> None:
        result = run_scenario(load("hannover_abbruch_gegenverkehr", "off"), agent=blind, agent_name="blind")
        self.assertIsNone(result.abort_reason)
        self.assertTrue(result.collision)

    def test_traffic_rules_stay_hard_in_every_mode(self) -> None:
        for guardrails in ("advisory", "off"):
            with self.subTest(guardrails):
                result = run_scenario(load("hannover_durchgezogen", guardrails), agent=blind, agent_name="blind")
                self.assertIn("RULE_REJECTED", result.agent_error or "")

    def test_executor_geometry_is_never_waived(self) -> None:
        session = AgentSession(
            _tools_at_deadlock(load("hannover_umgekippter_lkw", "off")), time_s=0.0, stopped_for_s=5.0
        )
        with self.assertRaises(AgentContractError) as caught:
            session.submit_decision(NUDGE_LEFT)
        self.assertIn("ROAD_FULLY_BLOCKED", str(caught.exception))


def _tools_at_deadlock(scenario):
    """Werkzeugsicht in dem Moment, in dem die Simulation den Agenten rufen wuerde."""
    from autonomy_recovery_sim.engine import SimulationEngine

    tools = []

    def capture(session: AgentSession):
        tools.append(session._tools)
        return {"command": "SAFE_STOP", "parameters": {"reason_code": "NO_SAFE_RECOVERY"}, "reason": "Ende"}

    engine = SimulationEngine(scenario, agent=capture, agent_name="capture")
    while not engine.done and not tools:
        engine.step()
    return tools[0]


if __name__ == "__main__":
    unittest.main()
