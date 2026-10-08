# Stufe 6: Messen, vergleichen, berichten

**Teamzeit:** 120 Minuten Pflichtkern · **Phase:** Sprint 4 · **Modus:** gemeinsam ·
**Voraussetzung:** ein Agent aus dem Tutorial-Track (L1 bis L8), freigegebener Versuchsplan · **Schlüssel:** teils

Ein Agent ohne Messung ist eine Meinung. Diese Stufe macht aus eurem Agenten ein
**Ergebnis**: reproduzierbar gemessen, fair verglichen und ehrlich berichtet. Hier
entscheidet sich, ob eure Aussage wissenschaftlich trägt.

## Teammodus und Freeze

Vor dem Abschlusslauf friert das Team Agentencode, Prompt, Modellkonfiguration und
Szenariomengen ein. Eine Person startet die Läufe, eine prüft Rohdaten und Dateinamen,
eine wertet Kennzahlen aus und eine kontrolliert Hypothesen und Schlussfolgerungen.
Danach reviewt jede Person einen fremden Bereich.

Der Simulator-Score und die Buchstabennote sind **formatives technisches Feedback**, keine
Modulnote. Für die Laborleistung zählen zusätzlich Versuchsdesign, Nachvollziehbarkeit,
Fehleranalyse und die Grenzen der Aussage.

## 1. Was gemessen wird

Ein Batchlauf fährt eine Menge von Szenarien und schreibt Kennzahlen, die genau die
Fragen aus Stufe 0 beantworten:

| Frage | Kennzahl | Wo |
|---|---|---|
| Sicher? | `collision_count`, `personal_injury_count` | Zusammenfassung; bei einem Treffer ist die Einstufung immer D |
| Richtig? | Bestehensquote, `decision_accuracy`, unerwartete und verpasste Manöver | Zusammenfassung |
| Erkannt, ob es festhängt? | `false_alarm_count` (eingegriffen, obwohl Warten reicht) und `missed_intervention_count` (gewartet, obwohl Eingriff nötig) | Zusammenfassung, Bericht |
| Wirtschaftlich? | Gesamtkosten, Budgetquote, Remote-Assistance-Anrufe | Zusammenfassung, HTML |
| Kunden zufrieden? | `average_customer_satisfaction` | Zusammenfassung |
| Aufwand? | Werkzeugaufrufe, Modelltokens, Latenz | Zusammenfassung |
| Zuverlässig? | Bestehensquote und Kostenstreuung je Szenario bei `--repeats` | `scenario_stats` |

Ein Szenario **besteht** nur, wenn der erste inhaltliche Befehl passt, das erwartete
Ergebnis eintritt, keine Kollision auftritt **und** das Kostenbudget eingehalten wird.
Ein Agent, der immer Remote Assistance ruft, besteht deshalb nicht.

## 2. Ein Lauf, ein Bericht

```bash
AUTONOMY_RECOVERY_MODEL=none python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/released_sprint4.txt \
  --perception tracked --agent mein_agent:decide --output artifacts/experiments/teil-a-v1
```

Es entstehen `batch-report.md`, `batch-report.html` und `batch-result.json` (die
maschinenlesbare Quelle für alles) sowie je Szenario ein `result.json`. Öffnet die
HTML-Seite und beantwortet: Wie lautet die Einstufung? Was hat sich seit dem letzten Lauf
geändert? Was ist der größte Kostenposten? In
welchen Szenarien ist der Agent über dem Budget?

