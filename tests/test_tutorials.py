"""Prueft, dass die Lernunterlagen zum Code passen: Links, Namen, lauffaehige Beispiele, Zahlen."""

from __future__ import annotations

import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from autonomy_recovery_sim.agent_session import AgentSession, AgentToolError
from autonomy_recovery_sim.batch import run_batch
from autonomy_recovery_sim.commands import COMMAND_NAMES
from autonomy_recovery_sim.agent_session import TOOL_CATALOG
from autonomy_recovery_sim.policy import heuristic_agent
from autonomy_recovery_sim.scenario import load_scenario
from autonomy_recovery_sim.tutorials import mock_llm_demo, vergleich
from autonomy_recovery_sim.tutorials.helpers import call_with_retry, collect_evidence, is_stale
from tests.test_commands import command, run

ROOT = Path(__file__).resolve().parents[1]
AUTONOMY_RECOVERY = ROOT / "autonomy_recovery_sim"
TUTORIALS = AUTONOMY_RECOVERY / "tutorials"
DOCS = (
    [ROOT / "README.md"]
    + sorted((ROOT / "docs").rglob("*.md"))
    + sorted(AUTONOMY_RECOVERY.rglob("*.md"))
    + sorted((ROOT / "lehrende").rglob("*.md"))
)
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def slug(heading: str) -> str:
    # Wie GitHub: Backticks und Sternchen fallen weg, Unterstriche bleiben (#replan_route).
    text = re.sub(r"[`*]", "", heading.strip().lower())
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text)


def anchors(path: Path) -> set[str]:
    return {slug(line.lstrip("#")) for line in path.read_text("utf8").splitlines() if line.startswith("#")}


def runnable_blocks(path: Path) -> list[str]:
    return re.findall(r"<!-- lauffaehig -->\n```python\n(.*?)```", path.read_text("utf8"), re.S)


def load_agent_from(path: Path):
    namespace: dict[str, object] = {}
    exec(runnable_blocks(path)[0], namespace)
    return namespace["decide"]


class DocumentationLinksTest(unittest.TestCase):
    def test_learning_path_files_exist(self) -> None:
        names = {p.name for p in TUTORIALS.glob("*.md")}
        for expected in (
            "README.md", "00-grundlagen.md", "01-recovery-agent-spielen.md", "02a-forschungsplan.md",
            "L1-einfachster-agent.md", "L2-regelagent.md", "L3-gedaechtnis.md", "L4-selbst-wahrnehmen.md",
            "L5-llm-agent.md", "L6-alpamayo-misstrauen.md", "L7-phasen-und-dynamik.md",
            "L8-unfaelle-und-schutzregeln.md", "06-evaluieren.md",
            "CHEATSHEET.md", "GLOSSAR.md",
        ):
            self.assertIn(expected, names)
        self.assertTrue((TUTORIALS / "vorlagen/lab-journal.md").is_file())
        self.assertTrue((TUTORIALS / "vorlagen/laborbericht.md").is_file())

    def test_every_relative_link_and_anchor_resolves(self) -> None:
        problems = []
        for document in DOCS:
            for target in LINK.findall(document.read_text("utf8")):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                file_part, _, anchor = target.partition("#")
                resolved = (document.parent / file_part).resolve() if file_part else document
                if not resolved.exists():
                    problems.append(f"{document.name}: {target}")
                elif anchor and resolved.suffix == ".md" and anchor not in anchors(resolved):
                    problems.append(f"{document.name}: Anker {target}")
        self.assertEqual(problems, [])

    def test_learning_path_is_linked_from_the_main_docs(self) -> None:
        for name in ("README.md", "QUICKSTART.md", "ASSIGNMENT.md"):
            self.assertIn("tutorials/README.md", (AUTONOMY_RECOVERY / name).read_text("utf8"), name)

    def test_referenced_scenarios_and_sets_exist(self) -> None:
        names = set()
        for document in DOCS:
            text = document.read_text("utf8")
            # Praefixe wie `hannover_abbruch_*` meinen eine Gruppe, kein einzelnes Szenario.
            names |= {name for name in re.findall(r"\b(hannover_[a-z_]+)\b", text) if not name.endswith("_")}
            for name in re.findall(r"scenario_sets/([a-z_]+\.txt)", text):
                self.assertTrue((AUTONOMY_RECOVERY / "scenario_sets" / name).is_file(), name)
        existing = {p.stem for p in (AUTONOMY_RECOVERY / "scenarios").glob("*.json")}
        existing |= {p.stem for p in (AUTONOMY_RECOVERY / "data").glob("hannover_*")}  # Kartendateien
        self.assertEqual(sorted(names - existing), [])

    def test_cheatsheet_matches_the_registries(self) -> None:
        text = (TUTORIALS / "CHEATSHEET.md").read_text("utf8")
        for name in COMMAND_NAMES:
            self.assertIn(f"`{name}`", text)
        for name in TOOL_CATALOG:
            self.assertIn(f"`{name}`", text)
        self.assertEqual(len(TOOL_CATALOG), 12)  # Stufe 0 und Spickzettel sprechen von zwölf Werkzeugen


