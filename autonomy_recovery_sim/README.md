# AutonomyRecoverySim

Ein kleiner deterministischer 2D-Simulator fuer den Use Case
**Agentic Autonomy Recovery**. Der zu entwickelnde **Autonomy Recovery Agent**
untersucht festgefahrene Situationen und waehlt einen begrenzten
High-Level-Befehl. Der Simulator trennt drei Fragen:

1. Erkennt der Stillstandsmonitor eine echte Blockade?
2. Waehlt der Autonomy Recovery Agent den richtigen High-Level-Befehl aus dem Katalog
   ([`COMMANDS.md`](COMMANDS.md))?
3. Kann ein zertifizierter Ausfuehrer den genehmigten Befehl sicher fahren, und
   was kostet die Entscheidung (Standzeit, Remote Assistance, Schaeden)?

Der Simulator startet bewusst **ohne Entscheidungsagenten**. Das Ego faehrt
autonom bis zu einer Blockade und wartet dort sicher. Erst nachdem der
Stillstandsmonitor einen Deadlock-Verdacht gemeldet hat, wird ein explizit geladener
Agent aktiviert. Er muss zuerst pruefen, ob wirklich ein Eingriff noetig ist. Eine
transparente Heuristik steht nur als auswaehlbare
Referenzbaseline zur Verfuegung.

