# Laboraufgabe: Agentic Autonomy Recovery

> **Team-Lernpfad:** Das Viererteam beginnt mit dem Pflichtkern in
> [tutorials/README.md](tutorials/README.md). Die späteren Stufen werden nicht vorab
> „abgearbeitet“, sondern liefern die Ergebnisse der regulären Sprints. Die Aufgabe unten
> und der Lernpfad gehören zusammen.

## Teamauftrag

Ihr bearbeitet die Aufgabe als **Team aus vier Studierenden**. Das Team entwickelt ein
gemeinsames Recovery-System: einen Agenten, der ohne und mit Sprachmodell läuft, und eine
gemeinsame Evaluationspipeline. Es werden nicht vier voneinander unabhängige Agenten abgegeben.

Arbeitsteilung ist ausdrücklich erwünscht, fachliche Silos nicht: Jede Implementierung wird
von einer zweiten Person reviewed, Rollen rotieren zwischen den Sprints und alle Mitglieder
müssen Architektur, Safety-Vertrag, Versuchsaufbau und zentrale Ergebnisse erklären können.
Der verbindliche Arbeitsmodus steht im [Team-Lernpfad](tutorials/README.md).

## Auftrag

Entwickelt einen werkzeugnutzenden Agenten, der erst bei einem durch den
Stillstandsmonitor erkannten **Deadlock-Verdacht** aktiviert wird. Er untersucht die
Verkehrslage, entscheidet zuerst, ob wirklich ein Eingriff nötig ist, und wählt dann einen
High-Level-Befehl (u. a. `WAIT`, `OVERTAKE`, `REPLAN_ROUTE`, `TURN_AROUND`, `PULL_OVER`,
`REQUEST_REMOTE_ASSISTANCE`, `SAFE_STOP`), siehe [`COMMANDS.md`](COMMANDS.md).

Der Agent erzeugt **keine Trajektorie** und steuert das Fahrzeug nicht direkt.
Sein Ergebnis ist ein validierter Befehl aus Name, Parametern und Begründung.
Regel- und Sicherheitsprüfung sowie der Ausführer bleiben Infrastruktur.

**Kostenmodell:** Personenschäden sind am teuersten, dicht gefolgt
von Materialschäden. Jeder Remote-Assistance-Anruf und jede Standzeit kostet die
Abteilung Geld. Kunden sind zufrieden, wenn sie schnell und sicher ans Ziel
kommen. Die Kennzahlen stehen in `result.json` (`costs`) und im Batchbericht.

## Lernziele

Nach dem Projekt könnt ihr:

1. die Agentenaufgabe von Fahrzeugregelung, Regelprüfung und Sicherheitsmonitor abgrenzen und
   begründen, welche Prüfung ins Programm und welche ins Modell gehört,
2. einen Stillstand anhand von Werkzeugdaten als regulären Halt oder echten Deadlock einordnen
   und einen sicheren, wirtschaftlich vertretbaren Eingriff wählen,
3. einen Agentenloop mit Werkzeugen, Kontext und Gedächtnis entwerfen und unzuverlässige
   Modellausgaben durch Budgets, Verträge und fail-safe begrenzen,
4. Werkzeugdaten, Freitext und die Selbstauskunft eines Fahrstacks als nicht vertrauenswürdig
   behandeln und gegen eine zweite Quelle prüfen,
5. eine widerlegbare Hypothese formulieren und einen fairen Vergleich von Regel- und
   Sprachmodellagent mit Baselines und Wiederholungen planen,
6. Sicherheit, Fehlalarme, verpasste Eingriffe, Befreiungsrate und Kosten getrennt messen,
   Streuung berücksichtigen und Ergebnisse reproduzierbar und mit ihren Grenzen berichten.

So hängen Lernziele und Lernpfad zusammen:

