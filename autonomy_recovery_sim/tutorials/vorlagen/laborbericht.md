# Laborbericht: Ein Recovery-Agent für den autonomen Kleinbus

**Gruppe / Namen:** ____________________

**Datum:** ____________________

**Commit des Codes (`git rev-parse HEAD`):** ____________________

## Teamarbeit und Reviews

Beschreibt knapp, wie die Arbeit verteilt, reviewed und integriert wurde. Die Tabelle
dokumentiert Schwerpunkte, keine vier isolierten Einzelabgaben.

| Teammitglied | Schwerpunkte | reviewter fremder Bereich | Beitrag zur Integration |
|---|---|---|---|
| | | | |
| | | | |
| | | | |
| | | | |

## 1. Fragestellung

Was wollt ihr herausfinden? Formuliert **eine bis drei** konkrete, prüfbare Fragen. Nicht „ein
guter Agent“, sondern z. B. „Senkt ein fester Untersuchungsablauf im Prompt die Kosten auf
`public.txt` gegenüber dem Ausgangsprompt?“

Verweist auf den freigegebenen Versuchsplan und erklärt begründet, falls Forschungsfrage,
Hypothese oder Messplan später geändert wurden.

## 2. Methode

### 2.1 Agenten

Beschreibt jede Variante knapp, so dass man sie nachbauen kann.

| Name | Art (Regel / LLM / Hybrid) | Kernidee | Datei |
|---|---|---|---|
| starter | Regel | wartet immer | `student_agent.py` (Ausgangszustand) |
| baseline | Regel | Referenzheuristik | `--agent baseline` |
| ... | | | |

Bei Modellagenten: Modell, Endpunkt, Temperatur (fest 0), Systemprompt im Wortlaut
(Anhang), Rundenlimit.

### 2.2 Szenarien und Messung

Welche Szenariomengen, wie oft wiederholt (`--repeats`)? Welche Kennzahlen (siehe
[Stufe 6](../06-evaluieren.md#1-was-gemessen-wird))?

### 2.3 Hypothesen

Vor den Läufen aufgeschrieben, je Experiment eine.

### 2.4 Reproduktion

Wörtliche Befehle für alle Läufe:

```bash

```

## 3. Ergebnisse

Eine Tabelle mit den **unveränderten** Kennzahlen aus `batch-result.json` (Einstufung, bestanden,
Budget, Kosten, Remote-Assistance-Anrufe, Kundenzufriedenheit, Werkzeugaufrufe, Tokens).

| Agent | Einstufung | Bestanden | Im Budget | Kosten (EUR) | Anrufe | Zufriedenheit | Fehlalarme | Verpasste Eingriffe |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

Für Teil A (regelbasiert) und Teil B (Sprachmodell) der Laboraufgabe getrennt auf
`erkennen.txt` **und** einer größeren Menge angeben; die Fehlalarm- und Verpasst-Quote gehört in
jeden Vergleich.

Bei Wiederholungen: Bestehensquote und Kostenstreuung je Szenario (Auszug oder Anhang).

Ihr dürft Abbildungen erzeugen, aber jede Zahl muss sich aus den Rohberichten ergeben. Nennt
die Quelle.

## 4. Fehleranalyse

Kategorisiert die Fehlschläge des besten Agenten (Kategorien aus
[Stufe 6](../06-evaluieren.md#5-fehler-kategorisieren)) mit Häufigkeit und **je einem
belegten Beispiel** (Szenario, Trace-Auszug).

| Kategorie | Anzahl | Beispiel (Szenario, Beleg) |
|---|---|---|
| | | |

Was funktioniert **nicht**, und warum?

## 5. Diskussion

- Wurde jede Hypothese bestätigt oder widerlegt? Welche Zahl belegt das?
- Was ist der Unterschied zwischen Regel-, Modell- und Hybridagent in euren Daten?
- Wo lag das Risiko (Sicherheit, Kosten, Streuung)?
- Was hat die Ergebnisse überrascht?

## 6. Grenzen

Was zeigt euer Ergebnis **nicht**? Denkt an: Szenariomenge (nur Hannover, nur diese
Fälle), Anzahl Wiederholungen, ein Modell, Modellannahmen im Kostenmodell (siehe
[COMMANDS.md](../../COMMANDS.md)), Overfitting auf das öffentliche Set.

## 7. Fazit

Drei Sätze: Was haben wir gefragt, was haben wir gefunden, was würden wir als Nächstes tun?

## Anhang

- Systemprompts im Wortlaut
- vollständige `batch-result.json`-Dateien (oder Verweis auf das Repository)
- Fehlerbeispiele aus dem Trace