class RunnableExamplesTest(unittest.TestCase):
    def test_stage_two_example_shows_that_acting_on_half_the_evidence_is_worse_than_waiting(self) -> None:
        decide = load_agent_from(TUTORIALS / "archiv/02-regelagent.md")
        demo = run_batch(AUTONOMY_RECOVERY / "scenario_sets/demo.txt", agent=decide, agent_name="t").to_dict()["summary"]
        public = run_batch(AUTONOMY_RECOVERY / "scenario_sets/public.txt", agent=decide, agent_name="t").to_dict()["summary"]
        self.assertEqual(demo["passed_count"], 2)
        self.assertEqual(public["passed_count"], 5)
        self.assertEqual(public["collision_count"], 0)

    def test_the_documented_starter_and_baseline_numbers_hold(self) -> None:
        from autonomy_recovery_sim.student_agent import decide

        starter_demo = run_batch(AUTONOMY_RECOVERY / "scenario_sets/demo.txt", agent=decide, agent_name="s").to_dict()["summary"]
        self.assertEqual((starter_demo["passed_count"], starter_demo["grading"]["grade"]), (2, "C"))
        starter = run_batch(AUTONOMY_RECOVERY / "scenario_sets/public.txt", agent=decide, agent_name="s").to_dict()["summary"]
        baseline = run_batch(AUTONOMY_RECOVERY / "scenario_sets/public.txt", agent=heuristic_agent, agent_name="b").to_dict()["summary"]
        self.assertEqual((starter["passed_count"], starter["grading"]["grade"]), (11, "D"))
        self.assertEqual((baseline["passed_count"], baseline["grading"]["grade"]), (14, "C"))
        self.assertEqual(starter["scenario_count"], 25)

    def test_stage_five_example_solves_exactly_the_documented_scenarios(self) -> None:
        decide = load_agent_from(TUTORIALS / "archiv/05-robust.md")
        batch = run_batch(AUTONOMY_RECOVERY / "scenario_sets/uncertainty.txt", agent=decide, agent_name="t")
        passed = {item.result.scenario_id for item in batch.evaluations if item.passed}
        self.assertEqual(
            passed,
            {
                "hannover_geplanter_halt",
                "hannover_werkzeug_timeout",
                "hannover_veraltete_daten",
                "hannover_injektion",
            },
        )
        self.assertEqual(batch.to_dict()["summary"]["collision_count"], 0)

    def test_stage_one_cost_table_matches_the_simulator(self) -> None:
        scenario = load_scenario(AUTONOMY_RECOVERY / "scenarios/hannover_frei.json")

        def cost(*steps):
            return run(scenario, *steps).costs["total_eur"]

        code = "UNRECOVERABLE_BLOCKAGE"
        self.assertAlmostEqual(cost(command("NUDGE_AROUND_OBSTACLE", side="LEFT", max_longitudinal_distance_m=35)), 1.55, delta=0.5)
        self.assertAlmostEqual(cost(command("REQUEST_REMOTE_ASSISTANCE", reason_code="NO_SAFE_RECOVERY")), 34.0, delta=2.0)
        self.assertAlmostEqual(cost(command("PULL_OVER"), command("DROP_PASSENGER")), 23.0, delta=2.0)
        self.assertGreater(cost(command("DROP_PASSENGER")), 100_000)
        self.assertAlmostEqual(cost(command("SAFE_STOP", reason_code=code)), 251.0, delta=3.0)
        self.assertAlmostEqual(cost(command("PULL_OVER"), command("SAFE_STOP", reason_code=code)), 153.0, delta=3.0)
        self.assertAlmostEqual(cost(command("RETURN_HOME")), 126.0, delta=3.0)

    def test_stage_one_scenarios_have_the_traps_the_text_describes(self) -> None:
        from autonomy_recovery_sim.engine import SimulationEngine

        def first_tools(name):
            engine = SimulationEngine(load_scenario(AUTONOMY_RECOVERY / f"scenarios/{name}.json"), console=True)
            for _ in range(6000):
                if engine.pending_session is not None:
                    return engine.pending_session
                engine.step()
            raise AssertionError(name)

        self.assertIn("observation_age_s", first_tools("hannover_veraltete_daten").call_tool("get_blocker"))
        self.assertIn("scene_description", first_tools("hannover_injektion").call_tool("get_blocker"))
        self.assertIn("track_confidence", first_tools("hannover_phantom_hindernis").call_tool("get_blocker"))


