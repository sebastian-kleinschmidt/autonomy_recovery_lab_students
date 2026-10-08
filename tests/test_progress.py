"""Fortschritt zwischen Batchlaeufen: Rueckmeldung, ob sich ein Agent verbessert (progress.py)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from autonomy_recovery_sim.batch import run_batch
from autonomy_recovery_sim.progress import HISTORY_FILE, summary_lines
from autonomy_recovery_sim.policy import heuristic_agent
from autonomy_recovery_sim.tutorials.track import l1_start

SETS = Path(__file__).resolve().parents[1] / "autonomy_recovery_sim/scenario_sets"


def batch(agent, name: str, set_name: str = "released_sprint1.txt", **options):
    return run_batch(SETS / set_name, agent=agent, agent_name=name, **options)


class ProgressTest(unittest.TestCase):
    def test_first_run_then_improvement_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            first = batch(l1_start.decide, "l1").write(output)
            self.assertFalse(first["available"])
            second = batch(heuristic_agent, "baseline").write(output)
            self.assertTrue(second["comparable"])
            self.assertEqual((second["passed_before"], second["passed_now"]), (6, 8))
            self.assertEqual(second["newly_passed"], ["hannover_frei", "hannover_gegenverkehr_fern"])
            self.assertEqual(second["newly_failed"], [])
            self.assertIn("6 -> 8 bestanden (+2)", "\n".join(summary_lines(second)))
            history = (output / HISTORY_FILE).read_text("utf8").splitlines()
            self.assertEqual([json.loads(line)["passed"] for line in history], [6, 8])
            report = (output / "batch-report.html").read_text("utf8")
            self.assertIn("Fortschritt seit dem letzten Lauf", report)
            self.assertIn("Neu bestanden", report)
            stored = json.loads((output / "batch-result.json").read_text("utf8"))
            self.assertEqual(stored["progress"]["passed_now"], 8)

    def test_regressions_are_named(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            batch(heuristic_agent, "baseline").write(output)
            worse = batch(l1_start.decide, "l1").write(output)
            self.assertEqual(worse["newly_failed"], ["hannover_frei", "hannover_gegenverkehr_fern"])
            self.assertIn("neu gescheitert", "\n".join(summary_lines(worse)))

    def test_different_sets_or_settings_are_not_compared(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            batch(l1_start.decide, "l1").write(output)
            other_set = batch(l1_start.decide, "l1", "demo.txt").write(output)
            self.assertFalse(other_set["comparable"])
            self.assertIn("Szenariomenge", other_set["reason"])
            batch(l1_start.decide, "l1", "demo.txt").write(output)
            other_mode = batch(l1_start.decide, "l1", "demo.txt", guardrails="off").write(output)
            self.assertFalse(other_mode["comparable"])
            self.assertIn("guardrails", other_mode["reason"])


if __name__ == "__main__":
    unittest.main()