**Die Einstufung** ist Rückmeldung, keine Note. Sie beantwortet, ob die Abteilung mit eurem Agenten wirtschaftlich arbeitet
und ob die Kunden zufrieden sind: Bei einer Kollision oder einem Personenschaden gibt es
immer D; sonst zählen Bestehensquote, Budgetquote, Anteil der Remote-Assistance-Episoden
und Kundenzufriedenheit. Die Schwellen stehen in
[COMMANDS.md](../COMMANDS.md#budget-einstufung-und-auswertungswebsite).

**Der Fortschritt** steht oben im Bericht: Der Lauf vergleicht sich mit dem vorigen im
selben Ausgabeordner und nennt neu bestandene und neu gescheiterte Fälle; `verlauf.jsonl`
führt die Reihe fort (siehe [Prüfstand](../PRUEFSTAND.md#fortschritt-verfolgen)). Für
saubere Experimente bekommt jede Variante ihren eigenen Ordner, wie in Abschnitt 3.

## 3. Experimente sauber aufbauen

Ein Vergleich ist nur so gut wie sein Aufbau. Für jedes Experiment:

1. **Frage und Hypothese vorher aufschreiben.** „Prompt B senkt die Kosten, weil er
   Remote Assistance seltener wählt.“ Nicht: „mal sehen, was besser ist.“
2. **Eine Änderung pro Experiment.** Wer Prompt und Modell zugleich ändert, weiß nicht,
   was gewirkt hat.
3. **Eine Baseline mitführen.** Ohne Vergleichswert ist „14 von 25“ keine Aussage. Nehmt den
   Starter, die Referenzbaseline (`--agent baseline`) und euren Regelagenten mit.
4. **Gleiche Szenarien, gleiche Bedingungen.** Modell, Prompt, Szenariomenge und
   Umgebungsvariablen festhalten.
5. **Wiederholen bei Modellen.** `--repeats N`, mindestens 3, und die Streuung berichten.
6. **Seeds variieren.** Alle 61 Sprintfälle und alle 18 Familienvarianten sind öffentlich.
   Erzeugt Varianten mit `scripts/make_variants.py`, getrennt für `released_sprint4.txt` und
   `familien_alle.txt`; die Befehle stehen im [Szenarienkatalog](../SCENARIOS.md#robustheit-mit-seed-variationen).
   Nutzt vorab dokumentierte Entwicklungs-Seeds und nach dem Freeze weitere Seeds.
   Jeder Seed bekommt einen eigenen Ordner. `--repeats` ändert den Szenario-Seed nicht.

Vergleich zweier Läufe:

```bash
python3 -m autonomy_recovery_sim.tutorials.vergleich artifacts/experiments/regel-v1 artifacts/experiments/regel-v2
```

Beispielausgabe (Starter gegen Referenzbaseline auf `public.txt`, gekürzt):

```text
                                        starter        baseline
Einstufung                                    D               C
Bestanden                                 11/25           14/25
Gesamtkosten (EUR)                       447.35         1247.50
Remote-Assistance-Anrufe                      0               2
```

Lest die Tabelle gegen die Intuition: Die Baseline besteht mehr, kostet aber fast das
Dreifache. Wer nur „bestanden“ vergleicht, sieht die Hälfte.

## 4. Typische Denkfehler

| Fehler | Beispiel | Gegenmittel |
|---|---|---|
| **Rauschen für Effekt halten** | 2 von 3 statt 3 von 3 nach einer Promptänderung | mehr Wiederholungen, mehr Szenarien |
| **Szenarien auswendig behandeln** | Entscheidungstabelle nach ID oder Referenzlabel | Beobachtungen als Grundlage; Code-Review und weitere Seeds |
| **Nur eine Kennzahl beachten** | Bestehensquote steigt, Kosten verdoppeln sich | alle Kennzahlen der Tabelle in Abschnitt 1 |
| **Ausreißer verstecken** | ein Kollisionslauf fehlt im Bericht | Rohberichte unverändert abgeben |
| **Zu früh generalisieren** | „Modell A ist besser“ nach fünf Fällen | Grenzen der Aussage nennen |
| **Fehler nicht analysieren** | „scheitert manchmal“ | Fehler kategorisieren (siehe unten) |

## 5. Fehler kategorisieren

Eine Einstufung ohne Fehleranalyse erklärt nichts. Nehmt jedes fehlgeschlagene Szenario und
ordnet die **Ursache** ein:

| Kategorie | Erkennbar an | Beispiel |
|---|---|---|
| Falsche Untersuchung | fehlende oder unbeachtete Werkzeugergebnisse | Alter der Daten nicht gelesen |
| Falsche Entscheidung | Werkzeuge korrekt gelesen, falscher Befehl | Umfahren statt Warten |
| Ungültige Ausgabe | `agent_error`, Ablehnung | Parameter außerhalb der Grenzen |
| Falsche Abwägung | Befehl richtig, Budget überschritten | Anruf statt Regel-Engine |
| Modellproblem | Prosa statt Werkzeugaufruf, JSON-Fehler | schwaches Function Calling |
| Zufall | Ergebnis schwankt bei Wiederholung | Nichtdeterminismus |

Eine Häufigkeitstabelle über eure Fehler zeigt sofort, wo sich Verbesserung lohnt.

## 6. Reproduzierbarkeit

Jeder muss eure Zahlen nachvollziehen können. Haltet fest:

- **Befehle** wörtlich, mit allen Parametern (`--agent`, `--repeats`, `--output`).
- **Seeds** für Entwicklung und Abschlusslauf sowie Parameter des Variationsgenerators.
- **Version** des Codes (`git rev-parse HEAD`) und der Szenariomenge.
- **Modell und Endpunkt** (`AUTONOMY_RECOVERY_MODEL`, `AUTONOMY_RECOVERY_BASE_URL`), ohne den Schlüssel.
- **Prompt** im Wortlaut je Experiment, als Datei im Repository.
- **Rohdaten:** die unveränderten `batch-result.json` und Berichte aller Läufe.

Der Simulator ist deterministisch; nur das Modell ist es nicht. Damit lässt sich jeder
Regelagent bit-genau wiederholen und jeder Modellagent statistisch.

## 7. Bericht

Nutzt die Vorlage [`vorlagen/laborbericht.md`](vorlagen/laborbericht.md). Sie führt durch
Fragestellung, Methode, Ergebnisse, Fehleranalyse und Grenzen. Zwei Dinge unterscheiden
einen guten Bericht von einer Sammlung von Zahlen:

- **Er nennt, was nicht funktioniert hat** und warum. Das ist ein Ergebnis, kein Makel.
- **Er benennt die Grenzen der Aussage**: Welche Szenarien, welches Modell, wie viele
  Wiederholungen, was wurde nicht getestet?

## Aufgabe

1. Führt für **drei Varianten** `released_sprint4.txt` im Modell `tracked` und die
   Szenariofamilien (`familien_alle.txt`, alle 18 Varianten) aus: den Startstand aus L1, euren Agenten **ohne Modell** (Teil A,
   `AUTONOMY_RECOVERY_MODEL=none`) und denselben Agenten **mit Modell** (Teil B, mit
   `--repeats 3`). Wertet `erkennen.txt` zusätzlich als eigene Teilmenge für Fehlalarme und
   verpasste Eingriffe aus. Den Referenzadapter (`student_llm_agent.py`, nur Modell) nehmt ihr
   als Maßstab dazu.
2. Vergleicht sie mit dem Hilfsprogramm. Formuliert **drei Aussagen**, die durch die
   Zahlen gedeckt sind, und eine, die *nicht* gedeckt wäre (und warum nicht).
3. Kategorisiert die Fehler eures besten Agenten in der Tabelle aus Abschnitt 5.
4. Prüft die eingefrorenen Varianten mit weiteren Seeds und dokumentiert Seeds,
   Referenzprüfung und alle Ergebnisse. Die Aussage gilt für die getesteten Falltypen
   und Variationsbereiche, nicht für beliebige neue Verkehrssituationen.
5. Schreibt den Bericht nach der Vorlage.

## Team-Checkpoint

- Alle Aussagen im Bericht stützen sich auf Zahlen aus unveränderten Rohberichten.
- Das Team hat Baseline und Streuung berücksichtigt.
- Jede Person kann mindestens einen Fehlschlag samt Ursachenkategorie erklären.
- Jede Person kann sagen, was das Ergebnis **nicht** zeigt.
