# Spickzettel

Alles zum Nachschlagen auf einer Seite. Details in [COMMANDS.md](../COMMANDS.md).

## Befehle starten

```bash
# Prüfen (Selbsttest; alle Tests mit: python3 -m unittest discover -s tests)
python3 -m unittest tests.test_autonomy_recovery_sim
python3 -m autonomy_recovery_sim validate autonomy_recovery_sim/scenarios

# Live-Oberfläche (ohne Agent: Recovery Console = ihr seid der Agent)
python3 -m autonomy_recovery_sim.live --scenario autonomy_recovery_sim/scenarios/hannover_frei.json

# Ein Szenario mit Agent (Ergebnis: artifacts/autonomy-recovery-sim/<szenario>/result.json)
python3 -m autonomy_recovery_sim autonomy_recovery_sim/scenarios/hannover_frei.json --agent autonomy_recovery_sim.student_agent:decide

# Prüfstand: euer Agent gegen alle Szenarien oder eine Freigabestufe (siehe PRUEFSTAND.md)
python3 -m autonomy_recovery_sim batch --agent autonomy_recovery_sim.student_loop_agent:decide
python3 -m autonomy_recovery_sim batch --release sprint2 --agent autonomy_recovery_sim.student_loop_agent:decide --output artifacts/loop/e1

# Derselbe Prüfstand mit VLA-Fahrstack (Semantik nur als Modelltext)
python3 -m autonomy_recovery_sim batch --vla --release sprint3 --agent autonomy_recovery_sim.student_loop_agent:decide

# Eigener Loop ohne Schlüssel (Spielmodell)
AUTONOMY_RECOVERY_MODEL=spielmodell python3 -m autonomy_recovery_sim batch --release sprint1 --agent autonomy_recovery_sim.student_loop_agent:decide

# Viele Szenarien (Bericht: artifacts/autonomy-recovery-sim/batch/ oder --output)
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/public.txt --agent baseline
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/demo.txt --agent autonomy_recovery_sim.student_llm_agent:decide --repeats 3

# Zwei Auswertungen vergleichen
python3 -m autonomy_recovery_sim.tutorials.vergleich <ordner-a> <ordner-b>
```

`--agent`: `none` · `baseline` · `llm` · `python_modul:funktion`.

## Szenariemengen

| Datei | Inhalt |
|---|---|
| `scenario_sets/demo.txt` | drei erklärte Einstiegsfälle |
| `scenario_sets/public.txt` | 25 Entwicklungsfälle |
| `scenario_sets/commands.txt` | je ein Fall pro Befehl plus Kostenabwägungen |
| `scenario_sets/uncertainty.txt` | Datenqualität, Ausfälle, Manipulation, Kontrollfall |
| `scenario_sets/hannover.txt` | Hannover-typisch auf OSM: Abpfiff am Stadion, Marathon-Sperrung und -Läufer |
| `scenario_sets/mehrstufig.txt` | Mehrstufige Lösungswege: bestanden nur mit allen Schritten |
| `scenario_sets/vla.txt` | VLA-Fahrstack: Selbstauskunft des Fahrstacks gegen die Lage prüfen |
| `scenario_sets/erkennen.txt` | erst erkennen: steckt das Fahrzeug fest? (Ampel, Zug, Stau, Halt) |

Empfohlene kumulative Sprintmengen (alle Fälle sind zugänglich): `released_sprint1.txt` (8),
`released_sprint2.txt` (20), `released_sprint3.txt` (36) und
`released_sprint4.txt` (61). Die Zuordnung steht im
[`Szenarienkatalog`](../SCENARIOS.md).

## Die Werkzeuge

Im Wahrnehmungsmodell `exact` (Standard, L1 bis L3) gibt es zwölf lesende Werkzeuge:

| Werkzeug | Liefert |
|---|---|
| `get_blocker` | stehendes Hindernis: Art, Abstand, Position, ggf. `track_confidence`, `scene_description` |
| `get_center_marking` | `dashed` oder `solid`, Ausnahme erlaubt? |
| `check_oncoming_traffic` | Gegenverkehr im Horizont (`horizon_s`, Standard 8) |
| `check_rear_traffic` | überholender Verkehr von hinten (`horizon_s`, Standard 6) |
| `check_vulnerable_road_users` | Fuß- und Radverkehr sowie Tiere im Fahrkorridor |
| `get_lateral_clearance` | verfügbarer und nötiger seitlicher Abstand |
| `get_visibility` | Sichtweite und Verdeckungen |
| `get_route_state` | Routenblockade, Alternative, Umwegkosten |
| `get_mission_context` | Fahrgäste, Hub, Leitstelle, Halteposition, Nachbarspuren, `mission_state` |
| `get_recovery_history` | frühere Befehle, Wiederholungswarnungen |
| `get_sensor_health` | Kamera, LiDAR, Lokalisierung |
| `get_traffic_control` | Ampeln und Bahnübergänge voraus: Zustand (`RED`, `GREEN`, `DARK`, `OPEN`, `CLOSED`) und Alter |

