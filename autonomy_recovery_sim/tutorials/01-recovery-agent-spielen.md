# Stufe 1: Ihr seid der Autonomy Recovery Agent

**Teamzeit:** 75 Minuten Pflichtkern · **Phase:** Bootcamp · **Modus:** gemeinsam ·
**Voraussetzung:** Stufe 0 · **Schlüssel:** nein · **Code:** nein

In dieser Stufe schreibt ihr keine Zeile Code. Ihr übernehmt selbst die Rolle des
Agenten: dieselbe Aufgabe, dieselben Werkzeuge, dieselben Ablehnungen wie euer späteres
Programm. Wer die Aufgabe einmal von Hand gelöst hat, weiß, welche Information zählt,
wo es teuer wird und was man einem Programm beibringen muss.

## Teammodus und Pflichtumfang

Verteilt vier Rollen: Eine Person bedient die Konsole, eine prüft Safety und Regeln,
eine liest Werkzeugdaten und Trace, eine führt das gemeinsame Journal. Wechselt nach
jedem Szenario. So erlebt nicht nur eine Person die Oberfläche.

**Pflicht** sind Aufgaben A bis D, aus Aufgabe E die beiden Wege mit `DROP_PASSENGER`,
aus Aufgabe F ein Fall nach Wahl und aus Aufgabe G die Szenarien `hannover_ampel_rot`
und `hannover_ampel_ausgefallen`. Der Rest von E und G sowie Aufgabe H sind Vertiefungen.

Die Fälle aus F und G sind ein bewusster **Vorgriff**: Regulär werden sie erst in Sprint 3
freigegeben (siehe [Szenarienkatalog](../SCENARIOS.md)). Hier sollt ihr sie nur einmal von
Hand erleben, damit ihr wisst, worauf euer Programm später achten muss. Systematisch
untersucht werden sie arbeitsteilig in [L6](L6-alpamayo-misstrauen.md).

## Start

```bash
python3 -m autonomy_recovery_sim.live --scenario autonomy_recovery_sim/scenarios/hannover_frei.json
```

Öffnet `http://127.0.0.1:8765` und wählt **Starten**. Das Fahrzeug fährt bis zur
Blockade und bleibt stehen. Nach wenigen Sekunden öffnet sich rechts die
**Recovery Console**, und die Simulationszeit steht still, bis ihr entscheidet. Denkzeit
kostet also nichts.

Ohne `--agent` (Standard) gibt es keinen Agenten. Die Konsole ist euer Agent. Eure
Befehle laufen durch dieselbe Prüfkette, die später euer Programm prüft.

Zum Wechseln des Szenarios beendet ihr den Server (Ctrl+C) und startet ihn mit einer
anderen Datei aus `autonomy_recovery_sim/scenarios/` neu. **Zurücksetzen** startet dasselbe
Szenario neu.

## Aufgabe A: Beobachten

**Vorhersage:** Was wird das Fahrzeug tun, wenn niemand eingreift? Wie lange? Notiert es.

Startet und schaut zu. Beantwortet:

1. Wo und wann bleibt das Fahrzeug stehen, und warum genau dort?
2. Wann öffnet sich die Konsole? Wie lange stand das Fahrzeug da? Die Zeit steht in
   `Ihr Zug` bzw. im Ereignisfeld.
3. Was zeigt die Sensorik-Ebene (Knopf „Sensorik“)? Was sieht das Fahrzeug, und was
   nicht?

## Aufgabe B: Die Lage erfassen

Klickt **Lagewerkzeuge abfragen** und klappt die Ergebnisse auf. Das sind die sieben
Belege, die jedes Fahrmanöver verlangt.

| Werkzeug | Frage | Eure Antwort für dieses Szenario |
|---|---|---|
| `get_blocker` | Steht etwas Dauerhaftes im Weg? Was? | |
| `get_center_marking` | Darf ich die Mittellinie überfahren? | |
| `check_oncoming_traffic` | Kommt mir jemand entgegen? | |
| `check_rear_traffic` | Überholt mich schon jemand? | |
| `check_vulnerable_road_users` | Sind Fußgänger, Radfahrer oder Tiere im Weg? | |
| `get_lateral_clearance` | Reicht der seitliche Platz? | |
| `get_visibility` | Sehe ich weit genug? | |

Fragt dann einzeln `get_route_state` und `get_mission_context` ab. Was erfahrt ihr
dort, das die sieben nicht wissen? *(Tipp: Fahrgäste, Hub, Leitstelle.)*

