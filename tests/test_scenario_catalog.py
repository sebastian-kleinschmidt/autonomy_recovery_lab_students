"""Konsistenz und Kalibrierung des gestuften Szenarienkatalogs."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from autonomy_recovery_sim.batch import discover_scenarios, run_batch
from autonomy_recovery_sim.engine import SimulationEngine
from autonomy_recovery_sim.policy import heuristic_agent
from autonomy_recovery_sim.scenario import load_scenario
from autonomy_recovery_sim.simulation import run_scenario


ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "autonomy_recovery_sim"
SETS = SIM / "scenario_sets"
ORDER = ("bootcamp", "sprint1", "sprint2", "sprint3", "sprint4")
INCREMENTAL = {
    "bootcamp": "bootcamp.txt",
    "sprint1": "sprint1_foundations.txt",
    "sprint2": "sprint2_decisions.txt",
    "sprint3": "sprint3_robustness.txt",
    "sprint4": "sprint4_transfer.txt",
}


class ScenarioCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads((SIM / "scenario_catalog.json").read_text("utf8"))

    def ids(self, filename: str) -> list[str]:
        return [path.stem for path in discover_scenarios(SETS / filename)]

    def test_catalog_covers_every_scenario_exactly_once(self) -> None:
        entries = self.catalog["scenarios"]
        ids = [entry["id"] for entry in entries]
        files = {path.stem for path in (SIM / "scenarios").glob("*.json")}
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), files)
        self.assertTrue(self.catalog["usable_without_llm"])
        self.assertEqual(tuple(self.catalog["release_order"]), ORDER)

    def test_every_actor_has_an_observable_scene_description(self) -> None:
        for path in sorted((SIM / "scenarios").glob("*.json")):
            scenario = json.loads(path.read_text("utf8"))
            for actor in scenario.get("actors", []):
                with self.subTest(scenario=path.stem, actor=actor["id"]):
                    description = actor.get("description")
                    self.assertIsInstance(description, str)
                    self.assertGreaterEqual(len(description.strip()), 20)

    def test_incremental_sets_are_disjoint_and_have_the_planned_sizes(self) -> None:
        expected_sizes = {"bootcamp": 3, "sprint1": 5, "sprint2": 12, "sprint3": 16, "sprint4": 25}
        seen: set[str] = set()
        for release in ORDER:
            ids = self.ids(INCREMENTAL[release])
            self.assertEqual(len(ids), expected_sizes[release], release)
            self.assertFalse(seen.intersection(ids), release)
            seen.update(ids)
        self.assertEqual(len(seen), 61)

    def test_cumulative_sets_contain_every_prior_release(self) -> None:
        cumulative = self.ids("bootcamp.txt")
        expected_sizes = {"sprint1": 8, "sprint2": 20, "sprint3": 36, "sprint4": 61}
        for release in ORDER[1:]:
            cumulative.extend(self.ids(INCREMENTAL[release]))
            self.assertEqual(self.ids(f"released_{release}.txt"), cumulative)
            self.assertEqual(len(cumulative), expected_sizes[release])

    def test_generated_sets_are_up_to_date(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SIM / "scripts/build_scenario_sets.py"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_sprint_one_separates_the_waiting_starter_from_the_baseline(self) -> None:
        from autonomy_recovery_sim.student_agent import decide

        source = SETS / "released_sprint1.txt"
        starter = run_batch(source, agent=decide, agent_name="starter").to_dict()["summary"]
        baseline = run_batch(source, agent=heuristic_agent, agent_name="baseline").to_dict()["summary"]
        self.assertEqual((starter["passed_count"], starter["scenario_count"]), (6, 8))
        self.assertEqual((baseline["passed_count"], baseline["scenario_count"]), (8, 8))
        self.assertEqual(starter["collision_count"], 0)
        self.assertEqual(baseline["collision_count"], 0)


class NewScenarioTest(unittest.TestCase):
    NAMES = (
        "hannover_wildunfall",
        "hannover_sitzblockade",
        "hannover_zootiere",
        "hannover_fussballfans_blockade",
        "hannover_umgekippter_lkw",
    )
    LOST_CARGO_NAMES = (
        "hannover_ladung_karton",
        "hannover_ladung_reifen",
        "hannover_ladung_holzbalken",
        "hannover_ladung_scherben",
        "hannover_ladung_verstreut",
    )

    def test_new_scenarios_are_safe_and_solvable_by_the_reference_baseline(self) -> None:
        for name in self.NAMES:
            with self.subTest(name=name):
                result = run_scenario(
                    SIM / f"scenarios/{name}.json",
                    agent=heuristic_agent,
                    agent_name="baseline",
                )
                self.assertTrue(result.command_correct)
                self.assertEqual(result.outcome, result.scenario.expected_outcome)
                self.assertTrue(result.within_budget)
                self.assertFalse(result.collision)

    def test_animal_observations_are_explicit_and_block_a_maneuver(self) -> None:
        scenario = load_scenario(SIM / "scenarios/hannover_wildunfall.json")
        engine = SimulationEngine(scenario, console=True)
        for _ in range(6000):
            if engine.pending_session is not None:
                break
            engine.step()
        self.assertIsNotNone(engine.pending_session)
        session = engine.pending_session
        assert session is not None
        blocker = session.call_tool("get_blocker")
        vulnerable = session.call_tool("check_vulnerable_road_users")
        self.assertEqual(blocker["kind"], "animal")
        self.assertTrue(vulnerable["conflict"])
        self.assertTrue(all("kind" in actor for actor in vulnerable["actors"]))

    def test_lost_cargo_matrix_covers_cross_avoid_nudge_and_replan(self) -> None:
        commands = set()
        for name in self.LOST_CARGO_NAMES:
            with self.subTest(name=name):
                result = run_scenario(
                    SIM / f"scenarios/{name}.json",
                    agent=heuristic_agent,
                    agent_name="baseline",
                )
                commands.add(result.command)
                self.assertTrue(result.command_correct)
                self.assertEqual(result.outcome, result.scenario.expected_outcome)
                self.assertTrue(result.within_budget)
                self.assertFalse(result.collision)
        self.assertEqual(
            commands,
            {
                "CROSS_LOW_RISK_OBJECT",
                "AVOID_TEMPORARY_OBSTRUCTION",
                "NUDGE_AROUND_OBSTACLE",
                "REPLAN_ROUTE",
            },
        )

    def test_lost_cargo_profile_is_exposed_as_structured_perception(self) -> None:
        scenario = load_scenario(SIM / "scenarios/hannover_ladung_karton.json")
        engine = SimulationEngine(scenario, console=True)
        for _ in range(6000):
            if engine.pending_session is not None:
                break
            engine.step()
        assert engine.pending_session is not None
        blocker = engine.pending_session.call_tool("get_blocker")
        self.assertEqual(blocker["obstacle_profile"]["material"], "CARDBOARD")
        self.assertEqual(blocker["scene_description"], scenario.actors[0].description)


if __name__ == "__main__":
    unittest.main()
