"""Ein gespieltes Sprachmodell zum Entwickeln ohne Schluessel (Stufe 3b).

Es spricht dasselbe Nachrichtenformat wie ein OpenAI-kompatibler Endpunkt, entscheidet
aber mit wenigen festen Regeln und ist deterministisch. Es ist absichtlich einfaeltig:

- Runde 1: Es fragt die sieben Lagewerkzeuge und ``get_traffic_control`` ab; im
  Wahrnehmungsmodell ``tracked`` stattdessen die drei Messwerkzeuge und rechnet mit
  ``recovery_helpers``.
- Danach: Rot oder geschlossene Schranke, kein Blocker, Personen, Gegen- oder
  Rueckverkehr fuehren zu ``WAIT``; sonst versucht es ``NUDGE_AROUND_OBSTACLE``.
- Kommt eine Entscheidung als Fehler zurueck, weicht es auf ``WAIT`` aus.

Es kennt keine durchgezogene Linie, keine dunkle Ampel, keine Kosten und liest keine
Freitexte. Ein guter Agentenloop macht auch aus diesem Modell mehr, als es allein kann;
ein echtes Modell kann mehr als dieses hier.

Nutzung im eigenen Agenten: ``AUTONOMY_RECOVERY_MODEL=spielmodell`` setzen.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from autonomy_recovery_sim.commands import MANEUVER_EVIDENCE_TOOLS

MODEL_NAME = "spielmodell"
FIRST_ROUND_TOOLS = tuple(sorted(MANEUVER_EVIDENCE_TOOLS)) + ("get_traffic_control",)
TRACKED_FIRST_ROUND_TOOLS = ("get_tracked_objects", "get_sensor_coverage", "get_map_context", "get_traffic_control")
HOLDING_STATES = {"RED", "YELLOW", "CLOSED"}


def _reply(content: str | None, tool_calls: list[dict[str, object]], prompt_chars: int) -> dict[str, object]:
    tokens = prompt_chars // 4  # grobe Schaetzung wie bei echten Modellen (~4 Zeichen je Token)
    return {
        "choices": [
            {
                "finish_reason": "tool_calls" if tool_calls else "stop",
                "message": {"role": "assistant", "content": content, "tool_calls": tool_calls},
            }
        ],
        "usage": {"prompt_tokens": tokens, "completion_tokens": 40, "total_tokens": tokens + 40},
    }


def _call(index: int, name: str, arguments: Mapping[str, object] | None = None) -> dict[str, object]:
    return {
        "id": f"spiel-{index}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(dict(arguments or {}))},
    }


def _decision(command: str, reason: str, **parameters: object) -> dict[str, object]:
    return {"command": command, "parameters": parameters, "reason": reason}


def _tool_results(messages: list[Mapping[str, Any]]) -> tuple[dict[str, Any], bool, dict[str, int]]:
    """Letzte Ergebnisse je Werkzeug, ob die letzte Entscheidung abgelehnt wurde, Fehlschlaege."""
    results: dict[str, Any] = {}
    failures: dict[str, int] = {}
    rejected = False
    for message in messages:
        if message.get("role") != "tool":
            continue
        try:
            content = json.loads(str(message.get("content") or "{}"))
        except json.JSONDecodeError:
            continue
        name = str(message.get("name", ""))
        if name == "submit_decision":
            rejected = not content.get("ok", False)
        elif content.get("ok"):
            results[name] = content.get("result")
        else:
            failures[name] = failures.get(name, 0) + 1
    return results, rejected, failures


def _choose(results: Mapping[str, Any]) -> dict[str, object]:
    controls = (results.get("get_traffic_control") or {}).get("controls", [])
    if any(item.get("state") in HOLDING_STATES for item in controls):
        return _decision("WAIT", "Signal zeigt Halt", duration_s=10.0)
    if not (results.get("get_blocker") or {}).get("detected"):
        return _decision("WAIT", "Kein Hindernis erkannt", duration_s=10.0)
    for name in ("check_vulnerable_road_users", "check_oncoming_traffic", "check_rear_traffic"):
        if (results.get(name) or {}).get("conflict"):
            return _decision("WAIT", f"Konflikt laut {name}", duration_s=10.0)
    return _decision(
        "NUDGE_AROUND_OBSTACLE",
        "Hindernis steht, keine Konflikte gemeldet",
        side="LEFT",
        max_longitudinal_distance_m=35.0,
    )


def _choose_tracked(results: Mapping[str, Any]) -> dict[str, object]:
    """Dieselben einfachen Regeln, aber selbst aus der Objektliste gerechnet."""
    from autonomy_recovery_sim import recovery_helpers as helpers

    controls = (results.get("get_traffic_control") or {}).get("controls", [])
    if any(item.get("state") in HOLDING_STATES for item in controls):
        return _decision("WAIT", "Signal zeigt Halt", duration_s=10.0)
    objects, lanes = results.get("get_tracked_objects"), results.get("get_map_context")
    coverage = results.get("get_sensor_coverage")
    if not objects or not lanes or not coverage:
        return _decision("WAIT", "Keine Messung", duration_s=10.0)
    if helpers.blocker_ahead(objects, lanes) is None:
        return _decision("WAIT", "Kein Hindernis erkannt", duration_s=10.0)
    if helpers.vulnerable_road_users(objects, lanes)["conflict"] or helpers.oncoming_conflict(objects, lanes)["conflict"]:
        return _decision("WAIT", "Konflikt in der Objektliste", duration_s=10.0)
    return _decision(
        "NUDGE_AROUND_OBSTACLE",
        "Hindernis steht, keine Konflikte gemessen",
        side="LEFT",
        max_longitudinal_distance_m=35.0,
    )


def answer(payload: Mapping[str, object]) -> dict[str, object]:
    """Antwortet auf eine Chat-Completion-Anfrage wie ein Endpunkt es taete."""
    messages = list(payload.get("messages") or [])  # type: ignore[arg-type]
    offered = {
        str(tool.get("function", {}).get("name"))
        for tool in payload.get("tools") or []  # type: ignore[union-attr]
        if isinstance(tool, Mapping)
    }
    prompt_chars = len(json.dumps(messages, ensure_ascii=False))
    results, rejected, failures = _tool_results(messages)
    if "submit_decision" not in offered:
        return _reply("Ich kann ohne submit_decision nicht entscheiden.", [], prompt_chars)
    if rejected:
        decision = _decision("WAIT", "Vorschlag wurde abgelehnt; sicher warten", duration_s=10.0)
        return _reply(None, [_call(99, "submit_decision", decision)], prompt_chars)
    tracked = "get_tracked_objects" in offered
    missing = [
        name
        for name in (TRACKED_FIRST_ROUND_TOOLS if tracked else FIRST_ROUND_TOOLS)
        if name in offered and name not in results and failures.get(name, 0) < 2
    ]
    if missing:
        return _reply(None, [_call(index, name) for index, name in enumerate(missing, start=1)], prompt_chars)
    choice = _choose_tracked(results) if tracked else _choose(results)
    return _reply(None, [_call(99, "submit_decision", choice)], prompt_chars)
