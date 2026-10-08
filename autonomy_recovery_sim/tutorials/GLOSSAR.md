# Glossar

**Abbruchbedingung.** Bedingung, bei der ein laufendes Manöver sicher abgebrochen wird
(`oncoming_traffic`, `blocker_moves`, `collision_risk`). Der Ausführer überwacht sie immer,
unabhängig vom Agenten.

**Agent.** Programm, das ein Sprachmodell in eine Schleife einbaut, ihm Werkzeuge gibt und
seine Vorschläge begrenzt ausführt. Siehe [Stufe 0](00-grundlagen.md).

**Agentenloop.** Die Schleife aus Modellaufruf, Werkzeugausführung und erneutem
Modellaufruf, bis das Modell entscheidet oder ein Limit greift.

**Agent-Trace.** Protokoll einer Sitzung in `result.json`: Werkzeugaufrufe,
Entscheidungsversuche und Modellrunden in Reihenfolge.

**Auslöser (Trigger).** Regel im Szenario, die einen Akteur reagieren lässt, sobald das Ego
eine Bedingung erfüllt, etwa ausschert. So wird der Grund einer Blockade erst beim
Überholversuch sichtbar. Jeder Auslöser muss fair sein: vorher mit einem Werkzeug
erkennbar. Siehe [L7](L7-phasen-und-dynamik.md).

**Ausführer.** Der zertifizierte Teil des Simulators, der einen freigegebenen Befehl in
Fahrbewegung umsetzt. Er ist nicht der Agent.

**Baseline.** Vergleichswert. Hier die Referenzheuristik `--agent baseline`; sie ist Maßstab,
keine Musterlösung.

**Batchlauf.** Auswertung vieler Szenarien mit einem Agenten: `python3 -m autonomy_recovery_sim batch …`.

**Befehl (High-Level-Befehl).** Eine der 24 Anweisungen, die ein Agent geben darf, z. B.
`WAIT`. Kein Lenken, kein Bremsen. Siehe [COMMANDS.md](../COMMANDS.md).

**Checkpoint.** Haltepunkt in einem Phasenmanöver (`PEEK_OUT`, `OVERTAKE`). Dort wird der
Agent erneut gerufen (`trigger.type = "CHECKPOINT"`) und entscheidet mit `RESUME` oder einem
anderen Befehl, während die Uhr weiterläuft.

**Chain of Causation (CoC).** Begründung eines VLA-Fahrstacks in Text: erst die Ursache,
dann die Entscheidung („Ein Lieferwagen blockiert die Spur, also halte ich“). Sie erklärt
das Verhalten, muss aber nicht stimmen. Hier über `get_vla_output`.

**Budget.** Obergrenze, hier in dreierlei Sinn: **Werkzeugbudget** (Aufrufe je Sitzung),
**Befehlsbudget** (Befehle je Episode) und **Kostenbudget** (Euro je Szenario).

**Deadlock.** Das Fahrzeug steht und kommt nicht weiter. Der Stillstandsmonitor erkennt es
nach einigen Sekunden und ruft den Agenten.

**Episode.** Ein Lauf eines Szenarios vom Start bis zum Ende, mit ggf. mehreren Sitzungen.

**Evidenz / Beleg.** Werkzeugergebnisse, auf die sich eine Entscheidung stützt. Für Manöver
sind im Prüfmodus `strict` die sieben Lagewerkzeuge Pflicht (im Wahrnehmungsmodell
`tracked` die drei Messwerkzeuge).

**Einstufung.** Zusammenfassung eines Batchlaufs als A bis D aus Sicherheit, Bestehens- und
Budgetquote, Leitstellenanteil und Zufriedenheit. Rückmeldung, keine Note: Das Labor ist
unbenotet. Eine Kollision ergibt immer D.

**Fail-safe.** Festes, sicheres Ersatzverhalten bei Fehlern. Hier `WAIT` (5 s).

