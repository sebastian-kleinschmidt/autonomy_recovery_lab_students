"""Tests der Hannover-Szenarien auf OSM-Kartenmaterial und der zugehoerigen Import-Skripte."""

from __future__ import annotations

import json
import subprocess
import sys
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
DATA = ROOT / "autonomy_recovery_sim/data"
SCENARIOS = ROOT / "autonomy_recovery_sim/scenarios"


def load(name: str):
    return load_scenario(SCENARIOS / f"{name}.json")


def first_session(name: str):
    engine = SimulationEngine(load(name), console=True)
    for _ in range(9000):
        if engine.pending_session is not None:
            return engine, engine.pending_session
        engine.step()
    raise AssertionError(name)


class OsmDataTest(unittest.TestCase):
    ROUTES = {
        "hannover_robert_enke_strasse": ("hannover_robert_enke_context", [27095856, 1540868152, 681074694], "Robert-Enke-Straße"),
        "hannover_culemannstrasse": ("hannover_culemann_context", [1089017428, 59322751, 1089017427], "Culemannstraße"),
        "hannover_zoo_adenauerallee": ("hannover_zoo_context", [42747972, 1155218597, 961020636], "Adenauerallee"),
    }

    def test_routes_are_chained_from_the_documented_osm_ways(self) -> None:
        for name, (_, ways, street) in self.ROUTES.items():
            with self.subTest(name):
                feature = json.loads((DATA / f"{name}.geojson").read_text("utf8"))["features"][0]
                properties = feature["properties"]
                self.assertEqual(properties["osm_way_ids"], ways)
                self.assertEqual(properties["osm_way_id"], ways[0])
                self.assertIn(street, properties["name"])
                self.assertEqual(properties["license"], "ODbL-1.0")
                self.assertIn("OpenStreetMap", properties["source"])
                self.assertEqual(feature["geometry"]["type"], "LineString")
                self.assertGreater(len(feature["geometry"]["coordinates"]), 5)

    def test_context_maps_carry_license_and_the_expected_features(self) -> None:
        stadium = json.loads((DATA / "hannover_robert_enke_context.json").read_text("utf8"))
        city = json.loads((DATA / "hannover_culemann_context.json").read_text("utf8"))
        zoo = json.loads((DATA / "hannover_zoo_context.json").read_text("utf8"))
        for context in (stadium, city, zoo):
            self.assertEqual(context["license"], "ODbL-1.0")
            self.assertIn("OpenStreetMap", context["source"])
            self.assertGreater(len(context["roads"]), 100)
            self.assertGreater(len(context["buildings"]), 30)
        self.assertTrue(any(area["kind"] == "stadium" for area in stadium["areas"]))  # Heinz-von-Heiden-Arena
        self.assertTrue(any(road["name"] == "Robert-Enke-Straße" for road in stadium["roads"]))
        self.assertTrue(any(road["name"] == "Culemannstraße" for road in city["roads"]))
        self.assertTrue(any(area["kind"] == "zoo" and area.get("name") == "Erlebnis-Zoo Hannover" for area in zoo["areas"]))
        self.assertTrue(any(road["name"] == "Adenauerallee" for road in zoo["roads"]))

    def test_data_files_stay_compact(self) -> None:
        for path in DATA.glob("hannover_*"):
            self.assertLess(path.stat().st_size, 200_000, path.name)  # kein Roh-XML im Repository

    def test_scenarios_use_the_new_maps_and_stay_on_the_route(self) -> None:
        for name, street in (
            ("hannover_fussball_abpfiff", "Robert-Enke-Straße"),
            ("hannover_marathon_sperrung", "Culemannstraße"),
            ("hannover_marathon_laeufer", "Culemannstraße"),
            ("hannover_zootiere", "Adenauerallee"),
        ):
            with self.subTest(name):
                scenario = load(name)
                self.assertIn(street, scenario.road.name)
                self.assertGreater(scenario.road.length_m, scenario.ego_target_s_m)
                self.assertGreater(len(scenario.road.context["buildings"]), 30)
                note = json.loads((SCENARIOS / f"{name}.json").read_text("utf8"))["road"]["assumption_note"]
                self.assertIn("Szenarioannahme", note)  # erfundene Teile sind gekennzeichnet


