"""Regel- und Sicherheitspruefung fuer Befehlskandidaten.

Stellt die Rolle von Rule Engine und Safety Validator dar: Der Agent schlaegt
vor, dieses Modul lehnt ab. Die Pruefung ist nicht durch den Agenten
uebersteuerbar; jede Ablehnung nennt einen maschinenlesbaren Code.

Im Pruefmodus ``advisory`` oder ``off`` (Szenarioblock ``difficulty``) werden
Lagebeurteilungen aus ``WAIVABLE_SAFETY_CHECKS`` nur gemeldet statt abgelehnt.
Verkehrsregeln, Verfuegbarkeit und die Geometrie des Ausfuehrers gelten immer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .commands import COMMANDS, OBSTRUCTION_TYPES, CommandError
from .incidents import LEAVING_COMMANDS
from .models import ActorState, CommandRequest, EgoState, WorldFacts
from .scenario import Scenario
from .tools import SituationTools

NUDGE_LEFT_SPEED_MPS = 10.0 / 3.6
NUDGE_RIGHT_SPEED_MPS = 10.0 / 3.6
AVOID_SPEED_MPS = 2.0
CHANGE_LANE_SPEED_MPS = 3.0
AVOID_MAX_DISTANCE_M = 30.0
CHANGE_LANE_MAX_DISTANCE_M = 40.0
PASS_MARGIN_M = 0.5
SMALL_OBSTRUCTION_MARGIN_M = 0.4
REVERSE_REAR_MARGIN_M = 1.5
PULL_OVER_MARGIN_M = 0.3
LOW_RISK_MAX_HEIGHT_M = 0.12
LOW_RISK_MIN_CONFIDENCE = 0.9
LOW_RISK_MATERIALS = frozenset({"CARDBOARD", "FOAM"})
# Lagebeurteilungen, die der Agent selbst verantworten kann, weil die Simulation ihre
# Folgen abbildet (Kollision). Weitere kommen hinzu, sobald ihre Folgen modelliert sind.
WAIVABLE_SAFETY_CHECKS = frozenset(
    {
        "TARGET_LANE_OCCUPIED",
        "REAR_NOT_CLEAR",
        "VULNERABLE_ROAD_USER_IN_CORRIDOR",
        "VISIBILITY_INSUFFICIENT",
        # Ueberfahren eines ungeeigneten Objekts beschaedigt das Fahrzeug (incidents.UNDERBODY).
        "OBSTACLE_PROFILE_UNKNOWN",
        "OBJECT_CLASSIFICATION_UNCERTAIN",
        "OBJECT_TOO_HIGH",
        "OBJECT_NOT_DEFORMABLE",
        "SHARP_EDGES_DETECTED",
        "LIQUID_HAZARD_DETECTED",
        "ONCOMING_TOO_CLOSE",
        "REAR_TRAFFIC_APPROACHING",
    }
)
# PEEK_OUT: Gegenverkehr, der in diesem Horizont die Ausscherstelle erreicht, ist zu nah.
PEEK_ONCOMING_HORIZON_S = 4.0
# Wenden: Verkehr, der in diesem Horizont die Wendestelle erreicht, ist zu nah.
TURN_TRAFFIC_HORIZON_S = 8.0
# Groesster Lenkeinschlag des Fahrzeugmodells (dynamics.step_vehicle).
MAX_STEERING_RAD = math.radians(31.0)


@dataclass(frozen=True)
class PassPlan:
    """Geometrie und Grenzen eines Vorbeifahr- oder Spurwechselmanoevers."""

    target_d_m: float
    speed_mps: float
    max_distance_m: float
    keeps_new_lane: bool
    crosses_center: bool
    monitor_lane_d_m: float | None


def turning_radius_m(ego: EgoState, wheelbase_m: float = 2.99) -> float:
    """Wenderadius der Fahrzeugmitte bei vollem Lenkeinschlag (kinematisches Modell)."""
    return wheelbase_m / math.tan(MAX_STEERING_RAD) + ego.width_m / 2.0


def pull_over_target_d(scenario: Scenario, ego_width_m: float) -> float:
    return -(scenario.road.lane_width_m + ego_width_m / 2.0 + PULL_OVER_MARGIN_M)


def pull_over_possible(scenario: Scenario, ego_width_m: float, shoulder_m: float) -> bool:
    return shoulder_m >= ego_width_m + 2 * PULL_OVER_MARGIN_M - 1e-6


def _require_center_crossing_allowed(scenario: Scenario) -> None:
    if scenario.road.center_marking == "solid" and not scenario.allow_solid_exception:
        raise CommandError(
            "RULE_REJECTED", "CENTER_LINE_SOLID: durchgezogene Mittellinie ohne Ausnahmefreigabe"
        )


def _check_right_edge(scenario: Scenario, facts: WorldFacts, target_d: float, ego_width_m: float) -> None:
    if not scenario.allow_shoulder_passing:
        raise CommandError(
            "RULE_REJECTED",
            "SHOULDER_PASSING_NOT_ALLOWED: der Seitenstreifen darf nur zum sicheren Halten genutzt werden",
        )
    limit = -(scenario.road.lane_width_m + facts.shoulder_m)
    if target_d - ego_width_m / 2.0 < limit - 1e-6:
        raise CommandError(
            "SAFETY_REJECTED", "NO_SHOULDER_SPACE: rechts steht nicht genug befahrbarer Raum bereit"
        )


def plan_pass(
    request: CommandRequest,
    scenario: Scenario,
    ego: EgoState,
    blocker: ActorState,
    facts: WorldFacts,
) -> PassPlan:
    """Berechnet Zielquerablage und Grenzen; wirft CommandError bei Regelverstoss."""
    params = request.parameters
    lane_d = facts.lane_d_m
    lane_w = scenario.road.lane_width_m
    blocker_half = blocker.spec.width_m / 2.0
    ego_half = ego.width_m / 2.0

    if request.command in {"NUDGE_AROUND_OBSTACLE", "OVERTAKE"}:
        max_distance = float(params["max_longitudinal_distance_m"])
        if params["side"] == "LEFT":
            _require_center_crossing_allowed(scenario)
            target = max(lane_d + lane_w, blocker.d_m + blocker_half + PASS_MARGIN_M + ego_half)
            if target + ego_half > lane_w + 1e-6:
                raise CommandError(
                    "SAFETY_REJECTED",
                    "ROAD_FULLY_BLOCKED: das Hindernis versperrt die ganze Fahrbahn, links ist kein Platz",
                )
            return PassPlan(target, NUDGE_LEFT_SPEED_MPS, max_distance, False, True, -lane_d)
        target = min(lane_d, blocker.d_m - blocker_half - PASS_MARGIN_M - ego_half)
        _check_right_edge(scenario, facts, target, ego.width_m)
        return PassPlan(target, NUDGE_RIGHT_SPEED_MPS, max_distance, False, False, None)

    if request.command == "AVOID_TEMPORARY_OBSTRUCTION":
        expected_kind = OBSTRUCTION_TYPES[params["obstruction_type"]]
        if blocker.spec.kind != expected_kind:
            raise CommandError(
                "NOT_AVAILABLE",
                f"OBSTRUCTION_TYPE_MISMATCH: vor dem Fahrzeug steht {blocker.spec.kind}, "
                f"nicht {params['obstruction_type']}",
            )
        if params["side"] == "LEFT":
            target = max(lane_d, blocker.d_m + blocker_half + SMALL_OBSTRUCTION_MARGIN_M + ego_half)
        else:
            target = min(lane_d, blocker.d_m - blocker_half - SMALL_OBSTRUCTION_MARGIN_M - ego_half)
        offset = abs(target - lane_d)
        if offset > float(params["max_lateral_offset_m"]) + 1e-6:
            raise CommandError(
                "SAFETY_REJECTED",
                f"OFFSET_EXCEEDS_LIMIT: benoetigter Versatz {offset:.2f} m "
                f"> max_lateral_offset_m {params['max_lateral_offset_m']:g}",
            )
        crosses = target + ego_half > 0.0
        if crosses:
            _require_center_crossing_allowed(scenario)
        else:
            _check_right_edge(scenario, facts, target, ego.width_m)
        return PassPlan(
            target, AVOID_SPEED_MPS, AVOID_MAX_DISTANCE_M, False, crosses, -lane_d if crosses else None
        )

    if request.command == "CHANGE_LANE":
        direction = params["direction"]
        lanes = [lane for lane in facts.adjacent_lanes if lane["side"] == direction]
        if direction == "LEFT" and not lanes:
            raise CommandError(
                "RULE_REJECTED",
                "LANE_OPPOSITE_DIRECTION: die linke Nachbarspur ist die Gegenfahrbahn",
            )
        if not lanes or lanes[0]["direction"] != "SAME" or not lanes[0].get("available", True):
            raise CommandError("NOT_AVAILABLE", "NO_ADJACENT_LANE: keine freie Nachbarspur in Fahrtrichtung")
        target = lane_d - lane_w
        return PassPlan(target, CHANGE_LANE_SPEED_MPS, CHANGE_LANE_MAX_DISTANCE_M, True, False, target)

    raise ValueError(f"{request.command} ist kein Vorbeifahrbefehl")


POSE_DEPENDENT_COMMANDS = frozenset(
    {
        "NUDGE_AROUND_OBSTACLE", "AVOID_TEMPORARY_OBSTRUCTION", "CHANGE_LANE",
        "CROSS_LOW_RISK_OBJECT", "PULL_OVER", "REVERSE_SHORT",
        "CREEP_FORWARD", "PEEK_OUT", "OVERTAKE", "ABORT_TO_LANE", "WAIT_FOR_GAP", "TURN_AROUND",
    }
)
PASSING_COMMANDS = frozenset({"NUDGE_AROUND_OBSTACLE", "OVERTAKE", "AVOID_TEMPORARY_OBSTRUCTION", "CHANGE_LANE"})
LOCALIZATION_MIN_QUALITY = 0.5


def check_command(
    request: CommandRequest,
    *,
    tools: SituationTools,
    facts: WorldFacts,
    warnings: list[str] | None = None,
) -> None:
    """Situationsabhaengige Regel- und Sicherheitspruefung eines Kandidaten.

    Mit ``warnings`` (Pruefmodus advisory/off) landen Befunde aus
    ``WAIVABLE_SAFETY_CHECKS`` dort statt als Ablehnung.
    """

    def safety(check: str, message: str) -> None:
        detail = f"{check}: {message}" if message else check
        if warnings is not None and check in WAIVABLE_SAFETY_CHECKS:
            warnings.append(detail)
            return
        raise CommandError("SAFETY_REJECTED", detail)

    name = request.command
    params = request.parameters
    scenario = tools.scenario
    ego = tools.ego

    if COMMANDS[name].open_guardrails_only and scenario.difficulty.guardrails == "strict":
        raise CommandError(
            "NOT_AVAILABLE", f"{name} gibt es nur in den Pruefmodi advisory und off"
        )
    if facts.incident_detected:
        if name in LEAVING_COMMANDS:
            raise CommandError(
                "RULE_REJECTED",
                "LEAVING_ACCIDENT_SCENE: nach einem Unfall darf das Fahrzeug die Stelle nicht verlassen",
            )
        if name == "PULL_OVER":
            raise CommandError(
                "RULE_REJECTED",
                "MUST_STAY_AT_SCENE: kein geringfuegiger Schaden, das Fahrzeug bleibt an der Unfallstelle",
            )

    if name in PASSING_COMMANDS | {"CROSS_LOW_RISK_OBJECT", "PEEK_OUT", "WAIT_FOR_GAP"}:
        for control in facts.traffic_controls:
            if control["state"] in {"RED", "CLOSED"} and control["stop_line_distance_m"] <= 40.0:
                raise CommandError(
                    "RULE_REJECTED",
                    f"TRAFFIC_CONTROL_ACTIVE: {control['id']} steht auf {control['state']}; "
                    "die Haltelinie darf nicht ueberfahren werden",
                )

    if name in POSE_DEPENDENT_COMMANDS and facts.localization_quality < LOCALIZATION_MIN_QUALITY:
        raise CommandError(
            "SAFETY_REJECTED",
            "LOCALIZATION_UNCERTAIN: Kein Fahrmanoever auf unsicherer Pose; SAFE_STOP oder Eskalation waehlen",
        )

    if name == "WAIT_FOR_GAP":
        # Das Folgemanoever wird schon jetzt geprueft; beim Start entfaellt nur die Evidenz.
        follow_up = CommandRequest(
            str(params["then"]),
            {"side": params["side"], "max_longitudinal_distance_m": params["max_longitudinal_distance_m"]},
            request.reason,
        )
        check_command(follow_up, tools=tools, facts=facts, warnings=warnings)
        return

    if name == "PEEK_OUT":
        offset = float(params["lateral_offset_m"])
        if params["side"] == "LEFT":
            if facts.lane_d_m + offset + ego.width_m / 2.0 > 0.0:
                _require_center_crossing_allowed(scenario)
            if tools.oncoming_conflict(PEEK_ONCOMING_HORIZON_S)["conflict"]:
                safety("ONCOMING_TOO_CLOSE", "Gegenverkehr erreicht die Ausscherstelle in Kuerze")
        else:
            _check_right_edge(scenario, facts, facts.lane_d_m - offset, ego.width_m)
        return

    if name == "TURN_AROUND":
        if not facts.alternative_route_available:
            raise CommandError("NOT_AVAILABLE", "NO_ALTERNATIVE_ROUTE: nach dem Wenden gibt es keine Route zum Ziel")
        if scenario.road.center_marking == "solid":
            raise CommandError(
                "RULE_REJECTED", "CENTER_LINE_SOLID: Wenden ueber eine durchgezogene Linie ist verboten"
            )
        if params["method"] == "U_TURN":
            road_width = 2.0 * scenario.road.lane_width_m + facts.shoulder_m
            needed = 2.0 * turning_radius_m(ego) + ego.width_m
            if road_width < needed:
                raise CommandError(
                    "NOT_AVAILABLE",
                    f"ROAD_TOO_NARROW_FOR_U_TURN: {road_width:.1f} m < {needed:.1f} m; THREE_POINT waehlen",
                )
        if tools.oncoming_conflict(TURN_TRAFFIC_HORIZON_S)["conflict"]:
            safety("ONCOMING_TOO_CLOSE", "Gegenverkehr erreicht die Wendestelle in Kuerze")
        if tools.rear_conflict(TURN_TRAFFIC_HORIZON_S, lane_d_m=facts.lane_d_m)["conflict"]:
            safety("REAR_TRAFFIC_APPROACHING", "Verkehr von hinten erreicht die Wendestelle in Kuerze")
        return

    if name == "ABORT_TO_LANE":
        if abs(ego.d_m - facts.lane_d_m) < 0.15:
            raise CommandError("NOT_AVAILABLE", "ALREADY_IN_LANE: das Fahrzeug steht bereits in der Spur")
        return

    if name in PASSING_COMMANDS:
        blocker = tools.blocker_ahead()
        if blocker is None:
            raise CommandError("NOT_AVAILABLE", "NO_STATIONARY_BLOCKER: kein stehendes Hindernis vor dem Fahrzeug")
        if blocker.spec.kind == "barrier":
            raise CommandError(
                "RULE_REJECTED", "ROAD_CLOSED: eine Absperrung sperrt die Fahrspur und darf nicht umfahren werden"
            )
        plan = plan_pass(request, scenario, ego, blocker, facts)
        if name == "CHANGE_LANE":
            for actor in tools.actors:
                if actor is blocker:
                    continue
                if abs(actor.d_m - plan.target_d_m) < (actor.spec.width_m + ego.width_m) / 2.0 + 0.3 and (
                    ego.s_m - 12.0 <= actor.s_m <= ego.s_m + 25.0
                ):
                    safety("TARGET_LANE_OCCUPIED", f"{actor.spec.actor_id} belegt die Zielspur")
                    break
        return

    if name == "CROSS_LOW_RISK_OBJECT":
        blocker = tools.blocker_ahead()
        if blocker is None:
            raise CommandError(
                "NOT_AVAILABLE", "NO_STATIONARY_BLOCKER: kein stehendes Hindernis vor dem Fahrzeug"
            )
        if blocker.spec.kind != "debris":
            raise CommandError(
                "NOT_AVAILABLE",
                f"OBJECT_NOT_TRAVERSABLE: Akteurstyp {blocker.spec.kind} ist kein pruefbares Ladegut",
            )
        profile = blocker.spec.obstacle_profile
        if profile is None:
            safety("OBSTACLE_PROFILE_UNKNOWN", "kein strukturiertes Hindernisprofil")
            return
        if blocker.spec.confidence < LOW_RISK_MIN_CONFIDENCE or profile.assessment_confidence < LOW_RISK_MIN_CONFIDENCE:
            safety("OBJECT_CLASSIFICATION_UNCERTAIN", "Konfidenz unter 0.9")
        if profile.height_m > LOW_RISK_MAX_HEIGHT_M:
            safety("OBJECT_TOO_HIGH", f"{profile.height_m:.2f} m > {LOW_RISK_MAX_HEIGHT_M:.2f} m")
        if profile.material not in LOW_RISK_MATERIALS or profile.deformability != "HIGH":
            safety("OBJECT_NOT_DEFORMABLE", "Material oder Verformbarkeit ungeeignet")
        if profile.sharp_edges:
            safety("SHARP_EDGES_DETECTED", "")
        if profile.liquid:
            safety("LIQUID_HAZARD_DETECTED", "")
        if tools.vulnerable_road_users()["conflict"]:
            safety("VULNERABLE_ROAD_USER_IN_CORRIDOR", "")
        if not tools.visibility()["sufficient"]:
            safety("VISIBILITY_INSUFFICIENT", "")
        return

    if name == "PULL_OVER":
        if params.get("side_preference", "RIGHT") == "LEFT":
            raise CommandError(
                "RULE_REJECTED", "PULL_OVER_LEFT_NOT_ALLOWED: im Rechtsverkehr nur an den rechten Rand"
            )
        if not pull_over_possible(scenario, ego.width_m, facts.shoulder_m):
            raise CommandError(
                "NOT_AVAILABLE", "NO_SAFE_HALT_POSITION: kein ausreichend breiter Seitenstreifen"
            )
        return

    if name == "REVERSE_SHORT":
        limit = float(params["max_distance_m"]) + ego.length_m / 2.0 + REVERSE_REAR_MARGIN_M
        for actor in tools.actors:
            gap = ego.s_m - actor.s_m - actor.spec.length_m / 2.0
            if (
                0.0 < gap <= limit
                and abs(actor.d_m - ego.d_m) < (actor.spec.width_m + ego.width_m) / 2.0 + 0.3
            ):
                safety("REAR_NOT_CLEAR", f"{actor.spec.actor_id} steht hinter dem Fahrzeug")
                break
        return

    if name == "DROP_PASSENGER" and facts.passengers_on_board <= 0:
        raise CommandError("NOT_AVAILABLE", "NO_PASSENGER_ON_BOARD: keine Fahrgaeste an Bord")

    if name == "RETURN_HOME" and not facts.hub_available:
        raise CommandError("NOT_AVAILABLE", "HUB_UNREACHABLE: der Hub ist nicht erreichbar")

    if name not in COMMANDS:
        raise CommandError("INVALID_ARGUMENT", f"Unbekannter Befehl {name}")
