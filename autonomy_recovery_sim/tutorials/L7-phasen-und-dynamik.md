# L7 · Manöver mit Phasen und Lagen, die sich ändern

**Teamzeit:** 120 Minuten · **Phase:** Sprint 3 · **Stufe:** B bis D (Szenariofamilien) ·
**Schlüssel:** nein

Ein Transporter steht ohne erkennbaren Grund. Davor könnte die Müllabfuhr arbeiten, eine
Unfallstelle liegen oder ein Umzug stattfinden. Von hier sieht man es nicht. Wer blind
überholt, hat Glück oder kracht; wer ewig wartet, steht. Die Lösung ist, **Information zu
kaufen**: so weit ausscheren, dass man sieht, und dann neu entscheiden.

## Ziel

- Ihr nutzt Manöver mit Checkpoint (`OVERTAKE`, `PEEK_OUT`) und entscheidet am Checkpoint neu.
- Ihr wendet sicher (`TURN_AROUND`), wenn die Straße voraus dicht ist.
- Ihr merkt euch über Sitzungen hinweg, was ihr gesehen habt.

## Startstand

Euer Stand aus L6 oder `l7_start.py` (wird später freigegeben). Die Szenariofamilien beschreibt der
[Szenarienkatalog](../SCENARIOS.md#szenariofamilien-f1-bis-f6-lagen-die-sich-ändern); die
Manöver stehen in [COMMANDS.md](../COMMANDS.md#phasenmanoever-und-checkpoints).

## Vorhersage

Alle drei Varianten jeder Familie sind veröffentlicht. Vergleicht vor dem Lauf die
Startbilder und sagt vorher, welche Beobachtung zu einer anderen Entscheidung führen muss.
Warum reicht eine feste Antwort pro Familie nicht?

## Bauen

1. **Den Auslöser lesen.** Jede Sitzung nennt unter `session.context["trigger"]`, warum ihr
   gerufen werdet. `CHECKPOINT` mit `phase: "PULLED_OUT"` heißt: Ihr steht 1,2 m ausgeschert
   hinter dem Hindernis und seht jetzt, was davor liegt.

2. **Information kaufen.** Ist die Ursache unklar (der Szenentext sagt es) oder die Gegenspur
   durch ein Objekt verdeckt (`get_sensor_coverage`), wählt `OVERTAKE`. Am Checkpoint:
   - Straße auf beiden Spuren dicht: `ABORT_TO_LANE`, merken, dann wenden.
   - Das Hindernis fährt an, Fuß- oder Radverkehr, Gegenverkehr: `ABORT_TO_LANE`.
   - Gegenspur immer noch nicht einsehbar: `ABORT_TO_LANE`.
   - Sonst `RESUME`.

   **Am Checkpoint läuft die Uhr.** Jeder Werkzeugaufruf kostet 0,2 s, jede Modellrunde 2 s,
   während der Gegenverkehr näher kommt. Entscheidet dort mit Regeln, nicht mit dem Modell.

3. **Gedächtnis.** Was ihr am Checkpoint seht, steht in der nächsten Sitzung nicht mehr in der
   Objektliste. Ein kleines Gedächtnis je Episode (neu, sobald `commands_used == 0` oder die
   `scenario_id` wechselt) merkt sich „Straße dicht“.

4. **Sicher wenden.** Weiß die Karte von der Sperrung (`get_route_state`), plant `REPLAN_ROUTE`
   um. Scheitert es mit `TURN_REQUIRED` oder kennt die Karte die Sperrung nicht, wendet ihr
   mit `TURN_AROUND` und `THREE_POINT`, aber:
   - erst, wenn kein Gegenverkehr naht und kein wartender Gegenverkehr gleich losfährt,
   - erst, wenn niemand hinter dem Fahrzeug ist (auch Radfahrer am Rand),
   - und nach zweimaligem Hinsehen: Ein Track kann in einer Messung fehlen.

5. **Geduld bei Stau.** Mehrere Fahrzeuge hintereinander lösen sich auf; wartet länger als bei
   einem einzelnen Hindernis.

## Messen

```bash
# Einstieg: sechs Fälle, danach alle 18 Varianten
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/familien_sichtbar.txt --agent mein_agent:decide
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/familien_alle.txt --agent mein_agent:decide
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/released_sprint2.txt --perception tracked --agent mein_agent:decide
```

| Menge | Startstand | Richtwert nach L7 |
|---|---|---|
| `familien_sichtbar.txt` | 3 von 6 | 6 von 6 |
| `released_sprint2.txt --perception tracked` | 19 von 20 | 18 von 20 |

Der kleine Rückgang auf Sprint 2 ist der Preis der Vorsicht: Wer unklare Lagen erst
anschaut, ist in einfachen Fällen manchmal langsamer. Ein guter Agent findet die Balance;
prüft anschließend alle 18 Varianten und zusätzliche Seeds. Die Richtwerte oben beziehen
sich auf die sechs Einstiegsfälle, nicht auf den gesamten Familienkatalog.

## Was typischerweise schiefgeht

- **Auf den Einstiegsfall zugeschnitten.** „Bei Transporter immer warten“ besteht
  `f1_muellabfuhr` und scheitert an der Unfallstelle.
- **Am Checkpoint zu lange nachdenken.** Ein LLM am Checkpoint lässt den Gegenverkehr
  heranfahren.
- **Wenden ohne Blick nach hinten.** Der Radfahrer am Rand ist nur in der Objektliste zu sehen.
- **Ausscheren bei Nebel.** Wer bei schlechter Sicht durch Wetter ausschert, sieht nichts mehr
  als vorher.

## Erweitere selbst

- Nutzt `PEEK_OUT`, wo `OVERTAKE` zu viel ist. Wann reicht ein kurzer Blick?
- `WAIT_FOR_GAP` statt `RESUME`, wenn Gegenverkehr kommt, aber danach frei ist. Was sieht der
  Ausführer dabei nicht?
- Schätzt ab, ob die Zeit zum Wenden reicht, bevor Verkehr von hinten den Rückweg verbaut.
- Haltet euren Checkpoint-Code so kurz, dass er mit höchstens drei Werkzeugaufrufen auskommt.

## Team-Checkpoint

- Ihr könnt an einem Trace zeigen, was euer Agent am Checkpoint gesehen hat, das er vorher
  nicht sehen konnte.
- Ihr habt begründet, warum euer Agent keine Szenario-IDs oder Referenzlabels für Entscheidungen verwendet.

Weiter mit [L8 · Unfälle und eigene Schutzregeln](L8-unfaelle-und-schutzregeln.md).
