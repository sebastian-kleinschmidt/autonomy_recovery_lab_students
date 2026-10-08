# Stufe 2: Euer erster Agent, ohne Sprachmodell

**Teamzeit:** 90 Minuten Pflichtkern · **Phase:** Sprint 1 · **Modus:** Paararbeit ·
**Voraussetzung:** Stufen 0 und 1, etwas Python im Team · **Schlüssel:** nein

Ihr schreibt jetzt ein Programm, das die Rolle des Autonomy Recovery Agents übernimmt: Werkzeuge
aufrufen, Ergebnisse lesen, einen Befehl wählen. Noch ohne Sprachmodell. Das hat einen
Grund: Ihr lernt an einem Entscheidungsbaum, was **Werkzeuge, Budgets und Verträge**
leisten, und ihr findet heraus, **wo Regeln an ihre Grenzen stoßen**. Das ist die
Motivation für Stufe 4, nicht ihre Vorwegnahme.

## Teammodus und Ergebnis

Arbeitet zunächst in zwei Paaren. Ein Paar implementiert und misst die Regelbaseline,
das andere Paar prüft Werkzeugfelder, Safety-Vertrag und Reproduktionsbefehl. Danach
wechselt ihr: Das zweite Paar erklärt den Code, das erste Paar liest einen Fehltrace und
prüft die Messung. Abgegeben wird **eine** gemeinsame Regelbaseline, nicht vier Agenten.

Der Pflichtkern endet nach Schritt 5 mit einem reproduzierbaren Ausgangslauf. Schritt 6
ist Vertiefung innerhalb des Sprints und wird erst nach dem Forschungscheckpoint gezielt
ausgewählt.

## Das Grundgerüst

Eure Datei ist [`student_agent.py`](../../student_agent.py). Ein Agent ist eine Funktion,
die eine `AgentSession` bekommt und einen Befehl einreicht:

```python
from autonomy_recovery_sim.agent_session import AgentSession

def decide(session: AgentSession):
    blocker = session.call_tool("get_blocker")           # Werkzeug aufrufen
    return session.submit_decision({                      # genau einen Befehl einreichen
        "command": "WAIT",
        "parameters": {"duration_s": 5.0},
        "reason": f"Blockade erkannt: {blocker['detected']}",
    })
```

Drei Dinge sind neu und wichtig:

- **`session.call_tool(name)`** liefert ein Wörterbuch. Jeder Aufruf kostet Budget (14 je
  Sitzung).
- **`session.submit_decision(payload)`** prüft Schema, Evidenz und Regeln. Bei einer
  Ablehnung wirft es eine Ausnahme (siehe Schritt 4).
- **Der Agent wird nicht einmal, sondern bei Bedarf mehrfach aufgerufen.** Nach jedem
  Befehl, der das Problem nicht löst, beginnt bei anhaltendem Stillstand eine neue
  Sitzung.

## Schritt 1: Messen, wo ihr steht

```bash
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/demo.txt \
  --agent autonomy_recovery_sim.student_agent:decide
```

Der Starter wartet immer. Erwartet: **2 von 3 Szenarien bestanden, Note C.** Öffnet
`artifacts/autonomy-recovery-sim/batch/batch-report.html` und findet das Szenario, das er verfehlt.
Warum besteht ein „nur wartender“ Agent zwei Szenarien?

Auf der fuer Sprint 1 freigegebenen kumulativen Menge bekommt der Starter 6 von 8
Faellen. Das ist euer Nullpunkt:

```bash
python3 -m autonomy_recovery_sim batch \
  autonomy_recovery_sim/scenario_sets/released_sprint1.txt \
  --agent autonomy_recovery_sim.student_agent:decide
```

## Schritt 2: Sehen, was die Werkzeuge liefern

Legt in `student_agent.py` eine Hilfsausgabe an und fahrt ein Szenario:

```python
def decide(session: AgentSession):
    for name in ("get_blocker", "get_center_marking", "check_oncoming_traffic"):
        print(name, session.call_tool(name))
    ...
```

```bash
python3 -m autonomy_recovery_sim autonomy_recovery_sim/scenarios/hannover_gegenverkehr.json \
  --agent autonomy_recovery_sim.student_agent:decide
```

