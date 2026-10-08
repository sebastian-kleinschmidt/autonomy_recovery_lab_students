"""Registry der High-Level-Befehle, die ein Agent anfordern darf.

Ein Befehl ist nur ein *Kandidat*: Schema (dieses Modul), Regel- und
Sicherheitspruefung (``rules.py``) und der zertifizierte Ausfuehrer (Engine)
muessen ihn freigeben. Es gibt bewusst keine Befehle fuer Lenkwinkel, Pedale
oder freie Trajektorien.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .models import CommandRequest


class CommandError(ValueError):
    """Ein Befehl ist ungueltig, unzulaessig oder nicht verfuegbar.

    ``code`` folgt den Standardfehlern der Schnittstellenspezifikation
    (INVALID_ARGUMENT, NOT_AVAILABLE, RULE_REJECTED, SAFETY_REJECTED, ...).
    """

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.detail = message


# Kategorien: was der Befehl im Fahrzeug bzw. in der Mission bewirkt.
MOTION = "motion"
ROUTE = "route"
MISSION = "mission"
ESCALATION = "escalation"
INFORMATION = "information"

# Sieben Lagewerkzeuge, ohne die kein Manoever ueber die Fahrbahn freigegeben wird.
MANEUVER_EVIDENCE_TOOLS = frozenset(
    {
        "get_blocker",
        "get_center_marking",
        "check_oncoming_traffic",
        "check_rear_traffic",
        "check_vulnerable_road_users",
        "get_lateral_clearance",
        "get_visibility",
    }
)

# Im Wahrnehmungsmodell ``tracked`` gibt es die sieben Lagewerkzeuge nicht; die Evidenz fuer
# ein Manoever ist dann die eigene Auswertung dieser drei Quellen.
TRACKED_EVIDENCE_TOOLS = frozenset({"get_tracked_objects", "get_sensor_coverage", "get_map_context"})

# Ausscheren zum Schauen braucht nur den Blick auf Gegenverkehr, Heck und Markierung.
PEEK_EVIDENCE_TOOLS = frozenset({"check_oncoming_traffic", "check_rear_traffic", "get_center_marking"})

OBSTRUCTION_TYPES = {
    "CONSTRUCTION_BEACON": "beacon",
    "TRASH_BIN": "trash_bin",
    "MISPLACED_OBJECT": "debris",
}
TEMPORARY_OBSTRUCTION_KINDS = frozenset(OBSTRUCTION_TYPES.values())
REASON_CODES = (
    "AMBIGUOUS_SCENE",
    "NO_SAFE_RECOVERY",
    "BLOCKED_ROUTE",
    "PERCEPTION_DEGRADED",
    "RECOVERY_TIME_EXCEEDED",
    "UNRECOVERABLE_BLOCKAGE",
    "DESTINATION_UNREACHABLE",
    "SAFETY_CONCERN",
)


@dataclass(frozen=True)
class ParamSpec:
    name: str
    kind: str  # "number" | "enum" | "bool" | "string"
    required: bool = True
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] = ()
    default: Any = None
    max_length: int = 200

    def schema(self) -> dict[str, Any]:
        if self.kind == "number":
            result: dict[str, Any] = {"type": "number"}
            if self.minimum is not None:
                result["minimum"] = self.minimum
            if self.maximum is not None:
                result["maximum"] = self.maximum
        elif self.kind == "enum":
            result = {"enum": list(self.choices)}
        elif self.kind == "bool":
            result = {"type": "boolean"}
        else:
            result = {"type": "string", "maxLength": self.max_length}
        if self.default is not None:
            result["default"] = self.default
        return result

    def normalize(self, value: object) -> Any:
        if self.kind == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise CommandError("INVALID_ARGUMENT", f"{self.name} muss eine Zahl sein")
            number = float(value)
            if not math.isfinite(number):
                raise CommandError("INVALID_ARGUMENT", f"{self.name} muss endlich sein")
            if self.minimum is not None and number < self.minimum:
                raise CommandError(
                    "INVALID_ARGUMENT", f"{self.name} muss mindestens {self.minimum:g} sein"
                )
            if self.maximum is not None and number > self.maximum:
                raise CommandError(
                    "INVALID_ARGUMENT", f"{self.name} darf {self.maximum:g} nicht uebersteigen"
                )
            return number
        if self.kind == "enum":
            if value not in self.choices:
                raise CommandError(
                    "INVALID_ARGUMENT", f"{self.name} muss eines von {', '.join(self.choices)} sein"
                )
            return value
        if self.kind == "bool":
            if not isinstance(value, bool):
                raise CommandError("INVALID_ARGUMENT", f"{self.name} muss true oder false sein")
            return value
        if not isinstance(value, str) or len(value) > self.max_length:
            raise CommandError(
                "INVALID_ARGUMENT",
                f"{self.name} muss ein Text mit hoechstens {self.max_length} Zeichen sein",
            )
        return value


@dataclass(frozen=True)
class CommandSpec:
    name: str
    summary: str
    category: str
    params: tuple[ParamSpec, ...] = ()
    evidence_tools: frozenset[str] = frozenset()
    # Terminale Befehle beenden die Episode (Wiederaufnahme der Fahrt ausserhalb der Simulation).
    terminal: bool = False
    cost_note: str = ""
    # Nur in den Pruefmodi advisory/off (Unfallabwicklung, Kontrollpunkte nach Manoevern).
    open_guardrails_only: bool = False

    def required_tools(self, perception_model: str = "exact") -> frozenset[str]:
        if self.evidence_tools and perception_model == "tracked":
            return TRACKED_EVIDENCE_TOOLS
        return self.evidence_tools

    def catalog_entry(self, perception_model: str = "exact") -> dict[str, Any]:
        return {
            "command": self.name,
            "category": self.category,
            "description": self.summary,
            "parameter_schema": {param.name: param.schema() for param in self.params},
            "required_parameters": [param.name for param in self.params if param.required],
            "required_tools": sorted(self.required_tools(perception_model)),
            "ends_episode": self.terminal,
            "cost_note": self.cost_note,
        }


def _spec(*items: CommandSpec) -> dict[str, CommandSpec]:
    return {item.name: item for item in items}


SIDE = ("LEFT", "RIGHT")

COMMANDS: dict[str, CommandSpec] = _spec(
    CommandSpec(
        "WAIT",
        "Zeitlich begrenztes Warten auf eine voruebergehende Blockade, z. B. eine "
        "Fussgaengergruppe. Endet frueher, sobald der Weg frei ist.",
        MOTION,
        (ParamSpec("duration_s", "number", minimum=1.0, maximum=30.0),),
        cost_note="Standzeit",
    ),
    CommandSpec(
        "REPLAN_ROUTE",
        "Berechnet eine alternative globale Route, wenn die geplante Route blockiert ist "
        "(z. B. Baustelle). Die neue Route ist laenger und verursacht Umwegkosten.",
        ROUTE,
        (ParamSpec("avoid_current_segment", "bool", required=False, default=True),),
        terminal=True,
        cost_note="Umweg (Zeit)",
    ),
    CommandSpec(
        "REVERSE_SHORT",
        "Begrenztes, gerades Zuruecksetzen, um Manoevrierraum zu gewinnen. Nur bei freiem Heck.",
        MOTION,
        (ParamSpec("max_distance_m", "number", minimum=0.5, maximum=5.0),),
        cost_note="Standzeit",
    ),
    CommandSpec(
        "PULL_OVER",
        "Faehrt an den sicheren rechten Fahrbahnrand (Seitenstreifen) und haelt dort an.",
        MOTION,
        (ParamSpec("side_preference", "enum", required=False, choices=SIDE, default="RIGHT"),),
        cost_note="Standzeit",
    ),
    CommandSpec(
        "NUDGE_AROUND_OBSTACLE",
        "Langsames, raeumlich begrenztes Vorbeifahren an einem stehenden Hindernis ueber die "
        "Gegenfahrbahn (LEFT) oder den Seitenstreifen (RIGHT). Abbruchbedingungen "
        "oncoming_traffic, blocker_moves und collision_risk werden immer ueberwacht.",
        MOTION,
        (
            ParamSpec("side", "enum", choices=SIDE),
            ParamSpec("max_longitudinal_distance_m", "number", minimum=5.0, maximum=50.0),
        ),
        evidence_tools=MANEUVER_EVIDENCE_TOOLS,
        cost_note="Kollisionsrisiko",
    ),
    CommandSpec(
        "CHANGE_LANE",
        "Validierter Spurwechsel auf eine benachbarte Fahrspur gleicher Richtung. Eine Spur "
        "in Gegenrichtung ist nie zulaessig.",
        MOTION,
        (ParamSpec("direction", "enum", choices=SIDE),),
        evidence_tools=MANEUVER_EVIDENCE_TOOLS,
        cost_note="Kollisionsrisiko",
    ),
    CommandSpec(
        "AVOID_TEMPORARY_OBSTRUCTION",
        "Umfaehrt ein kleines voruebergehendes Hindernis (Baustellenbake, Muelltonne, falsch "
        "abgestelltes Objekt) mit kleinem seitlichem Versatz.",
        MOTION,
        (
            ParamSpec("obstruction_type", "enum", choices=tuple(OBSTRUCTION_TYPES)),
            ParamSpec("side", "enum", choices=SIDE),
            ParamSpec("max_lateral_offset_m", "number", minimum=0.2, maximum=2.5),
        ),
        evidence_tools=MANEUVER_EVIDENCE_TOOLS,
        cost_note="Kollisionsrisiko",
    ),
    CommandSpec(
        "CROSS_LOW_RISK_OBJECT",
        "Ueberrollt ein sicher klassifiziertes, sehr flaches und stark verformbares Objekt "
        "geradeaus mit begrenzter Geschwindigkeit. Unbekannte, starre, scharfkantige oder "
        "fluessige Hindernisse werden abgelehnt.",
        MOTION,
        (
            ParamSpec(
                "max_speed_mps", "number", required=False, minimum=0.5, maximum=1.5, default=1.0
            ),
        ),
        evidence_tools=MANEUVER_EVIDENCE_TOOLS,
        cost_note="Langsamfahrt; nur fuer validiertes Niedrigrisiko-Objekt",
    ),
    CommandSpec(
        "REQUEST_REMOTE_ASSISTANCE",
        "Eskaliert an einen Remote Operator. Jeder Aufruf kostet Geld; das Fahrzeug wartet "
        "sicher, bis die Leitstelle antwortet. Keine Fernsteuerung.",
        ESCALATION,
        (
            ParamSpec("reason_code", "enum", choices=REASON_CODES),
            ParamSpec("summary", "string", required=False, max_length=200),
        ),
        cost_note="Pauschale je Anruf + Standzeit",
    ),
    CommandSpec(
        "ABORT_MISSION",
        "Beendet die Mission logisch. Fahrgaeste bleiben an Bord, sofern sie nicht vorher "
        "abgesetzt wurden.",
        MISSION,
        (ParamSpec("reason_code", "enum", choices=REASON_CODES),),
        terminal=True,
        cost_note="Missionsausfall; gestrandete Fahrgaeste",
    ),
    CommandSpec(
        "SAFE_STOP",
        "Missionsabbruch mit risikominimiertem Halt. Halt im Fahrstreifen behindert den "
        "Verkehr; nach PULL_OVER ist er guenstiger.",
        MISSION,
        (ParamSpec("reason_code", "enum", choices=REASON_CODES),),
        terminal=True,
        cost_note="Bergung; Behinderung bei Halt im Fahrstreifen",
    ),
    CommandSpec(
        "RETURN_HOME",
        "Faehrt zum Hub zurueck. Fahrgaeste an Bord sind darueber verstimmt.",
        MISSION,
        (),
        terminal=True,
        cost_note="Rueckfahrtzeit; unzufriedene Fahrgaeste",
    ),
    CommandSpec(
        "DROP_PASSENGER",
        "Laesst Fahrgaeste aussteigen. An einer sicheren Stelle (Fahrzeug am Rand) nur ein "
        "kleiner Erstattungsbetrag; im Fahrstreifen drohen Verletzte oder Tote.",
        MISSION,
        (),
        terminal=True,
        cost_note="Erstattung; bei unsicherer Stelle Personenschaden",
    ),
    CommandSpec(
        "REQUEST_ADDITIONAL_INFORMATION",
        "Sammelt gezielt weitere Evidenz, ohne das Fahrzeug zu bewegen. Das Ergebnis steht "
        "in der naechsten Untersuchung unter additional_information.",
        INFORMATION,
        (
            ParamSpec("topic", "enum", choices=("MOTION_REASSESSMENT", "SCENE_REFRESH", "MAP_CONSISTENCY")),
            ParamSpec("duration_s", "number", minimum=1.0, maximum=10.0),
        ),
        cost_note="Standzeit",
    ),
    CommandSpec(
        "ESCALATE_TO_RULE_ENGINE",
        "Uebergibt die Entscheidung an die deterministische Regel-Engine. Guenstiger als eine "
        "Remote Assistance, aber nur mit konservativen Standardregeln.",
        ESCALATION,
        (ParamSpec("focus", "enum", required=False, choices=("GENERAL", "PASSING", "ROUTE"), default="GENERAL"),),
        cost_note="kleine Pauschale",
    ),
    CommandSpec(
        "RESUME",
        "Setzt ein an einem Checkpoint angehaltenes Manoever fort; sonst gibt es die Fahrt an "
        "den Fahrstack zurueck. Nach einem erkannten Unfall unzulaessig.",
        MOTION,
        cost_note="keine",
    ),
    CommandSpec(
        "CREEP_FORWARD",
        "Tastet sich in der aktuellen Querlage langsam vor, um mehr zu sehen. Haelt vor jedem "
        "Objekt im Fahrweg an.",
        MOTION,
        (ParamSpec("max_distance_m", "number", minimum=0.5, maximum=5.0),),
        cost_note="Standzeit",
    ),
    CommandSpec(
        "PEEK_OUT",
        "Schert leicht aus, nur um am Hindernis vorbeizusehen, und haelt dort an einem "
        "Checkpoint (PEEKING). Danach OVERTAKE, ABORT_TO_LANE oder ein anderer Befehl.",
        MOTION,
        (
            ParamSpec("side", "enum", choices=SIDE),
            ParamSpec("lateral_offset_m", "number", minimum=0.3, maximum=1.5),
        ),
        evidence_tools=PEEK_EVIDENCE_TOOLS,
        cost_note="Standzeit; kurz auf der Gegenfahrbahn",
    ),
    CommandSpec(
        "OVERTAKE",
        "Ueberholt ein stehendes Hindernis in Phasen: PULL_OUT bis neben das Heck des Hindernisses, "
        "dort Checkpoint (PULLED_OUT), nach RESUME vorbeifahren und wieder einscheren.",
        MOTION,
        (
            ParamSpec("side", "enum", choices=SIDE),
            ParamSpec("max_longitudinal_distance_m", "number", minimum=5.0, maximum=60.0),
        ),
        evidence_tools=MANEUVER_EVIDENCE_TOOLS,
        cost_note="Kollisionsrisiko",
    ),
    CommandSpec(
        "TURN_AROUND",
        "Wendet physisch: U_TURN in einem Zug oder THREE_POINT mit Zuruecksetzen. Danach "
        "faehrt das Fahrzeug die Alternativroute; die Episode endet mit Umwegkosten.",
        ROUTE,
        (ParamSpec("method", "enum", choices=("U_TURN", "THREE_POINT")),),
        evidence_tools=MANEUVER_EVIDENCE_TOOLS,
        terminal=True,
        cost_note="Umweg (Zeit); Kollisionsrisiko beim Wenden",
    ),
    CommandSpec(
        "ABORT_TO_LANE",
        "Kehrt aus einer seitlichen Lage hinter das Hindernis in die eigene Spur zurueck, "
        "notfalls mit geradem Zuruecksetzen.",
        MOTION,
        cost_note="Standzeit",
    ),
    CommandSpec(
        "WAIT_FOR_GAP",
        "Wartet, bis die Wahrnehmung auf der Gegenspur eine ausreichende Luecke meldet, und "
        "startet dann selbst das genannte Manoever. Was verdeckt ist, sieht sie nicht.",
        MOTION,
        (
            ParamSpec("min_gap_s", "number", minimum=3.0, maximum=15.0),
            ParamSpec("timeout_s", "number", minimum=5.0, maximum=60.0),
            ParamSpec("then", "enum", choices=("OVERTAKE", "NUDGE_AROUND_OBSTACLE")),
            ParamSpec("side", "enum", choices=SIDE),
            ParamSpec("max_longitudinal_distance_m", "number", minimum=5.0, maximum=60.0),
        ),
        evidence_tools=MANEUVER_EVIDENCE_TOOLS,
        cost_note="Standzeit; danach wie das Manoever",
    ),
    CommandSpec(
        "SECURE_SCENE",
        "Sichert die Stelle: Fahrzeug haelt, Warnblinker an, Unfallstelle absichern. Das "
        "Fahrzeug bleibt danach stehen.",
        MISSION,
        open_guardrails_only=True,
        cost_note="Standzeit",
    ),
    CommandSpec(
        "REPORT_INCIDENT",
        "Meldet einen Unfall an Leitstelle und Polizei, bei Verdacht auf Verletzte mit Notruf. "
        "Das Fahrzeug wartet danach an der Stelle; die Episode endet.",
        ESCALATION,
        (
            ParamSpec("injured_persons_suspected", "bool"),
            ParamSpec("summary", "string", required=False, max_length=200),
        ),
        terminal=True,
        open_guardrails_only=True,
        cost_note="Unfallaufnahme; ohne Unfall ein Fehlalarm",
    ),
)

COMMAND_NAMES = tuple(COMMANDS)


def list_commands(perception_model: str = "exact", guardrails: str = "strict") -> list[dict[str, Any]]:
    return [
        spec.catalog_entry(perception_model)
        for spec in COMMANDS.values()
        if guardrails != "strict" or not spec.open_guardrails_only
    ]


def parse_command(payload: object) -> CommandRequest:
    """Prueft Form und Parameterbounds eines Agentenbefehls (ohne Situationsbezug)."""
    if isinstance(payload, CommandRequest):
        payload = {
            "command": payload.command,
            "parameters": dict(payload.parameters),
            "reason": payload.reason,
        }
    if not isinstance(payload, Mapping):
        raise CommandError("INVALID_ARGUMENT", "Agentenausgabe muss ein JSON-Objekt sein")
    required = {"command", "parameters", "reason"}
    missing = required - set(payload)
    extra = set(payload) - required
    if missing:
        raise CommandError("INVALID_ARGUMENT", f"Pflichtfelder fehlen: {', '.join(sorted(missing))}")
    if extra:
        raise CommandError("INVALID_ARGUMENT", f"Unbekannte Felder: {', '.join(sorted(extra))}")
    name = payload["command"]
    if not isinstance(name, str) or name not in COMMANDS:
        raise CommandError(
            "INVALID_ARGUMENT",
            f"Unbekannter Befehl {name!r}; erlaubt: {', '.join(COMMAND_NAMES)}",
        )
    reason = payload["reason"]
    if not isinstance(reason, str) or not reason.strip():
        raise CommandError("INVALID_ARGUMENT", "reason muss ein nichtleerer Text sein")
    raw = payload["parameters"]
    if not isinstance(raw, Mapping):
        raise CommandError("INVALID_ARGUMENT", "parameters muss ein Objekt sein")
    spec = COMMANDS[name]
    known = {param.name for param in spec.params}
    unknown = set(raw) - known
    if unknown:
        raise CommandError(
            "INVALID_ARGUMENT", f"Unbekannte Parameter fuer {name}: {', '.join(sorted(unknown))}"
        )
    normalized: dict[str, Any] = {}
    for param in spec.params:
        if param.name in raw:
            normalized[param.name] = param.normalize(raw[param.name])
        elif param.required:
            raise CommandError("INVALID_ARGUMENT", f"Parameter {param.name} fehlt fuer {name}")
        elif param.default is not None:
            normalized[param.name] = param.default
    return CommandRequest(command=name, parameters=normalized, reason=reason.strip())


def request_to_payload(request: CommandRequest) -> dict[str, Any]:
    return {
        "command": request.command,
        "parameters": dict(request.parameters),
        "reason": request.reason,
    }


def decision_schema() -> dict[str, Any]:
    """JSON-Schema der Agentenausgabe, aus der Registry erzeugt (siehe schemas/)."""
    branches = []
    for spec in COMMANDS.values():
        properties = {param.name: param.schema() for param in spec.params}
        branches.append(
            {
                "if": {"properties": {"command": {"const": spec.name}}, "required": ["command"]},
                "then": {
                    "properties": {
                        "parameters": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [param.name for param in spec.params if param.required],
                            "properties": properties,
                        }
                    }
                },
            }
        )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://example.local/autonomy-recovery-sim/agent_decision.schema.json",
        "title": "AutonomyRecoverySim Agent Command 3.0",
        "type": "object",
        "additionalProperties": False,
        "required": ["command", "parameters", "reason"],
        "properties": {
            "command": {"enum": list(COMMAND_NAMES)},
            "parameters": {"type": "object"},
            "reason": {"type": "string", "minLength": 1},
        },
        "allOf": branches,
    }