| Lernziel | Erarbeitet in | Ergebnis |
|---|---|---|
| 1 Abgrenzen | [Stufen 0](tutorials/00-grundlagen.md), [1](tutorials/01-recovery-agent-spielen.md), [L1](tutorials/L1-einfachster-agent.md) | Systemskizze, kommentierter Trace |
| 2 Halt einordnen, Eingriff wählen | [Stufe 1](tutorials/01-recovery-agent-spielen.md), [L2](tutorials/L2-regelagent.md), [L3](tutorials/L3-gedaechtnis.md) | Fehlalarm- und Verpasst-Quote auf `erkennen.txt` |
| 3 Agentenloop entwerfen | [L5](tutorials/L5-llm-agent.md), [L7](tutorials/L7-phasen-und-dynamik.md) | hybrider Agent, Tabelle der Änderungen |
| 4 Quellen prüfen | [Stufe 1](tutorials/01-recovery-agent-spielen.md) (F), [L4](tutorials/L4-selbst-wahrnehmen.md), [L6](tutorials/L6-alpamayo-misstrauen.md) | Fälle aus `uncertainty.txt` und `vla.txt` |
| 5 Vergleich planen | [Forschungsplan](tutorials/02a-forschungsplan.md), [L5](tutorials/L5-llm-agent.md) | freigegebener Versuchsplan |
| 6 Messen und berichten | [L1](tutorials/L1-einfachster-agent.md), [L8](tutorials/L8-unfaelle-und-schutzregeln.md), [Stufe 6](tutorials/06-evaluieren.md) | Rohberichte, Laborbericht |

## Bereitgestellte Infrastruktur

- autonomer Spurfolger bis zur Blockade,
- Deadlock-Erkennung nach konfigurierbarem Stillstand,
- deterministische Wahrnehmung mit Reichweite, Verdeckung und Tracks, wahlweise als fertige
  Lageurteile (`exact`) oder als Objektliste mit Messunsicherheit (`tracked`),
- ein Fahrstack-Mock nach dem Vorbild von NVIDIA Alpamayo, der sein Verhalten in Text begründet
  und sich dabei irren kann,
- High-Level-Befehle mit Schema, Regel- und Sicherheitsprüfung, darunter Manöver mit
  Checkpoints und eine physische Wende,
- zertifizierter Ausführer mit dynamischer Abbruchüberwachung; wie viel er abnimmt, legt der
  Prüfmodus fest (`strict`, `advisory`, `off`),
- Unfallfolgen mit Fahrzeugstatus und Unfallabwicklung in `advisory` und `off`,
- Kostenmodell (Standzeit, Remote Assistance, Schäden, Kundenzufriedenheit),
- Live-Ansicht, Einzel- und Batchlauf mit Fortschrittsvergleich,
- 61 Sprintfälle und sechs Szenariofamilien mit je drei Varianten,
- regelbasierte Baseline, OpenAI-kompatibler LLM-Adapter und ein Spielmodell ohne Schlüssel.

Diese Teile sind Infrastruktur und nicht die eigentliche Agentenleistung.

## Eure Aufgabe

Der Stillstandsmonitor ruft den Agenten nach wenigen Sekunden Stillstand, egal warum das
Fahrzeug steht. Er ist Infrastruktur und unterscheidet eine rote Ampel nicht von einem
Hindernis. **Eure erste und wichtigste Aufgabe ist deshalb die Einordnung des Halts:**
*Steckt das Fahrzeug wirklich fest und braucht einen Eingriff, oder ist Warten richtig?*
Erst danach entscheidet ihr, welcher Eingriff der passende ist.

