from __future__ import annotations

import json
import math
import struct
import tempfile
import time
import unittest
from unittest.mock import patch
from dataclasses import replace
from pathlib import Path

from autonomy_recovery_sim.agent_contract import AgentContractError, validate_agent_decision
from autonomy_recovery_sim.agent_loader import load_agent
from autonomy_recovery_sim.agent_session import AgentSession
from autonomy_recovery_sim.batch import discover_scenarios, run_batch
from autonomy_recovery_sim.dynamics import Control
from autonomy_recovery_sim.engine import SimulationEngine
from autonomy_recovery_sim.live import LiveSimulation, resolve_static_path
from autonomy_recovery_sim.llm_agent import LLMConfig, LLMConfigurationError, OpenAICompatibleAgent
from autonomy_recovery_sim.models import ActorSpec, ActorState, EgoState
from autonomy_recovery_sim.perception import PerceptionModel, _rectangle, _silhouette_points
from autonomy_recovery_sim.policy import heuristic_agent
from autonomy_recovery_sim.render import write_svg
from autonomy_recovery_sim.road import Road, load_road
from autonomy_recovery_sim.scenario import load_scenario
from autonomy_recovery_sim.simulation import run_scenario


ROOT = Path(__file__).resolve().parents[1]


class AutonomyRecoverySimTest(unittest.TestCase):
    def test_hannover_map_has_expected_length(self) -> None:
        road = load_road(
            ROOT / "autonomy_recovery_sim/data/hannover_wilhelm_busch_strasse.geojson",
            lane_width_m=3.5,
            center_marking="dashed",
        )
        self.assertGreater(road.length_m, 290.0)
        self.assertLess(road.length_m, 305.0)
        self.assertEqual(road.osm_way_id, 4289539)

    def test_hannover_scenario_loads_city_context(self) -> None:
        scenario = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        context = scenario.road.context
        self.assertIsNotNone(context)
        assert context is not None
        self.assertGreater(len(context["roads"]), 100)
        self.assertGreater(len(context["buildings"]), 100)
        self.assertEqual(context["license"], "ODbL-1.0")
        self.assertGreater(sum(building["height_m"] > 0 for building in context["buildings"]), 180)
        self.assertGreater(
            sum(building["height_source"].startswith("osm:") for building in context["buildings"]),
            150,
        )
        self.assertTrue(any(building["is_part"] for building in context["buildings"]))

    def test_recovery_config_is_loaded(self) -> None:
        scenario = load_scenario(
            ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json"
        )
        self.assertEqual(scenario.stuck_after_s, 3.0)

    def test_free_road_releases_and_passes(self) -> None:
        result = run_scenario(
            ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json",
            agent=heuristic_agent,
            agent_name="baseline",
        )
        self.assertEqual(result.command, "NUDGE_AROUND_OBSTACLE")
        self.assertTrue(result.command_correct)
        self.assertTrue(result.liberated)
        self.assertFalse(result.collision)
        self.assertIn("recovery_requested", {event.event for event in result.events})

    def test_oncoming_traffic_denies_release(self) -> None:
        result = run_scenario(
            ROOT / "autonomy_recovery_sim/scenarios/hannover_gegenverkehr.json",
            agent=heuristic_agent,
            agent_name="baseline",
        )
        self.assertEqual(result.command, "WAIT")
        self.assertTrue(result.command_correct)
        self.assertFalse(result.liberated)
        self.assertFalse(result.collision)

    def test_outputs_are_machine_readable_and_visualizable(self) -> None:
        result = run_scenario(
            ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json",
            agent=heuristic_agent,
            agent_name="baseline",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result.write_json(root / "result.json")
            write_svg(result, root / "replay.svg")
            payload = json.loads((root / "result.json").read_text())
            self.assertEqual(payload["scenario_id"], "hannover_frei")
            self.assertIn("OpenStreetMap", payload["map"]["source"])
            self.assertIn("OpenStreetMap-Mitwirkende", (root / "replay.svg").read_text())

    def test_manual_steering_changes_vehicle_path(self) -> None:
        scenario = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        engine = SimulationEngine(scenario)
        engine.set_mode("manual")
        initial_yaw = engine.ego.yaw_rad
        for _ in range(30):
            engine.step(Control(throttle=1.0, steering=0.55))
        self.assertGreater(abs(engine.ego.yaw_rad - initial_yaw), 0.05)
        self.assertGreater(abs(engine.ego_route_state[1] - scenario.ego_lane_d_m), 0.2)

    def test_oncoming_vehicle_moves_continuously_towards_ego(self) -> None:
        scenario = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_gegenverkehr.json")
        engine = SimulationEngine(scenario)
        start_s = engine._actor_states()[1].s_m
        for _ in range(20):
            engine.step()
        end_s = engine._actor_states()[1].s_m
        self.assertLess(end_s, start_s - 5.0)

    def test_live_commands_control_mode_pause_and_step(self) -> None:
        scenario = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        live = LiveSimulation(scenario)
        state = live.command({"mode": "manual", "action": "step", "throttle": 1.0})
        self.assertEqual(state["mode"], "manual")
        self.assertGreater(state["time_s"], 0.0)
        self.assertTrue(state["paused"])
        self.assertEqual(state["ego"]["kind"], "minibus")
        self.assertGreater(state["ego"]["length_m"], 4.6)

    def test_live_start_command_is_immediate_and_idempotent(self) -> None:
        scenario = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        live = LiveSimulation(scenario)
        self.assertTrue(live.snapshot()["paused"])
        self.assertFalse(live.command({"action": "start"})["paused"])
        self.assertFalse(live.command({"action": "start"})["paused"])

    def test_live_snapshot_exposes_perception_diagnostics(self) -> None:
        scenario = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        self.assertEqual(scenario.perception_range_m, 60.0)
        state = LiveSimulation(scenario).snapshot()
        self.assertEqual(state["perception"]["update_rate_hz"], 2.0)
        self.assertIn("target_lane_visible_m", state["perception"]["visibility"])
        self.assertIn("effective_range_m", state["perception"]["visibility"])
        self.assertTrue(state["actors"])
        actor = state["actors"][0]
        self.assertIn("perception_status", actor)
        self.assertIn("ground_truth_perception_status", actor)
        self.assertIn("visible_fraction", actor)
        self.assertIn("detected", actor)

    def test_start_restarts_a_completed_live_scenario(self) -> None:
        scenario = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_gegenverkehr.json")
        # Mit Agent: Ohne ihn wartet die Recovery Console auf einen Menschen und die Zeit steht still.
        live = LiveSimulation(scenario, agent=heuristic_agent, agent_name="baseline")
        while not live.engine.done:
            live.engine.step()
        self.assertTrue(live.snapshot()["done"])
        state = live.command({"action": "start"})
        self.assertFalse(state["done"])
        self.assertFalse(state["paused"])
        self.assertEqual(state["time_s"], 0.0)

    def test_live_worker_advances_after_start_and_stops_after_pause(self) -> None:
        scenario = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        live = LiveSimulation(scenario)
        live.start_worker()
        try:
            live.command({"action": "start"})
            deadline = time.monotonic() + 1.0
            while live.snapshot()["time_s"] <= 0.0 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertGreater(live.snapshot()["time_s"], 0.0)

            paused = live.command({"action": "pause"})
            paused_at = paused["time_s"]
            time.sleep(0.15)
            self.assertTrue(live.snapshot()["paused"])
            self.assertEqual(live.snapshot()["time_s"], paused_at)
        finally:
            live.stop_worker()

    def test_live_ui_offers_perspective_and_topdown_views(self) -> None:
        html = (ROOT / "autonomy_recovery_sim/web/index.html").read_text(encoding="utf8")
        self.assertIn('id="perspectiveView"', html)
        self.assertIn('id="mapView"', html)
        self.assertIn('id="perspectiveTools"', html)
        self.assertIn('id="cameraZoomIn"', html)
        self.assertIn('id="resetPerspective"', html)
        self.assertIn('id="zoomIn"', html)
        self.assertIn('id="resetMap"', html)
        self.assertIn('<span id="mapZoom" aria-live="polite">800 %</span>', html)
        self.assertIn('aria-label="Ego-Fahrzeug zentriert halten"', html)
        self.assertIn('id="perceptionToggle"', html)
        self.assertIn('id="perceptionPanel"', html)
        self.assertIn('id="runButton" class="primary is-loading"', html)
        self.assertNotIn('id="runButton" class="primary" type="button" disabled', html)
        self.assertLess(
            html.index("__autonomyRecoverySimEarlyRunCapture"),
            html.index('id="runButton"'),
        )

        javascript = (ROOT / "autonomy_recovery_sim/web/app.js").read_text(encoding="utf8")
        self.assertIn("const mapCamera = { zoom: 8", javascript)
        self.assertIn("followEgo: true", javascript)
        self.assertIn("if (mapCamera.followEgo)", javascript)
        self.assertIn('setAttribute("aria-pressed", String(mapCamera.followEgo))', javascript)
        self.assertIn('addEventListener("click", centerMapOnEgo)', javascript)
        self.assertIn("const perspectiveCamera = { yawOffset: 0, pitch: .19, zoom: 1 }", javascript)
        self.assertIn('addEventListener("click", resetPerspectiveCamera)', javascript)
        self.assertIn("perspectiveCamera.yawOffset = wrapCameraAngle", javascript)
        self.assertIn("state.maneuver_aborted", javascript)
        self.assertIn("state.abort_stabilized", javascript)
        self.assertIn("state.minimum_risk_completion", javascript)
        self.assertIn('state.agent?.status === "waiting_for_agent"', javascript)
        self.assertIn('title.textContent = "Autonome Anfahrt"', javascript)
        self.assertIn("function drawTopDownPerception(transform)", javascript)
        self.assertIn("function drawPerspectivePerception(project)", javascript)
        self.assertIn("function visibleSensorPolygon(origin, range, heading, fov)", javascript)
        self.assertIn("function perceptionOccluders(origin, range)", javascript)
        self.assertIn("function perspectiveSensorFan(points, origin, project, fill, closed)", javascript)
        self.assertIn("function sensorOrigins()", javascript)
        self.assertIn("function visibleSensorPolygons(origins, range, heading, fov)", javascript)
        self.assertIn("visibleSensorPolygons(sensorOrigins()", javascript)
        self.assertIn("perspectiveSensorFan(area, origins[index]", javascript)
        self.assertIn("sensor_origins_xy", javascript)
        self.assertNotIn("laneWidth * 2.18", javascript)
        self.assertNotIn("Sichtgrenze", javascript)
        self.assertIn("actor.perception_status", javascript)
        self.assertIn("async function toggleSimulationRunState(requestedAction = null)", javascript)
        self.assertIn("if (pollPromise) return pollPromise", javascript)
        self.assertNotIn("state || await poll()", javascript)
        self.assertIn('!state || state.done || state.paused ? "start" : "pause"', javascript)
        self.assertIn('runButton.addEventListener("click", () => toggleSimulationRunState())', javascript)
        self.assertIn("const runToggleGuardMs = 450", javascript)
        self.assertIn(
            "if (!requestedAction && lastRunIntent && action !== lastRunIntent",
            javascript,
        )
        self.assertIn("lastRunIntent = null;", javascript)
        self.assertIn("requestAnimationFrame(draw);\n  }\n}", javascript)
        self.assertIn('runButton.classList.toggle("is-loading", runCommandInFlight)', javascript)
        self.assertIn('document.removeEventListener("click", window.__autonomyRecoverySimEarlyRunCapture, true)', javascript)
        self.assertIn('toggleSimulationRunState("start")', javascript)

    def test_ego_minibus_asset_has_target_dimensions_and_is_loaded(self) -> None:
        asset_path = ROOT / "autonomy_recovery_sim/vehicles/ego_minibus.glb"
        data = asset_path.read_bytes()
        magic, version, declared_length = struct.unpack_from("<4sII", data)
        self.assertEqual((magic, version, declared_length), (b"glTF", 2, len(data)))
        chunks: dict[int, bytes] = {}
        offset = 12
        while offset < len(data):
            length, kind = struct.unpack_from("<II", data, offset)
            offset += 8
            chunks[kind] = data[offset : offset + length]
            offset += length
        document = json.loads(chunks[0x4E4F534A].decode("utf8").rstrip("\x00 "))
        primitive = document["meshes"][0]["primitives"][0]
        position = document["accessors"][primitive["attributes"]["POSITION"]]
        dimensions = [position["max"][axis] - position["min"][axis] for axis in range(3)]
        self.assertAlmostEqual(dimensions[0], 1.99, places=4)
        self.assertAlmostEqual(dimensions[1], 1.94, places=4)
        self.assertAlmostEqual(dimensions[2], 4.71, places=4)
        self.assertAlmostEqual(position["min"][1], 0.0, places=4)
        self.assertLessEqual(document["accessors"][primitive["indices"]]["count"] // 3, 20_000)
        self.assertEqual(resolve_static_path("/vehicles/ego_minibus.glb"), asset_path)

        html = (ROOT / "autonomy_recovery_sim/web/index.html").read_text(encoding="utf8")
        self.assertLess(html.index('/vehicle_asset.js'), html.index('/app.js'))
        javascript = (ROOT / "autonomy_recovery_sim/web/app.js").read_text(encoding="utf8")
        self.assertIn('AutonomyRecoveryVehicleAssets.load("/vehicles/ego_minibus.glb")', javascript)
        self.assertIn("prozeduraler Fallback bleibt aktiv", javascript)

    def test_live_ui_offers_the_recovery_console_without_hijacking_keys(self) -> None:
        html = (ROOT / "autonomy_recovery_sim/web/index.html").read_text(encoding="utf8")
        self.assertIn("<title>AutonomyRecoverySim", html)
        self.assertIn("Agentic Autonomy Recovery", html)
        for element in ("recoveryConsole", "consoleCommand", "consoleParams", "consoleEvidence", "consoleSubmit", "consoleError"):
            self.assertIn(f'id="{element}"', html)
        javascript = (ROOT / "autonomy_recovery_sim/web/app.js").read_text(encoding="utf8")
        self.assertIn('recovery_requested: "Stillstandsmonitor hat Autonomy Recovery angefordert"', javascript)
        self.assertIn('action: "console_submit"', javascript)
        self.assertIn('action: "console_evidence"', javascript)
        # Eingaben in der Konsole duerfen keine Fahr- oder Zoomtasten ausloesen.
        self.assertIn("isTypingTarget(event)", javascript)
        self.assertLess(
            javascript.index("if (isTypingTarget(event)) return;"),
            javascript.index('["KeyW", "KeyA", "KeyS", "KeyD"'),
        )

    def test_perspective_view_projects_right_lane_to_screen_right(self) -> None:
        javascript = (ROOT / "autonomy_recovery_sim/web/app.js").read_text(encoding="utf8")
        self.assertIn("x: width / 2 - lateral * focal / depth", javascript)

    def test_perspective_view_extrudes_osm_buildings(self) -> None:
        javascript = (ROOT / "autonomy_recovery_sim/web/app.js").read_text(encoding="utf8")
        self.assertIn("function drawPerspectiveBuilding(building, project)", javascript)
        self.assertIn("project(point[0], point[1], height)", javascript)

    def test_scenario_matrix_passes_batch_evaluation(self) -> None:
        batch = run_batch(
            ROOT / "autonomy_recovery_sim/scenarios",
            agent=heuristic_agent,
            agent_name="baseline",
        )
        payload = batch.to_dict()
        self.assertEqual(payload["summary"]["scenario_count"], 61)
        self.assertEqual(payload["summary"]["collision_count"], 0)
        self.assertEqual(payload["summary"]["successful_abort_count"], 4)
        self.assertEqual(payload["summary"]["stabilized_abort_count"], 4)
        # Die Baseline loest bewusst nicht alles: Diese Faelle lassen Raum fuer bessere Agenten.
        failed = {item.result.scenario_id for item in batch.evaluations if not item.passed}
        self.assertEqual(
            failed,
            {
                "hannover_ampel_ausgefallen",
                "hannover_doppelparker_belegt",
                # Mehrstufig: Die Baseline schafft den ersten Schritt, aber nicht den ganzen Weg.
                "hannover_fussgaenger_vor_lieferwagen",
                "hannover_zwei_hindernisse",
                "hannover_karte_veraltet_fahrgaeste",
                "hannover_ampel_dunkel_lieferwagen",
                "hannover_karte_veraltet",
                "hannover_leitstelle_offline",
                "hannover_lieferwagen_faehrt_los",
                "hannover_lokalisierung_drift",
                "hannover_marathon_laeufer",
                "hannover_marathon_sperrung",
                "hannover_passagier_absetzen",
                "hannover_phantom_hindernis",
                "hannover_veraltete_daten",
                # VLA-Faelle: ohne Objektklasse und bei falscher Selbstauskunft des Fahrstacks.
                "hannover_vla_ampel_dunkel",
                "hannover_vla_karton",
                "hannover_vla_phantom",
                "hannover_werkzeug_timeout",
                "hannover_werkzeugbudget_knapp",
                "hannover_stau_loest_sich",
                "hannover_ziel_gesperrt",
            },
        )

    def test_public_scenario_manifest_is_resolvable(self) -> None:
        paths = discover_scenarios(ROOT / "autonomy_recovery_sim/scenario_sets/public.txt")
        self.assertEqual(len(paths), 25)
        self.assertTrue(all(path.suffix == ".json" and path.is_file() for path in paths))
        self.assertTrue((ROOT / "autonomy_recovery_sim/QUICKSTART.md").is_file())
        self.assertTrue((ROOT / "autonomy_recovery_sim/ASSIGNMENT.md").is_file())

    def test_grazing_sliver_behind_a_blocker_stays_occluded(self) -> None:
        """Ein Ecksensor sieht knapp am LKW vorbei eine Ecke des Radfahrers.

        Frueher genuegte dieser Splitter fuer "teilweise sichtbar" samt voller
        Detektion - im UI trug damit ein Objekt ein Sichtbarkeitsetikett, das im
        Bild komplett hinter dem LKW lag.
        """
        scenario = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        ego = EgoState(80.86, -1.70, 0.0, 4.71, 1.99)
        blocker = ActorSpec("blocker", "truck", 92.0, -1.75, 0.0, 1, 7.5, 2.5)
        cyclist = ActorSpec("cyclist", "bicycle", 102.0, -0.3, 0.0, 1, 1.8, 0.6)
        actors = (ActorState.from_spec(blocker), ActorState.from_spec(cyclist))

        self.assertEqual(scenario.perception_min_detectable_fraction, 0.3)
        snapshot = PerceptionModel(scenario).observe(0.0, ego, actors)
        self.assertEqual(snapshot.ground_truth_status["cyclist"], "occluded")
        self.assertNotIn("cyclist", {actor.spec.actor_id for actor in snapshot.actors})

        sensitive = replace(scenario, perception_min_detectable_fraction=0.01)
        exposed = PerceptionModel(sensitive).observe(0.0, ego, actors)
        self.assertEqual(exposed.ground_truth_status["cyclist"], "partially_visible")
        self.assertLess(exposed.actor_metadata["cyclist"]["visible_fraction"], 0.3)

    def test_visible_fraction_samples_the_whole_silhouette(self) -> None:
        scenario = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        ego = EgoState(20.0, -1.75, 0.0, 4.71, 1.99)
        car = ActorSpec("car", "car", 60.0, -1.75, 0.0, 1, 4.5, 1.8)
        snapshot = PerceptionModel(scenario).observe(
            0.0,
            ego,
            (ActorState.from_spec(car),),
        )
        # Mittelpunkt plus vier Ecken ergaeben nur Vielfache von 0,2.
        self.assertEqual(snapshot.ground_truth_status["car"], "visible")
        self.assertEqual(len(_silhouette_points((0.0, 0.0), _rectangle((0.0, 0.0), 0.0, 4.0, 2.0))), 17)

    def test_sensor_origins_stay_on_the_vehicle_corners(self) -> None:
        """Der seitliche Versatz traegt die Freigabeentscheidung der Matrix.

        Ohne ihn ist die Gegenfahrbahn hinter jedem stehenden Blocker blind.
        """
        scenario = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        ego = EgoState(80.0, -1.75, 0.0, 4.71, 1.99)
        origins = PerceptionModel(scenario)._sensor_origins(ego)
        self.assertEqual(len(origins), 4)
        center_x, center_y, _ = scenario.road.to_xy(ego.s_m, ego.d_m)
        offsets = sorted(
            round(math.dist((center_x, center_y), origin), 2) for origin in origins
        )
        self.assertEqual(len(set(offsets)), 1)
        self.assertGreater(offsets[0], 2.0)

    def test_perception_visibility_report_publishes_sensor_origins(self) -> None:
        state = LiveSimulation(
            load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        ).snapshot()
        origins = state["perception"]["visibility"]["sensor_origins_xy"]
        self.assertEqual(len(origins), 4)
        self.assertTrue(all(len(origin) == 2 for origin in origins))

    def test_occluded_actor_is_not_exposed_to_situation_tools(self) -> None:
        scenario = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        ego = EgoState(81.19, -1.715, 0.0, 4.71, 1.99)
        blocker = ActorSpec("blocker", "truck", 92.0, -1.75, 0.0, 1, 7.5, 2.5)
        cyclist = ActorSpec("cyclist", "bicycle", 102.0, -0.3, 0.0, 1, 1.8, 0.6)
        snapshot = PerceptionModel(scenario).observe(
            14.0,
            ego,
            (ActorState.from_spec(blocker), ActorState.from_spec(cyclist)),
        )
        self.assertEqual(snapshot.ground_truth_status["cyclist"], "occluded")
        self.assertNotIn("cyclist", {actor.spec.actor_id for actor in snapshot.actors})

    def test_partial_visibility_and_short_lived_tracks_are_reported(self) -> None:
        scenario = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        ego = EgoState(82.64, -1.715, 0.0, 4.71, 1.99)
        van = ActorSpec("van", "van", 110.0, 1.75, 0.0, -1, 6.5, 2.4, "parked")
        car = ActorSpec("car", "car", 125.0, 1.75, 0.0, -1, 4.5, 1.8)
        foreground = ActorSpec("foreground", "car", 92.0, -1.75, 0.0, 1, 4.5, 1.8)
        model = PerceptionModel(scenario)
        partial = model.observe(
            0.0,
            ego,
            (
                ActorState.from_spec(foreground),
                ActorState.from_spec(van),
                ActorState.from_spec(car),
            ),
        )
        self.assertEqual(partial.ground_truth_status["car"], "partially_visible")

        blocker = ActorSpec("blocker", "truck", 92.0, -1.75, 0.0, 1, 7.5, 2.5)
        cyclist = ActorSpec("cyclist", "bicycle", 102.0, -0.3, 0.0, 1, 1.8, 0.6)
        tracking = PerceptionModel(scenario)
        tracking.observe(0.0, ego, (ActorState.from_spec(cyclist),))
        hidden = (ActorState.from_spec(blocker), ActorState.from_spec(cyclist))
        tracked = tracking.observe(1.0, ego, hidden)
        self.assertEqual(tracked.actor_metadata["cyclist"]["status"], "tracked")
        self.assertEqual(tracked.actor_metadata["cyclist"]["track_age_s"], 1.0)
        expired = tracking.observe(3.1, ego, hidden)
        self.assertNotIn("cyclist", {actor.spec.actor_id for actor in expired.actors})

    def test_configured_sensor_field_of_view_hides_rear_actor(self) -> None:
        scenario = replace(
            load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json"),
            perception_horizontal_fov_deg=120.0,
        )
        ego = EgoState(82.0, -1.75, 0.0, 4.71, 1.99)
        rear_actor = ActorSpec("rear", "car", 60.0, -1.75, 0.0, 1, 4.5, 1.8)
        snapshot = PerceptionModel(scenario).observe(
            0.0,
            ego,
            (ActorState.from_spec(rear_actor),),
        )
        self.assertEqual(snapshot.ground_truth_status["rear"], "outside_fov")
        self.assertEqual(snapshot.actors, ())

    def test_osm_style_building_footprint_occludes_actor(self) -> None:
        base = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        road = Road(
            name="synthetic",
            points_xy=((0.0, 0.0), (100.0, 0.0)),
            lane_width_m=3.5,
            center_marking="dashed",
            source="test",
            source_url="",
            context={
                "buildings": [
                    {
                        "points_xy": [
                            [9.0, -3.0],
                            [11.0, -3.0],
                            [11.0, 3.0],
                            [9.0, 3.0],
                            [9.0, -3.0],
                        ],
                        "height_m": 9.0,
                        "min_height_m": 0.0,
                    }
                ]
            },
        )
        scenario = replace(base, road=road)
        actor = ActorSpec("behind_building", "car", 20.0, 0.0, 0.0, 1, 4.5, 1.8)
        snapshot = PerceptionModel(scenario).observe(
            0.0,
            EgoState(0.0, 0.0, 0.0, 4.71, 1.99),
            (ActorState.from_spec(actor),),
        )
        self.assertEqual(
            snapshot.ground_truth_status["behind_building"],
            "occluded",
        )
        self.assertEqual(snapshot.actors, ())

    def test_occlusion_scenarios_cover_denial_and_dynamic_reappearance(self) -> None:
        cases = {
            "hannover_verdeckung_gegenverkehr.json": ("WAIT", "waiting", None),
            "hannover_verdeckung_radverkehr.json": (
                "NUDGE_AROUND_OBSTACLE",
                "aborted",
                "collision_risk",
            ),
            "hannover_verdeckung_auftauchen.json": (
                "NUDGE_AROUND_OBSTACLE",
                "aborted",
                "oncoming_traffic",
            ),
        }
        for filename, expected in cases.items():
            with self.subTest(filename=filename):
                result = run_scenario(
                    ROOT / "autonomy_recovery_sim/scenarios" / filename,
                    agent=heuristic_agent,
                    agent_name="baseline",
                )
                self.assertEqual(
                    (result.command, result.outcome, result.abort_reason),
                    expected,
                )
                self.assertFalse(result.collision)
                if result.outcome == "aborted":
                    self.assertTrue(result.abort_stabilized)
                tool_results = {
                    entry["name"]: entry["result"]
                    for entry in result.agent_trace
                    if entry["type"] == "tool_call"
                }
                if filename == "hannover_verdeckung_gegenverkehr.json":
                    self.assertIn("occlusion", tool_results["get_visibility"]["limited_by"])
                elif filename == "hannover_verdeckung_radverkehr.json":
                    self.assertNotIn(
                        "hidden_cyclist",
                        tool_results["check_vulnerable_road_users"]["actor_ids"],
                    )
                elif filename == "hannover_verdeckung_auftauchen.json":
                    self.assertFalse(tool_results["check_oncoming_traffic"]["conflict"])

    def test_dynamic_hazards_abort_and_stabilize_maneuver(self) -> None:
        cases = {
            "hannover_abbruch_gegenverkehr.json": "oncoming_traffic",
            "hannover_abbruch_blocker.json": "blocker_moves",
        }
        for filename, expected_reason in cases.items():
            with self.subTest(filename=filename):
                result = run_scenario(
                    ROOT / "autonomy_recovery_sim/scenarios" / filename,
                    agent=heuristic_agent,
                    agent_name="baseline",
                )
                self.assertEqual(result.command, "NUDGE_AROUND_OBSTACLE")
                self.assertEqual(result.outcome, "aborted")
                self.assertEqual(result.abort_reason, expected_reason)
                self.assertTrue(result.abort_stabilized)
                self.assertFalse(result.collision)
                self.assertTrue(
                    any(event.event == "maneuver_aborted" for event in result.events)
                )
                self.assertTrue(
                    any(event.event == "abort_stabilized" for event in result.events)
                )

    def test_agent_observation_is_logged_and_json_serializable(self) -> None:
        result = run_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        observations = [event.details for event in result.events if event.event == "agent_observation"]
        self.assertEqual(len(observations), 1)
        observation = observations[0]
        self.assertEqual(observation["schema_version"], "3.0")
        self.assertNotIn("tools", observation)
        self.assertEqual(
            {tool["name"] for tool in observation["available_tools"]},
            {
                "get_blocker",
                "get_center_marking",
                "check_oncoming_traffic",
                "check_rear_traffic",
                "check_vulnerable_road_users",
                "get_lateral_clearance",
                "get_visibility",
                "get_route_state",
                "get_mission_context",
                "get_recovery_history",
                "get_sensor_health",
                "get_traffic_control",
            },
        )
        # 24 Befehle, ohne die zwei der Unfallabwicklung (nur advisory/off).
        self.assertEqual(len(observation["available_commands"]), 22)
        json.dumps(observation)

    def test_default_run_drives_autonomously_then_waits_for_agent(self) -> None:
        result = run_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        self.assertEqual(result.agent_name, "none")
        self.assertEqual(result.agent_status, "waiting_for_agent")
        self.assertEqual(result.command, "NONE")
        self.assertEqual(result.outcome, "waiting_for_agent")
        self.assertFalse(result.liberated)
        self.assertFalse(result.collision)
        self.assertGreater(result.final_s_m, 75.0)
        self.assertLess(result.final_s_m, 90.0)
        self.assertTrue(any(event.event == "agent_requested" for event in result.events))

    def test_agent_is_called_only_after_deadlock_detection(self) -> None:
        sessions: list[AgentSession] = []

        def student_agent(session: AgentSession):
            sessions.append(session)
            return session.submit_decision(
                {
                    "command": "WAIT",
                    "parameters": {"duration_s": 5.0},
                    "reason": "Testentscheidung",
                }
            )

        result = run_scenario(
            ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json",
            agent=student_agent,
            agent_name="student-test",
        )
        # Nach jedem beendeten WAIT wird der Agent bei fortbestehendem Stillstand erneut gefragt.
        self.assertGreaterEqual(len(sessions), 2)
        self.assertEqual(sessions[1].context["commands_used"], 1)
        context = sessions[0].context
        self.assertGreater(context["time_s"], 10.0)
        self.assertGreaterEqual(context["ego"]["stopped_for_s"], 3.0)
        self.assertEqual(result.agent_status, "decided")

    def test_baseline_uses_tools_and_records_trace(self) -> None:
        result = run_scenario(
            ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json",
            agent=heuristic_agent,
            agent_name="baseline",
        )
        tool_calls = [item for item in result.agent_trace if item["type"] == "tool_call"]
        attempts = [item for item in result.agent_trace if item["type"] == "decision_attempt"]
        self.assertEqual(len(tool_calls), 10)
        self.assertEqual(len({item["name"] for item in tool_calls}), 10)  # ohne get_sensor_health
        self.assertEqual(len(attempts), 1)
        self.assertTrue(attempts[0]["accepted"])

    def test_release_without_tool_evidence_fails_safe(self) -> None:
        def unsupported_release(session: AgentSession):
            return session.submit_decision(
                {
                    "command": "NUDGE_AROUND_OBSTACLE",
                    "parameters": {"side": "LEFT", "max_longitudinal_distance_m": 30.0},
                    "reason": "Unbelegte Freigabe",
                }
            )

        result = run_scenario(
            ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json",
            agent=unsupported_release,
            agent_name="unsupported-release",
        )
        self.assertEqual(result.agent_status, "error")
        self.assertEqual(result.command, "WAIT")
        self.assertIn("Werkzeugevidenz", result.agent_error)

    def test_tool_budget_is_enforced(self) -> None:
        def wasteful_agent(session: AgentSession):
            for _ in range(15):
                session.call_tool("get_blocker")

        result = run_scenario(
            ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json",
            agent=wasteful_agent,
            agent_name="wasteful",
        )
        self.assertEqual(result.agent_status, "error")
        self.assertIn("Werkzeugbudget", result.agent_error)
        self.assertEqual(
            sum(
                item["type"] == "tool_call" and item["session"] == 1
                for item in result.agent_trace
            ),
            14,
        )

    def test_optional_tool_horizon_uses_safe_default(self) -> None:
        observed: list[dict[str, object]] = []

        def checking_agent(session: AgentSession):
            observed.append(session.call_tool("check_oncoming_traffic"))
            return session.submit_decision(
                {"command": "WAIT", "parameters": {"duration_s": 5.0}, "reason": "Test"}
            )

        run_scenario(
            ROOT / "autonomy_recovery_sim/scenarios/hannover_gegenverkehr.json",
            agent=checking_agent,
            agent_name="horizon-test",
        )
        self.assertEqual(observed[0]["horizon_s"], 8.0)
        self.assertTrue(observed[0]["conflict"])

    def test_agent_can_correct_a_rejected_decision_attempt(self) -> None:
        def correcting_agent(session: AgentSession):
            try:
                session.submit_decision({"command": "WAIT"})
            except AgentContractError:
                pass
            return session.submit_decision(
                {
                    "command": "WAIT",
                    "parameters": {"duration_s": 5.0},
                    "reason": "Korrigierter Entscheidungsversuch",
                }
            )

        result = run_scenario(
            ROOT / "autonomy_recovery_sim/scenarios/hannover_gegenverkehr.json",
            agent=correcting_agent,
            agent_name="correcting-test",
        )
        attempts = [
            item
            for item in result.agent_trace
            if item["type"] == "decision_attempt" and item["session"] == 1
        ]
        self.assertEqual(result.agent_status, "decided")
        self.assertEqual(len(attempts), 2)
        self.assertFalse(attempts[0]["accepted"])
        self.assertTrue(attempts[1]["accepted"])

    def test_agent_loader_requires_explicit_baseline(self) -> None:
        self.assertIsNone(load_agent("none").policy)
        self.assertIs(load_agent("baseline").policy, heuristic_agent)
        self.assertTrue(callable(load_agent("llm").policy))
        loaded = load_agent("autonomy_recovery_sim.student_agent:decide")
        self.assertEqual(loaded.name, "autonomy_recovery_sim.student_agent:decide")
        self.assertTrue(callable(loaded.policy))

    def test_llm_configuration_requires_a_key_without_logging_it(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(LLMConfigurationError, "API-Schluessel"):
                LLMConfig.from_environment()

    def test_llm_configuration_uses_autonomy_recovery_names(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "AUTONOMY_RECOVERY_API_KEY": "new-key",
                "AUTONOMY_RECOVERY_MODEL": "new-model",
            },
            clear=True,
        ):
            config = LLMConfig.from_environment()
            self.assertEqual((config.api_key, config.model), ("new-key", "new-model"))

    def test_missing_llm_key_fails_safe_at_the_deadlock(self) -> None:
        llm_policy = load_agent("llm").policy
        assert llm_policy is not None
        with patch.dict("os.environ", {}, clear=True):
            result = run_scenario(
                ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json",
                agent=llm_policy,
                agent_name="llm",
            )
        self.assertEqual(result.agent_status, "error")
        self.assertEqual(result.command, "WAIT")
        self.assertIn("API-Schluessel", result.agent_error)
        self.assertFalse(result.collision)

    def test_llm_agent_executes_tools_and_submits_a_safe_contract(self) -> None:
        tool_calls = [
            {
                "id": f"tool-{index}",
                "type": "function",
                "function": {"name": name, "arguments": "{}"},
            }
            for index, name in enumerate(
                (
                    "get_blocker",
                    "get_center_marking",
                    "check_oncoming_traffic",
                    "check_rear_traffic",
                    "check_vulnerable_road_users",
                    "get_lateral_clearance",
                    "get_visibility",
                ),
                start=1,
            )
        ]
        decision = {
            "command": "NUDGE_AROUND_OBSTACLE",
            "parameters": {"side": "LEFT", "max_longitudinal_distance_m": 35.0},
            "reason": "Blockade erkannt; Sicht und Fahrkorridor sind frei",
        }
        responses = [
            {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {"role": "assistant", "content": None, "tool_calls": tool_calls},
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            },
            {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "decision-1",
                                    "type": "function",
                                    "function": {
                                        "name": "submit_decision",
                                        "arguments": json.dumps(decision),
                                    },
                                }
                            ],
                        },
                    }
                ]
            },
        ]
        requests: list[dict[str, object]] = []

        def transport(payload: dict[str, object]) -> dict[str, object]:
            requests.append(payload)
            return responses.pop(0)

        agent = OpenAICompatibleAgent(
            LLMConfig(api_key="secret-test-key", model="test-model"),
            transport=transport,
        )
        result = run_scenario(
            ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json",
            agent=agent,
            agent_name="mock-llm",
        )
        self.assertEqual(result.agent_status, "decided")
        self.assertEqual(result.command, "NUDGE_AROUND_OBSTACLE")
        self.assertTrue(result.liberated)
        self.assertEqual(len(requests), 2)
        self.assertEqual(
            sum(item["type"] == "tool_call" for item in result.agent_trace),
            7,
        )
        self.assertEqual(
            sum(item["type"] == "model_round" for item in result.agent_trace),
            2,
        )
        self.assertNotIn("secret-test-key", json.dumps(result.agent_trace))

    def test_reset_restores_autonomous_mode(self) -> None:
        scenario = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        live = LiveSimulation(scenario)
        live.command({"mode": "manual"})
        state = live.command({"action": "reset"})
        self.assertEqual(state["mode"], "autopilot")

    def test_manual_standstill_does_not_activate_agent(self) -> None:
        scenario = load_scenario(ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json")
        engine = SimulationEngine(scenario)
        engine.set_mode("manual")
        for _ in range(50):
            engine.step(Control())
        self.assertEqual(engine.agent_status, "inactive")
        self.assertFalse(any(event.event == "agent_requested" for event in engine.events))

    def test_malformed_agent_output_fails_safe(self) -> None:
        def malformed_agent(_session: AgentSession) -> dict[str, object]:
            return {"command": "NUDGE_AROUND_OBSTACLE"}

        result = run_scenario(
            ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json",
            agent=malformed_agent,
        )
        self.assertEqual(result.command, "WAIT")
        self.assertIsNotNone(result.agent_error)
        self.assertFalse(result.command_correct)
        self.assertTrue(any(event.event == "agent_contract_error" for event in result.events))

    def test_crashing_student_agent_fails_safe(self) -> None:
        def crashing_agent(_session: AgentSession) -> dict[str, object]:
            raise RuntimeError("studentischer Testfehler")

        result = run_scenario(
            ROOT / "autonomy_recovery_sim/scenarios/hannover_frei.json",
            agent=crashing_agent,
            agent_name="crashing-test",
        )
        self.assertEqual(result.command, "WAIT")
        self.assertEqual(result.agent_status, "error")
        self.assertIn("studentischer Testfehler", result.agent_error)
        self.assertFalse(result.collision)

    def test_agent_contract_rejects_out_of_bounds_parameters(self) -> None:
        for payload in (
            {"command": "WAIT", "parameters": {"duration_s": 99.0}, "reason": "Test"},
            {"command": "WAIT", "parameters": {"duration_s": 5.0, "extra": 1}, "reason": "Test"},
            {"command": "TELEPORT", "parameters": {}, "reason": "Test"},
            {"command": "WAIT", "parameters": {"duration_s": True}, "reason": "Test"},
        ):
            with self.subTest(payload=payload), self.assertRaises(AgentContractError):
                validate_agent_decision(payload)

if __name__ == "__main__":
    unittest.main()