Nur in Szenarien mit VLA-Fahrstack (`driving_stack` im Kontext) kommen zwei Werkzeuge dazu.
Beide liefern **Modellausgaben**, die falsch sein können:

| Werkzeug | Liefert |
|---|---|
| `get_vla_output` | Begründung des Fahrstacks, Meta-Aktion, Konfidenz, 6,4-s-Trajektorie, letzte Ausgaben (`last_n`) |
| `get_camera_caption` | Bildbeschreibung einer Kamera (`front_wide`, `front_tele`, `cross_left`, `cross_right`) |

Im Wahrnehmungsmodell `tracked` (`--perception tracked`, ab L4) entfallen die ersten
sieben. Statt fertiger Urteile gibt es Messungen, aus denen euer Agent selbst rechnet
(Hilfsfunktionen in `recovery_helpers`):

| Werkzeug | Liefert |
|---|---|
| `get_tracked_objects` | Objektliste im Fahrzeugrahmen `base_link`: Klasse mit Wahrscheinlichkeiten, Position, Geschwindigkeit, Unsicherheit, Alter |
| `get_sensor_coverage` | Sichtweite je Bereich und verdeckende Objekte |
| `get_map_context` | Fahrstreifen, Mittellinie, Breiten aus der Karte |

Im Prüfmodus `strict` sind die **ersten sieben** (bzw. die drei Messwerkzeuge) die Belege,
die jedes Fahrmanöver verlangt. Ergebnisse können
`observation_age_s` (veraltet) tragen. Budget: 14 Aufrufe je Sitzung, 3 Entscheidungsversuche.

## Die Befehle

| Befehl | Pflichtparameter | Endet Episode |
|---|---|:---:|
| `WAIT` | `duration_s` (1–30) | |
| `REPLAN_ROUTE` | – | ja |
| `REVERSE_SHORT` | `max_distance_m` (0,5–5) | |
| `PULL_OVER` | – | |
| `NUDGE_AROUND_OBSTACLE` | `side`, `max_longitudinal_distance_m` (5–50) | |
| `CHANGE_LANE` | `direction` | |
| `AVOID_TEMPORARY_OBSTRUCTION` | `obstruction_type`, `side`, `max_lateral_offset_m` (0,2–2,5) | |
| `CROSS_LOW_RISK_OBJECT` | `max_speed_mps` (0,5–1,5; Standard 1,0) | |
| `REQUEST_REMOTE_ASSISTANCE` | `reason_code` | |
| `ABORT_MISSION` | `reason_code` | ja |
| `SAFE_STOP` | `reason_code` | ja |
| `RETURN_HOME` | – | ja |
| `DROP_PASSENGER` | – | ja |
| `REQUEST_ADDITIONAL_INFORMATION` | `topic`, `duration_s` (1–10) | |
| `ESCALATE_TO_RULE_ENGINE` | – | |
| `RESUME` | – | |
| `CREEP_FORWARD` | `max_distance_m` (0,5–5) | |
| `PEEK_OUT` | `side`, `lateral_offset_m` (0,3–1,5) | |
| `OVERTAKE` | `side`, `max_longitudinal_distance_m` (5–60) | |
| `ABORT_TO_LANE` | – | |
| `WAIT_FOR_GAP` | `min_gap_s`, `timeout_s`, `then`, `side`, `max_longitudinal_distance_m` | |
| `TURN_AROUND` | `method` (`U_TURN`, `THREE_POINT`) | ja |
| `SECURE_SCENE` ¹ | – | |
| `REPORT_INCIDENT` ¹ | `injured_persons_suspected` | ja |

`PEEK_OUT` und `OVERTAKE` halten an einem Checkpoint (`trigger.type = "CHECKPOINT"`):
`RESUME` setzt fort, jeder andere Befehl ersetzt das Manöver. Dort läuft die Uhr.

¹ Nur in den Prüfmodi `advisory` und `off` (`difficulty.guardrails` im Kontext). Dort gibt
es auch `get_vehicle_status` (Aufprall, Warnblinker, Meldung) und jede Sitzung nennt ihren
Auslöser unter `trigger`: `DEADLOCK`, `IMPACT_DETECTED` oder `MANEUVER_FINISHED`.

