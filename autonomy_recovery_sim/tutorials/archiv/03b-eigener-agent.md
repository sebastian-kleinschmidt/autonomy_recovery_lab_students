# Stufe 3b: Euren eigenen Agenten schreiben

**Teamzeit:** 120 Minuten Pflichtkern · **Phase:** Sprint 2 · **Modus:** Paararbeit, dann arbeitsteilig ·
**Voraussetzung:** Stufe 3 · **Schlüssel:** nein (Spielmodell), für Schritt 5 ja

**Reihenfolge in Sprint 2:** Schritte 1 bis 4 arbeitet ihr ohne Schlüssel. Danach bearbeitet
ihr [Stufe 4](04-llm-agent.md): Modellzugang, Trace lesen und eine LLM-Baseline mit dem
Referenzadapter. Mit diesem Maßstab kehrt ihr für Schritt 5 hierher zurück.

In Stufe 3 habt ihr den Agentenloop gelesen. Jetzt schreibt ihr ihn selbst. Ausgangspunkt ist
[`student_loop_agent.py`](../../student_loop_agent.py): eine vollständige, lauffähige Schleife mit
Modellaufruf, Werkzeugausführung und Entscheidung, keine hundert Zeilen lang. Sie ist
**absichtlich naiv**. An sechs Stellen steht `BAUSTELLE`. Dort entscheidet ihr, wie euer Agent
arbeitet. Was gut ist, zeigt euch der Prüfstand.

Ihr braucht dafür keinen Schlüssel. Das [Spielmodell](../spielmodell.py) antwortet im selben Format
wie ein echter Endpunkt, deterministisch und mit wenigen festen Regeln. Es ist bewusst
einfältig: Es kennt keine durchgezogene Linie, keine dunkle Ampel und keine Kosten. Ein guter
Loop holt trotzdem mehr aus ihm heraus als ein schlechter, und genau das lässt sich messen.

## Teammodus und Ergebnis

Schritte 1 bis 3 arbeitet ihr zu zweit am Bildschirm, das andere Paar liest parallel den Code und
bereitet Vorhersagen vor. Schritt 4 verteilt ihr: Jede Person übernimmt mindestens eine
Baustelle, misst sie allein und erklärt sie dem Team. Zusammengeführt wird erst, was gemessen
besser ist.

Abgegeben wird **ein** gemeinsamer Agent in `student_loop_agent.py` mit einer Tabelle
„Baustelle, Änderung, Hypothese, Messung vorher und nachher“ im Lab-Journal.

## Die Datei in fünf Bausteinen

| Funktion | Aufgabe | Baustelle |
|---|---|---|
| `ask_model` | ein Modellaufruf: Spielmodell oder echter Endpunkt | – |
| `build_task` | erste Nachricht: Aufgabe und Ausgangslage | **C** Kontext |
| `choose_tools` | welche Werkzeuge das Modell angeboten bekommt | **D** Werkzeuge |
| `run_tool` | ein Werkzeug ausführen; Fehler werden zu Daten | **D** eigene Werkzeuge |
| `decide` | die Schleife: fragen, ausführen, entscheiden | **A** Ablehnungen, **E** Regeln, **F** Ende |

Dazu kommt der Systemprompt `SYSTEM_PROMPT` (**B**). Alles, was ihr sonst braucht, liefert die
`AgentSession`: `call_tool`, `submit_decision`, `context`, `tool_catalog` und `trace`.

## Schritt 1: Den Nullpunkt messen

```bash
AUTONOMY_RECOVERY_MODEL=spielmodell python3 -m autonomy_recovery_sim batch --release sprint1 \
  --agent autonomy_recovery_sim.student_loop_agent:decide --output artifacts/loop/e0
```

Erwartet: **5 von 8** Fällen bestanden. Über alle Szenarien (`--release all`) sind es 24 von 61.
Das ist euer Nullpunkt. Öffnet `artifacts/loop/e0/batch-report.html` und lest die Spalte
**Befund**. Wie ihr den Bericht lest, steht im [Prüfstand](../../PRUEFSTAND.md).

## Schritt 2: Einen Fall bis zum Ende verfolgen

Öffnet die Detailseite `artifacts/loop/e0/scenarios/hannover_durchgezogen/report.md`. Sie zeigt
Sitzung für Sitzung, welche Werkzeuge das Modell abgefragt und was es eingereicht hat.

1. Was schlägt das Modell vor, und wer lehnt es mit welchem Code ab?
2. Was passiert danach in eurem Loop? Sucht die Zeile im Code.
3. Welcher Befund steht oben, und warum zählt der ausgeführte `WAIT` nicht?

