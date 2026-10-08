# Team-Lernpfad: Agentic AI mit AutonomyRecoverySim

Dieser Lernpfad führt euer **Viererteam** von „Was ist ein Agent?“ bis zu einem
gemeinsam entwickelten und gemessenen Recovery-System. Er ist kein Stapel von
Einzelübungen: Ihr verantwortet als Team eine Regelbaseline, einen LLM-Agenten, die
Szenarien und die Evaluation. Arbeit darf aufgeteilt werden, das Verständnis des
Gesamtsystems nicht.

Den technischen Kern bildet der **Tutorial-Track L1 bis L8**: Ein Agent wächst von Lektion
zu Lektion, vom festen Befehl bis zum hybriden Agenten mit eigenen Schutzregeln. Darum
herum stehen Bootcamp, Forschungsplan und Evaluation.

```text
 0  Grundlagen              Gemeinsames Systembild                    (Bootcamp, 30 min)
 1  Agent spielen           Lage gemeinsam untersuchen                (Bootcamp, 75 min)
 L1 Einfachster Agent       Schnittstelle und Messung                 (Sprint 1, 45 min)
 L2 Regelagent              Werkzeuge und Entscheidungsbaum           (Sprint 1, 90 min)
 L3 Gedächtnis              Verlauf, Ablehnungen, mehrere Schritte    (Sprint 1, 90 min)
    Forschungsplan          Frage, Hypothese und Messplan             (Sprint 1, 60 min)
 L4 Selbst wahrnehmen       Objektliste mit Messunsicherheit          (Sprint 2, 120 min)
 L5 LLM-Agent               Hybrid: Regeln plus Sprachmodell          (Sprint 2, 120 min)
 L6 Alpamayo misstrauen     Quellen und Datenqualität prüfen          (Sprint 3, 90 min)
 L7 Phasen und Dynamik      Checkpoints, Wenden, Lagen ändern sich    (Sprint 3, 120 min)
 L8 Unfälle, Schutzregeln   Unfall abwickeln, rote Linien             (Sprint 4, 90 min)
 6  Evaluieren              Eingefroren messen und berichten          (Sprint 4, 120 min)
```

Die Zeiten sind **gemeinsame Teamzeit** für den Pflichtumfang, keine Zeit pro Person.
Vertiefungen und die eigentliche Implementierung kommen zusätzlich innerhalb der
Sprints hinzu.

Alle 61 Sprintfälle und alle 18 Familienvarianten sind von Anfang an zugänglich.
Die Sprintzuordnung empfiehlt eine Bearbeitungsreihenfolge. Nutzt am Sprintende jeweils
`released_sprint1.txt` bis `released_sprint4.txt` als kumulativen Regressionstest;
Zuordnung und fachliche Checkpoints stehen im [Szenarienkatalog](../SCENARIOS.md).

