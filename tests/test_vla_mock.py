"""VLA-Fahrstack-Mock (an NVIDIA Alpamayo 1.5 angelehnt): Ausgabeform, Fehlerbilder, Werkzeuge."""

from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from autonomy_recovery_sim.agent_session import TOOL_CATALOG, AgentSessionError
from autonomy_recovery_sim.engine import SimulationEngine
from autonomy_recovery_sim.policy import heuristic_agent
from autonomy_recovery_sim.scenario import VlaSpec, load_scenario
from autonomy_recovery_sim.simulation import run_scenario
from autonomy_recovery_sim.vla_mock import HORIZON_STEPS, META_ACTIONS, VAGUE_PHRASE
from tests.test_commands import command, run

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "autonomy_recovery_sim/scenarios"


def load(name: str):
    return load_scenario(SCENARIOS / f"{name}.json")


def with_vla(name: str, **settings: object):
    return dataclasses.replace(load(name), vla=VlaSpec(**settings))  # type: ignore[arg-type]


def first_session(engine: SimulationEngine):
    for _ in range(6000):
        if engine.pending_session is not None:
            return engine.pending_session
        engine.step()
    raise AssertionError("Kein Deadlock erkannt")


def reasoning_timeline(scenario) -> list[tuple[float, str, str]]:
    engine = SimulationEngine(scenario)
    timeline = []
    while not engine.done:
        engine.step()
        latest = engine.vla.latest
        timeline.append((round(latest.t_s, 1), latest.meta_action, latest.reasoning))
    return timeline


class WithoutVlaBlockTest(unittest.TestCase):
    def test_scenarios_without_vla_block_have_no_mock_and_no_extra_tools(self) -> None:
        engine = SimulationEngine(load("hannover_frei"), console=True)
        session = first_session(engine)
        self.assertIsNone(engine.vla)
        self.assertIsNone(engine.snapshot()["vla"])
        self.assertNotIn("driving_stack", session.context)
        self.assertEqual(set(session.tool_catalog), set(TOOL_CATALOG))
        with self.assertRaises(AgentSessionError):
            session.call_tool("get_vla_output")

    def test_the_mock_only_observes_and_never_changes_the_driving(self) -> None:
        for name in ("hannover_frei", "hannover_ampel_rot", "hannover_fussgaengergruppe", "hannover_ladung_karton"):
            with self.subTest(name=name):
                plain = run_scenario(load(name), agent=heuristic_agent, agent_name="baseline")
                mocked = run_scenario(with_vla(name, seed=3), agent=heuristic_agent, agent_name="baseline")
                self.assertEqual(plain.outcome, mocked.outcome)
                self.assertEqual(plain.commands, mocked.commands)
                self.assertEqual(plain.costs, mocked.costs)
                self.assertEqual(plain.trajectory[-1], mocked.trajectory[-1])