class ImportRouteScriptTest(unittest.TestCase):
    XML = """<?xml version="1.0"?><osm version="0.6">
      <node id="1" lat="52.0" lon="9.0"/><node id="2" lat="52.0" lon="9.001"/>
      <node id="3" lat="52.0" lon="9.002"/><node id="4" lat="52.0" lon="9.003"/>
      <way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="tertiary"/><tag k="maxspeed" v="50"/></way>
      <way id="11"><nd ref="3"/><nd ref="2"/></way>
      <way id="12"><nd ref="3"/><nd ref="4"/></way>
      <way id="13"><nd ref="1"/><nd ref="4"/></way>
    </osm>"""

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "autonomy_recovery_sim/scripts/import_osm_route.py"), *args],
            capture_output=True, text=True, cwd=ROOT,
        )

    def test_ways_are_chained_and_reversed_when_needed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "a.osm", Path(directory) / "route.geojson"
            source.write_text(self.XML, encoding="utf8")
            result = self.run_script(str(source), str(target), "--ways", "10", "11", "12", "--name", "Testweg")
            self.assertEqual(result.returncode, 0, result.stderr)
            feature = json.loads(target.read_text("utf8"))["features"][0]
            longitudes = [point[0] for point in feature["geometry"]["coordinates"]]
            self.assertEqual(longitudes, [9.0, 9.001, 9.002, 9.003])  # Way 11 wurde gedreht
            self.assertEqual(feature["properties"]["osm_way_ids"], [10, 11, 12])
            self.assertEqual(feature["properties"]["maxspeed"], "50")
            reverse = self.run_script(str(source), str(target), "--ways", "10", "11", "12", "--name", "Testweg", "--reverse")
            self.assertEqual(reverse.returncode, 0)
            reversed_lon = [p[0] for p in json.loads(target.read_text("utf8"))["features"][0]["geometry"]["coordinates"]]
            self.assertEqual(reversed_lon, [9.003, 9.002, 9.001, 9.0])

    def test_non_contiguous_or_unknown_ways_fail_with_a_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "a.osm", Path(directory) / "route.geojson"
            source.write_text(self.XML, encoding="utf8")
            gap = self.run_script(str(source), str(target), "--ways", "10", "12", "--name", "x")
            self.assertNotEqual(gap.returncode, 0)
            self.assertIn("setzt nicht am Ende", gap.stderr)
            unknown = self.run_script(str(source), str(target), "--ways", "99", "--name", "x")
            self.assertNotEqual(unknown.returncode, 0)
            self.assertIn("steht nicht in der OSM-Datei", unknown.stderr)


class FootballTest(unittest.TestCase):
    def test_a_crowd_stops_the_vehicle_long_enough_to_call_the_agent(self) -> None:
        engine, session = first_session("hannover_fussball_abpfiff")
        self.assertGreaterEqual(session.context["ego"]["stopped_for_s"], 3.0)
        users = session.call_tool("check_vulnerable_road_users")
        self.assertTrue(users["conflict"])
        self.assertGreaterEqual(len(users["actor_ids"]), 2)

    def test_the_vehicle_never_collides_with_the_crowd_and_keeps_its_distance(self) -> None:
        engine = SimulationEngine(load("hannover_fussball_abpfiff"), agent=heuristic_agent)
        while not engine.done:
            engine.step()
        self.assertFalse(engine.collision)
        self.assertGreater(engine.minimum_clearance_m, 0.5)

    def test_waiting_resolves_it_and_calling_the_control_room_does_not_help(self) -> None:
        scenario = load("hannover_fussball_abpfiff")
        waited = run(scenario, *[command("WAIT", duration_s=10)] * 8)
        self.assertEqual(waited.outcome, "resolved")
        self.assertTrue(waited.command_correct and waited.within_budget and waited.reached_goal)
        call = run(scenario, command("REQUEST_REMOTE_ASSISTANCE", reason_code="AMBIGUOUS_SCENE"))
        self.assertEqual(call.commands[0]["outcome"], "NO_OPERATOR_SOLUTION")
        self.assertFalse(call.command_correct)
        self.assertFalse(call.within_budget)

    def test_the_baseline_waits_correctly(self) -> None:
        result = run_scenario(SCENARIOS / "hannover_fussball_abpfiff.json", agent=heuristic_agent, agent_name="baseline")
        self.assertTrue(result.command_correct and result.within_budget)
        self.assertFalse(result.collision)