Vergleicht die Ausgabe mit `hannover_frei` und `hannover_durchgezogen`. **Vorhersage
zuerst:** In welchem Feld unterscheiden sich die drei Szenarien?

## Schritt 3: Ein Entscheidungsbaum

Der folgende Agent läuft, ist aber bewusst unvollständig. Er prüft nur zwei der sieben
Belege, ruft aber alle ab (ein Manöver verlangt alle sieben):

<!-- lauffaehig -->
```python
from autonomy_recovery_sim.agent_session import AgentSession

EVIDENCE = (
    "get_blocker", "get_center_marking", "check_oncoming_traffic", "check_rear_traffic",
    "check_vulnerable_road_users", "get_lateral_clearance", "get_visibility",
)

def decide(session: AgentSession):
    results = {name: session.call_tool(name) for name in EVIDENCE}

    if not results["get_blocker"]["detected"]:
        return session.submit_decision({
            "command": "WAIT", "parameters": {"duration_s": 10},
            "reason": "Keine dauerhafte Blockade erkannt",
        })
    if results["check_oncoming_traffic"]["conflict"]:
        return session.submit_decision({
            "command": "WAIT", "parameters": {"duration_s": 10},
            "reason": "Gegenverkehr im Horizont",
        })
    return session.submit_decision({
        "command": "NUDGE_AROUND_OBSTACLE",
        "parameters": {"side": "LEFT", "max_longitudinal_distance_m": 35},
        "reason": "Blocker steht, kein Gegenverkehr",
    })
```

Fahrt die drei Demo-Szenarien und danach die Sprint-1-Freigabe:

```bash
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/demo.txt --agent autonomy_recovery_sim.student_agent:decide
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/released_sprint1.txt --agent autonomy_recovery_sim.student_agent:decide
```

**Erwartet:** 2 von 3 auf `demo.txt` und nur **3 von 8** auf `released_sprint1.txt`, also
*schlechter* als der Starter, der nur wartet. Handeln mit halber Evidenz ist oft
schlechter als Warten. Kollisionen gibt es trotzdem keine, weil Regelprüfung und
Sicherheitsmonitor nicht vom Agenten abhängen. Erklärt euch das, bevor ihr
weitermacht.

**Aufgabe:** Findet mindestens **drei Szenarien, in denen dieser Agent falsch
handelt**, und schreibt zu jedem auf, *welche Information* er hätte beachten müssen.
Hilfen:

| Symptom im Bericht | Wo ihr sucht |
|---|---|
| `agent_error` gefüllt | Die Ablehnung im `agent_trace` (Feld `error`) |
| Ausgang `aborted` | Ereignis `maneuver_aborted`, Feld `condition` |
| Befehl richtig, Ergebnis falsch | Kosten und Budget im Szenario (`budget_eur`) |
| Befehl falsch | `expected_reason` in `result.json` erklärt den Fall |

`result.json` enthält alles: `commands`, `agent_trace` (jede Werkzeugantwort),
`events` und `costs`. Lernt, ihn zu lesen. Er ist eure wichtigste Fehlerquelle.

## Schritt 4: Ablehnungen behandeln

`submit_decision` wirft `CommandError`, wenn ein Befehl abgelehnt wird. Ihr habt pro
Sitzung **drei Versuche**. Ein guter Agent fängt die Ablehnung ab und korrigiert:

```python
from autonomy_recovery_sim.commands import CommandError

try:
    return session.submit_decision(nudge_left)
except CommandError as error:
    if error.code == "RULE_REJECTED":
        return session.submit_decision(wait)   # Regel akzeptieren, nicht umgehen
    raise
```

**Frage:** Was passiert, wenn ihr die Ausnahme *nicht* abfangt? (Probiert es an
`hannover_durchgezogen`. Lest `agent_error` und das gewählte Ersatzverhalten.)

## Schritt 5: Verlauf und Wartebudget

Ein Agent, der nur wartet, wartet ewig. Nutzt `get_recovery_history`:

```python
history = session.call_tool("get_recovery_history")["attempts"]
waited_s = sum(a["elapsed_s"] for a in history if a["command"] == "WAIT")
```