class MockDemoTest(unittest.TestCase):
    def run_demo(self, *args: str) -> str:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(mock_llm_demo.main(list(args)), 0)
        return buffer.getvalue()

    def test_demo_prints_the_protocol_and_reaches_the_documented_result(self) -> None:
        output = self.run_demo()
        for expected in ("=== Runde 1", "=== Runde 2", "submit_decision", "NUDGE_AROUND_OBSTACLE (korrekt)", "liberated"):
            self.assertIn(expected, output)
        self.assertIn("13 Werkzeugbeschreibungen", output)  # zwölf Werkzeuge plus submit_decision
        self.assertIn("Der Simulator schickt 10 Nachrichten", output)

    def test_the_same_script_fails_in_another_situation(self) -> None:
        output = self.run_demo(str(AUTONOMY_RECOVERY / "scenarios/hannover_gegenverkehr.json"))
        self.assertIn("NUDGE_AROUND_OBSTACLE (falsch)", output)
        self.assertIn("aborted", output)

    def test_the_demo_needs_no_key(self) -> None:
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {}, clear=True):
            self.assertIn("Ergebnis", self.run_demo())


class HelpersTest(unittest.TestCase):
    def session(self, scenario: str):
        from autonomy_recovery_sim.engine import SimulationEngine

        engine = SimulationEngine(load_scenario(AUTONOMY_RECOVERY / f"scenarios/{scenario}.json"), console=True)
        for _ in range(6000):
            if engine.pending_session is not None:
                return engine.pending_session
            engine.step()
        raise AssertionError(scenario)

    def test_call_with_retry_survives_two_timeouts_but_not_three(self) -> None:
        session = self.session("hannover_werkzeug_timeout")
        result = call_with_retry(session, "check_oncoming_traffic", tries=3)
        self.assertIsNotNone(result)
        self.assertEqual(session.tool_call_count, 3)  # zwei Fehlversuche verbrauchen Budget
        session = self.session("hannover_werkzeug_timeout")
        self.assertIsNone(call_with_retry(session, "check_oncoming_traffic", tries=2))

    def test_stale_detection(self) -> None:
        self.assertTrue(is_stale({"observation_age_s": 9.0}))
        self.assertFalse(is_stale({"observation_age_s": 0.5}))
        self.assertFalse(is_stale({"conflict": False}))
        session = self.session("hannover_veraltete_daten")
        self.assertTrue(is_stale(session.call_tool("get_blocker")))

    def test_collect_evidence_returns_all_seven_or_marks_failures(self) -> None:
        evidence = collect_evidence(self.session("hannover_frei"))
        self.assertEqual(len(evidence), 7)
        self.assertTrue(all(value is not None for value in evidence.values()))
        broken = collect_evidence(self.session("hannover_werkzeug_timeout"))
        self.assertTrue(all(value is not None for value in broken.values()))  # Retry heilt den Ausfall


class CompareToolTest(unittest.TestCase):
    def test_compare_shows_metrics_and_differing_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            from autonomy_recovery_sim.student_agent import decide

            run_batch(AUTONOMY_RECOVERY / "scenario_sets/demo.txt", agent=decide, agent_name="starter").write(Path(first))
            run_batch(AUTONOMY_RECOVERY / "scenario_sets/demo.txt", agent=heuristic_agent, agent_name="baseline").write(Path(second))
            a, b = vergleich.load(Path(first)), vergleich.load(Path(second))
            text = vergleich.compare(a, b, ("starter", "baseline"))
        self.assertIn("Einstufung", text)
        self.assertIn("Gesamtkosten", text)
        self.assertIn("hannover_frei", text)  # der Starter scheitert dort, die Baseline nicht
        self.assertIn("0% ->  100%", text)

    def test_missing_directory_gives_a_helpful_message(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            vergleich.load(Path("/nonexistent-autonomy_recovery_sim-dir"))
        self.assertIn("batch", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
