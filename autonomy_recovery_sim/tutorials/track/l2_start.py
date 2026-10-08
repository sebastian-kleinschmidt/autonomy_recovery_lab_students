"""Lektion 1: Der einfachste Agent.

Ein Agent ist eine Funktion: Sie bekommt eine ``AgentSession`` und gibt genau einen Befehl
zurueck. Dieser Agent ruft noch kein Werkzeug auf. Er liest nur den Kontext der Sitzung
und wartet, beim wiederholten Aufruf jeweils laenger.

Startstand fuer Lektion 2.
"""

from __future__ import annotations

from autonomy_recovery_sim.agent_session import AgentSession

# Wartezeit je Sitzung: Wer nach einer Wartezeit wieder gerufen wird, wartet laenger.
WAIT_STEPS_S = (5.0, 10.0, 20.0)


def decide(session: AgentSession) -> dict[str, object]:
    context = session.context
    used = int(context["commands_used"])  # Befehle, die diese Episode schon gegeben hat
    duration = WAIT_STEPS_S[min(used, len(WAIT_STEPS_S) - 1)]
    stopped = float(context["ego"]["stopped_for_s"])  # type: ignore[index]
    return {
        "command": "WAIT",
        "parameters": {"duration_s": duration},
        "reason": f"Steht seit {stopped:.0f} s; Befehl Nr. {used + 1}: {duration:.0f} s warten",
    }