Ihr entwickelt **einen** Agenten im [Tutorial-Track](tutorials/README.md#der-tutorial-track)
(`mein_agent.py`) und messt ihn in zwei Betriebsarten:

- **Teil A, ohne Sprachmodell:** Euer Agent entscheidet allein mit Werkzeugergebnissen und
  selbst geschriebenen Regeln. Das ist der Stand aus L1 bis L4, ergänzt um die Regeln aus L6
  bis L8. Gemessen wird mit `AUTONOMY_RECOVERY_MODEL=none`.
- **Teil B, mit Sprachmodell:** Derselbe Agent übergibt die offenen Fälle an ein Modell (ab
  [L5](tutorials/L5-llm-agent.md)). Euer Hebel ist die Arbeitsteilung: Was entscheiden die
  Regeln sicher, was ist offen, welches Lagebild und welche Werkzeuge bekommt das Modell, wie
  geht ihr mit Ablehnungen um, welcher Prompt, welches Modell. Der Referenzadapter in
  [`student_llm_agent.py`](student_llm_agent.py), bei dem allein das Modell entscheidet, dient
  als Vergleichsmaßstab.
- **Teil C, Vergleich:** Teil A gegen Teil B auf denselben Szenarien mit denselben Kennzahlen
  (siehe „Zu messen“), einschließlich der Fehlalarm- und Verpasst-Quote. Weil sich beide nur im
  Modell unterscheiden, zeigt der Vergleich, was das Modell tatsächlich beiträgt. Gemessen wird
  mit dem [Prüfstand](PRUEFSTAND.md), im Wahrnehmungsmodell `tracked` und auf den
  Szenariofamilien.

Nach der ersten Regelbaseline erstellt das Team vor weiteren Optimierungen einen
[Versuchsplan](tutorials/02a-forschungsplan.md). Er hält Forschungsfrage, widerlegbare
Hypothese, Vergleich, Szenariomengen, Kennzahlen, Rollen und Freeze-Regel fest. Änderungen
am Plan bleiben möglich, müssen aber begründet und versioniert werden.

Grundlage der Einordnung sind
[`erkennen.txt`](scenario_sets/erkennen.txt) und die Fälle mit Datenqualität in
[`uncertainty.txt`](scenario_sets/uncertainty.txt). Dort gibt es Fälle, in denen jedes Eingreifen
falscher Alarm ist (rote Ampel, Güterzug, Stau, geplanter Halt), und Gegenstücke, in
denen der Halt echt ist (ausgefallenes Signal, grüne Ampel mit Blockade). Hinweise: `get_traffic_control`,
`get_mission_context` (`mission_state`), `get_route_state` und die Qualitätsfelder der
Werkzeuge. Zur Einführung dient [L6 des Tutorial-Tracks](tutorials/L6-alpamayo-misstrauen.md).

Euer Agent soll in beiden Betriebsarten mindestens folgende Fragen behandeln:

- Liegt wirklich eine dauerhafte Blockade vor, oder genügt Warten?
- Ist die Route blockiert (Umweg) oder das Hindernis lokal passierbar?
- Wann lohnt sich Remote Assistance, wann `SAFE_STOP`, `PULL_OVER` oder das
  sichere Absetzen von Fahrgästen?
- Welche Fahrbahnmarkierung und Ausnahmeregel sind gemeldet?
- Reichen Sicht und seitlicher Sicherheitsabstand?
- Gibt es Gegenverkehr, überholenden Verkehr oder ungeschützte
  Verkehrsteilnehmende?
- Welche Parametergrenzen sind für einen Befehl vertretbar?
- Wann muss der Agent konservativ warten oder eskalieren, statt zu handeln?

Innerhalb von Teil B vergleicht ihr zusätzlich mindestens zwei sinnvoll begründete
Varianten, beispielsweise Prompts, Modelle, Lagebilder oder die Grenze zwischen sicheren und
offenen Fällen. Eine reine Einzelfalldemonstration reicht nicht.

## Sicherheitsvertrag

Der Simulator behandelt den Agenten als nicht vertrauenswürdig:

- höchstens 14 Werkzeugaufrufe und drei Entscheidungsversuche je Sitzung,
- Verkehrsregeln sind nie übersteuerbar (durchgezogene Linie, Gegenfahrbahn, Absperrung,
  Wegfahren nach einem Unfall),
- Parametergrenzen je Befehl (z. B. `WAIT` 1 bis 30 s, Manöver höchstens 15 km/h, 60 m und
  20 s),
- im Prüfmodus `strict` verlangen Manöver über die Fahrbahn Evidenz aus den Lagewerkzeugen, und
  die Abbruchbedingungen `oncoming_traffic`, `blocker_moves` und `collision_risk` werden immer
  überwacht; in `advisory` werden Lagebedenken nur gemeldet, in `off` entfällt auch die
  vorausschauende Überwachung,
- höchstens acht bis zwölf Befehle je Episode (je nach Szenario),
- bei Ausnahme, Zeitüberschreitung oder ungültiger Ausgabe immer `WAIT`.

Die Simulation ist ein Lehr- und Versuchsmodell, keine Rechtsauskunft und kein
Nachweis für den Einsatz im realen Straßenverkehr.

## Versuchsmengen

Die empfohlene Bearbeitung folgt den in [`SCENARIOS.md`](SCENARIOS.md) beschriebenen
kumulativen Sprintmengen. Die folgenden thematischen
Mengen bleiben für Tutorials, Diagnose und spätere Querschnittsanalysen erhalten:

- [`scenario_sets/demo.txt`](scenario_sets/demo.txt): drei erklärte Fälle,
- [`scenario_sets/public.txt`](scenario_sets/public.txt): öffentliche
  Entwicklungsfälle (25, inklusive Kostenabwägungen),
- [`scenario_sets/erkennen.txt`](scenario_sets/erkennen.txt): Steckt das Fahrzeug wirklich
  fest? Reguläre Halte (Ampel, Zug, Stau, geplanter Halt) und ihre Gegenstücke,
- [`scenario_sets/uncertainty.txt`](scenario_sets/uncertainty.txt): Datenqualität,
  Werkzeugausfälle, Prompt-Injection und ein Kontrollfall,
- [`scenario_sets/hannover.txt`](scenario_sets/hannover.txt): Hannover-typische Lagen auf
  OSM-Kartenmaterial (Abpfiff am Stadion, Marathon-Sperrung),
- [`scenario_sets/commands.txt`](scenario_sets/commands.txt): je ein Fall pro
  High-Level-Befehl,
- [`scenario_sets/vla.txt`](scenario_sets/vla.txt): VLA-Fahrstack, dessen Selbstauskunft sich
  irrt (ab Sprint 3),
- [`scenario_sets/mehrstufig.txt`](scenario_sets/mehrstufig.txt): Fälle, die nur mit dem ganzen
  Lösungsweg bestehen (vollständig ab Sprint 4),
- [`scenario_sets/familien_sichtbar.txt`](scenario_sets/familien_sichtbar.txt): je Familie ein
  empfohlener Einstiegsfall (Sprint 3),
- [`scenario_sets/familien_alle.txt`](scenario_sets/familien_alle.txt): alle 18 veröffentlichten
  Familienvarianten zum Entwickeln und Vergleichen,
- Seed-Variationen: gleiche Falltypen und Erfolgskriterien, aber veränderte Positionen,
  Geschwindigkeiten und Zeitpunkte ([`scripts/make_variants.py`](scripts/make_variants.py)).

Alle 61 Sprintfälle und alle 18 Familienvarianten sind von Anfang an zugänglich. Die
Sprintmengen empfehlen eine Lernreihenfolge; ihr könnt jederzeit weitere Fälle untersuchen.
Legt Entwicklungs-Seeds im Versuchsplan fest und prüft nach dem Freeze weitere Seeds.
Dokumentiert alle verwendeten Seeds und Rohberichte, damit eure Ergebnisse reproduzierbar sind.

Die Referenzbaseline ist ein Vergleichsmaßstab und löst bewusst nicht alle
Fälle. Ein Szenario besteht nur innerhalb seines Kostenbudgets; der Batchbericht fasst das
Ergebnis in einer Einstufung A bis D zusammen (siehe
[`COMMANDS.md`](COMMANDS.md#budget-einstufung-und-auswertungswebsite)).

Entscheidet anhand der Werkzeugdaten, nicht anhand von Szenario-IDs oder Referenzlabels.
Eine Entscheidungstabelle pro Szenario erfüllt die Aufgabe nicht; Seed-Variationen allein
verhindern solche Abkürzungen nicht. Begründet im Review, welche Beobachtung eure Entscheidung trägt.

## Zu messen

- Kollisionen, Personenschäden und dynamisch nicht stabilisierte Abbrüche,
- **Fehlalarme** (Eingriff, obwohl Warten reicht) und **verpasste Eingriffe** (gewartet, obwohl ein
  Eingriff nötig war), getrennt für Teil A und Teil B,
- Unfälle und ihre Abwicklung im Prüfmodus `off` (`incident_handling`, Unfallflucht),
- unerwartete und verpasste Manöver,
- erfolgreiche Befreiungen,
- Gesamtkosten, Remote-Assistance-Anrufe und Kundenzufriedenheit,
- Befehlsgenauigkeit,
- vollständige Lösungswege und Teilpunkte in mehrstufigen Szenarien,
- Werkzeug- und Entscheidungsversuche,
- Modellrunden, Latenz und Tokenverbrauch,
- qualitative Nachvollziehbarkeit der Begründung.

Alle Kennzahlen liefert der [Prüfstand](PRUEFSTAND.md). Optional lässt sich jede Messung im
VLA-Modus (`--vla`) wiederholen: Dann gibt es Objektklassen, Profile und Signalzustände nur als
Text eines Fahrstack-Modells.

Die zentrale Sicherheitskennzahl ist das **unerwartete Manöver**. Ein Agent, der
immer handelt, erreicht zwar eine hohe Befreiungsrate, löst die Aufgabe aber
nicht sicher. Ein Agent, der immer eskaliert, ist sicher, aber unwirtschaftlich.
Die beiden Fehlerarten der Einordnung sind Gegenspieler: Wer nie eingreift, hat keine
Fehlalarme, verpasst aber jeden echten Deadlock; wer immer eingreift, verpasst nichts,
löst aber überall Fehlalarme aus. Gut ist, wer beides niedrig hält.

## Ergebnisse des Teams

Das Labor ist unbenotet. Am Ende steht einmal pro Team:

1. ein lauffähiger Agent (`mein_agent.py`), der ohne Sprachmodell (Teil A) und mit
   Sprachmodell (Teil B) läuft, mit dokumentierter Konfiguration und einer Tabelle
   „Lektion oder Änderung, Hypothese, Messung vorher und nachher“,
2. der Versuchsplan, bei Änderungen versioniert,
3. unveränderte Rohberichte der Batchläufe,
4. Skripte oder Befehle zur Reproduktion aller Tabellen und Abbildungen,
5. ein Laborbericht mit Fragestellung, Methode, Ergebnissen, Fehleranalyse und Grenzen,
6. der Vergleich von Teil A und Teil B mit Fehlalarm- und Verpasst-Quote und einer Analyse,
   welche Fälle das Modell besser oder schlechter löst als die Regeln allein und warum,
7. eine kurze Demonstration mit einer weiteren Seed-Variation eines veröffentlichten Falls, an der alle Teammitglieder
   fachlich beteiligt sind.

API-Schlüssel, personenbezogene Daten und generierte Laufartefakte gehören
nicht in das Repository.

## Rückmeldung statt Note

Ihr sollt jederzeit wissen, **wie gut** euer Ansatz funktioniert, **wo** er scheitert und
**ob** er sich verbessert. Dafür gibt es vier Quellen:

1. **Nach jedem Batchlauf:** Der [Prüfstand](PRUEFSTAND.md) zeigt Kennzahlen, eine Einstufung
   A bis D, einen Befund je Szenario mit dem wichtigsten Grund zuerst und bei Unfällen einen
   Rückblick auf die Entscheidung davor. Läuft ihr wiederholt in denselben Ausgabeordner, nennt
   der Bericht den **Fortschritt seit dem letzten Lauf**: neu bestandene und neu gescheiterte
   Fälle, Kollisionen, Kosten und einen Verlauf über die letzten Läufe.
2. **In jeder Lektion:** Richtwerte zeigen, was ein gut gelöster Stand erreicht.
3. **An jedem Team-Checkpoint:** Die Betreuung bespricht mit euch Ergebnis, Trace und
   Zusammenhänge; dabei kann jede Person zu jedem Teil befragt werden.
4. **Zum Abschluss:** Läufe mit weiteren Seeds zeigen, wie robust euer eingefrorener Agent
   auf veränderte Bedingungen der bekannten Szenarien reagiert. Seeds und Ergebnisse bleiben
   nachvollziehbar; daraus folgt keine Aussage über beliebige neue Falltypen.

Die Einstufung A bis D ist eine Zusammenfassung, keine Note. Eine Kollision ergibt immer D:
Sicherheit geht vor, und eine hohe Befreiungsrate gleicht einen Unfall nicht aus.

### Woran ihr einen guten Agenten mit Sprachmodell erkennt

Die folgenden Merkmale helfen bei der Selbstprüfung von Teil B. Entscheidend ist, was der Code
tut und was die Messung zeigt, nicht wie umfangreich der Prompt ist.

| Merkmal | Erfüllt, wenn … | Sichtbar in |
|---|---|---|
| Robuste Schleife | Ablehnungen und Werkzeugfehler gehen als Daten an das Modell zurück; Rundenlimit und Ende ohne Entscheidung sind bewusst gelöst; ohne Modell bleibt der Agent lauffähig | Code, Befunde ohne `Agentenfehler` |
| Kontext und Werkzeuge | Lagebild und Werkzeugangebot sind gewählt, nicht übernommen, und ihr Effekt auf Tokens und Genauigkeit ist gemessen | Tabelle der Änderungen, Vergleich zweier Läufe |
| Arbeitsteilung Programm und Modell | Harte Grenzen und klare Fälle stehen im Programm, Abwägungen beim Modell; die Aufteilung ist begründet und am Vergleich von Teil A und Teil B gemessen | Code, Laborbericht |
| Gedächtnis über Sitzungen | Der Agent nutzt Verlauf und Zusatzinformationen und schafft mehrstufige Lösungswege; kein Zustand, der Szenarien überdauert | Lösungswege im Prüfstand, Code |
| Umgang mit unzuverlässigen Quellen | Aussagen aus Freitext und Fahrstack-Selbstauskunft werden gegen eine zweite Quelle geprüft; Injektionen bleiben wirkungslos | Fälle aus `uncertainty.txt` und `vla.txt` |
| Messung statt Vermutung | Jede Änderung hat Vorhersage, Messung vorher und nachher und bei Sprachmodellen Wiederholungen | Lab-Journal, Fortschritt im Bericht |

## Empfohlener Arbeitsablauf

1. Quickstart und Demo-Menge gemeinsam reproduzieren.
2. Werkzeugergebnisse und Safety-Vertrag im Team erklären.
3. Eine konservative Regelbaseline bauen und messen.
4. Forschungsfrage, Hypothese und Versuchsplan vor weiterer Optimierung freigeben lassen.
5. Regel-, LLM-, Szenario- und Evaluationsarbeit parallelisieren und gegenseitig reviewen.
6. Öffentliche Fälle auswerten und Fehler kategorisieren.
7. Strategie gezielt verbessern, nicht einzelne IDs auswendig behandeln.
8. Finale Konfiguration einfrieren und als Team reproduzierbar dokumentieren.
