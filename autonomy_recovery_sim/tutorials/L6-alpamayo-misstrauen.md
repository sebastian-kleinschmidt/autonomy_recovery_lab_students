# L6 · Alpamayo misstrauen

**Teamzeit:** 90 Minuten · **Phase:** Sprint 3 · **Stufe:** B, mit Fehlern im Fahrstack und
in den Daten · **Schlüssel:** nein

Der Fahrstack begründet seine Entscheidungen in Worten, wie NVIDIA Alpamayo. Das ist
hilfreich und gefährlich: Die Begründung kann eine Ursache erfinden, vage bleiben oder der
eigenen Trajektorie widersprechen. Und auch die übrigen Daten können alt, lückenhaft oder
unsicher sein. In dieser Lektion prüft euer Agent seine Quellen, bevor er ihnen glaubt.

## Ziel

- Ihr gleicht die Begründung des Fahrstacks mit Tracker und Kamera ab.
- Ihr erkennt schlechte Daten: veraltet, unsichere Lokalisierung, knappes Budget.
- Ihr wisst, wann ihr neu beobachtet, eskaliert oder gezielt die Kamera fragt.

## Startstand

Euer Stand aus L5 oder `l6_start.py` (wird später freigegeben).

## Vorhersage

Der Fahrstack sagt „The traffic light ahead is red“. Was müsst ihr prüfen, bevor ihr wartet?

## Bauen

1. **Begründung und Trajektorie lesen.** `get_vla_output` liefert unter `current` die
   Begründung (`reasoning`) und die Trajektorie (`stationary`, `sampled_points_ego_m`). Im
   Modell `tracked` fehlen `meta_action` und `confidence`, weil Alpamayo beides nicht liefert.

2. **Drei Widersprüche erkennen.**
   - **Ampel:** Der Signalzustand ist im VLA-Modus `UNKNOWN`. Fragt `get_camera_caption` mit
     `front_tele`. Sagt die Kamera „no light“ oder „switched off“, ist die Ampel dunkel. Das ist
     ein Fall für die Leitstelle, nicht für endloses Warten.
   - **Phantom:** Der Fahrstack hält für „ein Objekt“, der Tracker sieht nur einen schwachen
     Kontakt (`existence_probability` unter 0,5). Erst neu beobachten
     (`REQUEST_ADDITIONAL_INFORMATION`, `MOTION_REASSESSMENT`).
   - **Unklares Objekt:** Die Begründung bleibt vage. Die Nahaufnahme (`front_wide`) beschreibt
     Material und Form. Ein flacher, weicher Karton darf mit `CROSS_LOW_RISK_OBJECT`
     überfahren werden; Glas, Holz oder Flüssigkeit nicht.

3. **Datenqualität zuerst.**
   - `get_sensor_health`: Lokalisierung unter 0,5 heißt kein Manöver, sondern `SAFE_STOP`.
   - `observation_age_s` in einem Ergebnis über 2 s: Daten sind alt, erst
     `SCENE_REFRESH`.
   - `session.context["budgets"]["max_tool_calls"]` klein: nur das Nötigste fragen.

## Messen

```bash
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/vla.txt --perception tracked --agent mein_agent:decide
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/uncertainty.txt --perception tracked --agent mein_agent:decide
```

| Menge | Startstand | Richtwert nach L6 |
|---|---|---|
| `vla.txt --perception tracked` | 0 von 3 | 3 von 3 |
| `uncertainty.txt --perception tracked` | 3 von 8 | 7 von 8 |

## Was typischerweise schiefgeht

- **Der Begründung glauben.** Wer bei „red“ wartet, wartet an einer dunklen Ampel ewig.
- **Der Kamera blind glauben.** Auch sie ist ein Modell. Ein Wort allein ist ein Hinweis, kein
  Beweis; bei Widerspruch ist Eskalation oft die beste Antwort.
- **Englisch und Deutsch.** Kamerabeschreibungen sind englisch, Szenentexte deutsch. Prüft
  beide Sprachen, wenn ihr nach Wörtern sucht.

## Erweitere selbst

- Berechnet einen Widerspruchswert: Passt „stationary“ der Trajektorie zur Begründung?
- Fragt die Kamera nur bei Widerspruch; das spart Budget.
- Vergleicht die Begründung über die letzten Ausgaben (`recent`): Ändert der Fahrstack seine
  Geschichte?

## Team-Checkpoint

- Ihr könnt für jeden der drei VLA-Fälle sagen, welche Quelle recht hatte und woran ihr es
  erkannt habt.
- Ihr habt eine Regel, wann euer Agent dem Fahrstack nicht glaubt.

Weiter mit [L7 · Manöver mit Phasen](L7-phasen-und-dynamik.md).
