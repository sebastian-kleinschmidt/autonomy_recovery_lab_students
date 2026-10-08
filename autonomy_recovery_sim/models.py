from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ObstacleProfile:
    """Strukturierte, wahrgenommene Eigenschaften kleiner Fahrbahnhindernisse."""

    height_m: float
    material: str
    deformability: str
    sharp_edges: bool
    liquid: bool
    assessment_confidence: float


@dataclass(frozen=True)
class ActorSpec:
    actor_id: str
    kind: str
    s_m: float
    d_m: float
    speed_mps: float
    direction: int = 1
    length_m: float = 4.5
    width_m: float = 1.8
    behavior: str = "lane_follow"
    motion_start_time_s: float | None = None
    target_speed_mps: float | None = None
    # Nur fuer behavior="crossing": Querablage, auf die der Aktor nach
    # motion_start_time_s mit target_speed_mps hinausgeht (z. B. Fussgaengergruppe).
    exit_d_m: float | None = None
    # Wahrnehmungsfelder fuer Unsicherheitsszenarien: Konfidenz des Tracks, ein vom Agenten
    # lesbarer Freitext der Szenenbeschreibung (z. B. OCR eines Schildes) und Phantomobjekte
    # (fuer Wahrnehmung und Planer vorhanden, physisch nicht existent).
    confidence: float = 1.0
    description: str | None = None
    phantom: bool = False
    obstacle_profile: ObstacleProfile | None = None
    # Ausloeser: Verhaltensaenderung, sobald das Ego etwas Bestimmtes tut (triggers.py).
    triggers: tuple[dict[str, Any], ...] = ()


@dataclass
class ActorState:
    spec: ActorSpec
    s_m: float
    d_m: float
    speed_mps: float

    @classmethod
    def from_spec(cls, spec: ActorSpec) -> "ActorState":
        return cls(spec=spec, s_m=spec.s_m, d_m=spec.d_m, speed_mps=spec.speed_mps)


@dataclass
class EgoState:
    s_m: float
    d_m: float
    speed_mps: float = 0.0
    length_m: float = 4.5
    width_m: float = 1.8


@dataclass(frozen=True)
class CommandRequest:
    """Ein einzelner, validierter High-Level-Befehl des Agenten."""

    command: str
    parameters: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass(frozen=True)
class WorldFacts:
    """Missions-, Routen- und Verlaufswissen, das Regelpruefung und Agent teilen."""

    mission_state: str = "ACTIVE"
    mission_type: str = "PASSENGER_TRANSPORT"
    passengers_on_board: int = 0
    hub_available: bool = True
    hub_return_s: float = 150.0
    route_blocked: bool = False
    alternative_route_available: bool = True
    detour_cost_s: float = 180.0
    reverse_required_m: float = 0.0
    reversed_m: float = 0.0
    remote_assistance_available: bool = True
    remote_assistance_calls: int = 0
    lane_d_m: float = -1.75
    shoulder_m: float = 3.0
    localization_quality: float = 1.0
    sensors: tuple[dict[str, Any], ...] = ()
    # Verkehrssteuerung voraus (Ampel, Bahnuebergang) mit aktuellem Zustand.
    traffic_controls: tuple[dict[str, Any], ...] = ()
    adjacent_lanes: tuple[dict[str, Any], ...] = ()
    history: tuple[dict[str, Any], ...] = ()
    # Vom Fahrzeug erkannter Unfall mit Dritten (MODERATE/SEVERE); leichte Beruehrungen nicht.
    incident_detected: bool = False


@dataclass
class Event:
    time_s: float
    event: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
