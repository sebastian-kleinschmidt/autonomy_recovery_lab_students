"""Pruefstand: eigener Agentenloop, Spielmodell und nachvollziehbare Berichte."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from autonomy_recovery_sim import student_loop_agent
from autonomy_recovery_sim.agent_contract import AgentContractError
from autonomy_recovery_sim.agent_session import AgentSessionError
from autonomy_recovery_sim.batch import run_batch
from autonomy_recovery_sim.policy import heuristic_agent
from autonomy_recovery_sim.simulation import run_scenario
from autonomy_recovery_sim.tutorials import spielmodell

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "autonomy_recovery_sim"
SCENARIOS = SIM / "scenarios"


def with_rejection_feedback(session):
    """Baustelle A, so wie ein Team sie loesen koennte: Ablehnungen gehen ans Modell zurueck."""
    base = student_loop_agent
    messages = [
        {"role": "system", "content": base.SYSTEM_PROMPT},
        {"role": "user", "content": base.build_task(session)},
    ]
    tools = base.choose_tools(session)
    for _ in range(base.MAX_ROUNDS):
        message = base.ask_model(messages, tools)["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
        for call in calls:
            name = call["function"]["name"]
            arguments = json.loads(call["function"]["arguments"] or "{}")
            if name == "submit_decision":
                try:
                    return session.submit_decision(arguments)
                except (AgentContractError, AgentSessionError) as exc:
                    content = {"ok": False, "error": str(exc)}
            else:
                content = base.run_tool(session, name, arguments)
            messages.append(base.tool_message(call["id"], name, content))
    raise RuntimeError("keine Entscheidung")


@mock.patch.dict(os.environ, {"AUTONOMY_RECOVERY_MODEL": "spielmodell"})
class LoopAgentTest(unittest.TestCase):
    def test_the_scaffold_runs_without_a_key_and_matches_the_documented_zero_point(self) -> None:
        batch = run_batch(
            SIM / "scenario_sets/released_sprint1.txt",
            agent=student_loop_agent.decide,
            agent_name="loop",
        )
        summary = batch.to_dict()["summary"]
        self.assertEqual((summary["passed_count"], summary["scenario_count"]), (5, 8))  # Stufe 3b, Schritt 1
        self.assertEqual(summary["collision_count"], 0)
        self.assertGreater(summary["average_model_tokens"], 0)  # Modellrunden landen im Trace

    def test_rejection_feedback_is_a_measurable_improvement(self) -> None:
        scenario = SCENARIOS / "hannover_durchgezogen.json"
        naive = run_scenario(scenario, agent=student_loop_agent.decide, agent_name="loop")
        improved = run_scenario(scenario, agent=with_rejection_feedback, agent_name="loop-a")
        self.assertIsNotNone(naive.agent_error)
        self.assertIn("RULE_REJECTED", naive.agent_error)
        self.assertIsNone(improved.agent_error)
        self.assertTrue(improved.command_correct)

    def test_the_toy_model_retries_a_failing_tool_at_most_twice(self) -> None:
        failing = {"role": "tool", "name": "get_blocker", "content": json.dumps({"ok": False, "error": "x"})}
        payload = {
            "messages": [{"role": "user", "content": "Lage"}, failing, failing],
            "tools": [{"type": "function", "function": {"name": name}} for name in ("get_blocker", "submit_decision")],
        }
        calls = spielmodell.answer(payload)["choices"][0]["message"]["tool_calls"]
        self.assertEqual([call["function"]["name"] for call in calls], ["submit_decision"])


class ReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source = SIM / "scenario_sets/released_sprint1.txt"
        cls.batch = run_batch(source, agent=heuristic_agent, agent_name="baseline")
        cls.hidden = run_batch(
            SCENARIOS / "hannover_schmal.json",
            agent=lambda session: session.submit_decision(
                {"command": "WAIT", "parameters": {"duration_s": 5.0}, "reason": "test"}
            ),
            agent_name="waiter",
            hide_reference=True,
        )

    def test_every_scenario_gets_a_finding_a_release_and_a_detail_page(self) -> None:
        payload = self.batch.to_dict()
        self.assertEqual(
            [row["release"] for row in payload["releases"]], ["bootcamp", "sprint1"]
        )
        for entry in payload["scenarios"]:
            self.assertTrue(entry["diagnosis"])
            self.assertIn(entry["release"], {"bootcamp", "sprint1"})
            self.assertEqual(entry["details"], f"scenarios/{entry['scenario_id']}/report.md")
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            self.batch.write(target)
            markdown = (target / "batch-report.md").read_text("utf8")
            self.assertIn("## Nach Freigabestufe", markdown)
            self.assertIn("(scenarios/hannover_frei/report.md)", markdown)
            detail = (target / "scenarios/hannover_frei/report.md").read_text("utf8")
            for heading in ("## Befund", "## Kennzahlen", "## Befehlsfolge", "## Agent-Trace", "### Sitzung 1"):
                self.assertIn(heading, detail)
            html = (target / "batch-report.html").read_text("utf8")
            self.assertIn("Nach Freigabestufe", html)
            self.assertIn('href="scenarios/hannover_frei/report.md"', html)

    def test_findings_explain_why_a_case_failed(self) -> None:
        def always_nudge(session):
            for name in ("get_blocker", "get_center_marking", "check_oncoming_traffic", "check_rear_traffic",
                         "check_vulnerable_road_users", "get_lateral_clearance", "get_visibility"):
                session.call_tool(name)
            return session.submit_decision(
                {"command": "NUDGE_AROUND_OBSTACLE", "parameters": {"side": "LEFT", "max_longitudinal_distance_m": 35.0}, "reason": "test"}
            )

        failed = run_batch(SCENARIOS / "hannover_sichtweite.json", agent=always_nudge, agent_name="nudge")
        findings = failed.to_dict()["scenarios"][0]["diagnosis"]
        self.assertFalse(failed.evaluations[0].passed)
        self.assertTrue(findings[0].startswith(("Fehlalarm", "Agentenfehler", "Unerwartetes")), findings)

    def test_hidden_reference_keeps_solutions_out_of_the_reports(self) -> None:
        payload = self.hidden.to_dict()
        entry = payload["scenarios"][0]
        self.assertTrue(payload["hide_reference"])
        self.assertNotIn("expected_commands", entry)
        self.assertFalse(any("Referenz" in finding for finding in entry["diagnosis"]))
        with tempfile.TemporaryDirectory() as folder:
            self.hidden.write(Path(folder))
            detail = (Path(folder) / "scenarios/hannover_schmal/report.md").read_text("utf8")
            raw = json.loads((Path(folder) / "scenarios/hannover_schmal/result.json").read_text("utf8"))
            batch_raw = json.loads((Path(folder) / "batch-result.json").read_text("utf8"))
        self.assertNotIn("Referenzbegruendung", detail)
        self.assertNotIn("Referenzbefehl", detail)
        for key in ("expected_commands", "expected_reason", "expected_sequence", "intervention_expected"):
            self.assertNotIn(key, raw)
        for key in ("expected_commands", "expected_outcome", "intervention_expected"):
            self.assertNotIn(key, batch_raw["scenarios"][0])
        self.assertIn("command", raw)  # das eigene Verhalten bleibt vollstaendig nachvollziehbar
        self.assertIn("agent_trace", raw)

    def test_hidden_findings_do_not_reveal_the_kind_of_solution(self) -> None:
        def always_nudge(session):
            for name in ("get_blocker", "get_center_marking", "check_oncoming_traffic", "check_rear_traffic",
                         "check_vulnerable_road_users", "get_lateral_clearance", "get_visibility"):
                session.call_tool(name)
            return session.submit_decision(
                {"command": "NUDGE_AROUND_OBSTACLE", "parameters": {"side": "LEFT", "max_longitudinal_distance_m": 35.0}, "reason": "test"}
            )

        hidden = run_batch(SCENARIOS / "hannover_sichtweite.json", agent=always_nudge, agent_name="n", hide_reference=True)
        findings = " ".join(hidden.to_dict()["scenarios"][0]["diagnosis"])
        for revealing in ("Fehlalarm", "Verpasster Eingriff", "Unerwartetes", "Referenz"):
            self.assertNotIn(revealing, findings)


class CommandLineTest(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "autonomy_recovery_sim", "batch", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_release_selects_the_cumulative_set_and_prints_the_release_table(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            completed = self.run_cli("--release", "bootcamp", "--agent", "baseline", "--output", folder)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Szenarien:  3/3 bestanden", completed.stdout)
            self.assertIn("bootcamp", completed.stdout)
            self.assertTrue((Path(folder) / "scenarios/hannover_frei/report.md").is_file())

    def test_source_and_release_are_mutually_exclusive(self) -> None:
        completed = self.run_cli("autonomy_recovery_sim/scenarios", "--release", "sprint1")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("nicht gleichzeitig", completed.stderr)


if __name__ == "__main__":
    unittest.main()
