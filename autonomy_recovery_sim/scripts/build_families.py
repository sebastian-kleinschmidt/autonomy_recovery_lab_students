#!/usr/bin/env python3
"""Erzeugt die Szenariofamilien F1 bis F6 (je drei Varianten) aus kompakten Beschreibungen.

Jede Familie hat dasselbe Startbild und je Variante eine andere richtige Antwort.
Alle Varianten sind öffentlich; die Einstiegsmenge enthält je Familie einen Fall. Ausgabe:

- ``families/<id>.json``: die Szenarien
- ``families/catalog.json``: Familie, Lernziel, Stufe und Empfehlung für den Einstieg
- ``scenario_sets/familien_sichtbar.txt`` (Einstieg), ``familien_alle.txt`` (alle 18)

    python autonomy_recovery_sim/scripts/build_families.py          # schreiben
    python autonomy_recovery_sim/scripts/build_families.py --check  # nur pruefen
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "families"
SETS = ROOT / "scenario_sets"

LEVELS = {
    # Stufe B: Objektliste mit leichtem Rauschen, strenge Pruefung.
    "B": {"guardrails": "strict", "noise": {}},
    # Stufe C: Klassen werden verwechselt, Tracks reissen ab; Warnung statt Ablehnung.
    "C": {"guardrails": "advisory", "noise": {"class_confusion": 0.15, "dropout_probability": 0.05}},
    # Stufe D: zusaetzlich Fehlalarme; keine vorausschauenden Abbrueche.
    "D": {
        "guardrails": "off",
        "noise": {"class_confusion": 0.15, "dropout_probability": 0.05, "false_positive_rate_hz": 0.05},
    },
}

BASE: dict[str, Any] = {
    "seed": 42,
    "simulation": {"duration_s": 150.0, "dt_s": 0.1},
    "road": {
        "map_file": "../data/hannover_wilhelm_busch_strasse.geojson",
        "context_file": "../data/hannover_wilhelm_busch_context.json",
        "lane_width_m": 3.5,
        "center_marking": "dashed",
        "assumption_note": "Spurbreite und Markierung sind Szenarioannahmen; OSM enthält sie hier nicht.",
    },
    "ego": {"start_s_m": 20.0, "lane_d_m": -1.75, "target_s_m": 260.0, "cruise_speed_mps": 8.0},
    "recovery": {"stuck_after_s": 3.0, "max_commands": 12},
    "policy": {"allow_solid_exception": False},
    "route": {"alternative_available": True, "detour_cost_s": 180.0},
}

# Gemeinsames Startbild von F1 und F4: ein breiter Transporter steht ohne erkennbaren Grund.
# Was davor steht und schmaler ist, liegt in seinem Sichtschatten.
STOPPED_CAR = {
    "id": "stehender_transporter",
    "kind": "van",
    "s_m": 92.0,
    "d_m": -1.75,
    "length_m": 6.0,
    "width_m": 2.4,
    "description": (
        "Ein Transporter steht mit Bremslicht in der eigenen Fahrspur. Was davor liegt, verdeckt er; "
        "einen Grund für den Halt sieht man von hier nicht."
    ),
}
# Unfallstelle quer ueber beide Spuren (F1b, F4a, F4b).
CRASH_SITE = [
    {
        "id": "unfallwagen",
        "kind": "car",
        "s_m": 106.0,
        "d_m": 0.0,
        "length_m": 2.0,
        "width_m": 6.8,
        "description": "Ein verunfallter Pkw steht quer über beiden Fahrspuren; Glassplitter liegen auf der Fahrbahn.",
    },
    {
        "id": "streifenwagen",
        "kind": "car",
        "s_m": 113.0,
        "d_m": 1.75,
        "direction": -1,
        "description": "Ein Streifenwagen mit Blaulicht sichert die Unfallstelle auf der Gegenspur ab.",
    },
]
CRASH_ROUTE = {"blocked": True, "map_stale": True, "alternative_available": True, "detour_cost_s": 200.0, "turn_required": True}


def trigger(when: dict[str, Any], then: dict[str, Any], tool: str, why: str) -> dict[str, Any]:
    return {"when": when, "then": then, "hint": {"tool": tool, "why": why}}


def after_first_session(seconds: float, speed: float, tool: str, why: str) -> dict[str, Any]:
    return trigger({"since_first_session_s": {"gte": seconds}}, {"start_motion": {"target_speed_mps": speed}}, tool, why)


def when_ego_pulls_out(speed: float, tool: str, why: str) -> dict[str, Any]:
    return trigger({"ego_lateral_offset_m": {"gte": 0.8}}, {"start_motion": {"target_speed_mps": speed}}, tool, why)


def queue_behind(start_after_s: float) -> list[dict[str, Any]]:
    """Ein Pkw kommt von hinten und haelt dicht hinter dem Ego (F4): danach ist kein Platz mehr."""
    travel_s = 18.0  # von s = 4 m bis kurz hinter das wartende Ego bei 4 m/s
    return [
        {
            "id": "nachfolger",
            "kind": "car",
            "s_m": 4.0,
            "d_m": -1.75,
            "description": "Ein Pkw nähert sich von hinten in der eigenen Spur und hält dahinter an.",
            "triggers": [
                after_first_session(
                    start_after_s, 4.0, "get_tracked_objects",
                    "Verkehr von hinten wird sichtbar, sobald er näher kommt; danach ist kein Platz mehr zum Wenden.",
                ),
                trigger(
                    {"since_first_session_s": {"gte": start_after_s + travel_s}},
                    {"stop": {}},
                    "get_tracked_objects",
                    "Der Nachfolger hält hinter dem Ego an.",
                ),
            ],
        }
    ]


FAMILIES: list[dict[str, Any]] = [
    {
        "family": "F1",
        "title": "Verdeckte Ursache",
        "level": "C",
        "goal": "Erst Information kaufen (ausscheren bis zum Checkpoint), dann handeln.",
        "variants": [
            {
                "id": "f1_muellabfuhr",
                "introductory": True,
                "actors": [
                    STOPPED_CAR | {"triggers": [after_first_session(38.0, 3.0, "get_tracked_objects", "Vor dem Transporter arbeitet die Müllabfuhr; sie fährt bald weiter.")]},
                    {
                        "id": "muellwagen",
                        "kind": "truck",
                        "s_m": 104.0,
                        "d_m": -1.75,
                        "length_m": 8.0,
                        "width_m": 2.3,
                        "description": "Ein Müllfahrzeug mit orangefarbener Rundumleuchte hält in der Fahrspur; Tonnen werden geleert.",
                        "triggers": [after_first_session(35.0, 3.0, "get_tracked_objects", "Ein Radartrack hinter dem Transporter zeigt ein großes Fahrzeug.")],
                    },
                    {
                        "id": "muellwerker",
                        "kind": "pedestrian",
                        "s_m": 106.0,
                        "d_m": -0.45,
                        "length_m": 0.6,
                        "width_m": 0.6,
                        "description": "Ein Müllwerker in Warnkleidung steht neben dem Müllfahrzeug auf der Fahrbahn.",
                        "triggers": [
                            trigger(
                                {"since_first_session_s": {"gte": 33.0}},
                                {"cross": {"exit_d_m": 5.5, "speed_mps": 1.2}},
                                "check_vulnerable_road_users",
                                "Am Checkpoint ist der Müllwerker im Überholweg zu sehen.",
                            )
                        ],
                    },
                ],
                "reference": {
                    "commands": ["WAIT", "PEEK_OUT", "OVERTAKE", "CREEP_FORWARD"],
                    "outcome": "resolved",
                    "budget_eur": 80.0,
                    "reason": "Vor dem Transporter arbeitet die Müllabfuhr, ein Müllwerker steht auf der Fahrbahn. Wer nachsieht, wartet; nach gut einer halben Minute fährt alles weiter.",
                },
            },
            {
                "id": "f1_unfallstelle",
                "introductory": False,
                "actors": [STOPPED_CAR, *CRASH_SITE],
                "route": CRASH_ROUTE,
                "reference": {
                    "commands": ["WAIT", "PEEK_OUT", "OVERTAKE", "CREEP_FORWARD", "TURN_AROUND", "REQUEST_ADDITIONAL_INFORMATION", "REPLAN_ROUTE"],
                    "sequence": [["TURN_AROUND"]],
                    "outcome": "rerouted",
                    "budget_eur": 220.0,
                    "reason": "Vor dem Transporter sperrt eine Unfallstelle beide Spuren. Die Karte weiß davon nichts; wer es sieht, wendet und nimmt den Umweg.",
                },
            },
            {
                "id": "f1_umzug",
                "introductory": False,
                "actors": [
                    STOPPED_CAR,
                    {
                        "id": "umzugswagen",
                        "kind": "truck",
                        "s_m": 103.0,
                        "d_m": -1.75,
                        "length_m": 7.0,
                        "width_m": 2.3,
                        "description": "Ein Umzugs-Lkw steht mit heruntergelassener Rampe in der Fahrspur; Möbel werden ausgeladen.",
                    },
                ],
                "reference": {
                    "commands": ["WAIT", "PEEK_OUT", "OVERTAKE", "NUDGE_AROUND_OBSTACLE", "WAIT_FOR_GAP", "CREEP_FORWARD"],
                    "outcome": "liberated",
                    "budget_eur": 60.0,
                    "reason": "Transporter und Umzugs-Lkw stehen auf Dauer, die Gegenspur ist frei: vorsichtig an beiden vorbei.",
                },
            },
        ],
    },
    {
        "family": "F2",
        "title": "Hindernis reagiert",
        "level": "B",
        "goal": "Wo liegt der Punkt ohne Rückkehr? Hinweise auf einen Fahrer ernst nehmen.",
        "variants": [
            {
                "id": "f2_fahrer_weg",
                "introductory": True,
                "actors": [
                    {
                        "id": "lieferwagen",
                        "kind": "van",
                        "s_m": 92.0,
                        "d_m": -1.75,
                        "length_m": 5.5,
                        "width_m": 2.1,
                        "description": "Ein Lieferwagen steht mit Warnblinker in zweiter Reihe; die Fahrerkabine ist leer, niemand ist in der Nähe.",
                    }
                ],
                "reference": {
                    "commands": ["NUDGE_AROUND_OBSTACLE", "OVERTAKE", "PEEK_OUT"],
                    "outcome": "liberated",
                    "budget_eur": 40.0,
                    "reason": "Niemand kommt zurück: Der Lieferwagen bleibt stehen, die Gegenspur ist frei.",
                },
            },
            {
                "id": "f2_fahrer_am_steuer",
                "introductory": False,
                "actors": [
                    {
                        "id": "lieferwagen",
                        "kind": "van",
                        "s_m": 92.0,
                        "d_m": -1.75,
                        "length_m": 5.5,
                        "width_m": 2.1,
                        "description": "Ein Lieferwagen steht mit Warnblinker in zweiter Reihe; der Fahrer sitzt am Steuer, der Motor läuft.",
                        "triggers": [
                            when_ego_pulls_out(3.0, "get_blocker", "Der Fahrer sitzt am Steuer; er kann jederzeit anfahren."),
                            after_first_session(30.0, 3.0, "get_blocker", "Der Fahrer sitzt am Steuer und fährt bald weiter."),
                        ],
                    }
                ],
                "reference": {
                    "commands": ["WAIT"],
                    "outcome": "resolved",
                    "budget_eur": 40.0,
                    "reason": "Der Fahrer sitzt am Steuer. Wer ausschert, provoziert ein gleichzeitiges Anfahren; Warten ist sicher und billig.",
                },
            },
            {
                "id": "f2_bote_kommt",
                "introductory": False,
                "actors": [
                    {
                        "id": "lieferwagen",
                        "kind": "van",
                        "s_m": 92.0,
                        "d_m": -1.75,
                        "length_m": 5.5,
                        "width_m": 2.1,
                        "description": "Ein Lieferwagen steht mit Warnblinker in zweiter Reihe; ein Paketbote geht gerade vom Gehweg zur Fahrertür.",
                        "triggers": [
                            when_ego_pulls_out(3.0, "get_blocker", "Der Bote steigt gleich ein."),
                            after_first_session(12.0, 3.0, "get_blocker", "Der Bote steigt gleich ein und fährt los."),
                        ],
                    }
                ],
                "reference": {
                    "commands": ["WAIT"],
                    "outcome": "resolved",
                    "budget_eur": 30.0,
                    "reason": "Der Bote ist auf dem Weg zur Fahrertür; nach wenigen Sekunden fährt der Lieferwagen weiter.",
                },
            },
        ],
    },
    {
        "family": "F3",
        "title": "Gegenverkehr aus der Verdeckung",
        "level": "C",
        "goal": "Verdeckung ernst nehmen, ohne zu erstarren: am Checkpoint neu entscheiden.",
        "variants": [
            {
                "id": "f3_pkw_kommt",
                "introductory": True,
                "actors": [
                    {
                        "id": "breiter_lkw",
                        "kind": "truck",
                        "s_m": 92.0,
                        "d_m": -1.6,
                        "length_m": 8.0,
                        "width_m": 2.55,
                        "description": "Ein breiter Lkw steht in der eigenen Spur und verdeckt die Gegenspur weiter vorn.",
                    },
                    {
                        "id": "gegenverkehr_pkw",
                        "kind": "car",
                        "s_m": 128.0,
                        "d_m": 1.75,
                        "direction": -1,
                        "description": "Ein Pkw auf der Gegenspur, vom Lkw verdeckt.",
                        "triggers": [
                            when_ego_pulls_out(5.0, "get_visibility", "Die Gegenspur hinter dem Lkw ist nicht einsehbar."),
                            after_first_session(45.0, 5.0, "get_visibility", "Die Gegenspur hinter dem Lkw ist nicht einsehbar."),
                        ],
                    },
                ],
                "reference": {
                    "commands": ["OVERTAKE", "PEEK_OUT", "WAIT"],
                    "sequence": [["OVERTAKE", "NUDGE_AROUND_OBSTACLE"]],
                    "outcome": "liberated",
                    "budget_eur": 80.0,
                    "reason": "Erst am Checkpoint taucht Gegenverkehr auf: zurück in die Spur, ihn vorbeilassen, dann überholen.",
                },
            },
            {
                "id": "f3_radfahrer_kommt",
                "introductory": False,
                "actors": [
                    {
                        "id": "breiter_lkw",
                        "kind": "truck",
                        "s_m": 92.0,
                        "d_m": -1.6,
                        "length_m": 8.0,
                        "width_m": 2.55,
                        "description": "Ein breiter Lkw steht in der eigenen Spur und verdeckt die Gegenspur weiter vorn.",
                    },
                    {
                        "id": "gegenverkehr_rad",
                        "kind": "bicycle",
                        "s_m": 122.0,
                        "d_m": 2.4,
                        "direction": -1,
                        "length_m": 1.8,
                        "width_m": 0.7,
                        "description": "Ein Radfahrer auf der Gegenspur, vom Lkw verdeckt.",
                        "triggers": [
                            when_ego_pulls_out(4.0, "get_visibility", "Die Gegenspur hinter dem Lkw ist nicht einsehbar."),
                            after_first_session(45.0, 4.0, "get_visibility", "Die Gegenspur hinter dem Lkw ist nicht einsehbar."),
                        ],
                    },
                ],
                "reference": {
                    "commands": ["OVERTAKE", "PEEK_OUT", "WAIT"],
                    "sequence": [["OVERTAKE", "NUDGE_AROUND_OBSTACLE"]],
                    "outcome": "liberated",
                    "budget_eur": 80.0,
                    "reason": "Am Checkpoint taucht ein Radfahrer auf: zurück, ihn vorbeilassen, dann überholen.",
                },
            },
            {
                "id": "f3_niemand_kommt",
                "introductory": False,
                "actors": [
                    {
                        "id": "breiter_lkw",
                        "kind": "truck",
                        "s_m": 92.0,
                        "d_m": -1.6,
                        "length_m": 8.0,
                        "width_m": 2.55,
                        "description": "Ein breiter Lkw steht in der eigenen Spur und verdeckt die Gegenspur weiter vorn.",
                    }
                ],
                "reference": {
                    "commands": ["OVERTAKE", "PEEK_OUT"],
                    "outcome": "liberated",
                    "budget_eur": 50.0,
                    "reason": "Am Checkpoint ist die Gegenspur frei: weiterfahren.",
                },
            },
        ],
    },
    {
        "family": "F4",
        "title": "Rückweg verbaut",
        "level": "D",
        "goal": "Optionen haben einen Wert: früh entscheiden, solange Wenden noch möglich ist.",
        "variants": [
            {
                "id": "f4_frueh_zu",
                "introductory": True,
                "actors": [STOPPED_CAR, *CRASH_SITE, *queue_behind(14.0)],
                "route": CRASH_ROUTE,
                "reference": {
                    "commands": ["WAIT", "OVERTAKE", "PEEK_OUT", "TURN_AROUND", "REPLAN_ROUTE"],
                    "sequence": [["TURN_AROUND"]],
                    "outcome": "rerouted",
                    "budget_eur": 220.0,
                    "reason": "Vorn ist alles gesperrt, und von hinten kommt bald Verkehr: sofort nachsehen und wenden, solange Platz ist.",
                },
            },
            {
                "id": "f4_spaet_zu",
                "introductory": False,
                "actors": [STOPPED_CAR, *CRASH_SITE, *queue_behind(45.0)],
                "route": CRASH_ROUTE,
                "reference": {
                    "commands": ["WAIT", "OVERTAKE", "PEEK_OUT", "TURN_AROUND", "REPLAN_ROUTE"],
                    "sequence": [["TURN_AROUND"]],
                    "outcome": "rerouted",
                    "budget_eur": 220.0,
                    "reason": "Vorn ist alles gesperrt; es bleibt Zeit, aber Warten bringt nichts: nachsehen und wenden.",
                },
            },
            {
                "id": "f4_nur_stau",
                "introductory": False,
                "actors": [
                    STOPPED_CAR | {"triggers": [after_first_session(25.0, 4.0, "get_tracked_objects", "Vor dem Transporter ist nichts; er fährt bald weiter.")]},
                    *queue_behind(10.0),
                ],
                "reference": {
                    "commands": ["WAIT", "OVERTAKE", "PEEK_OUT"],
                    "outcome": "liberated",
                    "budget_eur": 60.0,
                    "reason": "Vor dem Transporter ist nichts; vorbeifahren ist richtig. Wenden wäre teuer und unnötig.",
                },
            },
        ],
    },
    {
        "family": "F5",
        "title": "Wende mit Tücken",
        "level": "D",
        "goal": "Wenden ist selbst ein riskantes Manöver: Verkehr in beiden Richtungen prüfen.",
        "variants": [
            {
                "id": "f5_frei",
                "introductory": True,
                "actors": [],
                "reference": {
                    "commands": ["WAIT", "TURN_AROUND", "REPLAN_ROUTE"],
                    "sequence": [["TURN_AROUND"]],
                    "outcome": "rerouted",
                    "budget_eur": 160.0,
                    "reason": "Die Straße ist gesperrt, niemand kommt: mit einer Dreipunktwende umdrehen.",
                },
            },
            {
                "id": "f5_radfahrer_hinten",
                "introductory": False,
                "actors": [
                    {
                        "id": "radfahrer_hinten",
                        "kind": "bicycle",
                        "s_m": 12.0,
                        "d_m": -4.3,
                        "speed_mps": 2.5,
                        "length_m": 1.8,
                        "width_m": 0.7,
                        "description": "Ein Radfahrer fährt hinter dem Fahrzeug am rechten Rand und kommt näher.",
                        "triggers": [
                            after_first_session(0.5, 5.0, "get_tracked_objects", "Ein Radfahrer kommt hinter dem Fahrzeug am Rand näher; wer wendet, kreuzt seinen Weg."),
                        ],
                    }
                ],
                "reference": {
                    "commands": ["WAIT", "TURN_AROUND", "REPLAN_ROUTE"],
                    "sequence": [["TURN_AROUND"]],
                    "outcome": "rerouted",
                    "budget_eur": 180.0,
                    "reason": "Erst den Radfahrer vorbeilassen, dann wenden.",
                },
            },
            {
                "id": "f5_gegenverkehr",
                "introductory": False,
                "actors": [
                    {
                        "id": "gegenverkehr_1",
                        "kind": "car",
                        "s_m": 125.0,
                        "d_m": 1.75,
                        "direction": -1,
                        "description": "Ein Pkw wartet auf der Gegenspur, etwa an einer Ampel, und fährt gleich los.",
                        "triggers": [after_first_session(0.5, 7.0, "get_tracked_objects", "Zwei Fahrzeuge warten auf der Gegenspur und fahren gleich los.")],
                    },
                    {
                        "id": "gegenverkehr_2",
                        "kind": "car",
                        "s_m": 133.0,
                        "d_m": 1.75,
                        "direction": -1,
                        "description": "Ein zweiter Pkw wartet dahinter auf der Gegenspur.",
                        "triggers": [after_first_session(1.5, 7.0, "get_tracked_objects", "Zwei Fahrzeuge warten auf der Gegenspur und fahren gleich los.")],
                    },
                ],
                "reference": {
                    "commands": ["WAIT", "TURN_AROUND", "REPLAN_ROUTE"],
                    "sequence": [["TURN_AROUND"]],
                    "outcome": "rerouted",
                    "budget_eur": 180.0,
                    "reason": "Zwei Fahrzeuge kommen gleich entgegen: sie vorbeilassen, dann wenden.",
                },
            },
        ],
    },
    {
        "family": "F6",
        "title": "Lage entspannt sich",
        "level": "B",
        "goal": "Vor dem Punkt ohne Rückkehr neu prüfen, aber nicht übervorsichtig sein.",
        "variants": [
            {
                "id": "f6_stau_loest_sich",
                "introductory": True,
                "actors": [
                    {
                        "id": f"stau_{index}",
                        "kind": "car",
                        "s_m": 92.0 + 8.0 * index,
                        "d_m": -1.75,
                        "description": "Ein Pkw steht im Stau in der eigenen Fahrspur, Bremslicht an.",
                        "triggers": [after_first_session(12.0 - 1.0 * index, 4.0, "get_tracked_objects", "Mehrere Fahrzeuge stehen hintereinander: ein Stau, der sich bald auflöst.")],
                    }
                    for index in range(3)
                ],
                "reference": {
                    "commands": ["WAIT"],
                    "outcome": "resolved",
                    "budget_eur": 30.0,
                    "reason": "Ein gewöhnlicher Stau, der sich nach wenigen Sekunden auflöst. Überholen wäre unnötig riskant.",
                },
            },
            {
                "id": "f6_stau_faehrt_an",
                "introductory": False,
                "actors": [
                    {
                        "id": f"stau_{index}",
                        "kind": "car",
                        "s_m": 92.0 + 8.0 * index,
                        "d_m": -1.75,
                        "description": "Ein Pkw steht im Stau in der eigenen Fahrspur, Bremslicht an.",
                        "triggers": [
                            when_ego_pulls_out(4.0, "get_tracked_objects", "Mehrere Fahrzeuge stehen hintereinander: ein Stau, der jederzeit anfahren kann."),
                            after_first_session(40.0 - 1.0 * index, 4.0, "get_tracked_objects", "Ein Stau löst sich irgendwann auf."),
                        ],
                    }
                    for index in range(3)
                ],
                "reference": {
                    "commands": ["WAIT"],
                    "outcome": "resolved",
                    "budget_eur": 50.0,
                    "reason": "Ein Stau, der anfährt, sobald man ausschert. Geduld ist billiger als ein abgebrochenes Manöver.",
                },
            },
            {
                "id": "f6_panne",
                "introductory": False,
                "actors": [
                    {
                        "id": "pannenwagen",
                        "kind": "car",
                        "s_m": 92.0,
                        "d_m": -1.75,
                        "description": "Ein Pkw steht mit Warnblinker in der eigenen Fahrspur; ein Warndreieck steht dahinter, die Motorhaube ist offen.",
                    }
                ],
                "reference": {
                    "commands": ["NUDGE_AROUND_OBSTACLE", "OVERTAKE", "PEEK_OUT"],
                    "outcome": "liberated",
                    "budget_eur": 40.0,
                    "reason": "Eine Panne: Der Wagen bleibt stehen. Die Gegenspur ist frei, also vorbeifahren.",
                },
            },
        ],
    },
]

# F5: Absperrung der eigenen Spur; die Gegenspur bleibt fuer entgegenkommenden Verkehr offen.
ROAD_CLOSED = {
    "id": "absperrung",
    "kind": "barrier",
    "s_m": 100.0,
    "d_m": -1.75,
    "length_m": 0.6,
    "width_m": 3.4,
    "description": "Eine rot-weiße Absperrschranke mit Schild 'Straße gesperrt' steht quer über der eigenen Spur.",
}
F5_ROUTE = {"blocked": True, "alternative_available": True, "detour_cost_s": 180.0, "turn_required": True}


def scenario(family: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    level = LEVELS[family["level"]]
    data = copy.deepcopy(BASE)
    data = {"id": variant["id"], **data}
    actors = copy.deepcopy(variant["actors"])
    route = copy.deepcopy(variant.get("route", BASE["route"]))
    if family["family"] == "F5":
        actors = [copy.deepcopy(ROAD_CLOSED), *actors]
        route = copy.deepcopy(F5_ROUTE)
    data["actors"] = actors
    data["route"] = route
    if level["noise"]:
        data["perception"] = {"noise": dict(level["noise"])}
    data["difficulty"] = {"level": family["level"], "guardrails": level["guardrails"], "perception_model": "tracked"}
    data["reference"] = copy.deepcopy(variant["reference"])
    return data


def render(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def expected_files() -> dict[Path, str]:
    files: dict[Path, str] = {}
    catalog = []
    introductory, additional = [], []
    for family in FAMILIES:
        for variant in family["variants"]:
            files[OUT / f"{variant['id']}.json"] = render(scenario(family, variant))
            catalog.append(
                {
                    "id": variant["id"],
                    "family": family["family"],
                    "title": family["title"],
                    "level": family["level"],
                    "goal": family["goal"],
                    "visible": True,
                    "introductory": variant["introductory"],
                }
            )
            (introductory if variant["introductory"] else additional).append(variant["id"])
    files[OUT / "catalog.json"] = render({"version": 2, "families": catalog})

    def scenario_set(title: str, ids: list[str]) -> str:
        return "\n".join([f"# {title}", *(f"../families/{item}.json" for item in ids)]) + "\n"

    files[SETS / "familien_sichtbar.txt"] = scenario_set("Einstieg: je Familie eine Variante; alle 18 sind in familien_alle.txt veröffentlicht.", introductory)
    files[SETS / "familien_alle.txt"] = scenario_set("Alle 18 veröffentlichten Varianten der sechs Familien.", introductory + additional)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="nur pruefen, ob die Dateien aktuell sind")
    args = parser.parse_args(argv)
    stale = []
    for path, content in expected_files().items():
        current = path.read_text(encoding="utf8") if path.exists() else None
        if current == content:
            continue
        if args.check:
            stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf8")
    if stale:
        print("Veraltet, bitte build_families.py ausfuehren: " + ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