class OutputFormTest(unittest.TestCase):
    def test_output_has_reasoning_meta_action_and_a_64_point_trajectory(self) -> None:
        engine = SimulationEngine(with_vla("hannover_frei"), console=True)
        for _ in range(30):
            engine.step()
        latest = engine.vla.latest
        self.assertEqual(latest.meta_action, "FOLLOW_LANE")
        self.assertEqual(len(latest.trajectory_xy), HORIZON_STEPS)
        self.assertFalse(latest.stationary)
        self.assertGreater(latest.trajectory_ego[-1][0], 10.0)  # faehrt nach vorn
        # Die Strasse ist gekruemmt: Die Spurtreue zeigt sich im Querversatz zur Fahrbahn.
        _, end_d, _, _ = engine.scenario.road.project(*latest.trajectory_xy[-1])
        self.assertAlmostEqual(end_d, engine.scenario.ego_lane_d_m, delta=0.3)
        snapshot = engine.snapshot()["vla"]
        self.assertEqual(len(snapshot["trajectory_xy"]), HORIZON_STEPS)
        json.dumps(snapshot)

    def test_stopped_behind_a_blocker_the_stack_explains_why(self) -> None:
        engine = SimulationEngine(with_vla("hannover_frei"), console=True)
        session = first_session(engine)
        self.assertEqual(session.context["driving_stack"]["type"], "VLA_MOCK")
        report = session.call_tool("get_vla_output", {"last_n": 3})
        current = report["current"]
        self.assertEqual(current["meta_action"], "STOP")
        self.assertIn("parked car", current["reasoning"])
        self.assertTrue(current["trajectory"]["stationary"])
        self.assertEqual(current["trajectory"]["sampled_points_ego_m"], [])
        self.assertLessEqual(current["confidence"], 0.95)
        self.assertGreaterEqual(report["stationary_plan_for_s"], 3.0)
        self.assertLessEqual(len(report["recent"]), 3)
        self.assertTrue(all(item["meta_action"] in META_ACTIONS for item in report["recent"]))

    def test_output_is_deterministic_for_the_same_seed(self) -> None:
        scenario = load("hannover_vla_phantom")
        self.assertEqual(reasoning_timeline(scenario), reasoning_timeline(scenario))

    def test_latency_spaces_the_inferences(self) -> None:
        engine = SimulationEngine(with_vla("hannover_frei", latency_ms=500), console=True)
        times = set()
        for _ in range(40):
            engine.step()
            times.add(round(engine.vla.latest.t_s, 1))
        self.assertEqual(sorted(times), [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0])

    def test_an_approved_command_appears_as_instruction(self) -> None:
        engine = SimulationEngine(with_vla("hannover_frei"), console=True)
        first_session(engine)
        engine.console_gather_evidence()
        engine.console_submit(
            command("NUDGE_AROUND_OBSTACLE", side="LEFT", max_longitudinal_distance_m=35.0)
        )
        for _ in range(20):
            engine.step()
        latest = engine.vla.latest
        self.assertEqual(latest.instruction, "NUDGE_AROUND_OBSTACLE")
        self.assertEqual(latest.meta_action, "NUDGE_LEFT")
        _, end_d, _, _ = engine.scenario.road.project(*latest.trajectory_xy[-1])
        self.assertGreater(end_d, 0.0)  # Trajektorie fuehrt ueber die Mittellinie nach links


class CameraAndToolTest(unittest.TestCase):
    def test_camera_captions_describe_perceived_objects_only(self) -> None:
        engine = SimulationEngine(with_vla("hannover_frei"), console=True)
        session = first_session(engine)
        front = session.call_tool("get_camera_caption", {"camera": "front_wide"})
        self.assertIn("parked car", front["caption"])
        self.assertIn("ego lane", front["caption"])
        rear_side = session.call_tool("get_camera_caption", {"camera": "cross_left"})
        self.assertNotIn("parked car", rear_side["caption"])

    def test_tool_arguments_are_validated(self) -> None:
        engine = SimulationEngine(with_vla("hannover_frei"), console=True)
        session = first_session(engine)
        for name, arguments in (
            ("get_vla_output", {"last_n": 0}),
            ("get_vla_output", {"last_n": "3"}),
            ("get_camera_caption", {"camera": "rear"}),
            ("get_camera_caption", {"zoom": 2}),
        ):
            with self.subTest(name=name, arguments=arguments):
                with self.assertRaises(AgentSessionError):
                    session.call_tool(name, arguments)

    def test_vla_interface_removes_semantics_from_the_situation_tools(self) -> None:
        engine = SimulationEngine(load("hannover_vla_karton"), console=True)
        session = first_session(engine)
        blocker = session.call_tool("get_blocker")
        self.assertTrue(blocker["detected"])
        for field in ("kind", "obstacle_profile", "scene_description"):
            self.assertNotIn(field, blocker)
        self.assertIn("distance_m", blocker)
        # Die Regelpruefung arbeitet weiter auf der vollen Lage: Das Ueberfahren bleibt zulaessig.
        self.assertEqual(engine._situation_tools().blocker_report()["kind"], "debris")

    def test_vla_interface_hides_the_signal_state(self) -> None:
        engine = SimulationEngine(load("hannover_vla_ampel_dunkel"), console=True)
        session = first_session(engine)
        control = session.call_tool("get_traffic_control")["controls"][0]
        self.assertEqual(control["state"], "UNKNOWN")
        self.assertNotIn("note", control)
        caption = session.call_tool("get_camera_caption", {"camera": "front_tele"})["caption"]
        self.assertIn("no light", caption)