## Schritt 3: Die erste Baustelle gemeinsam (A: Ablehnungen)

Im Moment wirft `session.submit_decision` bei einer Ablehnung eine Ausnahme. Die Sitzung endet,
der Simulator weicht fail-safe aus, und das Modell erfährt nie, was falsch war. Dabei erlaubt die
Sitzung **drei** Entscheidungsversuche.

**Vorhersage zuerst:** Schreibt auf, in welchen Fällen der Nullpunkt sich ändern wird, wenn das
Modell die Ablehnung als Werkzeugergebnis zurückbekommt. Dann baut es:

- Welche Ausnahmen kann `submit_decision` werfen? (Tipp: Die Datei importiert beide.)
- Wie sieht eine `tool`-Nachricht für einen fehlgeschlagenen Aufruf aus? `run_tool` macht es vor.
- Was passiert, wenn auch der dritte Versuch scheitert?

Messt erneut nach `artifacts/loop/e1` und vergleicht:

```bash
python3 -m autonomy_recovery_sim.tutorials.vergleich artifacts/loop/e0 artifacts/loop/e1
```

Stimmt eure Vorhersage? Wenn sich weniger ändert als gedacht: Welcher Befund steht jetzt bei
den Fällen, die weiter scheitern?

## Schritt 4: Die übrigen Baustellen

Jede Baustelle ist eine eigene Hypothese mit eigener Messung. Ändert **eine** Baustelle pro
Messung, sonst wisst ihr nicht, was gewirkt hat.

| Baustelle | Frage | Woran ihr den Effekt seht | Falle |
|---|---|---|---|
| **B** Systemprompt | Was muss das Modell wissen, was erzwingt ohnehin das Programm? | Entscheidungsgenauigkeit, Fehlalarme | Regeln abschreiben, die der Simulator prüft; Szenario-IDs im Prompt |
| **C** Kontext | Welche Teile von `session.context` braucht das Modell wirklich? | Tokens pro Szenario im Bericht | Wichtiges wegkürzen (`stopped_for_s`, `additional_information`) |
| **D** Werkzeuge | Braucht das Modell alle Werkzeuge? Hilft ein eigenes, zusammengesetztes Werkzeug? | Werkzeugaufrufe, fehlgeschlagene Aufrufe | Budget von 14 Aufrufen; Manöver verlangen die sieben Lagewerkzeuge als Beleg |
| **E** Regeln vor dem Modell | Welche Fälle entscheidet ein Programm billiger und verlässlicher? | Modellrunden, Kosten, Fehlalarme | Regeln, die nur auf die bekannten Szenarien passen |
| **F** Ende ohne Entscheidung | Was ist die sicherste Antwort, wenn das Modell nicht entscheidet? | `agent_error` im Befund | eine „sichere“ Antwort, die teuer ist |

Hinweise zu **D**: Ein eigenes Werkzeug ist ein Eintrag in der Werkzeugliste (Name,
Beschreibung, Parameterschema wie in `tool_definitions`) plus ein Zweig in `run_tool`, der
intern `session.call_tool` aufruft. Die Aufrufe darin zählen zum Budget und als Beleg. Das
Modell sieht nur euer Ergebnis. Was sollte es zusammenfassen, und was darf dabei nicht verloren
gehen?

**Gedächtnis:** Nach jedem Befehl ohne Lösung ruft der Simulator euren Agenten mit einer
**neuen** Sitzung. Die Nachrichtenliste der letzten Sitzung ist dann weg. Was über Sitzungen
hinweg gilt, liefern `get_recovery_history` und `session.context["additional_information"]`.
Globale Variablen in eurem Modul überleben auch den Wechsel zum nächsten Szenario. Warum ist das
gefährlich? Prüfen lässt sich das Gedächtnis an Fällen mit mehrstufigem Lösungsweg: In Sprint 2
sind das `hannover_sackgasse` und `hannover_passagier_absetzen`. Bestanden ist ein solcher
Fall nur mit dem ganzen Weg; der Befund nennt, wie viele Schritte erledigt sind.
`hannover_leitstelle_offline` ist ebenfalls mehrstufig, aber eine **Vertiefung**: Im Lehrpilot
hat ihn kein Agent bestanden, auch nicht die Musterlösung. Wer ihn löst, hat etwas
Besonderes geschafft; wer ihn nicht löst, verfehlt kein Lernziel. Ab Sprint 4 enthält [`mehrstufig.txt`](../../scenario_sets/mehrstufig.txt) alle neun
Fälle, bei denen sich die Lage nach dem ersten Befehl ändert.

