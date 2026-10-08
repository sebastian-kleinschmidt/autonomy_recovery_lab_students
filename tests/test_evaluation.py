"""Tests der wirtschaftlichen Auswertung: Budgets, Einstufung A-D, HTML-Bericht, Varianten."""

from __future__ import annotations

import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from autonomy_recovery_sim.batch import run_batch
from autonomy_recovery_sim.engine import SimulationEngine
from autonomy_recovery_sim.grading import grade_summary
from autonomy_recovery_sim.policy import heuristic_agent
from autonomy_recovery_sim.scenario import load_scenario
from autonomy_recovery_sim.scripts.make_variants import SHIFT_M, make_variant
from autonomy_recovery_sim.simulation import run_scenario
from tests.test_commands import command, run

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "autonomy_recovery_sim/scenarios"


def load(name: str):
    return load_scenario(SCENARIOS / f"{name}.json")


def summary(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "scenario_count": 10,
        "passed_count": 10,
        "within_budget_count": 10,
        "remote_assistance_episodes": 1,
        "average_customer_satisfaction": 0.9,
        "collision_count": 0,
        "personal_injury_count": 0,
    }
    base.update(overrides)
    return base


class GradingTest(unittest.TestCase):
    def test_grade_bands(self) -> None:
        self.assertEqual(grade_summary(summary())["grade"], "A")
        self.assertEqual(grade_summary(summary(passed_count=8, within_budget_count=8))["grade"], "B")
        self.assertEqual(grade_summary(summary(passed_count=6, within_budget_count=6))["grade"], "C")
        self.assertEqual(grade_summary(summary(passed_count=4))["grade"], "D")

    def test_economic_and_customer_criteria_hold_back_the_grade(self) -> None:
        # Alles bestanden, aber zu viele Remote-Assistance-Faelle: hoechstens B.
        self.assertEqual(grade_summary(summary(remote_assistance_episodes=6))["grade"], "B")
        # Alles bestanden, aber unzufriedene Kunden: nicht A.
        unhappy = grade_summary(summary(average_customer_satisfaction=0.4))
        self.assertEqual(unhappy["grade"], "C")
        self.assertFalse(unhappy["customers_satisfied"])
        # Ohne Fahrgaeste (None) gibt es kein Zufriedenheitskriterium.
        self.assertEqual(grade_summary(summary(average_customer_satisfaction=None))["grade"], "A")

    def test_safety_incident_is_always_grade_d(self) -> None:
        for field in ("collision_count", "personal_injury_count"):
            graded = grade_summary(summary(**{field: 1}))
            self.assertEqual(graded["grade"], "D")
            self.assertFalse(graded["economic"])


class BudgetTest(unittest.TestCase):
    def test_every_scenario_declares_a_positive_budget(self) -> None:
        for path in SCENARIOS.glob("*.json"):
            self.assertGreater(load_scenario(path).budget_eur, 0.0, path.name)

    def test_always_calling_remote_assistance_no_longer_passes(self) -> None:
        # Fruehere Fassung: erster Befehl passt zufaellig; jetzt sprengt die Kostenbilanz das Budget.
        result = run(
            load("hannover_ziel_gesperrt"),
            command("REQUEST_REMOTE_ASSISTANCE", reason_code="DESTINATION_UNREACHABLE"),
            command("RETURN_HOME"),
        )
        self.assertFalse(result.within_budget)
        self.assertGreater(result.costs["total_eur"], load("hannover_ziel_gesperrt").budget_eur)

    def test_batch_pass_requires_the_budget(self) -> None:
        batch = run_batch(SCENARIOS / "hannover_leitstelle_offline.json", agent=heuristic_agent, agent_name="baseline")
        item = batch.evaluations[0]
        self.assertTrue(item.result.command_correct)
        self.assertFalse(item.result.within_budget)
        self.assertFalse(item.passed)


