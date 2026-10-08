"""Tests der Verkehrssteuerung (Ampel, Bahnuebergang, Zug) und der Faelle 'steckt es wirklich fest?'."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from autonomy_recovery_sim.batch import run_batch
from autonomy_recovery_sim.commands import CommandError, parse_command
from autonomy_recovery_sim.engine import SimulationEngine
from autonomy_recovery_sim.models import ActorSpec, ActorState, EgoState, WorldFacts
from autonomy_recovery_sim.policy import heuristic_agent
from autonomy_recovery_sim.rules import check_command
from autonomy_recovery_sim.scenario import load_scenario
from autonomy_recovery_sim.simulation import run_scenario
from autonomy_recovery_sim.tools import SituationTools
from tests.test_commands import command, run

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "autonomy_recovery_sim/scenarios"


def load(name: str):
    return load_scenario(SCENARIOS / f"{name}.json")


def pending(name: str) -> SimulationEngine:
    engine = SimulationEngine(load(name), console=True)
    for _ in range(6000):
        if engine.pending_session is not None:
            return engine
        engine.step()
    raise AssertionError(name)


class ControlScheduleTest(unittest.TestCase):
    def test_state_follows_the_schedule(self) -> None:
        engine = SimulationEngine(load("hannover_ampel_rot"))
        control = engine.scenario.traffic_controls[0]
        self.assertEqual(engine._control_state(control), ("RED", 0.0))
        engine.time_s = 29.9
        self.assertEqual(engine._control_state(control)[0], "RED")
        engine.time_s = 30.0
        self.assertEqual(engine._control_state(control), ("GREEN", 30.0))

    def test_invalid_controls_are_rejected(self) -> None:
        data = json.loads((SCENARIOS / "hannover_ampel_rot.json").read_text("utf8"))
        data["road"]["map_file"] = str((SCENARIOS / data["road"]["map_file"]).resolve())
        data["road"].pop("context_file", None)
        broken = {
            "schedule state": [{"state": "OPEN", "until_s": 5.0}],
            "descending time": [{"state": "RED", "until_s": 9.0}, {"state": "GREEN", "until_s": 3.0}],
            "empty": [],
        }
        for label, schedule in broken.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as directory:
                data["traffic_controls"][0]["schedule"] = schedule
                path = Path(directory) / "bad.json"
                path.write_text(json.dumps(data), encoding="utf8")
                with self.assertRaises(ValueError):
                    load_scenario(path)


class RedLightTest(unittest.TestCase):
    def test_vehicle_stops_before_the_stop_line_and_goes_on_at_green(self) -> None:
        engine = SimulationEngine(load("hannover_ampel_rot"), agent=lambda s: s.submit_decision(command("WAIT", duration_s=10)))
        stop_line = engine.scenario.traffic_controls[0]["s_m"]
        while not engine.done:
            engine.step()
            if engine.time_s < 30.0:
                front = engine.ego_route_state[0] + engine.ego.length_m / 2.0
                self.assertLess(front, stop_line, f"Haltelinie bei t={engine.time_s:.1f} ueberfahren")
        self.assertTrue(engine.reached_goal)
        self.assertFalse(engine.collision)

    def test_the_stop_is_not_charged_as_standstill_cost(self) -> None:
        result = run_scenario(SCENARIOS / "hannover_ampel_rot.json", agent=heuristic_agent, agent_name="baseline")
        self.assertLess(result.costs["stationary_s"], 3.0)
        self.assertLess(result.costs["total_eur"], 2.0)

    def test_the_agent_sees_the_state_and_its_age(self) -> None:
        tools = pending("hannover_ampel_rot").pending_session.call_tool("get_traffic_control")
        control = tools["controls"][0]
        self.assertEqual((control["type"], control["state"]), ("TRAFFIC_LIGHT", "RED"))
        self.assertGreater(control["changed_s_ago"], 5.0)
        self.assertLess(control["stop_line_distance_m"], 6.0)

    def test_the_stuck_monitor_still_calls_the_agent_which_must_recognize_the_normal_stop(self) -> None:
        engine = pending("hannover_ampel_rot")
        self.assertGreaterEqual(engine.pending_session.context["ego"]["stopped_for_s"], 3.0)

    def test_waiting_passes_and_calling_the_control_room_does_not(self) -> None:
        scenario = load("hannover_ampel_rot")
        good = run(scenario, command("WAIT", duration_s=10), command("WAIT", duration_s=10))
        self.assertEqual(good.outcome, "resolved")
        self.assertTrue(good.command_correct and good.within_budget and good.reached_goal)
        call = run(scenario, command("REQUEST_REMOTE_ASSISTANCE", reason_code="AMBIGUOUS_SCENE"))
        self.assertEqual(call.commands[0]["outcome"], "NO_OPERATOR_SOLUTION")  # ueber Rot gibt niemand frei
        self.assertFalse(call.within_budget)
        self.assertFalse(call.command_correct)

    def test_a_wait_lasts_until_the_light_changes(self) -> None:
        result = run(load("hannover_ampel_rot"), command("WAIT", duration_s=30))
        wait = result.commands[0]
        self.assertEqual(wait["outcome"], "PATH_CLEARED")
        self.assertGreater(wait["elapsed_s"], 5.0)  # nicht schon nach einer Sekunde beendet


class RuleTest(unittest.TestCase):
    def tools(self, state: str) -> SituationTools:
        scenario = load("hannover_frei")
        controls = ({"id": "signal-1", "type": "TRAFFIC_LIGHT", "state": state, "stop_line_distance_m": 12.0, "changed_s_ago": 4.0},)
        facts = WorldFacts(traffic_controls=controls)
        blocker = ActorSpec("blocker", "car", 92.0, -1.75, 0.0, 1, 4.5, 1.8)
        return SituationTools(scenario, EgoState(82.0, -1.75, 0.0, 4.71, 1.99), (ActorState.from_spec(blocker),), None, facts)

    def check(self, state: str, payload: dict[str, object]) -> str | None:
        tools = self.tools(state)
        try:
            check_command(parse_command(payload), tools=tools, facts=tools.facts)
        except CommandError as error:
            return error.code + ":" + error.detail.split(":")[0]
        return None

    def test_maneuvers_are_rejected_at_red_and_closed_but_not_at_green(self) -> None:
        nudge = command("NUDGE_AROUND_OBSTACLE", side="LEFT", max_longitudinal_distance_m=30)
        self.assertEqual(self.check("RED", nudge), "RULE_REJECTED:TRAFFIC_CONTROL_ACTIVE")
        self.assertEqual(self.check("CLOSED", nudge), "RULE_REJECTED:TRAFFIC_CONTROL_ACTIVE")
        self.assertIsNone(self.check("GREEN", nudge))
        self.assertIsNone(self.check("DARK", nudge))  # dunkles Signal regelt nichts

    def test_waiting_and_reversing_stay_allowed_at_red(self) -> None:
        self.assertIsNone(self.check("RED", command("WAIT", duration_s=5)))
        self.assertIsNone(self.check("RED", command("REVERSE_SHORT", max_distance_m=2.0)))


class RailwayTest(unittest.TestCase):
    def test_the_barrier_is_closed_whenever_the_train_covers_the_road(self) -> None:
        engine = SimulationEngine(load("hannover_gueterzug"), agent=lambda s: s.submit_decision(command("WAIT", duration_s=10)))
        control = engine.scenario.traffic_controls[0]
        covered_steps = 0
        while not engine.done:
            engine.step()
            train = engine._actor_states()[0]
            covers = abs(train.d_m) < train.spec.width_m / 2.0 + 3.5
            if covers:
                covered_steps += 1
                self.assertEqual(engine._control_state(control)[0], "CLOSED", f"t={engine.time_s:.1f}")
        self.assertGreater(covered_steps, 50)
        self.assertFalse(engine.collision)
        self.assertTrue(engine.reached_goal)

    def test_tool_reports_the_crossing_and_whether_a_train_is_detected(self) -> None:
        session = pending("hannover_gueterzug").pending_session
        control = session.call_tool("get_traffic_control")["controls"][0]
        self.assertEqual((control["type"], control["state"]), ("RAILWAY_CROSSING", "CLOSED"))
        self.assertIn("train_detected", control)

    def test_waiting_passes_the_freight_train(self) -> None:
        result = run_scenario(SCENARIOS / "hannover_gueterzug.json", agent=heuristic_agent, agent_name="baseline")
        self.assertTrue(result.command_correct and result.within_budget and result.reached_goal)
        self.assertEqual(result.outcome, "resolved")


class DarkSignalTest(unittest.TestCase):
    def test_the_tool_explains_the_failed_signal(self) -> None:
        control = pending("hannover_ampel_ausgefallen").pending_session.call_tool("get_traffic_control")["controls"][0]
        self.assertEqual(control["state"], "DARK")
        self.assertIn("ausgefallen", control["note"])

    def test_waiting_never_ends_but_the_control_room_can_release(self) -> None:
        scenario = load("hannover_ampel_ausgefallen")
        waiting = run(scenario, *[command("WAIT", duration_s=10)] * 6)
        self.assertFalse(waiting.reached_goal)
        self.assertGreater(waiting.costs["stationary_s"], 30.0)  # ein ausgefallenes Signal ist kein regulaerer Halt
        call = run(scenario, command("REQUEST_REMOTE_ASSISTANCE", reason_code="BLOCKED_ROUTE"))
        self.assertEqual(call.commands[0]["outcome"], "REMOTE_CLEARED")
        self.assertEqual(call.outcome, "remote_resolved")
        self.assertTrue(call.command_correct and call.within_budget and call.reached_goal)

    def test_the_baseline_waits_too_long_and_misses_the_budget(self) -> None:
        result = run_scenario(SCENARIOS / "hannover_ampel_ausgefallen.json", agent=heuristic_agent, agent_name="baseline")
        self.assertEqual(result.outcome, "remote_resolved")
        self.assertFalse(result.within_budget)  # 30 s gewartet, bevor sie anruft


class ContrastTest(unittest.TestCase):
    def test_a_green_light_is_not_the_reason_and_the_blocker_is_real(self) -> None:
        session = pending("hannover_ampel_gruen_blockiert").pending_session
        self.assertEqual(session.call_tool("get_traffic_control")["controls"][0]["state"], "GREEN")
        self.assertTrue(session.call_tool("get_blocker")["detected"])
        result = run_scenario(SCENARIOS / "hannover_ampel_gruen_blockiert.json", agent=heuristic_agent, agent_name="baseline")
        self.assertEqual(result.outcome, "liberated")
        self.assertTrue(result.command_correct and not result.collision)

    def test_a_normal_traffic_jam_resolves_by_waiting_and_a_maneuver_is_wrong(self) -> None:
        scenario = load("hannover_stau_loest_sich")
        waited = run(scenario, command("WAIT", duration_s=10), command("WAIT", duration_s=10))
        self.assertEqual(waited.outcome, "resolved")
        self.assertTrue(waited.command_correct and waited.within_budget and not waited.collision)
        baseline = run_scenario(SCENARIOS / "hannover_stau_loest_sich.json", agent=heuristic_agent, agent_name="baseline")
        self.assertFalse(baseline.command_correct)
        self.assertFalse(baseline.collision)

    def test_recognition_set_result_with_the_baseline(self) -> None:
        batch = run_batch(ROOT / "autonomy_recovery_sim/scenario_sets/erkennen.txt", agent=heuristic_agent, agent_name="baseline")
        failed = {item.result.scenario_id for item in batch.evaluations if not item.passed}
        self.assertEqual(failed, {"hannover_ampel_ausgefallen", "hannover_stau_loest_sich"})
        self.assertEqual(batch.to_dict()["summary"]["collision_count"], 0)


class SnapshotTest(unittest.TestCase):
    def test_controls_are_part_of_the_live_state(self) -> None:
        engine = SimulationEngine(load("hannover_ampel_rot"))
        state = engine.snapshot()
        json.dumps(state)
        self.assertEqual(state["controls"][0]["state"], "RED")
        self.assertEqual({"id", "type", "state", "x_m", "y_m", "yaw_rad"}, set(state["controls"][0]))
        engine.time_s = 31.0
        self.assertEqual(engine.snapshot()["controls"][0]["state"], "GREEN")

    def test_ui_draws_the_controls(self) -> None:
        javascript = (ROOT / "autonomy_recovery_sim/web/app.js").read_text("utf8")
        for name in ("drawTopControls", "drawPerspectiveControls", "Schranke geschlossen"):
            self.assertIn(name, javascript)

    def test_the_system_prompt_names_regular_stops(self) -> None:
        from autonomy_recovery_sim.llm_agent import SYSTEM_PROMPT

        self.assertIn("get_traffic_control", SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