Welche Lernziele jede Stufe trägt und welches Ergebnis dazu gehört, zeigt die Zuordnung in der
[Laboraufgabe](../ASSIGNMENT.md#lernziele).

## Die Idee dahinter

Wer einen Agenten nur *benutzt*, glaubt schnell, dass er „irgendwie denkt“. Wer ihn
*baut und misst*, versteht, woraus er besteht: aus einer Schleife, Werkzeugen, einem
Gedächtnis und Regeln, die ihn begrenzen. Deshalb beginnt der Pfad bei euch selbst:

1. **Erst selbst Agent sein** (Stufe 1). Ihr erlebt dieselbe Aufgabe, dieselben
   Werkzeuge und dieselben Ablehnungen, die später euer Programm erlebt.
2. **Dann ohne Sprachmodell** (L1 bis L4). Ein Regelagent zeigt, was Werkzeuge, Budgets
   und Verträge leisten. Ab L4 rechnet er mit verrauschten Messungen statt fertiger Urteile.
3. **Dann das Sprachmodell** (L5), als Ergänzung der Regeln und mit einem Maßstab, an dem
   ihr es messt.
4. **Zuletzt die schweren Fälle** (L6 bis L8): Quellen, die sich irren, Lagen, die sich
   ändern, und ein Ausführer, der euch nicht mehr schützt. Dort liegen die eigentlichen
   Erkenntnisse: Ein Agent, der im Normalfall funktioniert, ist noch kein guter Agent.

## Der Tutorial-Track

- **Ein Agent für den ganzen Track.** Ihr arbeitet in einer Datei `mein_agent.py` im
  Wurzelverzeichnis und startet sie mit `--agent mein_agent:decide`.
- **Startstände.** Zu jeder Lektion gibt es unter [`track/`](track/) einen Startstand, der der
  Lösung der vorigen Lektion entspricht. Wer zurückliegt, setzt damit neu an; wer weiter ist,
  baut auf dem eigenen Stand weiter.
- **Richtwerte.** Jede Lektion nennt, was ein gut gelöster Stand erreicht. Sie dienen der
  Orientierung; das Labor ist unbenotet. Ob ihr besser werdet, zeigt euch jeder Batchlauf
  im Abschnitt „Fortschritt seit dem letzten Lauf“.
- **Erweitere selbst.** Jede Lektion endet mit Ideen für euren Agenten. Neue Befehle
  gehören nicht dazu: Die Befehle sind der zertifizierte Ausführer, ihr verbessert die
  Entscheidungen.

Die früheren Stufen 2 bis 5 stehen weiter im [Archiv](archiv/README.md).

## So arbeitet ihr als Viererteam

Die Stufen verwenden drei Kennzeichnungen:

- **Pflicht:** Das Team bearbeitet den Abschnitt gemeinsam oder führt die Ergebnisse
  gemeinsam zusammen.
- **Arbeitsteilig:** Mitglieder bearbeiten verschiedene Teile und erklären sie
  anschließend dem Team.
- **Vertiefung:** Optional, falls es zur Forschungsfrage oder zu eurem Arbeitsstand passt.

Für eine Etappe könnt ihr vier Arbeitsrollen vergeben: **Bedienung/Implementierung**,
**Safety-Prüfung**, **Messung/Trace** und **Dokumentation**. Die Rollen rotieren spätestens
im nächsten Sprint. Sie sind keine dauerhaften Zuständigkeiten. Beim Checkpoint zieht die
Betreuung zufällig eine Person, die Ergebnis und Zusammenhänge erläutert.

Jede Stufe erzeugt genau **eine gemeinsame Teamabgabe**. Vier identische Journale oder
vier getrennte Agenten sind nicht erforderlich.

## Lernrhythmus in jeder Stufe

Jede Stufe folgt demselben Rhythmus, dem **Vorhersage-Beobachtung-Erklärung-Zyklus**:

1. **Vorhersagen.** Schreibt auf, was passieren wird, *bevor* ihr etwas startet.
2. **Beobachten.** Führt es aus und notiert, was tatsächlich passiert ist.
3. **Erklären.** Wenn Vorhersage und Beobachtung abweichen, ist das der Lerngewinn.
   Sucht die Ursache in `result.json`, im Agent-Trace oder im Quelltext.

Dafür gibt es das gemeinsame [Lab-Journal](vorlagen/lab-journal.md). Es ist kurz und
wird später die Grundlage für euren [Laborbericht](vorlagen/laborbericht.md). Haltet pro
Eintrag fest, wer Bedienung, Safety, Messung und Dokumentation übernommen hat.

Jede Stufe endet mit einem **Checkpoint**: konkrete Dinge, die ihr zeigen können
müsst. Wenn ihr einen nicht erfüllt, geht zurück, bevor ihr weitermacht.

## Voraussetzungen

- Python 3 und ein Terminal. Für L5 optional ein Zugang zu einem OpenAI-kompatiblen
  Modell (siehe [QUICKSTART](../QUICKSTART.md)); ohne Schlüssel nutzt ihr das Spielmodell.
- Ihr arbeitet im Wurzelverzeichnis des Repositories. Kurzer Selbsttest:

  ```bash
  python3 -m unittest tests.test_autonomy_recovery_sim
  python3 -m autonomy_recovery_sim validate autonomy_recovery_sim/scenarios
  ```

## Wegweiser und Teamabgaben

| Phase | Text | Modus | Gemeinsame Abgabe |
|---|---|---|---|
| Bootcamp | [0 · Grundlagen](00-grundlagen.md) | Pflicht, gemeinsam | erklärtes Systembild |
| Bootcamp | [1 · Recovery Agent spielen](01-recovery-agent-spielen.md) | Pflichtkern + Vertiefung | eine begründete manuelle Entscheidung |
| Sprint 1 | [L1 · Einfachster Agent](L1-einfachster-agent.md) | Pflicht, gemeinsam | gemessener Nullpunkt |
| Sprint 1 | [L2 · Regelagent](L2-regelagent.md) | Pflicht, Paararbeit | Regelagent mit Messwert |
| Sprint 1 | [L3 · Gedächtnis](L3-gedaechtnis.md) | Pflicht, Paararbeit | mehrstufiger Agent mit Eskalationsleiter |
| Sprint 1 | [Forschungsplan](02a-forschungsplan.md) | Pflicht, gemeinsam | freigegebener Versuchsplan |
| Sprint 2 | [L4 · Selbst wahrnehmen](L4-selbst-wahrnehmen.md) | Pflicht, arbeitsteilig | Agent im Modell `tracked` |
| Sprint 2 | [L5 · LLM-Agent](L5-llm-agent.md) | Pflicht, Paararbeit und Review | hybrider Agent plus kontrollierter Vergleich |
| Sprint 3 | [L6 · Alpamayo misstrauen](L6-alpamayo-misstrauen.md) | Pflicht, arbeitsteilig | Quellen- und Datenprüfung |
| Sprint 3 | [L7 · Phasen und Dynamik](L7-phasen-und-dynamik.md) | Pflicht, gemeinsam | Agent für die Szenariofamilien |
| Sprint 4 | [L8 · Unfälle und Schutzregeln](L8-unfaelle-und-schutzregeln.md) | Pflicht, arbeitsteilig | Unfallabwicklung und gemessene rote Linien |
| Sprint 4 | [6 · Evaluieren](06-evaluieren.md) | Pflicht, gemeinsam | reproduzierbarer Abschlussvergleich |

Zum Nachschlagen: [Spickzettel](CHEATSHEET.md) und [Glossar](GLOSSAR.md). Die Grundlagen zu
Agentic AI stehen im [Skript zur Vorlesung](../../docs/AGENTIC-AI.md). Wie ihr euren
Agenten gegen alle Szenarien testet und den Bericht lest, steht im
[Prüfstand](../PRUEFSTAND.md). Die
Aufgabenstellung des Labors steht in [ASSIGNMENT.md](../ASSIGNMENT.md), alle Befehle
in [COMMANDS.md](../COMMANDS.md).

## Wege für Vorkenntnisse

- **Ihr kennt LLM-APIs schon:** Übernehmt in Stufe 0 und L5 die Erklär- oder Reviewrolle,
  statt sie zu überspringen.
- **Ihr habt wenig Programmiererfahrung:** Übernehmt zunächst Bedienung, Messung oder
  Dokumentation und arbeitet in L2 und L3 im Paar. Bis zum Abschluss muss jede Person
  mindestens eine Änderung am Agenten oder an der Auswertung nachvollzogen haben.
- **Ihr habt keinen Modellzugang:** Der ganze Track ist ohne Schlüssel machbar. In L5 nutzt ihr
  das Spielmodell (`AUTONOMY_RECOVERY_MODEL=spielmodell`); ohne Modell entscheiden die Regeln
  allein. Für den echten Modellvergleich sprecht mit eurer Betreuung.

## Sprintregeln

- Am Anfang jedes Sprints nennt ihr Rollen, Ziel und eine prüfbare Hypothese.
- Am Ende integriert ihr auf dem gemeinsamen Stand; lose Einzelprototypen sind kein
  Sprint-Ergebnis.
- Mindestens eine Person reviewt einen Bereich, den sie nicht selbst implementiert hat.
- Alle vier Teammitglieder müssen Architektur, Safety-Vertrag, Versuchsaufbau und die
  wichtigsten Ergebnisse erklären können.
- Nach Freigabe des Abschlussversuchs werden Agent, Prompt, Modellkonfiguration und
  Szenariomenge eingefroren. Änderungen erfordern einen neuen, getrennten Lauf.

## Regeln, damit die Messung etwas bedeutet

- **Keine Entscheidungstabellen nach Szenario-ID.** Der Agent entscheidet anhand seiner
  Beobachtungen. Prüft bekannte Falltypen mit mehreren Seeds; ein Seed allein verhindert
  das Auswendiglernen von Szenario-IDs nicht.
- **Schlüssel gehören nie ins Repository und nie in einen Chat.**
- **Rohberichte nicht nachbearbeiten.** Alle Tabellen im Bericht müssen sich aus den
  unveränderten Läufen wiederherstellen lassen.