Legt eine Regel fest, ab wann Warten aufhört, und was dann folgt (`SAFE_STOP`, eine
Leitstellenanfrage, eine Umleitung). **Abwägung:** Jede Sekunde Stillstand kostet; ein
Anruf kostet einmalig 25 Euro. Ab welcher Wartezeit lohnt sich der Anruf? Rechnet es
aus, bevor ihr es festlegt.

## Schritt 6: Erweiterungen — Vertiefung nach dem Forschungscheckpoint

Öffnet den Katalog in [COMMANDS.md](../../COMMANDS.md) und erweitert euren Agenten um
Situationen, die der Baum noch nicht kennt:

| Erweiterung | Nötige Information | Befehl |
|---|---|---|
| Route ist blockiert | `get_route_state` | `REPLAN_ROUTE` |
| Kleines Objekt am Rand | `get_blocker` (`kind`) | `AVOID_TEMPORARY_OBSTRUCTION` |
| Sicher klassifiziertes weiches Niedrigobjekt | `get_blocker` (`obstacle_profile`) | `CROSS_LOW_RISK_OBJECT` |
| Freie Nachbarspur | `get_mission_context` (`adjacent_lanes`) | `CHANGE_LANE` |
| Fahrgäste an Bord, alles verriegelt | `get_mission_context` | `PULL_OVER`, `DROP_PASSENGER` |
| Leitstelle offline | `get_mission_context` | `SAFE_STOP` |
| Regulärer Halt (Ampel, Schranke, Stau, Fahrgastwechsel) | `get_traffic_control`, `get_mission_context` | `WAIT`, kein Eingreifen |

Die letzte Zeile ist **Teil A der Laboraufgabe**: die Einordnung „steckt es wirklich fest?“ ohne
Sprachmodell (siehe [ASSIGNMENT](../../ASSIGNMENT.md)). In Sprint 3 prueft ihr sie an
[`erkennen.txt`](../../scenario_sets/erkennen.txt) und achtet auf die Kennzahlen **Fehlalarme** (eingegriffen,
obwohl Warten reicht) und **verpasste Eingriffe** (gewartet, obwohl es nötig war). Der wartende Starter hat
keinen Fehlalarm, verpasst aber beide echten Fälle.

Schreibt zu jeder Erweiterung **vorher** auf, in welchem Szenario sie helfen soll, und
prüft es danach. Arbeitet nur mit den bis dahin freigegebenen Szenarien; die
Beschreibung des erwarteten Verhaltens steht dort in `expected_reason`.

## Wo Regeln an ihre Grenzen stoßen

Sammelt beim Arbeiten Beobachtungen zu diesen Fragen. Sie führen direkt zu Stufe 4:

1. Wie viele `if`-Zweige habt ihr, und wie viele Szenarien deckt jeder ab?
2. Welche Situation habt ihr **nicht** vorhergesehen? Was passiert damit?
3. Welche Entscheidung war am schwersten in Regeln zu fassen (Abwägungen, Kosten,
   „unklare Lage“)?
4. Was passiert bei einer Variante eines Szenarios (verschobene Positionen)?

## Gemeinsame Abgabe

- lauffähiger Stand von `student_agent.py`,
- unveränderter Rohbericht des Ausgangslaufs,
- ein kategorisierter Fehler mit Beleg aus Trace oder Werkzeugdaten,
- der exakte Reproduktionsbefehl.

## Team-Checkpoint

- Der gemeinsame Agent läuft ohne Ausnahme auf `demo.txt` und `released_sprint1.txt`; beide
  Ausgangswerte sind vor weiteren Änderungen festgehalten.
- Jede Person kann zu mindestens einer Fehlentscheidung sagen, welche Werkzeuginformation gefehlt hat.
- Das Team fängt Ablehnungen ab; jede Person erklärt den Unterschied zwischen `RULE_REJECTED` und
  `INVALID_ARGUMENT`.
- Der Agent enthält **keine Szenario-IDs**.

Weiter mit dem verpflichtenden [Forschungscheckpoint](../02a-forschungsplan.md), danach
mit [Stufe 3: Agentenloop](03-agentenloop.md).
