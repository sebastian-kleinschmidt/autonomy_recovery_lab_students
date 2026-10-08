"""Mehrstufige Loesungswege: reference.sequence, Bestehen und Teilpunkte."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from autonomy_recovery_sim.batch import run_batch
from autonomy_recovery_sim.report_details import diagnose
from autonomy_recovery_sim.scenario import load_scenario
from tests.test_commands import command, run, scripted

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "autonomy_recovery_sim/scenarios"
REPLAN_AFTER_CHECK = (
    command("REQUEST_ADDITIONAL_INFORMATION", topic="MAP_CONSISTENCY", duration_s=3),
    command("REPLAN_ROUTE"),
)


def load(name: str):
    return load_scenario(SCENARIOS / f"{name}.json")


def batch(name: str, *steps: dict[str, object], hide_reference: bool = False):
    return run_batch(
        SCENARIOS / f"{name}.json",
        agent=scripted(*steps),
        agent_name="script",
        hide_reference=hide_reference,
    )


class SequenceFormatTest(unittest.TestCase):
    def test_multi_step_scenarios_declare_their_solution_path(self) -> None:
        self.assertEqual(
            load("hannover_sackgasse").expected_sequence, (("REVERSE_SHORT",), ("REPLAN_ROUTE",))
        )
        self.assertEqual(
            load("hannover_passagier_absetzen").expected_sequence, (("PULL_OVER",), ("DROP_PASSENGER",))
        )
        self.assertEqual(load("hannover_frei").expected_sequence, ())

    def test_invalid_sequences_are_rejected(self) -> None:
        base = json.loads((SCENARIOS / "hannover_frei.json").read_text("utf8"))
        base["road"]["map_file"] = str((SCENARIOS / base["road"]["map_file"]).resolve())
        base["road"]["context_file"] = str((SCENARIOS / base["road"]["context_file"]).resolve())
        for sequence in ([[]], ["NUDGE_AROUND_OBSTACLE"], [["FLY"]]):
            with self.subTest(sequence=sequence), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "sequence.json"
                data = {**base, "reference": {**base["reference"], "sequence": sequence}}
                path.write_text(json.dumps(data), encoding="utf8")
                with self.assertRaises(ValueError):
                    load_scenario(path)


class SequenceScoringTest(unittest.TestCase):
    def test_the_complete_path_passes(self) -> None:
        for name, steps in {
            "hannover_sackgasse": (command("REVERSE_SHORT", max_distance_m=5.0), command("REPLAN_ROUTE")),
            "hannover_karte_veraltet": REPLAN_AFTER_CHECK,
            "hannover_passagier_absetzen": (command("PULL_OVER"), command("DROP_PASSENGER")),
            "hannover_leitstelle_offline": (
                command("PULL_OVER"),
                command("SAFE_STOP", reason_code="UNRECOVERABLE_BLOCKAGE"),
            ),
        }.items():
            with self.subTest(name=name):
                evaluation = batch(name, *steps).evaluations[0]
                self.assertTrue(evaluation.result.sequence_complete)
                self.assertTrue(evaluation.passed, diagnose(evaluation))

    def test_a_half_finished_path_fails_but_earns_partial_credit(self) -> None:
        result = batch("hannover_passagier_absetzen", command("PULL_OVER"))
        evaluation = result.evaluations[0]
        self.assertTrue(evaluation.result.command_correct)  # der erste Schritt war richtig
        self.assertEqual(evaluation.result.sequence_matched, 1)
        self.assertFalse(evaluation.passed)
        summary = result.to_dict()["summary"]
        self.assertEqual(summary["sequence_scenario_count"], 1)
        self.assertEqual(summary["sequence_complete_count"], 0)
        self.assertEqual(summary["average_sequence_score"], 0.5)
        self.assertIn("1 von 2 Schritten", " ".join(diagnose(evaluation)))
        self.assertIn("DROP_PASSENGER", " ".join(diagnose(evaluation)))

    def test_failed_commands_do_not_count_as_a_step(self) -> None:
        premature = run(load("hannover_karte_veraltet"), command("REPLAN_ROUTE"))
        self.assertEqual(premature.commands[0]["status"], "FAILED")
        self.assertEqual(premature.sequence_matched, 0)
        recovered = run(load("hannover_karte_veraltet"), command("REPLAN_ROUTE"), *REPLAN_AFTER_CHECK)
        self.assertTrue(recovered.sequence_complete)

    def test_the_order_of_the_steps_matters(self) -> None:
        # Umplanen vor dem Zuruecksetzen scheitert; der zweite Schritt allein genuegt nicht.
        result = run(load("hannover_sackgasse"), command("REPLAN_ROUTE"), command("REVERSE_SHORT", max_distance_m=5.0))
        self.assertEqual(result.sequence_matched, 1)
        self.assertFalse(result.sequence_complete)

    def test_hidden_reference_does_not_name_the_missing_step(self) -> None:
        result = batch("hannover_passagier_absetzen", command("PULL_OVER"), hide_reference=True)
        findings = " ".join(result.to_dict()["scenarios"][0]["diagnosis"])
        self.assertIn("1 von 2 Schritten", findings)
        self.assertNotIn("DROP_PASSENGER", findings)
        self.assertNotIn("expected_sequence", result.to_dict()["scenarios"][0])


NUDGE = command("NUDGE_AROUND_OBSTACLE", side="LEFT", max_longitudinal_distance_m=35.0)
AVOID = command("AVOID_TEMPORARY_OBSTRUCTION", obstruction_type="TRASH_BIN", side="LEFT", max_lateral_offset_m=2.0)
CALL = command("REQUEST_REMOTE_ASSISTANCE", reason_code="BLOCKED_ROUTE")
NEW_CASES = {
    "hannover_fussgaenger_vor_lieferwagen": ((command("WAIT", duration_s=10), NUDGE), (command("WAIT", duration_s=10),) * 6),
    "hannover_gegenverkehr_zieht_vorbei": ((command("WAIT", duration_s=10), NUDGE), (command("WAIT", duration_s=10),) * 6),
    "hannover_zwei_hindernisse": ((AVOID, NUDGE), (AVOID,)),
    "hannover_karte_veraltet_fahrgaeste": (
        (*REPLAN_AFTER_CHECK[:1], command("PULL_OVER"), command("DROP_PASSENGER")),
        (*REPLAN_AFTER_CHECK[:1], command("RETURN_HOME")),
    ),
    "hannover_ampel_dunkel_lieferwagen": ((CALL, NUDGE), (CALL, CALL)),
}


class NewMultiStepScenarioTest(unittest.TestCase):
    def test_the_reference_path_passes_and_stopping_after_the_first_step_fails(self) -> None:
        for name, (reference, first_step_only) in NEW_CASES.items():
            with self.subTest(name=name):
                solved = batch(name, *reference).evaluations[0]
                self.assertTrue(solved.passed, diagnose(solved))
                partial = batch(name, *first_step_only).evaluations[0]
                self.assertTrue(partial.result.command_correct)  # der erste Schritt stimmt
                self.assertGreaterEqual(partial.result.sequence_matched, 1)
                self.assertFalse(partial.passed)

    def test_the_new_cases_are_released_in_sprint_four_and_collected_in_a_set(self) -> None:
        catalog = {entry["id"]: entry for entry in json.loads((ROOT / "autonomy_recovery_sim/scenario_catalog.json").read_text("utf8"))["scenarios"]}
        listed = (ROOT / "autonomy_recovery_sim/scenario_sets/mehrstufig.txt").read_text("utf8")
        for name in NEW_CASES:
            self.assertEqual(catalog[name]["release"], "sprint4")
            self.assertIn("multi_step", catalog[name]["tags"])
            self.assertIn(f"{name}.json", listed)
            self.assertGreaterEqual(len(load(name).expected_sequence), 2)

    def test_a_second_call_cannot_release_the_same_signal_again(self) -> None:
        result = run(load("hannover_ampel_dunkel_lieferwagen"), CALL, CALL)
        self.assertEqual(
            [(item["command"], item["status"]) for item in result.commands[:2]],
            [("REQUEST_REMOTE_ASSISTANCE", "SUCCEEDED"), ("REQUEST_REMOTE_ASSISTANCE", "FAILED")],
        )


if __name__ == "__main__":
    unittest.main()
