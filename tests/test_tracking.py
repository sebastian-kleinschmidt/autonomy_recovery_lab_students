"""Wahrnehmungsmodell ``tracked``: Objektliste, Sichtabdeckung, Karte und Hilfsbibliothek."""

from __future__ import annotations

import json
import statistics
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from autonomy_recovery_sim import recovery_helpers as helpers
from autonomy_recovery_sim.agent_session import EXACT_ONLY_TOOLS, AgentContractError, AgentSession
from autonomy_recovery_sim.batch import run_batch
from autonomy_recovery_sim.commands import TRACKED_EVIDENCE_TOOLS
from autonomy_recovery_sim.engine import SimulationEngine
from autonomy_recovery_sim.scenario import NoiseSpec, load_scenario, with_perception_model
from autonomy_recovery_sim.simulation import run_scenario
from autonomy_recovery_sim.tracking import TrackingAccess

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "autonomy_recovery_sim/scenarios"
SAFE_STOP = {"command": "SAFE_STOP", "parameters": {"reason_code": "NO_SAFE_RECOVERY"}, "reason": "Ende"}


def tracked(name: str, **noise: object):
    scenario = with_perception_model(load_scenario(SCENARIOS / f"hannover_{name}.json"), "tracked")
    if noise:
        scenario = replace(scenario, perception_noise=replace(scenario.perception_noise, **noise))
    return scenario


def first_session(scenario) -> AgentSession:
    """Die erste Agentensitzung des Szenarios (danach endet die Episode mit SAFE_STOP)."""
    sessions: list[AgentSession] = []

    def capture(session: AgentSession):
        sessions.append(session)
        return SAFE_STOP

    engine = SimulationEngine(scenario, agent=capture, agent_name="capture")
    while not engine.done and not sessions:
        engine.step()
    captured = sessions[0]
    # Frische Sitzung zur selben Lage: die erfasste hat bereits entschieden.
    return AgentSession(captured._tools, time_s=engine.time_s, stopped_for_s=engine.stopped_for_s)


def helper_agent(session: AgentSession) -> dict[str, object]:
    """Einfacher Agent, der nur die Hilfsbibliothek nutzt."""
    objects = session.call_tool("get_tracked_objects")
    coverage = session.call_tool("get_sensor_coverage")
    lanes = session.call_tool("get_map_context")
    blocker = helpers.blocker_ahead(objects, lanes)
    if blocker is None:
        return {"command": "WAIT", "parameters": {"duration_s": 5.0}, "reason": "kein stehendes Hindernis"}
    unsafe = (
        helpers.oncoming_conflict(objects, lanes)["conflict"]
        or not helpers.lane_visibility(coverage, "ONCOMING_LANE")["sufficient"]
        or helpers.lateral_clearance(blocker, lanes, ego_width_m=objects["ego"]["dimensions_m"][1])["margin_m"] < 0.5
        or lanes["center_marking"]["type"] == "solid"
    )
    if unsafe:
        return {"command": "WAIT", "parameters": {"duration_s": 10.0}, "reason": "Vorbeifahren nicht sicher"}
    return {
        "command": "NUDGE_AROUND_OBSTACLE",
        "parameters": {"side": "LEFT", "max_longitudinal_distance_m": 30.0},
        "reason": "Gegenspur frei und einsehbar",
    }


class InterfaceTest(unittest.TestCase):
    def test_tracked_replaces_verdict_tools_with_measurements(self) -> None:
        session = first_session(tracked("doppelparker"))
        names = set(session.tool_catalog)
        self.assertFalse(names & EXACT_ONLY_TOOLS)
        self.assertTrue(TRACKED_EVIDENCE_TOOLS <= names)
        self.assertIn("get_camera_caption", names, "Bedeutung kommt im Modell tracked vom Fahrstack")
        nudge = next(c for c in session.context["available_commands"] if c["command"] == "NUDGE_AROUND_OBSTACLE")
        self.assertEqual(set(nudge["required_tools"]), TRACKED_EVIDENCE_TOOLS)
        self.assertEqual(session.context["difficulty"]["perception_model"], "tracked")

    def test_strict_still_demands_evidence_from_the_new_tools(self) -> None:
        session = first_session(tracked("doppelparker"))
        payload = {"command": "NUDGE_AROUND_OBSTACLE", "parameters": {"side": "LEFT", "max_longitudinal_distance_m": 30.0}, "reason": "t"}
        with self.assertRaises(AgentContractError) as caught:
            session.submit_decision(payload)
        self.assertIn("get_tracked_objects", str(caught.exception))

    def test_outputs_are_deterministic_and_reveal_no_scenario_ids(self) -> None:
        scenario = tracked("verdeckung_gegenverkehr")
        first, second = first_session(scenario), first_session(scenario)
        for name in TRACKED_EVIDENCE_TOOLS:
            a = first.call_tool(name)
            self.assertEqual(a, first.call_tool(name), "zweimal zum selben Zeitpunkt")
            self.assertEqual(a, second.call_tool(name), "zweiter Lauf")
            text = json.dumps(a)
            for actor in scenario.actors:
                self.assertNotIn(f'"{actor.actor_id}"', text)

    def test_vla_output_drops_fields_alpamayo_does_not_produce(self) -> None:
        output = first_session(tracked("doppelparker")).call_tool("get_vla_output")
        self.assertNotIn('"meta_action"', json.dumps(output))
        self.assertNotIn('"confidence"', json.dumps(output))
        self.assertIn("reasoning", output["current"])

    def test_rule_engine_keeps_working(self) -> None:
        escalate = {"command": "ESCALATE_TO_RULE_ENGINE", "parameters": {}, "reason": "Regeln"}
        result = run_scenario(tracked("gegenverkehr"), agent=lambda session: escalate, agent_name="e")
        self.assertIsNone(result.agent_error)

    def test_batch_can_force_the_model(self) -> None:
        result = run_batch(SCENARIOS / "hannover_frei.json", perception_model="tracked")
        self.assertEqual(result.evaluations[0].result.scenario.difficulty.perception_model, "tracked")


