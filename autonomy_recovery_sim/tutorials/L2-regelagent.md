# L2 · Regelagent mit Werkzeugen

**Teamzeit:** 90 Minuten · **Phase:** Sprint 1 · **Stufe:** A · **Schlüssel:** nein

Jetzt untersucht euer Agent die Lage, bevor er entscheidet. Er ruft Werkzeuge auf, liest ihre
Ergebnisse und wählt mit einem Entscheidungsbaum. Noch ohne Sprachmodell: Ihr lernt zuerst,
was Werkzeuge, Budgets und die Prüfung leisten.

## Ziel

- Ihr ruft Werkzeuge mit `session.call_tool(name)` auf und lest ihre Felder.
- Ihr versteht die **Evidenzpflicht**: Ein Manöver über die Fahrbahn verlangt alle sieben
  Lagewerkzeuge.
- Ihr erlebt, dass Handeln mit halber Evidenz schlechter ist als Warten.

## Startstand

Euer Stand aus L1 oder [`l2_start.py`](track/l2_start.py) (die Lösung von L1):

```bash
cp autonomy_recovery_sim/tutorials/track/l2_start.py mein_agent.py   # nur zum Neuansetzen
```

## Vorhersage

Ein Agent prüft nur, ob ein Hindernis da ist und ob Gegenverkehr kommt, und fährt sonst
links vorbei. Besteht er mehr oder weniger Fälle als der wartende Agent aus L1?

## Bauen

1. **Werkzeuge ansehen.** Fahrt ein einzelnes Szenario und gebt drei Werkzeuge aus:

   ```python
   for name in ("get_blocker", "get_center_marking", "check_oncoming_traffic"):
       print(name, session.call_tool(name))
   ```

   ```bash
   python3 -m autonomy_recovery_sim autonomy_recovery_sim/scenarios/hannover_gegenverkehr.json --agent mein_agent:decide
   ```

   Vergleicht mit `hannover_frei` und `hannover_durchgezogen`. In welchem Feld unterscheiden
   sie sich?

2. **Alle sieben Belege holen.** `get_blocker`, `get_center_marking`, `check_oncoming_traffic`,
   `check_rear_traffic`, `check_vulnerable_road_users`, `get_lateral_clearance`,
   `get_visibility`. Ohne sie lehnt die Prüfung jedes Manöver mit `SAFETY_REJECTED` ab.

3. **Ein Entscheidungsbaum.** Prüft in dieser Reihenfolge:
   1. Rote Ampel oder geschlossene Schranke (`get_traffic_control`): regulärer Halt, warten.
   2. Route gesperrt mit Alternative (`get_route_state`): `REPLAN_ROUTE`.
   3. Kein Hindernis: warten.
   4. Durchgezogene Linie, Gegenverkehr, Verkehr von hinten, Fuß- oder Radverkehr, zu wenig
      Seitenabstand, keine Sicht: warten, mit dem Grund in `reason`.
   5. Sonst: `NUDGE_AROUND_OBSTACLE` links.

4. **Messen und einen Fehlschlag erklären.** Nehmt einen Fall, den der Agent verfehlt, und
   findet in `result.json` (`expected_reason`, `agent_trace`) heraus, welche Information
   gefehlt hat.

## Messen

```bash
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/released_sprint2.txt --agent mein_agent:decide
```

| Menge | Startstand | Richtwert nach L2 |
|---|---|---|
| `released_sprint1.txt` | 6 von 8 | 8 von 8 |
| `released_sprint2.txt` | 7 von 20 | etwa 10 von 20 |

Kollisionen gibt es keine, auch wenn euer Baum Lücken hat: In Stufe A bricht der Ausführer
riskante Manöver selbst ab. Das ändert sich ab L7.

## Was typischerweise schiefgeht

- **`SAFETY_REJECTED: ... ohne erforderliche Werkzeugevidenz`.** Ein Werkzeug fehlt. Holt
  immer alle sieben, bevor ihr ein Manöver einreicht.
- **Halbe Evidenz.** Wer nur auf Gegenverkehr prüft, fährt in Lagen mit durchgezogener
  Linie oder Personen auf der Fahrbahn los und wird abgelehnt oder abgebrochen.
- **Werkzeugbudget.** 14 Aufrufe je Sitzung. Wer in Schleifen fragt, bekommt
  `Werkzeugbudget ... ueberschritten`.

## Erweitere selbst

- Bei einem kleinen Hindernis (`kind`: `beacon`, `trash_bin`, `debris`) reicht oft
  `AVOID_TEMPORARY_OBSTRUCTION` mit wenig Versatz. Wann ist das besser als vorbeifahren?
- Gibt es eine freie Nachbarspur (`get_mission_context`, `adjacent_lanes`), ist
  `CHANGE_LANE` schonender als die Gegenspur.
- Sortiert die Prüfungen nach Kosten: Welche Werkzeuge könnt ihr in Fällen ohne Hindernis
  einsparen?

## Team-Checkpoint

- Ihr könnt für jede Bedingung im Baum ein Szenario nennen, in dem sie greift.
- Ihr habt einen Fehlschlag mit `result.json` erklärt.

Weiter mit [L3 · Gedächtnis und mehrere Schritte](L3-gedaechtnis.md).