Diese Datei ist die **technische Referenz** des Simulators. Studierende beginnen mit dem
[Team-Lernpfad](tutorials/README.md) und dem Tutorial-Track L1 bis L8. Welches Dokument
wofuer da ist, zeigt die [Dokumentationsuebersicht](../README.md#dokumentation) im
Repository-Einstieg.


### Verbindliche Terminologie

- **Agentic Autonomy Recovery** bezeichnet den Use Case.
- **Autonomy Recovery Agent** bezeichnet den Entscheidungsagenten.
- **Recovery Request**, **Recovery Session** und **Recovery Decision** bezeichnen
  Aktivierung, Untersuchung und Ergebnis des Agenten.
- **Remote Assistance** bleibt die getrennte Eskalation an einen menschlichen
  Remote Operator; sie steuert das Fahrzeug nicht direkt.
- Das Python-Paket und der CLI-Einstieg heissen `autonomy_recovery_sim`.
  Szenarien konfigurieren den Ablauf im Block `recovery`.

## Schnellstart

Voraussetzung ist Python 3.10 oder neuer unter Linux, macOS oder Windows.
Der Simulator verwendet nur die Standardbibliothek. Alle Befehle werden aus
dem Wurzelverzeichnis des Checkouts ausgefuehrt; Einrichtung und Orientierung
stehen im [Repository-Einstieg](../README.md).

```bash
python3 -m autonomy_recovery_sim.live --scenario autonomy_recovery_sim/scenarios/hannover_frei.json
python3 -m autonomy_recovery_sim.live --scenario autonomy_recovery_sim/scenarios/hannover_frei.json --agent baseline
python3 -m autonomy_recovery_sim autonomy_recovery_sim/scenarios/hannover_frei.json --agent llm
python3 -m autonomy_recovery_sim autonomy_recovery_sim/scenarios/hannover_frei.json --agent baseline
python3 -m autonomy_recovery_sim validate autonomy_recovery_sim/scenarios
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/public.txt --agent baseline
python3 -m unittest discover -s tests
```

Die Live-Oberflaeche liegt danach unter `http://127.0.0.1:8765`. Sie startet
pausiert und nach jedem Neustart im Modus **Autopilot**. Der Autopilot folgt
zunaechst nur Route und Fahrspur. Er darf ein Ausweichmanoever erst ausfuehren,
nachdem der am Deadlock aktivierte Agent einen validen Befehl geliefert hat.
Ohne Agent bleibt das Ego am Hindernis stehen; die **Recovery Console** der
Oberflaeche laesst Sie dann selbst die Agentensitzung fuehren und jeden der 15
Befehle per Hand ausloesen (siehe [`COMMANDS.md`](COMMANDS.md#befehle-von-hand-ausloesen-recovery-console)). Im optionalen Modus **Manuell** wird das Fahrzeug mit
`W/A/S/D` oder den Pfeiltasten gefahren. Start/Pause, Einzelschritt, Reset und
Zeitfaktor sind direkt in der Oberflaeche verfuegbar.
Nach einem abgeschlossenen Lauf startet **Neu starten** dasselbe Szenario
automatisch wieder bei `t = 0`; ein vorheriger manueller Reset ist nicht noetig.

Links oben kann zwischen **3D Fahrt** und **Top-down** gewechselt werden. Die
perspektivische Ansicht folgt dem Ego-Fahrzeug, zeigt den geplanten Fahrkorridor
und stellt erkannte Fahrzeuge typabhaengig in Grau dar. Das Ego ist ein
Kleinbus mit ID.-Buzz-aehnlichen Abmessungen (`4,71 × 1,99 m`), aber ohne
geschuetztes Markenmodell. Ist `vehicles/ego_minibus.glb` vorhanden, wird dieses
Modell samt eingebetteter Textur in der 3D- und Top-down-Ansicht gerendert. Kann
es nicht geladen werden, bleibt automatisch die prozedurale Darstellung aktiv.
Die 3D-Kamera kann durch Ziehen horizontal und vertikal gedreht werden; Mausrad,
Pinch, `+`/`-` und die Schaltflaechen steuern den Zoom. Der Kamera-Reset oder
die Taste `0` stellt Blickrichtung, Neigung und 100-%-Zoom wieder her.

Die Top-down-Karte kann mit Mausrad oder Trackpad gezoomt und durch Ziehen
verschoben werden. Auf Touch-Geraeten funktionieren Ein-Finger-Verschieben und
Zwei-Finger-Zoom. Zusaetzlich stehen Schaltflaechen fuer Zoom und Zentrierung
bereit; auf der Tastatur gelten `+`, `-` und `0`. Die Karte startet bei 800 %.
Solange sie nicht
manuell bewegt oder gezoomt wurde, folgt sie dem Ego-Fahrzeug. Der
Zentrierungs-Button beziehungsweise `0` aktiviert diese Verfolgung wieder,
ohne die gewaehlte Zoomstufe zu veraendern.

Spezifikationen fuer spaetere echte Fahrzeugmodelle stehen in
[`ASSETS.md`](ASSETS.md).

Jeder Lauf schreibt `result.json` und `replay.svg` nach
`artifacts/autonomy-recovery-sim/<szenario>/`.

## Agentenvertrag und Auswertung

### Aktivierungsablauf

1. Das Ego startet autonom; der Entscheidungsagent hat den Zustand `inactive`.
2. Der normale Spurfolger faehrt bis zur erkannten Blockade und stoppt.
3. Nach der konfigurierten Stillstandszeit erzeugt der Simulator eine
   Agentenbeobachtung (eine *Sitzung*).
4. Ohne Agent wechselt der Zustand zu `waiting_for_agent`; es wird nichts
   ausgefuehrt.
5. Mit Agent wird dessen Funktion einmal je Sitzung aufgerufen. Erst ein
   validierter Befehl aktiviert den zertifizierten Ausfuehrer. Endet der Befehl
   ohne Loesung (z. B. `WAIT`) und steht das Fahrzeug weiter, beginnt eine neue
   Sitzung mit Verlauf und gesammelter Zusatzinformation. Terminale Befehle
   (`REPLAN_ROUTE`, `SAFE_STOP`, `ABORT_MISSION`, `RETURN_HOME`,
   `DROP_PASSENGER`) beenden die Episode.

Der Stillstandsmonitor und die Fahrzeugregelung sind damit Infrastruktur. Die
studentische Aufgabe beginnt am Deadlock: Werkzeuge auswerten, unter 15
High-Level-Befehlen den wirtschaftlich und sicherheitlich besten waehlen und
knapp begruenden. Alle Befehle, Parameter, Regeln und Kosten stehen in
[`COMMANDS.md`](COMMANDS.md).

Agenten werden explizit ausgewaehlt:

```bash
# Kein Entscheidungsagent; Standard fuer die Beobachtung des Laborablaufs
python3 -m autonomy_recovery_sim.live --agent none

# Referenzheuristik fuer Lehrende und Demonstrationen
python3 -m autonomy_recovery_sim.live --agent baseline

# OpenAI-kompatibler Referenzadapter; Zugangsdaten aus der Umgebung
python3 -m autonomy_recovery_sim.live --agent llm

# Euer Agent aus dem Tutorial-Track (Datei mein_agent.py im Wurzelverzeichnis)
python3 -m autonomy_recovery_sim.live --agent mein_agent:decide

# Referenzadapter, bei dem allein das Modell entscheidet; nur der Prompt ist editierbar
python3 -m autonomy_recovery_sim.live --agent autonomy_recovery_sim.student_llm_agent:decide
```

Eigene Module werden als `python_modul:funktion` geladen. Die Startstaende des
Tutorial-Tracks liegen in [`tutorials/track/`](tutorials/track/); der kleinste ist
`l1_start.py` und liefert absichtlich nur ein sicheres `WAIT`.

Der vollstaendige studentische Einstieg steht in
[`QUICKSTART.md`](QUICKSTART.md), die Arbeitsfassung der Laboraufgabe in
[`ASSIGNMENT.md`](ASSIGNMENT.md). Der eingebaute Agent `llm` spricht ohne
zusaetzliche Python-Pakete eine OpenAI-kompatible Chat-Completions-API. Der
editierbare Einstieg [`student_llm_agent.py`](student_llm_agent.py) verwendet
denselben Transport mit einem bewusst knappen Ausgangsprompt.

Der Simulator besitzt eine stabile Grenze zwischen Autonomy Recovery Agent und
Fahrzeugsteuerung. Der Agent erhaelt beim Deadlock nur einen Kontext mit
Ego-Zustand, Fahrauftrag, Werkzeugbeschreibungen und Budgets. Ergebnisse werden
nicht vorab geliefert. Stattdessen fragt der Agent ueber `session.call_tool(...)`
gezielt Werkzeuge ab: im Wahrnehmungsmodell `exact` zwoelf (sieben Lagewerkzeuge, dazu
Routen-, Missions-, Verlaufs-, Sensor- und Verkehrssteuerungsinformation), im Modell `tracked`
drei Messwerkzeuge statt der sieben Lagewerkzeuge (siehe
[Wahrnehmungsmodell `tracked`](#wahrnehmungsmodell-tracked)); dazu je nach Szenario die
Werkzeuge des Fahrstacks und `get_vehicle_status`. Das Kontextformat ist in
[`schemas/agent_observation.schema.json`](schemas/agent_observation.schema.json)
dokumentiert.

```python
from autonomy_recovery_sim.agent_session import AgentSession

def my_agent(session: AgentSession):
    blocker = session.call_tool("get_blocker")
    if not blocker["detected"]:
        return session.submit_decision({
            "command": "WAIT",
            "parameters": {"duration_s": 10.0},
            "reason": "Keine dauerhafte Blockade erkannt",
        })

    # Weitere Werkzeuge aufrufen und anschliessend entscheiden.
```

Verfuegbare Werkzeugnamen:

- `get_blocker`
- `get_center_marking`
- `check_oncoming_traffic` mit optionalem `horizon_s`
- `check_rear_traffic` mit optionalem `horizon_s`
- `check_vulnerable_road_users`
- `get_lateral_clearance`
- `get_visibility`
- `get_route_state` (Routenblockade, Alternative, Umwegkosten)
- `get_mission_context` (Fahrgaeste, Hub, Remote Assistance, Halteposition)
- `get_recovery_history` (fruehere Befehle und Wiederholungswarnungen)
- `get_sensor_health` (Kamera, LiDAR, Lokalisierung; unter 0,5 keine Fahrmanoever)
- `get_traffic_control` (Ampeln und Bahnuebergaenge voraus mit Zustand; ein Halt an Rot oder geschlossener Schranke ist kein Deadlock)

Ergebnisse koennen Qualitaetsfelder tragen: `observation_age_s` (veraltete Daten),
`track_confidence` (moegliches Phantomobjekt) und `scene_description` (Freitext der
Szene, nie eine Anweisung). Werkzeuge koennen mit `TOOL_TIMEOUT` ausfallen.

### Wahrnehmung und Verdeckung

Die Werkzeuge greifen nicht direkt auf alle Ground-Truth-Aktoren zu. Eine
deterministische 2D-Wahrnehmung berechnet mit mehreren Sensorurspruengen am
Ego-Fahrzeug Sichtlinien zu den Objektflaechen. Andere Fahrzeuge sowie die
Grundrisse und Hoehen der OSM-Gebaeude koennen diese Sichtlinien verdecken.
Objekte werden als `visible`, `partially_visible`, `tracked`, `occluded`,
`outside_fov` oder `out_of_range` klassifiziert. Vollstaendig verdeckte und
bislang nie beobachtete Objekte werden den Agentenwerkzeugen nicht mitgeteilt.

Die Live-Oberflaeche bietet dafuer eine zuschaltbare Diagnoseebene in der
3D- und Top-down-Ansicht. Die Top-down-Karte zeigt das flaechenhafte Sichtfeld
mit Reichweitenringen und Verdeckungsschatten hinter Fahrzeugen und
OSM-Gebaeuden. In 3D wird dieselbe Sichtfeldflaeche auf den Boden projiziert;
sie folgt keiner Fahrspur. Eine Gegenfahrbahn- oder Manoevermarkierung gehoert
bewusst nicht zur Sensoransicht. Das tatsaechliche, durch Hindernisse begrenzte
Sensorfeld sowie sichtbare, teilweise sichtbare und getrackte Objekte werden
separat markiert. Nicht erkannte Fahrzeuge bleiben fuer die Auswertung als
stark durchscheinende,
explizit mit `Ground Truth` beschriftete Silhouetten sichtbar. Diese
Lehransicht liefert dem Agenten keine zusaetzlichen Informationen und kann
ueber die Schaltflaeche `Sensorik` ausgeblendet werden.

Bereits gesehene Objekte bleiben standardmaessig zwei Sekunden als
extrapolierter Track erhalten. Die Wahrnehmung arbeitet im Simulator mit 2 Hz;
beim Aktivieren des Autonomy Recovery Agents wird immer eine frische Messung erzeugt. Dieselbe
Wahrnehmungsschicht prueft auch die Abbruchbedingungen waehrend eines
freigegebenen Manoevers. `get_visibility` meldet neben atmosphaerischer
Sichtweite die einsehbare Entfernung auf der Zielspur, den Beginn einer
Verdeckung und deren Ursache.

Das Ego misst aus vier Ecksensoren. Der seitliche Versatz ist gewollt: Nur
dadurch kann es an einem stehenden Blocker vorbei auf die Gegenfahrbahn
blicken - die Grundlage jeder Freigabeentscheidung. Ein Objekt gilt erst als
erkannt, wenn `min_detectable_fraction` seiner Silhouette frei liegt; ein
streifender Splitter hinter einem Hindernis bleibt `occluded` und damit fuer den
Agenten unsichtbar. Weil die Sensoren an den Ecken sitzen, sehen sie etwas mehr
als die auf der Mittelachse sitzende Kamera der 3D-Ansicht; die Sichtflaeche im
UI wird daher aus genau denselben vier Urspruengen gezeichnet.

Reichweite, horizontales Sichtfeld, Trackdauer und Mindestsichtflaeche sind pro
Szenario optional konfigurierbar:

```json
"perception": {
  "range_m": 60.0,
  "horizontal_fov_deg": 360.0,
  "track_memory_s": 2.0,
  "min_detectable_fraction": 0.3
}
```

Eine Sitzung erlaubt standardmaessig hoechstens 14 Werkzeugaufrufe und drei
Entscheidungsversuche. Manoever ueber die Fahrbahn (`NUDGE_AROUND_OBSTACLE`,
`CHANGE_LANE`, `AVOID_TEMPORARY_OBSTRUCTION`, `CROSS_LOW_RISK_OBJECT`) setzen Evidenz aus den sieben
Lagewerkzeugen voraus; `WAIT` und die uebrigen Befehle duerfen ohne unnoetige
weitere Aufrufe erfolgen. Unbekannte Werkzeuge, ungueltige Argumente und Budgetueberschreitungen
werden wie ein Agentenfehler fail-safe behandelt.

Die Antwort wird vor der Ausfuehrung strikt gegen
[`schemas/agent_decision.schema.json`](schemas/agent_decision.schema.json)
geprueft (`command`, `parameters`, `reason`). Unbekannte Befehle oder Felder und
Parameter ausserhalb der Grenzen werden mit `INVALID_ARGUMENT` abgelehnt; Regeln
und Sicherheit (`RULE_REJECTED`, `SAFETY_REJECTED`, `NOT_AVAILABLE`) prueft
[`rules.py`](rules.py). Der Agent darf innerhalb seines Entscheidungsbudgets
korrigieren. Bei Ausnahme oder erschoepftem Budget fuehrt der Simulator fail-safe
`WAIT` (5 s) aus und protokolliert `agent_contract_error`. Damit kann ein LLM
dieselbe Sitzungsschnittstelle wie die heuristische Baseline verwenden:

```python
from autonomy_recovery_sim.simulation import run_scenario

result = run_scenario(
    "autonomy_recovery_sim/scenarios/hannover_frei.json",
    agent=my_agent,
    agent_name="mein-agent",
)
```

Ein Manoever ist kein einmaliger Blankoscheck. Solange es aktiv ist, prueft der
Simulator in jedem Zeitschritt die Abbruchbedingungen. Aktuell werden neu auftretender Gegenverkehr, ein wieder
anfahrender Blocker sowie nachtraeglich erkannte Kollisionsrisiken ueberwacht.
Vor dem seitlichen Passieren des Hindernisses wird das Manoever widerrufen, das
Ego bremst auf der eigenen Fahrbahn bis zum Stillstand und protokolliert
`maneuver_aborted` sowie `abort_stabilized`. Ist der sichere Rueckweg bereits
versperrt, wird stattdessen `minimum_risk_completion` protokolliert und das
begonnene Passieren kontrolliert beendet. Diese vereinfachte Commit-Point-Logik
verhindert ein blindes Zuruecklenken in den Blocker.

`python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenarios --agent baseline` prueft die gesamte
Szenariomatrix und schreibt `batch-result.json` sowie `batch-report.md` nach
`artifacts/autonomy-recovery-sim/batch/`. Gemessen werden Befehlsgenauigkeit, Kollisionen,
unerwartete und verpasste Manoever, ungueltige Agentenausgaben, erfolgreiche
Befreiungen, sicher stabilisierte Abbrueche, die durchschnittliche Zahl der
Werkzeugaufrufe und Entscheidungsversuche sowie die **Wirtschaftlichkeit**:
Gesamtkosten in EUR, Remote-Assistance-Anrufe, Personenschaeden und
Kundenzufriedenheit (siehe [`COMMANDS.md`](COMMANDS.md#kostenmodell-und-einstufung)).
Ein Szenario besteht nur innerhalb seines Kostenbudgets. Der Batchlauf fasst das Ergebnis in
einer **Einstufung A bis D** zusammen (Rueckmeldung, keine Note), vergleicht mit dem vorigen
Lauf im selben Ausgabeordner und schreibt neben `batch-report.md` die Auswertungsseite
`batch-report.html`. Mit `--repeats N` wird jedes Szenario mehrfach ausgefuehrt
(sinnvoll fuer LLM-Agenten); der Bericht zeigt dann Bestehensquote und
Kostenstreuung. Details: [`COMMANDS.md`](COMMANDS.md#budget-einstufung-und-auswertungswebsite).
Fuer Studierende erklaert [`PRUEFSTAND.md`](PRUEFSTAND.md) den Ablauf: `--release sprintN`
waehlt die freigegebenen Faelle, jeder Fall bekommt einen Befund (warum er scheitert) und
eine Detailseite `scenarios/<id>/report.md` mit Befehlsfolge und Agent-Trace;
`--hide-reference` entfernt Referenzloesungen aus Berichten und Rohdaten (Abschlusslauf auf
verdeckten Faellen). Der
Modelladapter protokolliert zusaetzlich Modellrunden, Latenz und die vom
Endpunkt gemeldeten Tokenzahlen. Der
vollstaendige `agent_trace` enthaelt Reihenfolge, Argumente und Ergebnisse aller
Werkzeugaufrufe sowie angenommene oder abgelehnte Entscheidungsversuche. Zu
jedem Szenario wird ausserdem ein vollstaendiges `result.json` unter
`artifacts/autonomy-recovery-sim/batch/scenarios/<id>/` abgelegt.
Ein Batchlauf ohne `--agent` ist absichtlich keine bestandene Loesung: Die
Fahrzeuge erreichen den Deadlock, melden `waiting_for_agent` und warten dort.

Die 61 aktuellen Faelle decken freie Strecke, nahen und fernen Gegenverkehr,
durchgezogene Mittellinie, eingeschraenkte Sicht, einen bereits laufenden
Ueberholvorgang, Radverkehr im Korridor, eine zu schmale Fahrbahn sowie zwei
dynamische Abbrueche ab. Drei weitere Faelle pruefen teilweise verdeckten
Gegenverkehr, einen Radfahrer hinter dem Blocker und ein erst waehrend des
Versetzens sichtbar werdendes Fahrzeug. Im ersten klassischen dynamischen Fall
tritt Gegenverkehr erst nach der Freigabe in den Sicherheitshorizont ein; im
zweiten faehrt der Blocker wieder an. Zeitgesteuerte Aktoren verwenden gemeinsam
`motion_start_time_s` und `target_speed_mps`. Sieben weitere Faelle zeigen die
uebrigen Befehle: eine querende Fussgaengergruppe (`WAIT`), eine Baustelle mit
Umleitung (`REPLAN_ROUTE`), eine Sackgasse (`REVERSE_SHORT`, dann
`REPLAN_ROUTE`), eine Muelltonne (`AVOID_TEMPORARY_OBSTRUCTION`), einen
Doppelparker mit freier Nachbarspur (`CHANGE_LANE`), einen Fall ohne lokale
Loesung (`REQUEST_REMOTE_ASSISTANCE`) und eine freie Fahrt ohne Recovery.
Sieben schwierigere Faelle pruefen die Kostenabwaegung: Bake bei durchgezogener
Linie, falsch abgestelltes Objekt, belegte Nachbarspur, ein anfahrender
Lieferwagen (Warten statt Manoever), Fahrgaeste absetzen statt Rueckfahrt, ein
gesperrtes Ziel fuer ein leeres Fahrzeug und eine offline Leitstelle. Die
Baseline loest 11 der 25 oeffentlichen Faelle bewusst nicht; sie ist Vergleichsmassstab,
keine Musterloesung. Acht weitere Faelle ([`scenario_sets/uncertainty.txt`](scenario_sets/uncertainty.txt))
pruefen Datenqualitaet und Robustheit: Phantomobjekt, veraltete Werkzeugdaten,
veraltete Karte, driftende Lokalisierung, Werkzeug-Timeout, knappes Werkzeugbudget,
Prompt-Injection ueber einen Freitext und einen geplanten Halt als Kontrollfall.
Sechs weitere Faelle ([`scenario_sets/erkennen.txt`](scenario_sets/erkennen.txt)) verlangen, zuerst zu
erkennen, ob das Fahrzeug wirklich festhaengt: rote Ampel, Gueterzug am Bahnuebergang,
sich aufloesender Stau und geplanter Halt (dort ist Eingreifen falsch), dazu ein ausgefallenes
Signal und eine gruene Ampel mit echter Blockade als Gegenstuecke. Drei Hannover-typische Faelle
([`scenario_sets/hannover.txt`](scenario_sets/hannover.txt)) nutzen echtes OSM-Kartenmaterial: Fussgaengerstrom
nach dem Abpfiff am Stadion von Hannover 96, eine Marathon-Vollsperrung in der Innenstadt
und ein Laeuferstrom mit uneindeutig gestikulierendem Streckenposten. Fuenf
Sonderlagen in der Sprint-4-Freigabe ergaenzen Wildunfall, Sitzblockade,
entlaufene Zootiere, feiernde Fussballfans und einen umgekippten Lkw.
Fuenf Lost-Cargo-Varianten unterscheiden ausserdem zwischen einem sicher
klassifizierten flachen Karton (`CROSS_LOW_RISK_OBJECT`), einem umfahrbaren Reifen,
einem lokal zu passierenden Holzbalken sowie Scherben oder verstreuter schwerer
Ladung, die eine Umplanung erfordern. Eigene
Faelle folgen dem Vertrag in
[`schemas/scenario.schema.json`](schemas/scenario.schema.json) und koennen mit
dem `validate`-Kommando vor dem Lauf geprueft werden.

Fuer verdeckte Prueffaelle erzeugt
[`scripts/make_variants.py`](scripts/make_variants.py) aus bekannten Szenarien
reproduzierbar (Seed) Varianten mit verschobenen Aktorpositionen, veraenderten
Geschwindigkeiten und Zeitpunkten. Mit `--check` laeuft die Baseline darueber; bei
dynamischen Faellen muessen die Labels der gemeldeten Varianten von Lehrenden
geprueft werden, weil verschobene Zeitpunkte die erwartete Situation aendern
koennen. Die Ausgabe gehoert nicht in den Studierenden-Checkout.

## Reales Kartenmaterial

Das Beispiel verwendet den Verlauf der Wilhelm-Busch-Strasse in Hannover aus
OpenStreetMap, Way 4289539. OSM erfasst dort unter anderem Name, Strassentyp,
Tempo 30 und Asphalt. Spurbreite und Mittellinienmarkierung fehlen in diesem
Ausschnitt; sie sind deshalb im Szenario als Annahmen gekennzeichnet.

Die Live-Ansicht verwendet zusaetzlich einen lokal gespeicherten
`360 × 440 m`-Ausschnitt um die Route. Darin liegen umliegende Strassen,
Gebaeude, Gruenflaechen, Bahnlinien und ein Gewaesser. Gefahren wird weiterhin
auf der expliziten Szenarioroute; Gebaeudegrundrisse und -hoehen aus der
Kontextkarte dienen zusaetzlich als Sichtbarrieren fuer das Wahrnehmungsmodell.
Dadurch bleiben Tests deterministisch und die Oberflaeche braucht zur Laufzeit
keinen Kartendienst.

In der 3D-Ansicht werden Gebaeude als Hoehenbloecke dargestellt. Der Importer
verwendet bevorzugt `height`, danach `building:levels` (mit 3 m je Geschoss)
und erst zuletzt eine als Schaetzung gekennzeichnete, gebaeudetypabhaengige
Fallback-Hoehe. Vorhandene `building:part`-Geometrien werden getrennt
extrudiert; dadurch bleiben abgestufte Gebaeudekomplexe sichtbar.

Der Ausschnitt stammt aus der OSM Map API mit der Bounding Box
`9.7188,52.3785,9.7241,52.3825`. Eine erneut geladene OSM-XML-Datei wird so in
das kompakte Laufzeitformat ueberfuehrt:

```bash
python3 autonomy_recovery_sim/scripts/import_osm_context.py \
  context.osm \
  autonomy_recovery_sim/data/hannover_wilhelm_busch_strasse.geojson \
  autonomy_recovery_sim/data/hannover_wilhelm_busch_context.json
```

### Weitere Hannover-Ausschnitte

Fuer die Hannover-typischen Szenarien
([`scenario_sets/hannover.txt`](scenario_sets/hannover.txt)) gibt es weitere
OSM-Ausschnitte, geladen am 21./22.09.2026 ueber die OSM Map API:

| Ausschnitt | Route (OSM-Ways) | Bounding Box | Szenarien |
|---|---|---|---|
| Heinz-von-Heiden-Arena (Stadion von Hannover 96) | Robert-Enke-Strasse, 431 m (27095856, 1540868152, 681074694) | `9.7264,52.3590,9.7350,52.3630` | `hannover_fussball_abpfiff` |
| Innenstadt am Neuen Rathaus | Culemannstrasse, 513 m (1089017428, 59322751, 1089017427) | `9.7320,52.3635,9.7395,52.3690` | `hannover_marathon_sperrung`, `hannover_marathon_laeufer` |
| Erlebnis-Zoo / Zooviertel | Adenauerallee, 366 m (42747972, 1155218597, 961020636) | `9.7645,52.3780,9.7750,52.3840` | `hannover_zootiere` |

Aus OSM stammen Strassenverlauf, Namen, Gebaeude, Gruenflaechen und Gewaesser. **Erfunden**
(Szenarioannahmen, im Szenario unter `road.assumption_note` vermerkt) sind Spurbreite und
Mittellinie, der Fussgaengerstrom nach dem Abpfiff, die Marathon-Absperrung, der
Laeuferstrom, der Streckenposten und die entlaufenen Zootiere: OSM enthaelt weder
Veranstaltungssperrungen noch simulierte Tiere. Die Namen von Stadion und Zoo sind die
in OSM eingetragenen.

Routen aus mehreren OSM-Ways baut `scripts/import_osm_route.py`; die Kontextkarte entsteht
wie oben mit `import_osm_context.py` aus derselben XML-Datei:

```bash
python3 autonomy_recovery_sim/scripts/import_osm_route.py stadion.osm \
  autonomy_recovery_sim/data/hannover_robert_enke_strasse.geojson \
  --ways 27095856 1540868152 681074694 --name "Robert-Enke-Straße, Hannover"
python3 autonomy_recovery_sim/scripts/import_osm_context.py stadion.osm \
  autonomy_recovery_sim/data/hannover_robert_enke_strasse.geojson \
  autonomy_recovery_sim/data/hannover_robert_enke_context.json
```

Die rohen XML-Dateien liegen nicht im Repository, nur die kompakten Laufzeitdateien.

Kartendaten: © OpenStreetMap-Mitwirkende, ODbL 1.0.
https://www.openstreetmap.org/copyright

### VLA-Fahrstack-Mock (an NVIDIA Alpamayo 1.5 angelehnt)

Vorbild fuer den optionalen Mock ist NVIDIA Alpamayo 1.5 (`nvidia/Alpamayo-1.5-10B`), ein
Vision-Language-Action-Modell (VLA). Es liest vier Kameras und die Eigenbewegung und liefert
pro Inferenz eine Begruendung in Text ("Chain of Causation") und eine Trajektorie ueber 6,4 s
(64 Wegpunkte bei 10 Hz); ausserdem nimmt es Navigationshinweise als Text an und beantwortet
Fragen zur Szene. Ein Recovery Agent auf einem solchen Fahrzeug bekommt keine saubere
Objektliste, sondern die Selbstauskunft des Modells.

[`vla_mock.py`](vla_mock.py) bildet genau diese Schnittstelle nach, ohne GPU und
ohne Modell: Er uebersetzt die Fahrabsicht des Autopiloten regelbasiert in Text,
Konfidenz und Trajektorie; die Meta-Aktion ist eine daraus abgeleitete Kurzform, keine Ausgabe
von Alpamayo 1.5. Er sieht nur, was die Wahrnehmung sieht,
und ist ueber den Seed deterministisch. Der Mock ist ein Beobachter und veraendert
das Fahrverhalten nicht. Aktiviert wird er pro Szenario:

```json
"vla": {
  "seed": 7,
  "latency_ms": 120,
  "perception_interface": "vla",
  "faults": [{"type": "HALLUCINATED_CAUSE", "text": "the traffic light ahead is red"}]
}
```

- **Werkzeuge:** `get_vla_output(last_n)` liefert Begruendung, Meta-Aktion,
  Konfidenz, Trajektorienzusammenfassung und die letzten Ausgaben;
  `get_camera_caption(camera)` fragt das Modell, was `front_wide`, `front_tele`,
  `cross_left` oder `cross_right` zeigen (wie die Fragen-Antworten von Alpamayo 1.5). Beide gibt es nur mit `vla`-Block.
- **`perception_interface`:** `structured` (Standard) laesst die Lagewerkzeuge
  unveraendert. `vla` entfernt Objektklasse, Hindernisprofil, Szenentext und
  Signalzustand aus den Lagewerkzeugen; Abstaende, Zeitluecken und Freiraeume
  bleiben (sie entsprechen einer geometrischen Sicherheitsschicht). Regel- und
  Sicherheitspruefung arbeiten weiter auf der vollen Lage.
- **`latency_ms`:** neue Ausgaben nur in diesem Takt; jede Ausgabe traegt
  `output_age_s`.
- **`faults`:** `HALLUCINATED_CAUSE` (erfundene Ursache, Feld `text`),
  `REASONING_ACTION_MISMATCH` (Text und Trajektorie widersprechen sich),
  `VAGUE_CAUSE` und `OVERCONFIDENT` (optional auf `actor_id` begrenzt); alle mit
  optionalem Zeitfenster `from_s`/`until_s`.

**VLA-Modus fuer alle Szenarien:** Die Option `--vla` (Batchlauf, Einzellauf und
Live-Oberflaeche) faehrt jedes Szenario mit fehlerfreiem Mock und Schnittstelle `vla`;
vorhandene `vla`-Bloecke behalten ihre Fehlerbilder. Ein Test sichert zu, dass in jedem Fall
die entfernten Angaben (Objektklasse, Materialprofil, Signalzustand) in einer
Kamerabeschreibung stehen. Szenentexte in Nahsicht, etwa beschriftete Schilder, gibt die
Kamera als `Scene text` wieder. Kein Fall wird dadurch unloesbar, er wird nur schwerer.

```bash
python3 -m autonomy_recovery_sim batch --vla --agent baseline
```

Die Live-Oberflaeche zeigt die Begruendung und zeichnet die geplante Trajektorie.
Die drei Lehrfaelle stehen im [`Szenarienkatalog`](SCENARIOS.md#vla-fahrstack-selbstauskunft-pruefen).

### Schwierigkeit und Pruefmodus

Jedes Szenario kann einen Block `difficulty` tragen. Fehlt er, gilt das bisherige
Verhalten (Stufe `A`, `strict`, `exact`); alle mitgelieferten Szenarien laufen so.

```json
"difficulty": {"level": "C", "guardrails": "advisory", "perception_model": "exact"}
```

- **`level`:** Stufe `A` bis `D` fuer Szenariosets und Lernpfad. Sie aendert das
  Verhalten nicht selbst, sondern ordnet das Szenario ein.
- **`guardrails`:** wie viel der Ausfuehrer dem Agenten abnimmt.

  | Modus | Fehlende Werkzeugevidenz, Lagebedenken | Vorausschauender Abbruch im Manoever |
  |---|---|---|
  | `strict` | Ablehnung (`SAFETY_REJECTED`) | ja |
  | `advisory` | angenommen, Befund als Warnung | ja |
  | `off` | angenommen, Befund als Warnung | nein, die Folgen traegt die Entscheidung |

  Verkehrsregeln (`RULE_REJECTED`), Verfuegbarkeit (`NOT_AVAILABLE`) und die Geometrie
  des Ausfuehrers (etwa `ROAD_FULLY_BLOCKED`, `NO_SHOULDER_SPACE`) gelten in jedem Modus.
  Zur Warnung werden nur Lagebeurteilungen, deren Folgen die Simulation abbildet
  (`WAIVABLE_SAFETY_CHECKS` in [`rules.py`](rules.py)). Warnungen stehen im Trace am
  angenommenen Entscheidungsversuch (`warnings`) und im Ergebnis (`safety_warnings`).

  In `advisory` und `off` gilt ausserdem:
  - **Ein Aufprall beendet die Episode nicht.** Der Agent muss ihn erkennen
    (`get_vehicle_status`) und abwickeln (`SECURE_SCENE`, `REPORT_INCIDENT`). Leichte
    Beruehrungen loesen nichts aus, schwere starten sofort eine Sitzung
    `IMPACT_DETECTED`. Wer die Stelle verlaesst, begeht Unfallflucht.
  - **Kontrollpunkt nach jedem Manoever:** eine Sitzung `MANEUVER_FINISHED`, in der der
    Agent nachsieht und mit `RESUME` weiterfaehrt. Steht das Fahrzeug in einem Manoever
    laenger als 3 s still, bricht der Ausfuehrer ab und ruft ebenfalls den Agenten.
  - **Notbremse** auf der Wahrnehmung: Sie bremst fuer erkannte Objekte im Fahrweg, sieht
    aber nichts hinter Verdeckungen.
  - **Ueberfahren ungeeigneter Objekte** beschaedigt den Unterboden; die Pruefungen fuer
    Ladegut werden deshalb ebenfalls zu Warnungen.

  Jede Sitzung nennt ihren Ausloeser unter `trigger`. Einzelheiten, Befehle und Kosten
  stehen in [COMMANDS.md](COMMANDS.md#unfallabwicklung-und-kontrollpunkte-nur-pruefmodus-advisory-und-off).
  In `strict` beendet eine Kollision die Episode wie bisher.
- **`perception_model`:** `exact` (Lagewerkzeuge mit fertigen Urteilen auf exakter
  Geometrie) oder `tracked` (Messungen mit Unsicherheit, siehe unten).

Der Agent sieht die Einstellung in seiner Beobachtung unter `difficulty`.
Dass Stufe A unveraendert bleibt, sichert ein eingefrorener Regressionsstand
(`tests/data/regression_level_a.json`); Abweichungen zeigt
`python3 -m autonomy_recovery_sim.scripts.regression_baseline`.

### Wahrnehmungsmodell `tracked`

Ein echter Fahrstack liefert keine Urteile wie „Gegenverkehr: ja“, sondern eine
Objektliste mit Messunsicherheit. Im Modell `tracked` ([`tracking.py`](tracking.py))
entfallen deshalb die sieben Lagewerkzeuge mit fertigen Urteilen (`get_blocker`,
`get_center_marking`, `check_oncoming_traffic`, `check_rear_traffic`,
`check_vulnerable_road_users`, `get_lateral_clearance`, `get_visibility`). An ihre
Stelle treten:

- **`get_tracked_objects`:** Objektliste nach dem Vorbild von Autoware `TrackedObjects`
  im Fahrzeugsystem `base_link` (x vorn, y links, Ursprung Fahrzeugmitte):
  Existenzwahrscheinlichkeit, Klassenverteilung, Position, Geschwindigkeit und Gierwinkel
  mit Standardabweichung, Form (`FULL`, `PARTIAL` bei Teilverdeckung, `ASSUMED` bei reinen
  Radartracks), Spurzuordnung mit Wahrscheinlichkeit und Track-Zustand (`TENTATIVE`,
  `CONFIRMED`, `COASTING`). Track-IDs sind undurchsichtig.
- **`get_sensor_coverage`:** Sensorzustand, verlaessliche Reichweite und verdeckte
  Abschnitte je Spur samt verdeckendem Track. Damit weiss der Agent, *dass* er etwas
  nicht sieht.
- **`get_map_context`:** Spuren mit Richtung, Breite und Mittellinie in `base_link`,
  Markierung, Seitenstreifen und Haltelinien. Kartenwissen, das veraltet sein kann.

Manoever verlangen im Pruefmodus `strict` diese drei Werkzeuge als Evidenz. Material,
Szenentext und Signalzustand gibt es nur noch ueber den Fahrstack (`get_vla_output`,
`get_camera_caption`); hat das Szenario keinen Block `vla`, kommt ein fehlerfreier Mock
hinzu. Dessen Ausgabe enthaelt im Modell `tracked` weder `meta_action` noch `confidence`,
weil Alpamayo 1.5 beides nicht liefert. Die Regel-Engine
(`ESCALATE_TO_RULE_ENGINE`) und die Sicherheitspruefung arbeiten weiter auf der exakten Lage.

Das Rauschen steuert der Unterblock `perception.noise` und ist ueber den Seed
reproduzierbar. Die Standardwerte entsprechen leichtem Rauschen (Stufe B):

```json
"perception": {
  "noise": {
    "position_std_m": 0.10,
    "position_std_per_10m_m": 0.05,
    "velocity_std_mps": 0.15,
    "yaw_std_rad": 0.03,
    "class_confusion": 0.10,
    "dropout_probability": 0.0,
    "false_positive_rate_hz": 0.0,
    "radar_through_occluders": true
  }
}
```

`class_confusion` vertauscht die Klasse eines Objekts dauerhaft mit einer aehnlichen
(Pkw und Transporter, Bake und Muelltonne). `radar_through_occluders` laesst verdeckte
Fahrzeuge gelegentlich als schwachen Radartrack ohne Bewegungszustand erscheinen.

Die Hilfsbibliothek [`recovery_helpers.py`](recovery_helpers.py) rechnet die alten Urteile
aus diesen Messungen nach (`blocker_ahead`, `oncoming_conflict`, `rear_conflict`,
`vulnerable_road_users`, `lane_visibility`, `lateral_clearance`, `to_lane_frame`). Sie
nutzt nur Werkzeugausgaben, und ihre Antworten sind so unsicher wie die Messungen.

Jedes Szenario laesst sich im Modell `tracked` ausfuehren:

```bash
python3 -m autonomy_recovery_sim batch --perception tracked --agent mein_agent:decide
```

Die Referenzloesungen der Szenarien gelten fuer `exact`. Im Modell `tracked` kann eine
vorsichtigere Antwort richtig sein: In `hannover_verdeckung_auftauchen` etwa meldet die
Sichtabdeckung die Gegenspur hinter dem breiten Blocker ehrlich als verdeckt.

### Ausloeser: Akteure reagieren auf das Ego

Ein Akteur kann eine Liste `triggers` tragen. Jeder Ausloeser feuert einmal, sobald alle
Bedingungen erfuellt sind, und aendert dann das Verhalten des Akteurs
([`triggers.py`](triggers.py)):

```json
"triggers": [{
  "when": {"ego_lateral_offset_m": {"gte": 0.8}},
  "then": {"start_motion": {"target_speed_mps": 3.0}},
  "hint": {"tool": "get_blocker", "why": "Der Fahrer sitzt am Steuer; er kann jederzeit anfahren."}
}]
```

- **Bedingungen:** `time_s`, `ego_s_m`, `ego_lateral_offset_m` (Versatz zur eigenen
  Spurmitte, links positiv), `since_first_session_s` (jeweils `{"gte": Zahl}`) und
  `ego_phase` (`"OVERTAKE"` oder `"OVERTAKE.PULLED_OUT"`).
- **Folgen:** `start_motion` (`target_speed_mps`), `stop` und `cross` (`exit_d_m`,
  `speed_mps`, nur Fuss-, Radverkehr und Tiere).
- **Fairnessregeln, vom Lader geprueft:** Ausloeser aendern nur vorhandene Akteure (keine
  Phantome, nichts erscheint aus dem Nichts); jeder nennt unter `hint` ein Werkzeug, das
  vorher einen Hinweis liefert, und eine Begruendung; das Tempo bleibt in den Grenzen der Art.

Die bisherigen Felder `motion_start_time_s` und `target_speed_mps` funktionieren weiter. Wie
Ausloeser in den Szenariofamilien F1 bis F6 eingesetzt werden, zeigt der
[Szenarienkatalog](SCENARIOS.md#szenariofamilien-f1-bis-f6-lagen-die-sich-ändern).

Fuer Familien mit Wende gibt es das Routenfeld `turn_required`: Dann scheitert
`REPLAN_ROUTE` mit `TURN_REQUIRED`, weil die Alternativroute hinter dem Fahrzeug beginnt;
nur `TURN_AROUND` fuehrt dorthin. Eine Absperrung (`kind: "barrier"`) darf nie umfahren werden
(`RULE_REJECTED: ROAD_CLOSED`).

## Modell und bewusste Grenzen

- kinematisches Fahrradmodell statt Reifen- oder Fahrwerksmodell
- gerade und gekruemmte Strassen, aber noch keine Kreuzungslogik
- kollisionsfaehige, orientierte Fahrzeugrechtecke in kontinuierlichem XY
- Spurfolger fuer Ego und Gegenverkehr, aber noch kein vollstaendiges IDM/MOBIL
- Manoeverzustaende fuer Fahren, Warten, links Umfahren, Abbruch und
  Minimum-Risk-Abschluss nach dem Commit Point
- deterministische 2D-Sichtlinien statt physikalischer Kamera-, Radar- oder
  Lidar-Simulation
- Verdeckung, Reichweite, Sichtfeld, partielle Sichtbarkeit und kurzlebige
  Tracks, aber noch kein Sensorrauschen und keine Fehlklassifikationen
- die Referenzentscheidung ist eine Versuchspolitik, keine Rechtsauskunft
- der VLA-Fahrstack ist ein regelbasierter Mock: keine Kamerabilder, kein Modell,
  Recovery-Befehle werden noch direkt ausgefuehrt statt als Anweisung an den Stack

## Naechste Ausbaustufen

1. Einen Durchlauf aus einem frischen Studierenden-Checkout mit dem Tutorial-Track durchfuehren
   und die Zeitangaben der Lektionen anpassen.
2. Die Richtwerte von L5 mit einem echten Modell messen (bisher nur Spielmodell).
3. Echte Begruendungstexte eines VLA-Fahrstacks abspielen statt des regelbasierten Mocks.
4. Weitere Szenariofamilien, etwa an Kreuzungen; die Engine kennt bisher nur eine Route.
5. Weitere OSM-Strassen ueber einen reproduzierbaren Importer hinzufuegen.