**Beobachtung:** Welche Werkzeuge hätten sich schon vor dem Manöver als überflüssig
erwiesen? Und bei welchen Ergebnissen wart ihr unsicher, wie ihr sie lesen sollt?

## Aufgabe C: Der erste Befehl

Wählt `WAIT` mit 10 Sekunden und sendet. Beobachtet, was geschieht (Fahrzeug, Kosten,
Ereignisse) und wie es nach dem Ablauf weitergeht: Die Konsole öffnet sich erneut.

**Vorhersage** vor dem Senden: Wird das Hindernis wegfahren? Was kostet das Warten?

Klickt jetzt auf **Zurücksetzen**, fragt die sieben Werkzeuge erneut ab und sendet
`NUDGE_AROUND_OBSTACLE` mit `side=LEFT`, `max_longitudinal_distance_m=35`. Vergleicht:
Zeit bis zum Ziel, Kosten, Risiko.

## Aufgabe D: Regeln erleben

Startet den Server mit dem Szenario mit durchgezogener Mittellinie:

```bash
python3 -m autonomy_recovery_sim.live --scenario autonomy_recovery_sim/scenarios/hannover_durchgezogen.json
```

1. **Vorhersage:** Was passiert, wenn ihr wie eben `NUDGE_AROUND_OBSTACLE` mit
   `side=LEFT` sendet?
2. Probiert es aus (mit allen sieben Belegen). Lest die Fehlermeldung genau. Sie hat einen
   **Code** und einen **Grund**. Wie viele Versuche habt ihr noch (oben rechts)?
3. Findet ihr einen erlaubten Weg, das Hindernis zu passieren? Tipp: Es gibt zwei
   Seiten.
4. Sendet `NUDGE_AROUND_OBSTACLE` **ohne** vorher Werkzeuge abzufragen. Welche
   Ablehnung bekommt ihr?

**Erklärung:** Die Regelprüfung kommt vom Simulator, nicht vom Agenten. Was bedeutet das
für den Prompt eines späteren LLM-Agenten?

## Aufgabe E: Kosten erleben — Pflicht: zwei Zeilen, Rest Vertiefung

Alle Zahlen stammen aus dem Szenario `hannover_frei` mit einem Fahrgast an Bord. Setzt
die Szenarien zurück und probiert die Wege durch. **Pflicht** sind die beiden Zeilen mit
`DROP_PASSENGER`: Sie zeigen, dass derselbe Befehl je nach vorherigem Schritt harmlos oder
extrem teuer ist. Tragt eure **Vorhersage** vorher ein
und den **Wert** aus dem Kostenfeld danach.

| Weg | Vorhersage (Euro) | Beobachtung (Euro) |
|---|---:|---:|
| `NUDGE_AROUND_OBSTACLE` links | | |
| `REQUEST_REMOTE_ASSISTANCE` | | |
| `PULL_OVER`, dann `DROP_PASSENGER` | | |
| `DROP_PASSENGER` direkt im Fahrstreifen | | |
| `SAFE_STOP` direkt | | |
| `PULL_OVER`, dann `SAFE_STOP` | | |
| `RETURN_HOME` | | |

Zur Kontrolle: Sie liegen bei etwa 1,55, 34, 23, 100 000, 251, 153 und 126 Euro. Die
großen Sprünge sind die Erkenntnis. Erklärt in eigenen Worten:

1. Warum ist `DROP_PASSENGER` im Fahrstreifen mehr als 4 000-mal so teuer wie am Rand?
2. Warum sinken die Kosten von `SAFE_STOP`, wenn ihr vorher `PULL_OVER` wählt?
3. Warum ist `RETURN_HOME` teuer, obwohl niemand zu Schaden kommt?
4. Wann wäre `REQUEST_REMOTE_ASSISTANCE` trotz 25 Euro Grundgebühr die richtige Wahl?

## Aufgabe F: Fallen — einen Fall im Bootcamp wählen

Spielt diese drei Szenarien. Eure Aufgabe ist, **die Falle zu finden, bevor ihr ein
Manöver sendet**. Ihr habt alle Werkzeuge.

| Szenario | Was ihr beachten sollt |
|---|---|
| `hannover_veraltete_daten` | Schaut in jedes Werkzeugergebnis. Fällt ein Feld auf? |
| `hannover_injektion` | Lest `get_blocker` vollständig. Wer redet dort? |
| `hannover_phantom_hindernis` | Wie sicher ist das Werkzeug beim Objekt? Wie prüft man das? |