class MeasurementTest(unittest.TestCase):
    def objects_over_time(self, scenario, samples: int = 40) -> list[dict[str, object]]:
        engine = SimulationEngine(scenario)
        found = []
        for _ in range(samples):
            for _ in range(5):
                engine.step()
            tools = engine._agent_tools()
            assert tools.tracking is not None
            found.append(tools.tracking.tracked_objects())
        return found

    def test_position_noise_matches_the_configured_spread(self) -> None:
        scenario = tracked("frei", position_std_m=0.5, position_std_per_10m_m=0.0)
        engine = SimulationEngine(scenario)
        errors = []
        while len(errors) < 60:
            for _ in range(5):
                engine.step()
            tools = engine._agent_tools()
            access: TrackingAccess = tools.tracking  # type: ignore[assignment]
            if not tools.actors:
                continue
            actor = tools.actors[0]
            true_x, _, _ = access._route_point_ego(actor.s_m, actor.d_m)
            measured = access.tracked_objects()["objects"][0]["kinematics"]["position_m"][0]
            errors.append(measured - true_x)
        self.assertAlmostEqual(statistics.pstdev(errors), 0.5, delta=0.2)
        self.assertLess(abs(statistics.mean(errors)), 0.25)

    def test_persistent_misclassification(self) -> None:
        session = first_session(tracked("frei", class_confusion=1.0))
        labels = [helpers.best_label(obj)[0] for obj in session.call_tool("get_tracked_objects")["objects"]]
        self.assertNotIn("CAR", labels)

    def test_false_positives_and_dropouts(self) -> None:
        ghosts = self.objects_over_time(tracked("frei", false_positive_rate_hz=1.0), samples=10)
        self.assertTrue(all(any(o["track_id"].startswith("trk_9") for o in item["objects"]) for item in ghosts))
        empty = first_session(tracked("frei", dropout_probability=1.0)).call_tool("get_tracked_objects")
        self.assertEqual([o for o in empty["objects"] if o["track"]["status"] != "COASTING"], [])

    def test_radar_hints_at_occluded_vehicles_only_when_enabled(self) -> None:
        def radar_tracks(scenario) -> int:
            return sum(
                o["track"]["contributing_sensors"] == ["radar"]
                for item in self.objects_over_time(scenario, samples=12)
                for o in item["objects"]
            )

        # Im Stau verdecken die vorderen Fahrzeuge die hinteren.
        self.assertGreater(radar_tracks(tracked("stau_loest_sich")), 0)
        self.assertEqual(radar_tracks(tracked("stau_loest_sich", radar_through_occluders=False)), 0)

    def test_coverage_names_the_occluding_track(self) -> None:
        session = first_session(tracked("verdeckung_gegenverkehr"))
        objects = session.call_tool("get_tracked_objects")["objects"]
        coverage = session.call_tool("get_sensor_coverage")
        van = next(o for o in objects if helpers.best_label(o)[0] == "VAN")
        regions = [r for r in coverage["occluded_regions"] if r["lane"] == "ONCOMING_LANE"]
        self.assertIn(van["track_id"], {r["caused_by"] for r in regions})
        self.assertFalse(helpers.lane_visibility(coverage, "ONCOMING_LANE")["sufficient"])


class LoadingTest(unittest.TestCase):
    def test_noise_block_is_validated(self) -> None:
        data = json.loads((SCENARIOS / "hannover_frei.json").read_text("utf8"))
        for key in ("map_file", "context_file"):
            if key in data["road"]:
                data["road"][key] = str((SCENARIOS / data["road"][key]).resolve())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "variant.json"
            data.setdefault("perception", {})["noise"] = {"position_std_m": 0.3, "radar_through_occluders": False}
            data["difficulty"] = {"perception_model": "tracked"}
            path.write_text(json.dumps(data), encoding="utf8")
            scenario = load_scenario(path)
            self.assertEqual(scenario.perception_noise, NoiseSpec(position_std_m=0.3, radar_through_occluders=False))
            self.assertIsNotNone(scenario.vla, "tracked bringt einen Fahrstack fuer die Bedeutung mit")
            for bad in ({"class_confusion": 2}, {"position_std_m": -1}, {"blur": 1}):
                data["perception"]["noise"] = bad
                path.write_text(json.dumps(data), encoding="utf8")
                with self.subTest(bad), self.assertRaises(ValueError):
                    load_scenario(path)


class HelperAgentTest(unittest.TestCase):
    def test_a_helper_based_agent_solves_typical_cases(self) -> None:
        cases = {
            "frei": "liberated",
            "gegenverkehr_fern": "liberated",
            "doppelparker": "liberated",
            "gegenverkehr": "waiting",
            "schmal": "waiting",
            "durchgezogen": "waiting",
        }
        for name, outcome in cases.items():
            with self.subTest(name):
                result = run_scenario(tracked(name), agent=helper_agent, agent_name="helpers")
                self.assertIsNone(result.agent_error)
                self.assertFalse(result.collision)
                self.assertEqual(result.outcome, outcome)

    def test_lane_frame_round_trip(self) -> None:
        session = first_session(tracked("frei"))
        lanes = session.call_tool("get_map_context")
        along, lateral = helpers.to_lane_frame([20.0, 3.5], lanes, "EGO_LANE")
        self.assertAlmostEqual(along, 20.0, delta=0.6)
        self.assertAlmostEqual(lateral, 3.5, delta=0.6)


if __name__ == "__main__":
    unittest.main()
