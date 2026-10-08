"""Nachvollziehbare Batchberichte: Diagnose je Fall, Freigabestufen und Detailseiten.

Der Batchbericht sagt nicht nur *ob*, sondern *warum* ein Szenario scheitert, und
verlinkt fuer jedes Szenario eine Detailseite mit Befehlsfolge und Agent-Trace.
Mit ``hide_reference`` entfallen Referenzbefehle und Referenzbegruendung (verdeckte
Bewertungsfaelle); ``result.json`` enthaelt sie weiterhin.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .report_html import COST_LABELS

if TYPE_CHECKING:
    from .batch import ScenarioEvaluation

CATALOG = Path(__file__).with_name("scenario_catalog.json")
MANEUVERS = frozenset(
    {"NUDGE_AROUND_OBSTACLE", "AVOID_TEMPORARY_OBSTRUCTION", "CHANGE_LANE", "CROSS_LOW_RISK_OBJECT"}
)
OUTCOME_LABELS = {
    "not_triggered": "kein Deadlock ausgeloest",
    "waiting": "steht am Ende noch",
    "resolved": "Lage hat sich aufgeloest",
    "liberated": "Fahrzeug befreit",
    "aborted": "Manoever sicher abgebrochen",
    "rerouted": "umgeplant",
    "safe_stopped": "sicher angehalten (Bergung)",
    "mission_aborted": "Mission abgebrochen",
    "returned_home": "zum Hub zurueckgekehrt",
    "passenger_dropped": "Fahrgaeste abgesetzt",
    "remote_resolved": "durch die Leitstelle geloest",
}


@lru_cache(maxsize=1)
def catalog() -> dict[str, dict[str, Any]]:
    """Katalogeintraege (Freigabe, Fokus, Tags) je Szenario-ID; leer, falls nicht vorhanden."""
    if not CATALOG.is_file():
        return {}
    data = json.loads(CATALOG.read_text(encoding="utf8"))
    return {str(entry["id"]): entry for entry in data.get("scenarios", [])}


def release_order() -> list[str]:
    if not CATALOG.is_file():
        return []
    return list(json.loads(CATALOG.read_text(encoding="utf8")).get("release_order", []))


def _outcome(value: str) -> str:
    return f"{value} ({OUTCOME_LABELS[value]})" if value in OUTCOME_LABELS else value


def _costs_text(costs: dict[str, Any]) -> str:
    items = sorted(costs.get("items_eur", {}).items(), key=lambda item: -float(item[1]))
    return ", ".join(f"{COST_LABELS.get(name, name)} {float(value):.2f}" for name, value in items) or "keine"


def diagnose(item: ScenarioEvaluation, *, hide_reference: bool = False) -> list[str]:
    """Kurze, handlungsleitende Befunde; der erste nennt den wichtigsten Grund."""
    result = item.result
    scenario = result.scenario
    findings: list[str] = []
    if result.collision:
        findings.append("Sicherheit: Kollision. Das ist immer ein Fehlschlag und fuehrt zur Einstufung D.")
    if result.agent_error is not None:
        findings.append(
            f"Agentenfehler: {result.agent_error}. Der Simulator ist fail-safe auf WAIT ausgewichen."
        )
    if not result.command_correct and result.agent_error is not None:
        # Nach einem Agentenfehler stammt der ausgefuehrte Befehl aus dem fail-safe.
        findings.append("Der ausgefuehrte Befehl stammt aus dem fail-safe und zaehlt nicht als Entscheidung des Agenten.")
    elif not result.command_correct and hide_reference:
        # Verdeckt: keine Kategorie (Fehlalarm, verpasster Eingriff), sie verriete die Loesung.
        findings.append(f"Erster inhaltlicher Befehl {result.command} passt nicht zur Lage.")
    elif not result.command_correct:
        reference = f" Referenz: {' oder '.join(result.expected_commands)}."
        if result.command == "NONE":
            findings.append("Kein Befehl: Der Agent wurde nie aktiviert oder hat nichts eingereicht." + reference)
        elif result.intervened and not result.intervention_expected:
            findings.append(
                f"Fehlalarm: erster Befehl {result.command}, obwohl Warten gereicht haette." + reference
            )
        elif not result.intervened and result.intervention_expected:
            findings.append(
                f"Verpasster Eingriff: erster Befehl {result.command}, die Lage verlangt aber einen Eingriff."
                + reference
            )
        elif result.command in MANEUVERS and not MANEUVERS.intersection(result.expected_commands):
            findings.append(f"Unerwartetes Manoever: {result.command} in einer Lage ohne Manoeverloesung." + reference)
        else:
            findings.append(f"Erster inhaltlicher Befehl {result.command} passt nicht zur Lage." + reference)
    if result.outcome != scenario.expected_outcome and not hide_reference:
        findings.append(
            f"Ausgang {_outcome(result.outcome)} statt {_outcome(scenario.expected_outcome)}."
        )
    elif result.outcome != scenario.expected_outcome:
        findings.append(f"Ausgang {_outcome(result.outcome)} entspricht nicht dem erwarteten Ausgang.")
    steps = scenario.expected_sequence
    if steps and not result.sequence_complete:
        missing = "" if hide_reference else f" Naechster fehlender Schritt: {' oder '.join(steps[result.sequence_matched])}."
        findings.append(
            f"Loesungsweg unvollstaendig: {result.sequence_matched} von {len(steps)} Schritten erfolgreich erledigt."
            + missing
        )
    if not result.within_budget:
        findings.append(
            f"Budget ueberschritten: {float(result.costs['total_eur']):.2f} von {scenario.budget_eur:.0f} EUR "
            f"(Posten: {_costs_text(result.costs)})."
        )
    if scenario.expected_outcome == "aborted" and result.maneuver_aborted and not result.abort_stabilized:
        findings.append("Abbruch nicht sicher stabilisiert.")
    rejected = [entry for entry in result.agent_trace if entry["type"] == "decision_attempt" and not entry.get("accepted")]
    if rejected:
        codes = sorted({str(entry.get("error_code", "?")) for entry in rejected})
        findings.append(f"Hinweis: {len(rejected)} abgelehnte Entscheidungsversuche ({', '.join(codes)}).")
    tool_errors = [entry for entry in result.agent_trace if entry["type"] == "tool_call" and "error" in entry]
    if tool_errors:
        findings.append(f"Hinweis: {len(tool_errors)} fehlgeschlagene Werkzeugaufrufe.")
    if not findings:
        findings.append("Alle Kriterien erfuellt.")
    return findings


def release_summary(evaluations: tuple[ScenarioEvaluation, ...]) -> list[dict[str, object]]:
    """Bestehensquote je Freigabestufe (Bootcamp, Sprint 1-4, sonstige)."""
    entries = catalog()
    groups: dict[str, list[ScenarioEvaluation]] = {}
    for item in evaluations:
        release = str(entries.get(item.result.scenario_id, {}).get("release", "ohne Katalog"))
        groups.setdefault(release, []).append(item)
    order = release_order() + sorted(set(groups) - set(release_order()))
    return [
        {
            "release": release,
            "scenario_count": len(groups[release]),
            "passed_count": sum(item.passed for item in groups[release]),
            "total_cost_eur": round(sum(float(item.result.costs["total_eur"]) for item in groups[release]), 2),
            "collision_count": sum(item.result.collision for item in groups[release]),
        }
        for release in order
        if release in groups
    ]


def _short(value: object, limit: int = 180) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _trace_lines(trace: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    session = None
    for entry in trace:
        if entry.get("session") != session:
            session = entry.get("session")
            lines += ["", f"### Sitzung {session}", ""]
        kind = entry["type"]
        if kind == "model_round":
            tokens = (entry.get("usage") or {}).get("total_tokens")
            names = ", ".join(entry.get("tool_names") or []) or "keine Werkzeuge (Text)"
            suffix = f", {tokens} Tokens" if tokens else ""
            lines.append(f"- Modellrunde {entry.get('index')}: {names} ({entry.get('latency_s', 0)} s{suffix})")
        elif kind == "tool_call":
            arguments = _short(entry.get("arguments") or {}, 60)
            if "error" in entry:
                lines.append(f"- Werkzeug `{entry['name']}` {arguments} → **Fehler:** {_short(entry['error'])}")
            else:
                lines.append(f"- Werkzeug `{entry['name']}` {arguments} → `{_short(entry.get('result'))}`")
        elif kind == "decision_attempt":
            if entry.get("accepted"):
                lines.append(
                    f"- Entscheidung {entry.get('index')}: **{entry.get('command')}** "
                    f"{_short(entry.get('parameters') or {}, 80)} angenommen. Begruendung: {_short(entry.get('reason', ''), 120)}"
                )
            else:
                lines.append(f"- Entscheidung {entry.get('index')}: **abgelehnt** – {_short(entry.get('error', ''))}")
    return lines


def scenario_markdown(item: ScenarioEvaluation, *, hide_reference: bool = False) -> str:
    """Detailseite eines Szenarios: Befund, Kennzahlen, Befehlsfolge und Agent-Trace."""
    result = item.result
    scenario = result.scenario
    entry = catalog().get(result.scenario_id, {})
    trace = result.agent_trace
    tokens = sum(
        int((e.get("usage") or {}).get("total_tokens", 0))
        for e in trace
        if e["type"] == "model_round" and isinstance(e.get("usage"), dict)
    )
    lines = [
        f"# {result.scenario_id}: {'bestanden' if item.passed else 'nicht bestanden'}",
        "",
        f"Freigabe: {entry.get('release', '–')} · Fokus: {entry.get('focus', '–')} · "
        f"Tags: {', '.join(entry.get('tags', [])) or '–'} · Agent: {result.agent_name}"
        + (f" · Lauf {item.run_index}" if item.run_index > 1 else ""),
        "",
        "## Befund",
        "",
        *[f"- {finding}" for finding in diagnose(item, hide_reference=hide_reference)],
        "",
        "## Kennzahlen",
        "",
        "| Kriterium | Ergebnis |",
        "|---|---|",
        f"| Erster inhaltlicher Befehl | {result.command} ({'passt' if result.command_correct else 'passt nicht'}) |",
        f"| Ausgang | {_outcome(result.outcome)} |",
        f"| Kosten / Budget | {float(result.costs['total_eur']):.2f} / {scenario.budget_eur:.0f} EUR ({_costs_text(result.costs)}) |",
        f"| Kollision | {'ja' if result.collision else 'nein'} |",
        *(
            [f"| Loesungsweg | {result.sequence_matched} von {len(scenario.expected_sequence)} Schritten |"]
            if scenario.expected_sequence
            else []
        ),
        f"| Kundenzufriedenheit | {result.costs['customer_satisfaction'] if result.costs['customer_satisfaction'] is not None else '–'} |",
        f"| Werkzeugaufrufe | {sum(e['type'] == 'tool_call' for e in trace)} |",
        f"| Entscheidungsversuche | {sum(e['type'] == 'decision_attempt' for e in trace)} |",
        f"| Modellrunden / Tokens | {sum(e['type'] == 'model_round' for e in trace)} / {tokens} |",
    ]
    if not hide_reference:
        lines += [
            f"| Referenzbefehl | {' oder '.join(result.expected_commands) or '–'} |",
            *(
                [f"| Referenzweg | {' → '.join(' oder '.join(step) for step in scenario.expected_sequence)} |"]
                if scenario.expected_sequence
                else []
            ),
            f"| Erwarteter Ausgang | {_outcome(scenario.expected_outcome)} |",
        ]
    lines += ["", "## Befehlsfolge", ""]
    if result.commands:
        lines += ["| # | Befehl | Parameter | Status | Ergebnis | Quelle |", "|---:|---|---|---|---|---|"]
        for index, command in enumerate(result.commands, start=1):
            lines.append(
                f"| {index} | {command['command']} | `{_short(command.get('parameters', {}), 70)}` "
                f"| {command.get('status', '')} | {command.get('outcome', '')} | {command.get('source', '')} |"
            )
    else:
        lines.append("Kein Befehl ausgefuehrt.")
    lines += ["", "## Agent-Trace"]
    lines += _trace_lines(trace) if trace else ["", "Kein Trace: Der Agent wurde nicht aktiviert."]
    if not hide_reference:
        lines += [
            "",
            "## Referenzbegruendung",
            "",
            "Erst lesen, wenn ihr eine eigene Erklaerung fuer den Befund aufgeschrieben habt.",
            "",
            f"> {scenario.expected_reason}",
        ]
    lines += ["", "Rohdaten: `result.json` im selben Ordner.", ""]
    return "\n".join(lines)
