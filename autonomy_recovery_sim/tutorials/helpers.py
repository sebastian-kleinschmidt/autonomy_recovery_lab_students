"""Kleine, bewusst einfache Hilfen fuer eigene Agenten (siehe Tutorial 5).

Sie kapseln drei Gewohnheiten robuster Agenten: Werkzeugfehler begrenzt wiederholen,
das Alter der Daten pruefen und die sieben Belege fuer ein Manoever geordnet sammeln.
Sie entscheiden nichts: Die Strategie bleibt Aufgabe der Studierenden.
"""

from __future__ import annotations

from collections.abc import Mapping

from autonomy_recovery_sim.agent_session import AgentBudgetError, AgentSession, AgentToolError
from autonomy_recovery_sim.commands import MANEUVER_EVIDENCE_TOOLS

STALE_AFTER_S = 2.0


def call_with_retry(
    session: AgentSession,
    name: str,
    arguments: Mapping[str, object] | None = None,
    *,
    tries: int = 3,
) -> dict[str, object] | None:
    """Ruft ein Werkzeug auf und wiederholt es bei ``AgentToolError`` (z. B. Timeout).

    Gibt ``None`` zurueck, wenn alle Versuche scheitern. Jeder Versuch kostet Werkzeugbudget;
    ein ``AgentBudgetError`` wird nicht abgefangen, weil dann kein weiterer Versuch moeglich ist.
    """
    for _ in range(tries):
        try:
            return session.call_tool(name, arguments)
        except AgentToolError as error:
            if not error.retryable:
                return None
        except AgentBudgetError:
            raise
    return None


def is_stale(result: Mapping[str, object], *, max_age_s: float = STALE_AFTER_S) -> bool:
    """Wahr, wenn ein Werkzeugergebnis meldet, dass seine Daten zu alt sind."""
    age = result.get("observation_age_s")
    return isinstance(age, (int, float)) and age > max_age_s


def collect_evidence(session: AgentSession) -> dict[str, dict[str, object] | None]:
    """Sammelt die sieben Lagewerkzeuge, die jedes Fahrmanoever als Beleg verlangt.

    Fehlgeschlagene Werkzeuge stehen als ``None`` im Ergebnis; wer dann handelt, tut es ohne Beleg.
    """
    return {name: call_with_retry(session, name) for name in sorted(MANEUVER_EVIDENCE_TOOLS)}