class SolvabilityTest(unittest.TestCase):
    """Jeder schwierige Fall hat eine Loesung, die besteht - und plausible Fehlwahlen scheitern."""

    def assert_solved(self, name: str, *steps: dict[str, object]) -> None:
        scenario = load(name)
        result = run(scenario, *steps)
        self.assertTrue(result.command_correct, f"{name}: erster Befehl {result.command}")
        self.assertEqual(result.outcome, scenario.expected_outcome, name)
        self.assertTrue(result.within_budget, f"{name}: {result.costs['total_eur']} EUR")
        self.assertFalse(result.collision, name)

    def test_passenger_is_dropped_safely_at_the_edge(self) -> None:
        self.assert_solved("hannover_passagier_absetzen", command("PULL_OVER"), command("DROP_PASSENGER"))

    def test_returning_home_with_passengers_is_worse_than_a_safe_drop(self) -> None:
        drop = run(load("hannover_passagier_absetzen"), command("PULL_OVER"), command("DROP_PASSENGER"))
        home = run(load("hannover_passagier_absetzen"), command("RETURN_HOME"))
        self.assertEqual(home.outcome, "returned_home")
        self.assertGreater(home.costs["total_eur"], drop.costs["total_eur"])
        self.assertLess(home.costs["customer_satisfaction"], drop.costs["customer_satisfaction"])
        self.assertFalse(home.within_budget)

    def test_empty_vehicle_returns_home_directly(self) -> None:
        self.assert_solved("hannover_ziel_gesperrt", command("RETURN_HOME"))

    def test_offline_operator_needs_a_safe_stop_at_the_edge(self) -> None:
        self.assert_solved(
            "hannover_leitstelle_offline",
            command("PULL_OVER"),
            command("SAFE_STOP", reason_code="UNRECOVERABLE_BLOCKAGE"),
        )
        in_lane = run(load("hannover_leitstelle_offline"), command("SAFE_STOP", reason_code="UNRECOVERABLE_BLOCKAGE"))
        self.assertIn("blocking_traffic", in_lane.costs["items_eur"])

    def test_departing_van_is_cheaper_to_wait_out(self) -> None:
        self.assert_solved("hannover_lieferwagen_faehrt_los", command("WAIT", duration_s=10))

    def test_occupied_neighbour_lane_forces_the_nudge(self) -> None:
        self.assert_solved(
            "hannover_doppelparker_belegt",
            command("NUDGE_AROUND_OBSTACLE", side="LEFT", max_longitudinal_distance_m=35),
        )

    def test_solid_line_beacon_is_passed_on_the_right_only(self) -> None:
        result = run_scenario(SCENARIOS / "hannover_bake_durchgezogen.json", agent=heuristic_agent, agent_name="baseline")
        self.assertEqual(result.outcome, "liberated")
        self.assertLess(max(p["d_m"] for p in result.trajectory), -1.0)  # nie ueber die Mittellinie

    def test_misplaced_object_is_avoided_on_the_side_with_the_smaller_offset(self) -> None:
        result = run_scenario(SCENARIOS / "hannover_objekt_falsch_abgestellt.json", agent=heuristic_agent, agent_name="baseline")
        self.assertEqual(result.outcome, "liberated")
        self.assertEqual(result.commands[0]["parameters"]["side"], "RIGHT")

    def test_ego_follows_a_departing_vehicle_instead_of_rear_ending_it(self) -> None:
        engine = SimulationEngine(load("hannover_lieferwagen_faehrt_los"), agent=heuristic_agent)
        while not engine.done:
            engine.step()
        self.assertFalse(engine.collision)


class ReportTest(unittest.TestCase):
    def test_batch_writes_grade_and_a_self_contained_html_report(self) -> None:
        batch = run_batch(ROOT / "autonomy_recovery_sim/scenario_sets/demo.txt", agent=heuristic_agent, agent_name="baseline")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            batch.write(target)
            payload = json.loads((target / "batch-result.json").read_text("utf8"))
            html = (target / "batch-report.html").read_text("utf8")
            markdown = (target / "batch-report.md").read_text("utf8")
        grading = payload["summary"]["grading"]
        self.assertIn(grading["grade"], "ABCD")
        self.assertIn("cost_items", payload)
        self.assertIn(f"Einstufung {grading['grade']}", html)
        self.assertNotIn("http://", html.replace("http://www.w3.org", ""))  # keine externen Ressourcen
        self.assertIn("Einstufung:", markdown)
        self.assertIn("Kosten / Budget", markdown)

    def test_repeats_aggregate_pass_rate_and_cost_spread(self) -> None:
        batch = run_batch(
            SCENARIOS / "hannover_frei.json", agent=heuristic_agent, agent_name="baseline", repeats=3
        )
        payload = batch.to_dict()
        self.assertEqual(len(batch.evaluations), 3)
        self.assertEqual(payload["summary"]["repeats"], 3)
        stat = payload["scenario_stats"][0]
        self.assertEqual((stat["runs"], stat["pass_rate"], stat["cost_std_eur"]), (3, 1.0, 0.0))
        with tempfile.TemporaryDirectory() as directory:
            batch.write(Path(directory))
            self.assertTrue((Path(directory) / "scenarios/hannover_frei/run-3/result.json").is_file())
            self.assertIn("Streuung", (Path(directory) / "batch-report.md").read_text("utf8"))

    def test_invalid_repeats_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_batch(SCENARIOS / "hannover_frei.json", repeats=0)


