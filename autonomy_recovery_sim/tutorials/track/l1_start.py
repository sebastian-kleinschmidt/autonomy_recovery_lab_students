"""Lektion 1: Startstand.

Ein Agent ist eine Funktion ``decide(session)``. Sie bekommt eine ``AgentSession`` und gibt
genau einen Befehl als Woerterbuch zurueck: ``command``, ``parameters`` und ``reason``.
Dieser Startstand wartet immer fuenf Sekunden. Anleitung: tutorials/L1-einfachster-agent.md.
"""

from __future__ import annotations

from autonomy_recovery_sim.agent_session import AgentSession


def decide(session: AgentSession) -> dict[str, object]:
    return {"command": "WAIT", "parameters": {"duration_s": 5.0}, "reason": "Startstand: immer warten"}