## Schritt 5: Ein echtes Modell anschließen

Voraussetzung ist [Stufe 4](04-llm-agent.md): Der Zugang funktioniert, ihr könnt einen
Modell-Trace lesen, und die LLM-Baseline des Referenzadapters liegt vor. `AUTONOMY_RECOVERY_MODEL` zeigt jetzt
auf das echte Modell statt auf `spielmodell`. Dann dieselbe Messung mit Wiederholungen:

```bash
python3 -m autonomy_recovery_sim batch --release sprint2 \
  --agent autonomy_recovery_sim.student_loop_agent:decide --repeats 3 --output artifacts/loop/llm
```

Vergleicht mit drei Maßstäben: dem Spielmodell im selben Loop, dem Referenzadapter
(`--agent llm`) und eurem Regelagenten aus Stufe 2. Ist euer Loop besser als der Referenzadapter?
Wo, und ist der Unterschied größer als die Streuung?

**Orientierungswert aus dem Lehrpilot:** Mit `z-ai/glm-4.7` bestand der unveränderte naive
Loop in einem Lauf 11 von 20 bis Sprint 2 freigegebene Fälle. Der Referenzadapter kam auf
9/20, die Musterlösung auf 12/20. Das sind keine Zielwerte: Eine Wiederholung zeigt noch
keine Streuung, und euer eigener Loop darf deutlich anders ausfallen.

## Spielregeln für faire Verbesserungen

- Keine Szenario-IDs, Straßennamen oder Akteur-IDs im Code oder Prompt.
- Nur über die `AgentSession` an Informationen kommen. Kein Zugriff auf Szenario-Dateien,
  Engine oder Ground Truth.
- Eine Änderung pro Messung, jede Messung mit Vorhersage im Journal.
- Entwickeln auf den freigegebenen Sets, bewertet wird zusätzlich auf verdeckten Varianten.

## Weiterführende Ideen

Wenn die Baustellen erledigt sind, lohnt sich einer dieser Schritte. Wählt, was zu eurer
Forschungsfrage passt:

- **Erst denken, dann handeln (ReAct):** Das Modell schreibt vor jedem Werkzeugaufruf kurz, was
  es erwartet. Hilft das, oder kostet es nur Tokens?
- **Zweiter Blick:** Ein zweiter Modellaufruf prüft den Vorschlag gegen die gesammelten Belege,
  bevor er eingereicht wird. Wie oft widerspricht der Prüfer, und hat er recht?
- **Erst planen, dann ausführen:** Das Modell legt zuerst fest, welche Werkzeuge es braucht, euer
  Programm führt den Plan ohne weitere Modellrunden aus.
- **Mehrheitsentscheid:** Mehrere Antworten bei `temperature > 0` und die häufigste nehmen. Was
  kostet die gewonnene Stabilität?
- **Modellkaskade:** Ein kleines, schnelles Modell zuerst, ein großes nur bei Unsicherheit.
  Woran erkennt ihr Unsicherheit?
- **Beispiele aus eigenen Traces:** Gute Entscheidungen als Beispiele in den Prompt. Wie
  verhindert ihr, dass sie nur die bekannten Fälle abbilden?
- **Selbstauskunft des Fahrstacks prüfen:** In [`vla.txt`](../../scenario_sets/vla.txt) begründet der
  Fahrstack seinen Halt selbst und irrt sich dabei. Welche Aussage prüft ihr gegen welches
  Lagewerkzeug, im Programm oder im Prompt?
- **Kosten vor der Eskalation abschätzen:** Ein eigenes Werkzeug, das Standzeit, Anruf und Umweg
  gegeneinander rechnet, bevor das Modell eskaliert.

## Team-Checkpoint

- Jede Person kann in `student_loop_agent.py` zeigen, wo Modell, Werkzeug und Entscheidung
  zusammenkommen, und erklären, was bei einer Ablehnung passiert.
- Baustelle A ist gebaut und gegen den Nullpunkt gemessen.
- Jede Person hat eine weitere Baustelle mit Vorhersage und Messung bearbeitet.
- Der Agent enthält keine Szenario-IDs und keinen Zugriff außerhalb der `AgentSession`.

Nach Schritt 4 weiter mit [Stufe 4: LLM-Agent](04-llm-agent.md); nach Schritt 5 weiter mit
[Stufe 5: Robust](05-robust.md).