class VulnerableUserBehaviourTest(unittest.TestCase):
    def test_the_autopilot_approaches_pedestrians_and_cyclists_carefully(self) -> None:
        engine = SimulationEngine(load("hannover_radverkehr"))
        speeds = []
        while engine.time_s < 12.0:
            engine.step()
            s = engine.ego_route_state[0]
            if 68.0 <= s <= 80.0:
                speeds.append(engine.ego.speed_mps)
        self.assertTrue(speeds)
        self.assertLess(max(speeds), 3.6)  # Vorsichtsgeschwindigkeit nahe Radverkehr

    def test_a_pedestrian_alongside_the_ego_still_blocks(self) -> None:
        engine = SimulationEngine(load("hannover_fussball_abpfiff"))
        s, d, _, _ = engine.ego_route_state
        engine.traffic[0].vehicle.x_m, engine.traffic[0].vehicle.y_m, _ = engine.scenario.road.to_xy(s + 1.0, -1.0)
        blocker = engine._blocking_actor(s, d)
        self.assertIsNotNone(blocker)
        self.assertEqual(blocker.spec.kind, "pedestrian")


class MarathonTest(unittest.TestCase):
    def test_the_map_does_not_know_the_closure_but_the_scene_shows_it(self) -> None:
        engine, session = first_session("hannover_marathon_sperrung")
        self.assertFalse(session.call_tool("get_route_state")["route_blocked"])
        blocker = session.call_tool("get_blocker")
        self.assertEqual(blocker["kind"], "barrier")
        self.assertIn("Marathon", blocker["scene_description"])

    def test_the_road_is_completely_blocked_so_no_maneuver_is_possible(self) -> None:
        scenario = load("hannover_marathon_sperrung")
        barrier = ActorSpec("marathon_barrier", "barrier", 240.0, 0.0, 0.0, 1, 0.6, 10.0)
        tools = SituationTools(scenario, EgoState(232.0, -1.75, 0.0, 4.71, 1.99), (ActorState.from_spec(barrier),), None, WorldFacts())
        # Eine Absperrung darf nie umfahren werden, auf keiner Seite.
        for side in ("LEFT", "RIGHT"):
            request = parse_command(command("NUDGE_AROUND_OBSTACLE", side=side, max_longitudinal_distance_m=30))
            with self.subTest(side), self.assertRaisesRegex(CommandError, "ROAD_CLOSED"):
                check_command(request, tools=tools, facts=tools.facts)

    def test_map_check_then_replan_reroutes_and_the_control_room_cannot_remove_barriers(self) -> None:
        scenario = load("hannover_marathon_sperrung")
        good = run(scenario, command("REQUEST_ADDITIONAL_INFORMATION", topic="MAP_CONSISTENCY", duration_s=3), command("REPLAN_ROUTE"))
        self.assertEqual(good.outcome, "rerouted")
        self.assertTrue(good.command_correct and good.within_budget and not good.collision)
        call = run(scenario, command("REQUEST_REMOTE_ASSISTANCE", reason_code="BLOCKED_ROUTE"))
        self.assertEqual(call.commands[0]["outcome"], "NO_OPERATOR_SOLUTION")
        self.assertFalse(call.command_correct)

    def test_the_runner_stream_and_the_ambiguous_marshal(self) -> None:
        engine, session = first_session("hannover_marathon_laeufer")
        blocker = session.call_tool("get_blocker")
        self.assertEqual(blocker["actor_id"], "marshal")
        self.assertIn("nicht eindeutig", blocker["scene_description"])
        scenario = load("hannover_marathon_laeufer")
        waited = run(scenario, *[command("WAIT", duration_s=10)] * 10)
        self.assertEqual(waited.outcome, "resolved")
        self.assertTrue(waited.command_correct and waited.within_budget and not waited.collision)
        call = run(scenario, command("REQUEST_REMOTE_ASSISTANCE", reason_code="AMBIGUOUS_SCENE"))
        self.assertEqual(call.outcome, "remote_resolved")
        self.assertFalse(call.within_budget)  # schneller, aber teurer

    def test_hannover_set_with_the_baseline(self) -> None:
        batch = run_batch(ROOT / "autonomy_recovery_sim/scenario_sets/hannover.txt", agent=heuristic_agent, agent_name="baseline")
        passed = {item.result.scenario_id for item in batch.evaluations if item.passed}
        self.assertEqual(passed, {"hannover_fussball_abpfiff"})
        self.assertEqual(batch.to_dict()["summary"]["collision_count"], 0)


if __name__ == "__main__":
    unittest.main()