**Fortschritt.** Vergleich eines Batchlaufs mit dem vorigen im selben Ausgabeordner: mehr
oder weniger bestanden, welche Fälle neu bestanden oder neu gescheitert sind. Der Verlauf
steht in `verlauf.jsonl`. Siehe [Prüfstand](../PRUEFSTAND.md#fortschritt-verfolgen).

**Function Calling.** Schnittstelle, über die ein Modell strukturierte Werkzeugaufrufe
(Name und JSON-Argumente) statt Prosa liefert.

**Guardrail.** Prüfung im Programm, die ein Agent nicht umgehen kann (Schema, Regeln,
Sicherheit, Budgets).

**Halluzination.** Vom Modell erfundene Aussage, die nicht durch Daten gedeckt ist.

**Hybridagent.** Agent, der Regeln für einfache und harte Fälle und ein Modell für
schwierige Abwägungen nutzt.

**Injektion (Prompt-Injection).** Text in den Daten, der sich als Anweisung ausgibt und ein
Modell zu ungewollten Handlungen verleiten soll. Gegenmittel: Daten sind nie Anweisungen.

**Kontext.** Alle Nachrichten, die einem Modell in einer Runde mitgegeben werden. Begrenzt
und kostenpflichtig.

**Kontextgestaltung.** Die bewusste Auswahl dessen, was in der Nachrichtenliste steht: welche
Teile der Lage, welche Werkzeuge, welche Rückmeldungen. Siehe [L5](L5-llm-agent.md).

**Konsole (Recovery Console).** Bedienfeld der Live-Oberfläche, in dem ein Mensch die
Agentenrolle übernimmt.

**Autonomy Recovery Agent.** Der Agent dieses Projekts: Er wählt bei einem
Deadlock einen High-Level-Befehl. Er fährt nicht selbst und kann bei Bedarf
separat Remote Assistance durch einen menschlichen Operator anfordern.

**Lektion (L1 bis L8).** Ein Schritt im Tutorial-Track; jede Lektion baut den Agenten der
vorigen aus. Siehe [Lernpfad](README.md).

**Lösungsweg.** Geordnete Folge von Schritten, die eine mehrstufige Lage löst
(`reference.sequence`). Ein Schritt zählt nur mit einem erfolgreichen Befehl; bestanden ist der
Fall nur mit dem ganzen Weg. Siehe [Prüfstand](../PRUEFSTAND.md).

**Manöver.** Befehl, der das Fahrzeug über die Fahrbahn bewegt (`NUDGE_AROUND_OBSTACLE`,
`CHANGE_LANE`, `AVOID_TEMPORARY_OBSTRUCTION`, `CROSS_LOW_RISK_OBJECT`).

**Meta-Aktion.** Grobe Fahrabsicht eines VLA-Fahrstacks wie `STOP`, `YIELD`,
`FOLLOW_LANE` oder `LANE_CHANGE_LEFT`; feiner als ein Recovery-Befehl, gröber als eine
Trajektorie.

**Phasenmanöver.** Befehl, der in Phasen abläuft und an Checkpoints anhält (`PEEK_OUT`,
`OVERTAKE`). Bricht der Ausführer ab, fährt er selbst in die Spur zurück (`ABORT_TO_LANE`).

**Nichtdeterminismus.** Dasselbe Modell liefert bei gleicher Eingabe verschiedene Antworten.
Der Simulator ist deterministisch, das Modell nicht.

**Observation Age.** `observation_age_s`: Alter der Daten in einem Werkzeugergebnis.

**Phantom.** Objekt, das die Wahrnehmung meldet, das physisch aber nicht existiert.

**Prüfmodus (Guardrails).** Wie streng die Prüfung vor der Ausführung ist: `strict` lehnt
Manöver ohne Belege ab, `advisory` warnt nur, `off` prüft nur noch die harten Regeln. In
`advisory` und `off` kann es knallen, und der Agent muss es erkennen. Siehe
[L8](L8-unfaelle-und-schutzregeln.md).

**ReAct.** Muster, bei dem das Modell vor jedem Werkzeugaufruf kurz begründet, was es erwartet
(„Reasoning and Acting“), und danach Erwartung und Ergebnis vergleicht.

**Regel-Engine.** Deterministisches Regelwerk, an das `ESCALATE_TO_RULE_ENGINE` übergibt.

**Richtwert.** Ergebnis, das ein gut gelöster Stand einer Lektion erreicht. Orientierung,
kein Bestehenskriterium.

**Remote Assistance.** Leitstelle, die bei Bedarf hilft und pro Anruf Geld kostet.

**Sitzung.** Ein Aufruf des Agenten mit seinem Kontext, Werkzeug- und Versuchsbudget.
Eine Episode kann mehrere Sitzungen haben.

**Startstand.** Datei unter [`track/`](track/), mit der eine Lektion beginnt; sie entspricht
der Lösung der vorigen Lektion.

**Streuung.** Schwankung der Ergebnisse über Wiederholungen; bei Modellen zu berichten.

**Szenario.** Eine Ausgangslage mit Straße, Akteuren, Mission, Regeln und erwartetem
Ergebnis (JSON in `autonomy_recovery_sim/scenarios/`).

**Szenariofamilie.** Eine Lage (F1 bis F6) in drei Varianten: eine sichtbare zum Entwickeln
(`familien_sichtbar.txt`), zwei verdeckte zum Prüfen.

**Unfallabwicklung.** Was nach einem Aufprall zu tun ist: anhalten, `SECURE_SCENE`, dann
`REPORT_INCIDENT`. Weiterfahren ohne Meldung zählt wie ein Personenschaden.

**VLA (Vision-Language-Action-Modell).** Fahrmodell, das Kamerabilder liest und Text sowie
eine Trajektorie ausgibt, im Labor NVIDIA Alpamayo 1.5. Im Simulator als regelbasierter Mock
(`vla_mock.py`) in den Szenarien aus `scenario_sets/vla.txt`.

**Vertrauensgrenze.** Grenze zwischen dem, was ein Agent *glauben* darf (Regeln, Katalog) und
dem, was er nur als *Daten* behandelt (Werkzeugergebnisse, Freitext).

**Wahrnehmungsmodell.** Wie die Werkzeuge die Lage liefern: `exact` mit fertigen Urteilen
(`get_blocker`, …), `tracked` als Objektliste mit Unsicherheit, Sichtabdeckung und Karte im
Stil eines Fahrstacks wie Autoware. Schalter `--perception`.

**Werkzeug (Tool).** Funktion mit Name, Beschreibung und Parameterschema, die ein Agent
aufrufen darf. Hier im Wahrnehmungsmodell `exact` zwölf lesende Werkzeuge und die Entscheidung
`submit_decision` (in `tracked` drei Messwerkzeuge statt der sieben Lagewerkzeuge);
in Szenarien mit VLA-Fahrstack kommen `get_vla_output` und `get_camera_caption` dazu.
