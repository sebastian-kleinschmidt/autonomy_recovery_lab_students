from __future__ import annotations

from .agent_session import AgentSession
from .commands import OBSTRUCTION_TYPES
from .models import CommandRequest
from .tools import SituationTools

WAIT_STEP_S = 10.0
WAIT_BUDGET_S = 30.0
NUDGE_DISTANCE_M = 35.0
KIND_TO_OBSTRUCTION = {kind: name for name, kind in OBSTRUCTION_TYPES.items()}


def _command(command: str, reason: str, **parameters: object) -> dict[str, object]:
    return {"command": command, "parameters": parameters, "reason": reason}


def _waited_s(history: list[dict[str, object]]) -> float:
    return sum(
        float(item.get("elapsed_s") or 0.0) for item in history if item.get("command") == "WAIT"
    )


def decide_by_rules(session: AgentSession, *, allow_remote_assistance: bool = True) -> dict[str, object]:
    """Deterministische Regelkaskade: gleichzeitig Baseline und Regel-Engine.

    Sie kennt nur konservative Standardfaelle. Was sie nicht loesen kann, endet
    nach dem Wartebudget in Remote Assistance (falls erlaubt) oder SAFE_STOP.
    """
    history = list(session.call_tool("get_recovery_history")["attempts"])  # type: ignore[arg-type]
    route = session.call_tool("get_route_state")
    mission = session.call_tool("get_mission_context")
    waited = _waited_s(history)

    def give_up(reason: str) -> dict[str, object]:
        if waited < WAIT_BUDGET_S:
            return _command("WAIT", reason, duration_s=WAIT_STEP_S)
        if (
            allow_remote_assistance
            and mission["remote_assistance_available"]
            and mission["remote_assistance_calls"] == 0
        ):
            return _command(
                "REQUEST_REMOTE_ASSISTANCE",
                "Wartebudget erschoepft, keine sichere lokale Recovery",
                reason_code="NO_SAFE_RECOVERY",
            )
        return _command(
            "SAFE_STOP", "Wartebudget erschoepft, keine sichere lokale Recovery",
            reason_code="UNRECOVERABLE_BLOCKAGE",
        )

    if route["route_blocked"]:
        if float(route["reverse_required_m"]) > 0.0:
            return _command(
                "REVERSE_SHORT",
                "Fuer das Umplanen fehlt Manoevrierraum",
                max_distance_m=min(5.0, max(0.5, float(route["reverse_required_m"]) + 0.5)),
            )
        if route["alternative_route_available"]:
            return _command(
                "REPLAN_ROUTE", "Geplante Route ist blockiert; Alternativroute vorhanden",
                avoid_current_segment=True,
            )
        return give_up("Route blockiert und keine Alternative")

    blocker = session.call_tool("get_blocker")
    if not blocker["detected"]:
        vulnerable = session.call_tool("check_vulnerable_road_users")
        return give_up(
            "Ungeschuetzte Verkehrsteilnehmende queren; warten"
            if vulnerable["conflict"]
            else "Keine dauerhafte Blockade erkannt"
        )

    marking = session.call_tool("get_center_marking")
    visibility = session.call_tool("get_visibility")
    rear = session.call_tool("check_rear_traffic", {"horizon_s": 6.0})
    vulnerable = session.call_tool("check_vulnerable_road_users")
    oncoming = session.call_tool("check_oncoming_traffic", {"horizon_s": 8.0})
    clearance = session.call_tool("get_lateral_clearance")

    if vulnerable["conflict"]:
        return give_up("Ungeschuetzte Verkehrsteilnehmende befinden sich im Fahrkorridor")

    profile = blocker.get("obstacle_profile")
    if (
        blocker.get("kind") == "debris"
        and float(blocker.get("track_confidence", 1.0)) >= 0.9
        and isinstance(profile, dict)
        and float(profile.get("assessment_confidence", 0.0)) >= 0.9
        and float(profile.get("height_m", 999.0)) <= 0.12
        and profile.get("material") in {"CARDBOARD", "FOAM"}
        and profile.get("deformability") == "HIGH"
        and not profile.get("sharp_edges", True)
        and not profile.get("liquid", True)
        and visibility["sufficient"]
    ):
        return _command(
            "CROSS_LOW_RISK_OBJECT",
            "Sehr flaches, stark verformbares Objekt mit hoher Klassifikationssicherheit",
            max_speed_mps=1.0,
        )

    adjacent = [
        lane for lane in mission["adjacent_lanes"]  # type: ignore[union-attr]
        if lane["side"] == "RIGHT" and lane["direction"] == "SAME" and lane["available"]
    ]
    if adjacent and not rear["conflict"]:
        return _command(
            "CHANGE_LANE", "Freie Nachbarspur in Fahrtrichtung neben dem Hindernis", direction="RIGHT"
        )

    if not visibility["sufficient"]:
        return give_up("Sichtweite reicht fuer ein Ausweichmanoever nicht aus")

    obstruction = KIND_TO_OBSTRUCTION.get(str(blocker.get("kind")))
    if obstruction is not None and mission["shoulder_m"] >= 2.6:
        return _command(
            "AVOID_TEMPORARY_OBSTRUCTION",
            "Kleines voruebergehendes Hindernis, seitlich umfahrbar",
            obstruction_type=obstruction,
            # Liegt das Objekt rechts der Spurmitte, genuegt ein kleiner Versatz nach links
            # innerhalb der Spur; sonst wird rechts ausgewichen (keine Mittellinie).
            side="LEFT" if float(blocker["d_m"]) <= float(session.context["mission"]["normal_lane_d_m"]) - 0.3 else "RIGHT",
            max_lateral_offset_m=2.0,
        )

    if marking["type"] == "solid" and not marking["exception_allowed"]:
        return give_up("Durchgezogene Linie ohne Ausnahmefreigabe")
    if rear["conflict"]:
        return give_up("Ein Fahrzeug ueberholt bereits von hinten")
    if oncoming["conflict"]:
        return give_up("Gegenverkehr im Freigabehorizont")
    if clearance["available_m"] < clearance["required_m"]:
        return give_up("Seitlicher Sicherheitsabstand reicht nicht aus")

    return _command(
        "NUDGE_AROUND_OBSTACLE",
        "Blocker steht; Fahrkorridor, Sicht und Gegenfahrbahn sind frei",
        side="LEFT",
        max_longitudinal_distance_m=NUDGE_DISTANCE_M,
    )


def heuristic_agent(session: AgentSession) -> CommandRequest:
    """Transparent tool-using baseline for comparison with student agents."""
    return session.submit_decision(decide_by_rules(session))


def rule_engine(session: AgentSession) -> dict[str, object]:
    """Entscheidung der Regel-Engine (ESCALATE_TO_RULE_ENGINE), ohne Remote Assistance."""
    return decide_by_rules(session, allow_remote_assistance=False)


def heuristic_recovery_agent(tools: SituationTools) -> CommandRequest:
    """Convenience wrapper for callers using the direct Python tool API."""
    return heuristic_agent(AgentSession(tools, time_s=0.0, stopped_for_s=0.0))
