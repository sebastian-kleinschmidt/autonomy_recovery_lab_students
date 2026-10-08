# Prüfstand: den Agenten gegen alle Szenarien testen

Der Prüfstand fährt euren Agenten nacheinander durch eine Menge von Szenarien und schreibt einen
Bericht, der für jeden Fall sagt, **ob** er bestanden ist und **warum nicht**, und der zeigt,
**ob** sich euer Agent seit dem letzten Lauf verbessert hat. Er ist derselbe Batchlauf wie der
Abschlusslauf auf den verdeckten Fällen. Alle Befehle gelten aus dem
Repository-Wurzelverzeichnis.

## Der Grundbefehl

```bash
python3 -m autonomy_recovery_sim batch --agent mein_agent:decide
```

`mein_agent.py` ist euer Agent aus dem [Tutorial-Track](tutorials/README.md#der-tutorial-track).
Ohne weitere Angabe laufen **alle** 61 Sprintfälle. Die Konsole zeigt eine Zusammenfassung und je
Freigabestufe, wie viele Fälle bestanden sind. So sieht es für das unveränderte Gerüst mit dem
Spielmodell aus:

```text
Szenarien:  24/61 bestanden
Agent:      autonomy_recovery_sim.student_loop_agent:decide
Genauigkeit:42.6%
Kollisionen:0
Einstufung: D (Kosten 1068.05 EUR, im Budget 59/61)
  bootcamp     2/3 bestanden
  sprint1      3/5 bestanden
  sprint2      1/12 bestanden
  sprint3      5/16 bestanden
  sprint4      13/25 bestanden
Fortschritt: erster Lauf in diesem Ausgabeordner
Bericht:    artifacts/autonomy-recovery-sim/batch/batch-report.md
Website:    artifacts/autonomy-recovery-sim/batch/batch-report.html
Details:    artifacts/autonomy-recovery-sim/batch/scenarios/<szenario>/report.md
```

Der Rückgabewert ist `0` nur, wenn **alle** Fälle bestanden sind. So lässt sich der Prüfstand
auch in einem eigenen Test oder einer CI-Pipeline verwenden.

## Welcher Agent, welche Szenarien

| Option | Bedeutung | Beispiel |
|---|---|---|
| `--agent` | `baseline`, `llm`, `none` oder `modul:funktion` | `--agent mein_agent:decide` |
| `--release` | alle bis zu dieser Stufe freigegebenen Fälle: `bootcamp`, `sprint1` … `sprint4`, `all` | `--release sprint2` |
| Quelle (statt `--release`) | ein Szenario, ein Ordner oder eine Set-Datei | `autonomy_recovery_sim/scenario_sets/vla.txt` |
| `--repeats` | Läufe je Szenario; bei Sprachmodellen mindestens 3 | `--repeats 3` |
| `--output` | Zielordner, je Experiment ein eigener | `--output artifacts/loop/e1` |
| `--vla` | alle Szenarien mit VLA-Fahrstack: Objektklassen, Profile und Signalzustände nur als Modelltext | Vergleich „strukturiert gegen VLA“ |
| `--perception` | Wahrnehmungsmodell erzwingen: `exact` oder `tracked` (Objektliste mit Messunsicherheit) | `--perception tracked` |
| `--guardrails` | Prüfmodus erzwingen: `strict`, `advisory` oder `off` | `--guardrails off` |
| `--hide-reference` | keine Referenzbefehle und -begründungen in den Berichten | für den Abschlusslauf auf verdeckten Fällen |

Die Agenten im Repository:

| Agent | Datei | Wofür |
|---|---|---|
| euer Track-Agent | `mein_agent.py` (Startstände in [`tutorials/track/`](tutorials/track/)) | Teil A mit `AUTONOMY_RECOVERY_MODEL=none`, Teil B mit Modell |
| Prompt-Agent | [`student_llm_agent.py`](student_llm_agent.py) | Referenzschleife, nur der Prompt ist eurer; Maßstab für Teil B |
| früherer Regelagent | [`student_agent.py`](student_agent.py) | Starter der archivierten Stufe 2 |
| früherer Loop | [`student_loop_agent.py`](student_loop_agent.py) | Starter der archivierten Stufe 3b |
| Referenzbaseline | `--agent baseline` | Vergleichsmaßstab, löst bewusst nicht alles |

Ohne Schlüssel läuft der hybride Agent ab L5 mit dem Spielmodell, ohne Modell mit `none`:

```bash
AUTONOMY_RECOVERY_MODEL=spielmodell python3 -m autonomy_recovery_sim batch --release sprint2 \
  --perception tracked --agent mein_agent:decide --output artifacts/teil-b
AUTONOMY_RECOVERY_MODEL=none python3 -m autonomy_recovery_sim batch --release sprint2 \
  --perception tracked --agent mein_agent:decide --output artifacts/teil-a
```

## Was im Zielordner liegt

| Datei | Inhalt |
|---|---|
| `batch-report.html` | Bericht zum Lesen im Browser: Einstufung, Kennzahlen, Fortschritt, Kosten, Tabelle nach Freigabestufe, alle Szenarien mit Befund |
| `batch-report.md` | derselbe Bericht als Markdown, gut für Journal und Abgabe |
| `batch-result.json` | alle Kennzahlen maschinenlesbar, Eingabe für `tutorials.vergleich` |
| `scenarios/<id>/report.md` | **Detailseite** eines Szenarios: Befund, Kennzahlen, Befehlsfolge, Agent-Trace je Sitzung |
| `scenarios/<id>/result.json` | Rohdaten des Laufs, inklusive vollständigem Trace, Ereignissen und bei Unfällen dem Rückblick (`incident`) |
| `verlauf.jsonl` | eine Zeile je Lauf in diesem Ordner: Agent, Einstellungen, Bestanden, Kollisionen, Kosten, gescheiterte Fälle |

Mit `--repeats` liegen die Detailseiten unter `scenarios/<id>/run-<n>/`.

## Wann ein Szenario besteht

Alle Bedingungen müssen gelten:

1. keine Kollision,
2. kein Agentenfehler (keine Ausnahme, kein Überschreiten der Budgets),
3. der erste inhaltliche Befehl passt zur Lage (Informations- und Regel-Engine-Befehle bereiten nur vor),
4. der erwartete Ausgang tritt ein,
5. die Kosten bleiben im Budget des Szenarios,
6. bei erwartetem Abbruch stabilisiert sich das Fahrzeug sicher,
7. bei **mehrstufigen Szenarien** ist der Lösungsweg vollständig: Jeder Schritt wurde mit einem
   erfolgreichen Befehl erledigt, in der vorgegebenen Reihenfolge. Zwischenschritte wie ein
   zusätzliches `WAIT` sind erlaubt, kosten aber Zeit; ein gescheiterter Befehl zählt nicht.

Für mehrstufige Szenarien zeigt der Bericht zusätzlich **Teilpunkte**: den Anteil erledigter
Schritte, im Mittel über alle diese Szenarien („Lösungswege vollständig … · Ø …“). Die Einstufung
berücksichtigt nur das Bestehen; die Teilpunkte zeigen, wie nah ein Agent an der Lösung war.

## Fortschritt verfolgen

Lauft nach jeder Änderung in **denselben Ausgabeordner**. Der Bericht vergleicht dann
automatisch mit dem vorigen Lauf und nennt oben:

- wie viele Fälle vorher und jetzt bestanden sind, dazu Kollisionen, Kosten und Einstufung,
- welche Fälle **neu bestanden** und welche **neu gescheitert** sind,
- einen Verlauf über die letzten zehn Läufe (`verlauf.jsonl`).

Verglichen wird nur Vergleichbares: Ändert sich die Szenariomenge oder eine Einstellung
(`--vla`, `--perception`, `--guardrails`), sagt der Bericht das, statt Zahlen gegeneinander zu
stellen. Wer zwei Varianten nebeneinander halten will, nutzt eigene Ordner und den Vergleich
unten.

## Den Bericht lesen

Arbeitet von oben nach unten:

1. **Einstufung und Sicherheit.** Eine Kollision oder ein Personenschaden bedeutet immer
   Einstufung D. Das
   zuerst beheben, alles andere danach.
2. **Nach Freigabestufe.** Wo verliert ihr Fälle: bei den Grundlagen oder erst bei den späten
   Stufen? Ein Agent, der Sprint 1 nicht vollständig besteht, braucht keine Sprint-4-Tricks.
3. **Befund.** Jede Zeile nennt den wichtigsten Grund zuerst:

   | Befund | Was er bedeutet | Wo ihr sucht |
   |---|---|---|
   | Sicherheit: Kollision | das Fahrzeug hat etwas berührt | Befehlsfolge, Abbruchereignisse |
   | Agentenfehler | Ausnahme, Budget überschritten oder dreimal abgelehnt | letzte Einträge im Trace |
   | fail-safe | der ausgeführte Befehl kam nicht vom Agenten | Agentenfehler davor |
   | Fehlalarm | eingegriffen, obwohl Warten gereicht hätte | Werkzeuge, die einen regulären Halt zeigen |
   | Verpasster Eingriff | gewartet, obwohl die Lage einen Eingriff verlangt | Route, Mission, Signalzustand |
   | Unerwartetes Manöver | Manöver in einer Lage ohne Manöverlösung | Belege gegen das Manöver |
   | Befehl passt nicht | anderer Befehl als die Lage verlangt | welcher Befehl die Lage besser trifft |
   | Ausgang … statt … | der Befehl passte, die Wirkung nicht | Befehlsfolge: was geschah danach |
   | Lösungsweg unvollständig | ein Schritt fehlt oder ist gescheitert | Befehlsfolge: Status je Befehl, nächste Sitzung im Trace |
   | Budget überschritten | zu teuer, Posten stehen dabei | Standzeit, Anrufe, Umweg |
   | Hinweis | abgelehnte Versuche oder Werkzeugausfälle, auch in bestandenen Fällen | Trace |

4. **Detailseite.** Ein Klick auf das Szenario öffnet `report.md`. Lest Befund, dann
   Befehlsfolge, dann den Trace der ersten Sitzung: Welche Werkzeuge hat der Agent gefragt, was
   kam zurück, was hat er daraus gemacht?
5. **Referenzbegründung** steht am Ende der Detailseite. Lest sie erst, wenn ihr eine eigene
   Erklärung im Journal habt. Sonst lernt ihr die Lösung eines Falls statt einer Strategie.

## Zwei Läufe vergleichen

```bash
python3 -m autonomy_recovery_sim.tutorials.vergleich artifacts/loop/e0 artifacts/loop/e1
```

Die Ausgabe stellt Einstufung, Bestehensquote, Kosten, Werkzeugaufrufe, Tokens und Latenz nebeneinander
und listet die Szenarien, deren Ergebnis sich geändert hat. Bei Sprachmodellen gilt ein
Unterschied erst, wenn er größer ist als die Streuung über `--repeats`.

