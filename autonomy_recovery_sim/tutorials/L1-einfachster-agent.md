# L1 · Der einfachste Agent

**Teamzeit:** 45 Minuten · **Phase:** Sprint 1 · **Stufe:** A (exakte Lage, strenge Prüfung) ·
**Schlüssel:** nein

Bevor euer Agent klug wird, muss er laufen und messbar sein. In dieser Lektion baut ihr den
kleinstmöglichen Agenten, startet ihn gegen echte Szenarien und lest den Bericht. Alles,
was später kommt, misst ihr genauso.

## Ziel

- Ihr kennt die Schnittstelle: eine Funktion `decide(session)`, die genau einen Befehl
  zurückgibt.
- Ihr könnt einen Batchlauf starten und im Bericht erklären, warum ein Fall bestanden ist.
- Ihr habt einen gemessenen Nullpunkt für den ganzen Track.

## Einrichten

Euer Agent lebt im ganzen Track in **einer** Datei im Wurzelverzeichnis des Repositorys.
Legt sie aus dem Startstand an:

```bash
cp autonomy_recovery_sim/tutorials/track/l1_start.py mein_agent.py
```

Der Startstand ist sechs Zeilen lang:

```python
def decide(session: AgentSession) -> dict[str, object]:
    return {"command": "WAIT", "parameters": {"duration_s": 5.0}, "reason": "Startstand: immer warten"}
```

Ein Befehl ist ein Wörterbuch mit `command`, `parameters` und `reason`. Welche Befehle es
gibt, steht im [Spickzettel](CHEATSHEET.md#die-befehle).

## Vorhersage

Schreibt ins [Lab-Journal](vorlagen/lab-journal.md), bevor ihr etwas startet: Wie viele der acht
Szenarien aus Sprint 1 besteht ein Agent, der **immer wartet**? Warum?

## Bauen

1. **Messen.**

   ```bash
   python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/released_sprint1.txt --agent mein_agent:decide
   ```

   Öffnet `artifacts/autonomy-recovery-sim/batch/batch-report.html`. Sucht ein bestandenes und
   ein nicht bestandenes Szenario und erklärt beide.

2. **Den Kontext lesen.** `session.context` enthält, was der Agent weiß, ohne ein Werkzeug zu
   fragen: Zeit, eigene Lage (`ego.stopped_for_s`), Mission, Budgets und wie viele Befehle
   schon gegeben wurden (`commands_used`). Gebt ihn einmal aus:

   ```python
   import json
   def decide(session):
       print(json.dumps(session.context["ego"], indent=2))
       ...
   ```

3. **Länger warten, wenn Warten nicht reicht.** Der Agent wird erneut gerufen, solange das
   Fahrzeug steht. Lasst ihn beim ersten Mal 5 s, beim zweiten 10 s und danach 20 s warten,
   und schreibt in `reason`, wie lange das Fahrzeug schon steht. Eine gute Begründung ist
   Pflicht: Sie steht im Bericht und hilft euch beim Lesen.

## Messen

| Menge | Startstand | Richtwert nach L1 |
|---|---|---|
| `released_sprint1.txt` | 6 von 8 | 6 von 8 |
| `released_sprint2.txt` | 7 von 20 | 7 von 20 |

Die Zahl ändert sich in L1 kaum, und das ist richtig: Warten bleibt Warten. Wichtig ist,
dass ihr jeden Wert reproduzieren und erklären könnt.

## Was typischerweise schiefgeht

- **Der Agent stürzt ab.** Ein Tippfehler im Befehl führt zu `INVALID_ARGUMENT`; der Simulator
  weicht fail-safe auf `WAIT` aus und vermerkt `agent_error`. Sucht den Fehler im Bericht,
  nicht im Terminal.
- **Falscher Modulpfad.** `--agent mein_agent:decide` funktioniert nur aus dem
  Wurzelverzeichnis.
- **Kosten übersehen.** Auch Warten kostet: 0,50 EUR je Sekunde Standzeit.

## Erweitere selbst

- Gebt in `reason` aus, wie viele Befehle das Budget (`max_commands`) noch zulässt.
- Wählt die Wartezeit nach `ego.stopped_for_s` statt nach `commands_used`. Was ändert sich?
- Vergleicht einen Agenten, der immer `SAFE_STOP` wählt. Warum ist er schlechter, obwohl er
  „sicher“ ist?

## Team-Checkpoint

- Jede Person kann einen Batchlauf starten und einen Fall im Bericht erklären.
- Der Nullpunkt (6 von 8) steht mit Befehl und Commit im Lab-Journal.

Weiter mit [L2 · Regelagent mit Werkzeugen](L2-regelagent.md).
