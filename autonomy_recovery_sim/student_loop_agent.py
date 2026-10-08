"""Euer eigener Autonomy Recovery Agent mit selbst geschriebener Schleife (Stufe 3b).

Die Datei laeuft sofort und ist absichtlich naiv. Jede Stelle mit ``BAUSTELLE`` ist
eine Verbesserung, die ihr entwerft, begruendet und messt. Anleitung:
tutorials/archiv/03b-eigener-agent.md (der Tutorial-Track L5 baut einen hybriden Agenten).

Ohne Schluessel entwickeln:
    AUTONOMY_RECOVERY_MODEL=spielmodell python3 -m autonomy_recovery_sim batch \\
        autonomy_recovery_sim/scenario_sets/released_sprint1.txt \\
        --agent autonomy_recovery_sim.student_loop_agent:decide

Mit echtem Modell: Schluessel und Modell wie in QUICKSTART.md setzen, sonst gleich.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from .agent_contract import AgentContractError  # noqa: F401  (gebraucht fuer Baustelle A)
from .agent_session import AgentSession, AgentSessionError
from .llm_agent import LLMConfig, LLMServiceError, chat_completion, tool_definitions
from .models import CommandRequest

MAX_ROUNDS = 8  # Obergrenze der Modellrunden je Sitzung

# BAUSTELLE B (Rolle und Regeln): Was muss das Modell wissen, was erzwingt ohnehin das Programm?
SYSTEM_PROMPT = """Du bist der Autonomy Recovery Agent eines autonomen Kleinbusses.
Das Fahrzeug steht. Untersuche die Lage mit den Werkzeugen und reiche genau einen
Befehl mit submit_decision ein."""


# --------------------------------------------------------------------- Modellzugang


def ask_model(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
    """Ein Modellaufruf. ``AUTONOMY_RECOVERY_MODEL=spielmodell`` braucht keinen Schluessel."""
    payload = {
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0,
        "max_tokens": 1400,
    }
    if os.environ.get("AUTONOMY_RECOVERY_MODEL", "").strip() == "spielmodell":
        from .tutorials import spielmodell

        return spielmodell.answer({"model": spielmodell.MODEL_NAME, **payload})
    config = LLMConfig.from_environment()
    return chat_completion(config, {"model": config.model, **payload})


# ------------------------------------------------------------------ Kontext bauen


def build_task(session: AgentSession) -> str:
    """Die erste Nachricht an das Modell: Aufgabe und Ausgangslage."""
    # BAUSTELLE C (Kontext): Hier geht der komplette Sitzungskontext als JSON ans Modell,
    # inklusive Werkzeug- und Befehlskatalog, die das Modell ohnehin als tools bekommt.
    # Was braucht das Modell wirklich? Was kostet jedes weitere Token?
    return "Der Deadlock wurde erkannt. Ausgangslage: " + json.dumps(session.context, ensure_ascii=False)


def choose_tools(session: AgentSession) -> list[dict[str, Any]]:
    """Welche Werkzeuge das Modell angeboten bekommt."""
    # BAUSTELLE D (Werkzeuge): Alle Werkzeuge, immer. Reicht eine Auswahl? Braucht ihr ein
    # eigenes, zusammengesetztes Werkzeug (das ihr unten in run_tool selbst ausfuehrt)?
    return tool_definitions(session.tool_catalog)


# --------------------------------------------------------------- Werkzeuge ausfuehren


def run_tool(session: AgentSession, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Fuehrt einen Werkzeugaufruf des Modells aus; Fehler werden zu Daten, nicht zu Abstuerzen."""
    try:
        return {"ok": True, "result": session.call_tool(name, arguments)}
    except AgentSessionError as exc:
        return {"ok": False, "error": str(exc)}


def tool_message(call_id: str, name: str, content: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "name": name,
        "content": json.dumps(content, ensure_ascii=False),
    }


# ------------------------------------------------------------------- die Schleife


def decide(session: AgentSession) -> CommandRequest:
    # BAUSTELLE E (Regeln vor dem Modell): Jeder Fall geht ans Modell. Welche Faelle
    # entscheidet ein Programm billiger, schneller und verlaesslicher?
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_task(session)},
    ]
    tools = choose_tools(session)

    for round_index in range(1, MAX_ROUNDS + 1):
        started = time.monotonic()
        response = ask_model(messages, tools)
        message = response["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        # Protokoll fuer den Report: Latenz, Tokens und angefragte Werkzeuge je Runde.
        session.trace.append(
            {
                "type": "model_round",
                "index": round_index,
                "latency_s": round(time.monotonic() - started, 3),
                "finish_reason": response["choices"][0].get("finish_reason", ""),
                "tool_names": [call["function"]["name"] for call in calls],
                "usage": response.get("usage", {}),
            }
        )
        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
        if not calls:
            messages.append({"role": "user", "content": "Nutze die Werkzeuge und schliesse mit submit_decision ab."})
            continue

        for call in calls:
            name = call["function"]["name"]
            arguments = json.loads(call["function"].get("arguments") or "{}")
            if name == "submit_decision":
                # BAUSTELLE A (Ablehnungen): Eine abgelehnte Entscheidung wirft eine Ausnahme,
                # die Sitzung endet und der Simulator weicht fail-safe auf WAIT aus. Das Modell
                # erfaehrt nie, warum. Wie bekommt es eine zweite Chance (drei Versuche je Sitzung)?
                return session.submit_decision(arguments)
            messages.append(tool_message(call["id"], name, run_tool(session, name, arguments)))

    # BAUSTELLE F (Ende ohne Entscheidung): Was ist hier die sicherste Antwort?
    raise LLMServiceError(f"Keine Entscheidung nach {MAX_ROUNDS} Runden")
