# Stufe 4: Das Sprachmodell übernimmt die Entscheidung

**Teamzeit:** 120 Minuten Pflichtkern · **Phase:** Sprint 2 · **Modus:** Paararbeit und Review ·
**Voraussetzung:** Stufen 2, 3, Stufe 3b bis Schritt 4, freigegebener Forschungsplan ·
**Schlüssel:** ja

Jetzt ersetzt ihr die `if`-Zweige aus Stufe 2 durch ein Sprachmodell. Alles Übrige
bleibt gleich: dieselben Werkzeuge, dieselben Regeln, dieselbe Bewertung. Deshalb ist der
Vergleich fair. Ihr wisst aus Stufe 2, was ein Regelagent schafft, und aus Stufe 3b, wie
ein Loop gebaut ist, weil ihr ihn selbst geschrieben habt.

Diese Stufe arbeitet mit dem Referenzadapter und ändert nur den Prompt. Das Ergebnis ist
eure **LLM-Baseline**, der Vergleichsmaßstab für euren eigenen Loop aus Stufe 3b. Teil B der
Laboraufgabe ist nicht der Prompt allein, sondern euer eigener Loop: Nach dieser Stufe schließt
ihr ihn in [Stufe 3b, Schritt 5](03b-eigener-agent.md#schritt-5-ein-echtes-modell-anschließen)
an dasselbe Modell an. Jede Messung hier lässt sich mit
`--agent autonomy_recovery_sim.student_loop_agent:decide` für euren Loop wiederholen.

## Teammodus und Ergebnis

Ein Paar richtet Adapter und Prompt ein, das zweite Paar prüft Versuchsplan,
Konfiguration und Trace. Danach führt das jeweils andere Paar den Lauf allein anhand der
Dokumentation erneut aus. Verglichen wird zunächst genau **eine** begründete Änderung;
weitere Promptideen bleiben Vertiefung.

Abgegeben werden eine gemeinsame LLM-Baseline, ein kontrollierter Vergleich mit
Wiederholungen und ein Reviewvermerk des zweiten Paars. API-Schlüssel werden niemals
geteilt, dokumentiert oder eingecheckt.

## Zugang einrichten

Der Adapter spricht jeden OpenAI-kompatiblen Endpunkt. Die Einrichtung steht in
[QUICKSTART](../../QUICKSTART.md), Abschnitt 3. Kurz:

```bash
export AUTONOMY_RECOVERY_BASE_URL=https://chat-ai.academiccloud.de/v1
export AUTONOMY_RECOVERY_MODEL=glm-4.7
```

Den Schlüssel im selben Terminal verdeckt einlesen (zsh):

```zsh
read -rs "AUTONOMY_RECOVERY_API_KEY?Chat-AI-Schluessel: " && echo
export AUTONOMY_RECOVERY_API_KEY
```

**Der Schlüssel gehört nie ins Repository, nie in eine Datei im Projekt und nie in einen
Chat oder eine Abgabe.** Welche Modelle euer Zugang anbietet, zeigt `GET /v1/models` des
Dienstes. Fragt eure Betreuung, welches Modell ihr nehmen sollt. Ein Modell muss
**Function Calling** beherrschen; sehr kleine Modelle scheitern oft schon am Schema.

## Schritt 1: Der erste Lauf

```bash
python3 -m autonomy_recovery_sim autonomy_recovery_sim/scenarios/hannover_frei.json \
  --agent autonomy_recovery_sim.student_llm_agent:decide
```

Das Modell wird erst nach dem erkannten Deadlock gerufen. Prüft:

1. Endet der Lauf mit `NUDGE_AROUND_OBSTACLE`? Steht `agent_error` in `result.json`?
2. Wie viele Werkzeuge hat das Modell aufgerufen, in welcher Reihenfolge?
3. Wie viele Modellrunden, wie lange, wie viele Tokens?

## Schritt 2: Den Trace lesen

Der `agent_trace` in `result.json` ist euer Protokoll. Kurz auslesen:

```bash
python3 - <<'PY'
import json
d = json.load(open("artifacts/autonomy-recovery-sim/hannover_frei/result.json"))
for e in d["agent_trace"]:
    detail = e.get("name") or e.get("command") or e.get("finish_reason")
    print(e["type"], detail, e.get("error", ""))
PY
```

Es gibt drei Eintragsarten:

| `type` | Bedeutung | Nützliche Felder |
|---|---|---|
| `model_round` | eine Anfrage ans Modell | `latency_s`, `finish_reason`, `tool_names`, `usage` |
| `tool_call` | ein ausgeführtes Werkzeug | `name`, `arguments`, `result` oder `error` |
| `decision_attempt` | ein Entscheidungsversuch | `accepted`, `command`, `error`, `error_code` |

**Aufgabe:** Lest den Trace zu `hannover_durchgezogen`. Wo genau versucht das Modell
etwas Unzulässiges? Wie reagiert es auf die Ablehnung? Korrigiert es, oder wiederholt es
denselben Fehler?

## Schritt 3: Typische Fehler erkennen

| Symptom | Wahrscheinliche Ursache | Was ihr tut |
|---|---|---|
| „Kein API-Schluessel gesetzt“ | Variable nicht im selben Terminal exportiert | `export` prüfen |
| HTTP 401 | Schlüssel falsch oder abgelaufen | Betreuung fragen |
| HTTP 404 / „Modell nicht gefunden“ | Modellname falsch | `GET /v1/models` |
| Antwort in Prosa, kein Werkzeugaufruf | Modell ignoriert Function Calling | Prompt schärfen, größeres Modell |
| `arguments ist kein gueltiges JSON` | Modell formatiert Argumente falsch | Beispiele im Prompt |
| `SAFETY_REJECTED … Werkzeugevidenz` | Manöver ohne die sieben Belege | Prompt: erst alle sieben abfragen |
| `agent_error`, danach `WAIT` | Modell nach 12 Runden ohne Entscheidung | Rundenzahl, Prompt, Modell |
| Ergebnis schwankt | Nichtdeterminismus | Wiederholungen (`--repeats`) |

## Schritt 4: Experimente mit dem Prompt

Euer Hebel ist `STUDENT_SYSTEM_PROMPT` in
[`student_llm_agent.py`](../../student_llm_agent.py). Der Ausgangsprompt ist absichtlich knapp.
Arbeitet **wissenschaftlich**: eine Änderung pro Experiment, eine Hypothese vorher, eine
Messung nachher.

| Experiment | Hypothese (schreibt sie selbst) | Änderung am Prompt |
|---|---|---|
| E0 | Baseline: der Ausgangsprompt | keine |
| E1 | Ein fester Untersuchungsablauf verbessert die Befehlsgenauigkeit | „Fragt zuerst alle sieben Lagewerkzeuge ab, dann get_route_state und get_mission_context …“ |
| E2 | Kostenwissen verhindert teure Fehlgriffe | Kostenreihenfolge und Fahrgastfolgen erklären |
| E3 | Konkrete Beispiele helfen dem Modell mehr als allgemeine Regeln | ein bis zwei Beispielfälle einfügen |
| E4 | Eine Prüfung „regulärer Halt?“ im Prompt senkt die Fehlalarme (Vorstudie zu **Teil B**; im eigenen Loop wiederholen) | Ampel, Schranke, Stau und geplanten Halt als Erklärung nennen; messt auf `erkennen.txt` |

Führt jedes Experiment auf `demo.txt` mit Wiederholungen aus, weil das Modell nicht
deterministisch ist:

```bash
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/demo.txt \
  --agent autonomy_recovery_sim.student_llm_agent:decide --repeats 3 \
  --output artifacts/experiments/e0
```

Bevor ihr eine Variante bewertet, fuehrt ihr sie zusaetzlich auf der bis Sprint 2
empfohlenen Menge `released_sprint2.txt` aus. Falls noch kein Modellzugang vorhanden
ist, prueft `tutorials.mock_llm_demo` den Nachrichten- und Werkzeugloop ohne Schluessel;
Regelagent, Szenarien und Auswertung koennen parallel weiterentwickelt werden.

**Orientierungswert aus dem Lehrpilot:** Der unveränderte Referenzadapter mit
`z-ai/glm-4.7` bestand in einem Lauf 9 von 20 bis Sprint 2 freigegebene Fälle. Der naive
Loop erreichte 11/20, die Musterlösung 12/20. Nutzt diese Werte zur Plausibilitätsprüfung,
nicht als Bestehensgrenze; erst Wiederholungen zeigen, ob ein Unterschied stabil ist.

Vergleicht zwei Läufe mit dem Hilfsprogramm:

```bash
python3 -m autonomy_recovery_sim.tutorials.vergleich artifacts/experiments/e0 artifacts/experiments/e1
```

Es zeigt Note, Bestehensquote, Kosten, Werkzeugaufrufe, Tokens und Latenz nebeneinander,
und die Szenarien, in denen sich das Ergebnis unterscheidet. Achtet auf **Streuung**: Zeigt
ein Szenario bei drei Wiederholungen 33 %, 66 % oder 100 %, ist das keine Aussage über
die Prompt-Qualität, sondern über das Rauschen. Wiederholt mehr, oder testet an mehr Fällen.

## Schritt 5: Regeln und Modell mischen

Ein Sprachmodell ist teuer, langsam und unberechenbar. Regeln sind billig, schnell und
verlässlich. Die klügste Lösung nutzt beides an der jeweils passenden Stelle:

```python
from autonomy_recovery_sim.llm_agent import LLMConfig, OpenAICompatibleAgent

def decide(session):
    blocker = session.call_tool("get_blocker")
    if not blocker["detected"]:
        # Der leichte Fall braucht kein Modell: billig, schnell, deterministisch.
        return session.submit_decision({
            "command": "WAIT", "parameters": {"duration_s": 10},
            "reason": "Keine dauerhafte Blockade erkannt",
        })
    return OpenAICompatibleAgent(LLMConfig.from_environment())(session)  # schwerer Fall
```

Ein Aufruf in der Regelstufe zählt zum Werkzeugbudget der Sitzung mit. Der Preis dafür
ist eine Runde weniger für das Modell. Wann lohnt sich das?

| Aufgabe | Besser mit | Warum |
|---|---|---|
| Harte Grenzen (Budget, Parameterbereich, Pflichtbelege) | **Programm** | muss immer gelten, nicht nur meistens |
| Einfache, häufige Fälle | **Programm** | kostenlos, reproduzierbar |
| Abwägen mehrerer Kosten, unklare Lage | **Modell** | schwer in Regeln zu fassen |
| Auswerten von Freitext | **Modell** | Regeln kommen nicht mit Sprache zurecht |
| Sicherheitsentscheidung | **Programm entscheidet, Modell berät** | ein Vorschlag ist keine Handlung |

## Reflexion

1. Wie viel besser oder schlechter als euer Regelagent aus Stufe 2 ist das Modell? Auf
   welchen Szenarien? Ist der Unterschied größer als die Streuung?
2. Wo hat das Modell etwas Kluges getan, das ihr nicht programmiert habt? Wo etwas
   Dummes, das ein Regelagent nie getan hätte?
3. Was kostet ein Lauf (Tokens, Sekunden) im Verhältnis zum Nutzen?

## Team-Checkpoint

- Der gemeinsame LLM-Agent läuft auf `demo.txt` ohne `agent_error`.
- Jede Person kann einen Trace lesen und einen Fehler auf eine Ursache zurückführen.
- Das Team hat den Ausgangsprompt (E0) und mindestens eine begründete Variante mit
  Wiederholungen verglichen und die Streuung berücksichtigt.
- Der Prompt enthält nichts, was nur für ein bestimmtes Szenario gilt.

Weiter mit [Stufe 3b, Schritt 5](03b-eigener-agent.md#schritt-5-ein-echtes-modell-anschließen):
euren eigenen Loop an das echte Modell anschließen und mit dieser Baseline vergleichen. Danach
[Stufe 5: Robust](05-robust.md).