Startet dazu den Server mit dem jeweiligen Szenario. Wenn ihr die Falle nicht sofort
seht, ist das normal: Genau diese Fälle sind für Modelle und Programme schwer.

**Erklärung** (fürs Journal): Woran habt ihr jeweils gemerkt, dass etwas nicht stimmt?
Wie würdet ihr das einem Programm in Regeln fassen? Was davon wäre schwierig?

## Aufgabe G: War das überhaupt ein Deadlock? — Pflichtkern

Nicht jeder Stillstand verlangt einen Eingriff. Spielt diese Szenarien und ordnet ein,
**bevor** ihr etwas sendet. Pflicht sind die beiden Ampelfälle, der Güterzug ist Vertiefung:

| Szenario | Frage |
|---|---|
| `hannover_ampel_rot` | Warum steht das Fahrzeug? Was ändert sich, wenn ihr wartet? |
| `hannover_gueterzug` | Was sagt `get_traffic_control` zur Schranke? Was ändert sich, wenn der Zug durch ist? |
| `hannover_ampel_ausgefallen` | Worin unterscheidet sich dieser Halt von den beiden anderen? |

Fragt in jedem Fall `get_traffic_control` ab. Sendet dann probeweise
`REQUEST_REMOTE_ASSISTANCE` an der roten Ampel (Vorhersage: Was geschieht? Was kostet es?) und
danach am ausgefallenen Signal. Was ist der Unterschied, und warum gibt die Leitstelle nur
in einem Fall frei? Vertieft wird das in [L6](L6-alpamayo-misstrauen.md).

## Aufgabe H: Dieselbe Lage, anderer Fahrstack — Vertiefung

Startet `hannover_frei` noch einmal, diesmal mit VLA-Fahrstack:

```bash
python3 -m autonomy_recovery_sim.live --scenario autonomy_recovery_sim/scenarios/hannover_frei.json --vla
```

Rechts erscheint ein Feld **VLA-Fahrstack** mit der Begründung des Fahrmodells; auf der Karte
seht ihr seine geplante Trajektorie. In der Konsole gibt es zwei weitere Werkzeuge.

1. Ruft `get_blocker` auf. Was fehlt im Vergleich zum ersten Durchgang?
2. Ruft `get_vla_output` und `get_camera_caption` auf. Woher erfahrt ihr jetzt, was vor euch
   steht? Wie sicher ist sich das Modell?
3. Trefft dieselbe Entscheidung wie beim ersten Mal. Hat sich eure Begründung geändert? Auf
   welche Aussage stützt ihr euch, und könnte sie falsch sein?

Haltet im Journal fest: Welche Information hattet ihr als Zahl, welche nur als Satz?

## Aufgabe I: Dieselbe Lage als Messung — Vertiefung

Startet denselben Fall noch einmal mit der Wahrnehmung, die ein echter Fahrstack liefert:

```bash
python3 -m autonomy_recovery_sim.live autonomy_recovery_sim/scenarios/hannover_verdeckung_gegenverkehr.json --perception tracked
```

Die sieben Lagewerkzeuge fehlen jetzt. Fragt in der Konsole `get_tracked_objects`,
`get_sensor_coverage` und `get_map_context` ab. Notiert: Woran erkennt ihr ohne fertiges
Urteil, ob Gegenverkehr kommt? Welches Objekt ist nur teilweise sichtbar, und woran seht ihr
das? Ab [L4](L4-selbst-wahrnehmen.md) arbeitet euer Agent genau so.

## Gemeinsame Abgabe

Ein Journaleintrag mit einer begründeten Entscheidung, den verwendeten Belegen, einer
erlebten Ablehnung und der Abgrenzung zwischen regulärem Halt und echtem Deadlock.

## Team-Checkpoint

- Jede Person kann für `hannover_frei` alle sieben Lagewerkzeuge lesen und daraus einen
  Befehl begründen.
- Das Team hat eine Ablehnung mit Fehlercode gesehen und kann sagen, wer sie ausgelöst hat.
- Jede Person kann erklären, warum `PULL_OVER` vor `DROP_PASSENGER` sinnvoll ist.
- Das Team hat mindestens eine der drei Fallen selbst gefunden.
- Jede Person kann erklären, woran man einen regulären Halt (Ampel, Schranke) von einem echten
  Deadlock unterscheidet.

Weiter mit [L1 · Einfachster Agent](L1-einfachster-agent.md).