class DetectionMetricTest(unittest.TestCase):
    """Fehlalarme und verpasste Eingriffe: die zwei Fehlerarten der Einordnung 'steckt es fest?'."""

    def summary(self, agent, name: str) -> dict:
        return run_batch(ROOT / "autonomy_recovery_sim/scenario_sets/erkennen.txt", agent=agent, agent_name=name).to_dict()["summary"]

    def test_a_waiting_agent_never_raises_false_alarms_but_misses_every_real_case(self) -> None:
        from autonomy_recovery_sim.student_agent import decide

        summary = self.summary(decide, "starter")
        self.assertEqual((summary["false_alarm_count"], summary["no_intervention_scenarios"]), (0, 4))
        self.assertEqual((summary["missed_intervention_count"], summary["intervention_scenarios"]), (2, 2))
        self.assertEqual(summary["false_alarm_rate"], 0.0)
        self.assertEqual(summary["missed_intervention_rate"], 1.0)

    def test_the_baseline_misses_nothing_but_raises_a_false_alarm_in_the_traffic_jam(self) -> None:
        summary = self.summary(heuristic_agent, "baseline")
        self.assertEqual(summary["false_alarm_count"], 1)
        self.assertEqual(summary["missed_intervention_count"], 0)

    def test_an_always_intervening_agent_is_the_mirror_image(self) -> None:
        def always_calls(session):
            return session.submit_decision(command("REQUEST_REMOTE_ASSISTANCE", reason_code="AMBIGUOUS_SCENE"))

        summary = self.summary(always_calls, "always")
        self.assertEqual(summary["false_alarm_count"], summary["no_intervention_scenarios"])
        self.assertEqual(summary["missed_intervention_count"], 0)

    def test_per_scenario_flags_and_report_lines(self) -> None:
        batch = run_batch(ROOT / "autonomy_recovery_sim/scenario_sets/erkennen.txt", agent=heuristic_agent, agent_name="baseline")
        flags = {item["scenario_id"]: (item["intervention_expected"], item["intervened"]) for item in batch.to_dict()["scenarios"]}
        self.assertEqual(flags["hannover_ampel_rot"], (False, False))
        self.assertEqual(flags["hannover_stau_loest_sich"], (False, True))  # unnoetiges Umfahren
        self.assertEqual(flags["hannover_ampel_gruen_blockiert"], (True, True))
        with tempfile.TemporaryDirectory() as directory:
            batch.write(Path(directory))
            report = (Path(directory) / "batch-report.md").read_text("utf8")
            html = (Path(directory) / "batch-report.html").read_text("utf8")
        self.assertIn("Fehlalarme", report)
        self.assertIn("Verpasste Eingriffe", report)
        self.assertIn("Fehlalarme", html)

    def test_a_delegated_intervention_counts_as_intervention(self) -> None:
        result = run(load("hannover_frei"), command("ESCALATE_TO_RULE_ENGINE"))
        self.assertTrue(result.intervened)  # die Regel-Engine hat umfahren

    def test_the_assignment_asks_for_both_implementations(self) -> None:
        text = (ROOT / "autonomy_recovery_sim/ASSIGNMENT.md").read_text("utf8")
        for expected in (
            "Teil A", "Teil B", "Teil C", "erkennen.txt", "Fehlalarm", "mein_agent.py",
            "AUTONOMY_RECOVERY_MODEL=none", "student_llm_agent.py", "Rückmeldung statt Note",
        ):
            self.assertIn(expected, text)


class VariantGeneratorTest(unittest.TestCase):
    def test_family_variations_keep_rear_traffic_behind_the_ego(self) -> None:
        families = ROOT / "autonomy_recovery_sim/families"
        for name in ("f4_frueh_zu", "f5_radfahrer_hinten"):
            source = families / f"{name}.json"
            original = json.loads(source.read_text("utf8"))
            road_length = load_scenario(source).road.length_m
            for seed in (1, 2, 3, 2026):
                with self.subTest(name=name, seed=seed):
                    variant = make_variant(original, source, families, random.Random(seed), 1, road_length)
                    self.assertEqual(variant["reference"], original["reference"])
                    for before, after in zip(original["actors"], variant["actors"]):
                        self.assertLessEqual(abs(after["s_m"] - before["s_m"]), SHIFT_M + 0.01)
                        if before["s_m"] < original["ego"]["start_s_m"]:
                            self.assertLess(after["s_m"], variant["ego"]["start_s_m"])

    def test_variants_are_valid_deterministic_and_relabelled(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            for directory in (first, second):
                subprocess.run(
                    [
                        sys.executable, str(ROOT / "autonomy_recovery_sim/scripts/make_variants.py"),
                        str(ROOT / "autonomy_recovery_sim/scenario_sets/demo.txt"),
                        "--count", "2", "--seed", "7", "--output", directory,
                    ],
                    check=True, capture_output=True, cwd=ROOT,
                )
            names = sorted(path.name for path in Path(first).glob("*.json"))
            self.assertEqual(len(names), 6)
            for name in names:
                self.assertEqual((Path(first) / name).read_text("utf8"), (Path(second) / name).read_text("utf8"))
                load_scenario(Path(first) / name)
            changed = json.loads((Path(first) / "hannover_frei_v1.json").read_text("utf8"))
            original = json.loads((SCENARIOS / "hannover_frei.json").read_text("utf8"))
            self.assertEqual(changed["id"], "hannover_frei_v1")
            self.assertNotEqual(changed["actors"][0]["s_m"], original["actors"][0]["s_m"])
            self.assertEqual(changed["reference"], original["reference"])
            result = run_batch(Path(first) / "variants.txt", agent=heuristic_agent, agent_name="baseline")
            self.assertEqual(result.to_dict()["summary"]["collision_count"], 0)


if __name__ == "__main__":
    unittest.main()
