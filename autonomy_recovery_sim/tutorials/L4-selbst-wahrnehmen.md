# L4 · Selbst wahrnehmen

**Teamzeit:** 120 Minuten · **Phase:** Sprint 2 · **Stufe:** B (Objektliste mit leichtem
Rauschen, strenge Prüfung) · **Schlüssel:** nein

Bisher lieferten die Werkzeuge fertige Urteile: „Gegenverkehr: ja“, „Seitenabstand reicht“.
Ein echter Fahrstack tut das nicht. Er liefert eine **Objektliste mit Messunsicherheit**, und
alles Weitere rechnet ihr selbst. Ab jetzt läuft euer Agent im Wahrnehmungsmodell `tracked`.

## Ziel

- Ihr lest Objektliste, Sichtabdeckung und Karte und berechnet daraus Hindernis,
  Gegenverkehr, Sicht und Seitenabstand.
- Ihr rechnet mit Unsicherheit: Standardabweichung, Existenzwahrscheinlichkeit,
  Spurzuordnung.
- Ihr holt Bedeutung (was steht da, sitzt jemand am Steuer?) aus der Kamerabeschreibung.

## Startstand

Euer Stand aus L3 oder `l4_start.py` (wird später freigegeben). Startet ihn einmal im neuen Modell:

```bash
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/released_sprint2.txt --perception tracked --agent mein_agent:decide
```

**0 von 20**, jeder Fall mit Agentenfehler. Die sieben Lagewerkzeuge gibt es nicht mehr.

## Vorhersage

Wenn ihr dieselbe Logik auf Messungen umstellt: Werdet ihr schlechter, weil die Daten
verrauscht sind, oder gleich gut, weil das Rauschen klein ist?

## Bauen

1. **Die drei neuen Werkzeuge ansehen.** `get_tracked_objects` (Objekte im Fahrzeugsystem:
   x vorn, y links), `get_sensor_coverage` (verdeckte Abschnitte je Spur) und
   `get_map_context` (Spuren, Mittellinie, Markierung). Die Felder erklärt die
   [Simulator-Dokumentation](../README.md#wahrnehmungsmodell-tracked). Sie sind jetzt auch die
   Pflichtevidenz für Manöver.

2. **Urteile selbst rechnen.** Die Hilfsbibliothek
   [`recovery_helpers`](../recovery_helpers.py) rechnet die alten Urteile nach. Nutzt sie, aber
   lest, was sie annimmt:

   ```python
   from autonomy_recovery_sim import recovery_helpers as helpers

   objects = session.call_tool("get_tracked_objects")
   coverage = session.call_tool("get_sensor_coverage")
   lanes = session.call_tool("get_map_context")
   blocker = helpers.blocker_ahead(objects, lanes)
   oncoming = helpers.oncoming_conflict(objects, lanes, horizon_s=8.0)
   sight = helpers.lane_visibility(coverage, "ONCOMING_LANE", required_m=60.0)
   ```

   Ersetzt in eurem Baum jedes alte Werkzeug durch die passende Rechnung. Die Klasse kommt
   aus `helpers.best_label(blocker)`: `TRAFFIC_CONE`, `TRASH_BIN` und `DEBRIS` sind kleine
   Hindernisse.

3. **Bedeutung aus der Kamera.** Die Objektliste kennt kein Material und keinen Szenentext.
   `get_camera_caption` mit `front_wide` beschreibt, was die Kamera sieht, samt Szenentext.
   Sucht dort nach Hinweisen, dass das Hindernis von selbst weiterfährt (Fahrer am Steuer,
   Bote, Stau), und wartet dann.

4. **Familien ansehen.** Fahrt die sechs sichtbaren Varianten der Szenariofamilien:

   ```bash
   python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/familien_sichtbar.txt --agent mein_agent:decide
   ```

## Messen

| Menge | Startstand | Richtwert nach L4 |
|---|---|---|
| `released_sprint2.txt --perception tracked` | 0 von 20 | 19 von 20 |
| `familien_sichtbar.txt` | 0 von 6 | 3 von 6 |

Bei leichtem Rauschen gelingt fast alles wie in Stufe A. Die Familien zeigen, was noch fehlt:
Lagen, die sich ändern, und Ursachen, die man nicht sieht. Das ist L7.

## Was typischerweise schiefgeht

- **Falsches Koordinatensystem.** `position_m` ist relativ zur Fahrzeugmitte. Längsabstände
  entlang der Spur liefert `helpers.to_lane_frame`.
- **Schwache Tracks ignoriert.** Ein Track mit `existence_probability` 0,4 kann ein echtes
  Fahrzeug sein, das gerade verdeckt ist. Für Gegenverkehr zählen auch schwache Tracks.
- **Werkzeugbudget.** Kamerafragen kosten Aufrufe. Fragt die Kamera nur, wenn ein Hindernis
  da ist.

## Erweitere selbst

- Schreibt `oncoming_conflict` selbst und vergleicht mit der Hilfsbibliothek. Wie ändert sich
  das Ergebnis mit `sigma` 1, 2 und 3?
- Wertet `track.status` aus: Ein `COASTING`-Track ist alt. Wie lange vertraut ihr ihm?
- Fahrt dieselbe Menge mit stärkerem Rauschen (eigene Kopie eines Szenarios mit
  `perception.noise`). Wo bricht euer Agent ein?

## Team-Checkpoint

- Ihr könnt an einem Objekt der Liste erklären, was jedes Feld bedeutet.
- Ihr könnt sagen, welche Annahme `recovery_helpers` trifft, die ihr selbst anders treffen würdet.

Weiter mit [L5 · LLM-Agent](L5-llm-agent.md).
