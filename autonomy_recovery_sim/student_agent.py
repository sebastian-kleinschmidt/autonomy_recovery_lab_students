from __future__ import annotations

from .agent_session import AgentSession


def decide(session: AgentSession):
    """Sicherer Startpunkt: warten, bis hier eine eigene Policy implementiert ist."""
    blocker = session.call_tool("get_blocker")
    return session.submit_decision(
        {
            "command": "WAIT",
            "parameters": {"duration_s": 5.0},
            "reason": (
                "Studentischer Agent ist noch nicht implementiert; "
                f"Blockade erkannt: {blocker['detected']}"
            ),
        }
    )