class FaultTest(unittest.TestCase):
    def test_hallucinated_cause_contradicts_the_camera(self) -> None:
        engine = SimulationEngine(load("hannover_vla_ampel_dunkel"), console=True)
        session = first_session(engine)
        reasoning = session.call_tool("get_vla_output")["current"]["reasoning"]
        self.assertIn("red", reasoning)

    def test_overconfident_phantom_versus_the_tracker(self) -> None:
        engine = SimulationEngine(load("hannover_vla_phantom"), console=True)
        session = first_session(engine)
        current = session.call_tool("get_vla_output")["current"]
        self.assertEqual(current["confidence"], 0.97)
        self.assertNotIn("unclear", current["reasoning"])
        self.assertEqual(session.call_tool("get_blocker")["track_confidence"], 0.3)
        caption = session.call_tool("get_camera_caption", {"camera": "front_wide"})["caption"]
        self.assertIn("unclear", caption)

    def test_vague_cause_leaves_the_camera_detail_intact(self) -> None:
        engine = SimulationEngine(load("hannover_vla_karton"), console=True)
        session = first_session(engine)
        self.assertIn(VAGUE_PHRASE, session.call_tool("get_vla_output")["current"]["reasoning"])
        caption = session.call_tool("get_camera_caption", {"camera": "front_wide"})["caption"]
        self.assertIn("cardboard", caption)
        self.assertIn("flat", caption)

    def test_reasoning_action_mismatch_claims_driving_while_the_plan_stops(self) -> None:
        scenario = with_vla(
            "hannover_frei", faults=({"type": "REASONING_ACTION_MISMATCH", "from_s": 8.0},)
        )
        engine = SimulationEngine(scenario, console=True)
        session = first_session(engine)
        current = session.call_tool("get_vla_output")["current"]
        self.assertEqual(current["meta_action"], "FOLLOW_LANE")
        self.assertIn("clear", current["reasoning"])
        self.assertTrue(current["trajectory"]["stationary"])

    def test_invalid_vla_configuration_is_rejected(self) -> None:
        base = json.loads((SCENARIOS / "hannover_frei.json").read_text("utf8"))
        base["road"]["map_file"] = str((SCENARIOS / base["road"]["map_file"]).resolve())
        base["road"]["context_file"] = str((SCENARIOS / base["road"]["context_file"]).resolve())
        for vla in (
            {"perception_interface": "camera"},
            {"latency_ms": -1},
            {"faults": [{"type": "LIDAR_DROPOUT"}]},
            {"faults": [{"type": "HALLUCINATED_CAUSE"}]},
            {"faults": [{"type": "VAGUE_CAUSE", "actor_id": "nicht-da"}]},
            {"faults": [{"type": "OVERCONFIDENT", "from_s": 5, "until_s": 2}]},
        ):
            with self.subTest(vla=vla), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "vla.json"
                path.write_text(json.dumps({**base, "vla": vla}), encoding="utf8")
                with self.assertRaises(ValueError):
                    load_scenario(path)


class VlaScenarioTest(unittest.TestCase):
    def test_reference_commands_solve_the_vla_scenarios(self) -> None:
        cases = {
            "hannover_vla_phantom": command(
                "REQUEST_ADDITIONAL_INFORMATION", topic="MOTION_REASSESSMENT", duration_s=4
            ),
            "hannover_vla_ampel_dunkel": command("REQUEST_REMOTE_ASSISTANCE", reason_code="BLOCKED_ROUTE"),
            "hannover_vla_karton": command("CROSS_LOW_RISK_OBJECT", max_speed_mps=1.0),
        }
        for name, decision in cases.items():
            with self.subTest(name=name):
                result = run(load(name), decision)
                self.assertEqual(result.outcome, result.scenario.expected_outcome)
                self.assertTrue(result.command_correct)
                self.assertTrue(result.within_budget)
                self.assertFalse(result.collision)

    def test_trusting_the_hallucinated_red_light_means_waiting_forever(self) -> None:
        waiting = run(load("hannover_vla_ampel_dunkel"), *[command("WAIT", duration_s=10)] * 6)
        self.assertFalse(waiting.reached_goal)
        self.assertNotEqual(waiting.outcome, waiting.scenario.expected_outcome)
        self.assertGreater(waiting.costs["stationary_s"], 30.0)

    def test_the_baseline_without_semantics_does_not_cross_the_cardboard(self) -> None:
        result = run_scenario(load("hannover_vla_karton"), agent=heuristic_agent, agent_name="baseline")
        self.assertNotEqual(result.command, "CROSS_LOW_RISK_OBJECT")
        self.assertFalse(result.collision)


if __name__ == "__main__":
    unittest.main()