Ausgabeformat: `{"command": ..., "parameters": {...}, "reason": "..."}`.

## Fehlercodes

| Code | Bedeutung | Ursache liegt bei |
|---|---|---|
| `INVALID_ARGUMENT` | Schema oder Bereich verletzt | Agent |
| `NOT_AVAILABLE` | Befehl in dieser Lage nicht verfügbar (z. B. keine Nachbarspur) | Lage |
| `RULE_REJECTED` | Verkehrsregel (durchgezogene Linie, Gegenfahrbahn) | Regelprüfung |
| `SAFETY_REJECTED` | Sicherheit (fehlende Belege, Zielspur belegt, Lokalisierung) | Sicherheitsprüfung |
| `TOOL_TIMEOUT` | Werkzeug ausgefallen, erneut versuchbar | Werkzeug |

## Ausgänge (`outcome`)

`liberated` (Hindernis passiert) · `resolved` (Weg wurde frei) · `waiting` · `aborted`
(Manöver sicher abgebrochen) · `rerouted` · `safe_stopped` · `mission_aborted` ·
`returned_home` · `passenger_dropped` · `remote_resolved` · `not_triggered`.

## Kosten (Modellannahmen)

Personenschaden 100 000 € · Sachschaden 5 000 € · Remote-Anruf 25 € · Stillstand 0,50 €/s ·
Umweg/Rückfahrt 0,50 €/s · Bergung 150 € (+100 € im Fahrstreifen) · Missionsabbruch 40 €
(+200 € je gestrandetem Fahrgast) · Regel-Engine 1 € · abgelehnter Befehl 2 €.

## Wo steht was in `result.json`

| Feld | Inhalt |
|---|---|
| `command`, `commands` | erster inhaltlicher Befehl; Verlauf aller Befehle mit Status |
| `outcome`, `collision`, `reached_goal` | Ergebnis |
| `costs` | Kostenpositionen, Gesamtsumme, Kundenzufriedenheit |
| `within_budget`, `budget_eur` | Budget des Szenarios |
| `agent_trace` | `tool_call`, `decision_attempt`, `model_round` in Reihenfolge |
| `agent_error` | Fehler, der zum Ersatzverhalten `WAIT` führte |
| `events` | alles, was in der Simulation geschah |

## Modell einrichten

```bash
export AUTONOMY_RECOVERY_BASE_URL=https://chat-ai.academiccloud.de/v1
export AUTONOMY_RECOVERY_MODEL=glm-4.7
read -rs "AUTONOMY_RECOVERY_API_KEY?Schluessel: " && echo && export AUTONOMY_RECOVERY_API_KEY   # zsh
```

Weitere Variablen: `AUTONOMY_RECOVERY_TIMEOUT_S` (90), `AUTONOMY_RECOVERY_MAX_ROUNDS` (12).

## Dateien, die euch gehören

- `mein_agent.py` im Wurzelverzeichnis: euer Agent aus dem Tutorial-Track; Startstände je
  Lektion unter [`track/`](track/)
- [`student_llm_agent.py`](../student_llm_agent.py): Referenzadapter, bei dem allein das
  Modell entscheidet; nur der Prompt ist editierbar
- [`student_agent.py`](../student_agent.py), [`student_loop_agent.py`](../student_loop_agent.py):
  Starter der archivierten Stufen 2 und 3b
- [`tutorials/helpers.py`](helpers.py): Wiederholung, Datenalter, Belege

## Tutorial-Track: Mengen und Schalter

| Lektion | Messen mit |
|---|---|
| L1, L2 | `released_sprint1.txt`, `released_sprint2.txt` |
| L3 | `released_sprint2.txt`, `mehrstufig.txt` |
| L4, L5 | `released_sprint2.txt --perception tracked`, `familien_sichtbar.txt` |
| L6 | `vla.txt`, `uncertainty.txt` mit `--perception tracked` |
| L7 | `familien_sichtbar.txt` zum Einstieg, danach `familien_alle.txt` (18) |
| L8 | `released_sprint3.txt --perception tracked --guardrails off` |

`--perception tracked` schaltet auf die Objektliste mit Messunsicherheit, `--guardrails off`
auf den Prüfmodus ohne vorausschauende Abbrüche. Startstände: `tutorials/track/l{n}_start.py`.
Teil A der Laboraufgabe misst euren Agenten mit `AUTONOMY_RECOVERY_MODEL=none` (ohne Modell),
Teil B mit Modell.
