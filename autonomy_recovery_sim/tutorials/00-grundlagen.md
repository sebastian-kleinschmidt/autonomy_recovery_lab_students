# Stufe 0: Was ist ein Agent?

**Teamzeit:** 30 Minuten · **Phase:** Bootcamp · **Modus:** Pflicht, gemeinsam ·
**Voraussetzung:** keine · **Schlüssel:** nein

Nach dieser Stufe könnt ihr erklären, woraus ein Agent besteht, warum man ihn
begrenzen muss und woran man merkt, ob er gut ist. Alles hier wird in den nächsten
Stufen konkret. Lest zuerst, und kommt bei Unklarheiten zurück.

Diese Stufe ist die praktische Kurzfassung für euer Projekt. Einordnung, Herkunft der
Muster, Rechtsrahmen und Literatur stehen im Skript
[„Was ist Agentic AI?“](../../docs/AGENTIC-AI.md) zur Vorlesung.

## Teammodus

Lest die Abschnitte arbeitsteilig, erklärt sie euch aber gegenseitig: Je eine Person
übernimmt Agentenloop, Werkzeuge/Gedächtnis, Guardrails/Fehler und Evaluation/Projekt.
Zeichnet danach gemeinsam das Gesamtsystem, ohne die Abbildung unten abzuschreiben.
Die gemeinsame Skizze ist eure Abgabe für diese Stufe.

## 1. Vom Sprachmodell zum Agenten

Ein **Sprachmodell** (LLM) bekommt Text und liefert Text. Es hat keine Augen, keine
Hände und keinen Speicher außer dem Text, den ihr ihm gebt. Es kann keine Uhr lesen,
keine Datei öffnen und kein Auto bewegen.

Ein **Agent** ist ein Programm, das ein Sprachmodell in eine **Schleife** einbaut und
ihm **Werkzeuge** gibt. Das Modell entscheidet, was als Nächstes getan wird. Das
Programm führt es aus und meldet das Ergebnis zurück. Der Unterschied zum Chat:

| | Chat | Agent |
|---|---|---|
| Ablauf | eine Frage, eine Antwort | viele Runden, bis eine Aufgabe erledigt ist |
| Information | nur, was ihr eintippt | fragt sich Information selbst über Werkzeuge |
| Wirkung | Text | Aktionen in einem System |
| Kontrolle | ihr lest die Antwort | Programm und Regeln begrenzen, was ausgeführt wird |

## 2. Der Agentenloop

```text
            ┌─────────────────────────────────────────────────┐
            │                                                 │
   Aufgabe ─┴─▶ Modell ──▶ Werkzeugaufruf? ──ja──▶ Programm führt aus
              (denkt)          │                       │
                               │ nein                  ▼
                               ▼                 Ergebnis zurück ans Modell
                        Endentscheidung ◀──────────────┘
```

1. Das Modell bekommt die Aufgabe und eine Liste der verfügbaren Werkzeuge.
2. Es antwortet entweder mit einem **Werkzeugaufruf** („ruf `get_blocker` auf“) oder
   mit einer **Endentscheidung**.
3. Bei einem Aufruf führt *euer Programm* das Werkzeug aus, hängt das Ergebnis an die
   Nachrichtenliste und fragt das Modell erneut.
4. Das wiederholt sich, bis das Modell entscheidet oder ein **Budget** erschöpft ist.

Wichtig: **Das Modell führt nie selbst etwas aus.** Es *schlägt* Aufrufe vor.
Ausgeführt wird nur, was euer Programm zulässt. In Lektion L5 des
Tutorial-Tracks baut ihr eine solche Schleife um euren Regelagenten herum.

## 3. Werkzeuge und Function Calling

Ein Werkzeug ist eine Funktion mit Namen, Beschreibung und Parameterschema. Beim
**Function Calling** bekommt das Modell diese Beschreibungen mit und antwortet in
einem festen Format (Name plus Argumente als JSON) statt in Prosa. Gute Werkzeuge
haben:

- **einen klaren Namen und eine knappe Beschreibung**, denn nur danach wählt das Modell,
- **enge Parameter** mit Grenzen, damit falsche Aufrufe auffallen,
- **strukturierte, kurze Ergebnisse**, denn jedes Ergebnis kostet Kontext.

In AutonomyRecoverySim gibt es zwölf Werkzeuge zum Lesen (`get_blocker`,
`check_oncoming_traffic`, …) und die Entscheidung selbst (`submit_decision`). Im
Wahrnehmungsmodell `tracked` (ab L4) ersetzen drei Messwerkzeuge die sieben fertigen Urteile. In Lagen mit
VLA-Fahrstack (siehe Abschnitt 9) kommen zwei hinzu, die Text eines Modells liefern.

## 4. Gedächtnis

Das Modell erinnert sich an nichts. Alles, was es „weiß“, steht in der
**Nachrichtenliste**, die bei jeder Runde vollständig mitgeschickt wird. Daraus folgt:

- **Kontext ist begrenzt und kostet.** Je länger die Liste, desto teurer und langsamer.
- **Neue Sitzung = leeres Gedächtnis.** Was über mehrere Sitzungen gelten soll, muss
  euer Programm einspeisen. In AutonomyRecoverySim macht das `get_recovery_history` und das Feld
  `additional_information`.

## 5. Wie ein Agent vorgeht: vier Muster

Die Schleife ist immer gleich. Was einen Agenten gut macht, ist, **wie** er sie nutzt. Vier
Muster begegnen euch in diesem Labor immer wieder:

| Muster | Idee | Wo ihr es übt |
|---|---|---|
| **Erst denken, dann handeln** (ReAct) | Das Modell schreibt kurz auf, was es erwartet, bevor es ein Werkzeug ruft, und vergleicht danach Erwartung und Ergebnis | Stufe 3b, weiterführende Ideen |
| **Aus Rückmeldung korrigieren** | Eine Ablehnung oder ein Fehler geht als Beobachtung zurück ans Modell, das daraufhin einen anderen Vorschlag macht, statt dass die Sitzung abbricht | Stufe 3b, Baustelle A |
| **Kontext gestalten** | Was in der Nachrichtenliste steht, bestimmt die Entscheidung. Mehr ist nicht besser: Jedes Token kostet, und Unwichtiges lenkt ab | Stufe 3b, Baustelle C |
| **Über mehrere Schritte planen** | Viele Lagen lösen sich nicht mit einem Befehl. Nach jedem Schritt ist die Lage neu zu bewerten; was vorher geschah, steht im Verlauf, nicht im Gedächtnis des Modells | Stufe 3b (Gedächtnis), mehrstufige Szenarien |

Keines dieser Muster ist Magie im Modell. Jedes ist eine Entscheidung darüber, was euer
Programm dem Modell zeigt und was es mit dessen Antwort macht.

## 6. Autonomie begrenzen: Guardrails

Ein Agent, der alles darf, ist gefährlich. Ein Agent, der nichts darf, ist nutzlos.
Der übliche Weg ist eine **Kette**, in der das Modell nur der erste Baustein ist:

```text
Agent (Vorschlag) ─▶ Schema ─▶ Regelprüfung ─▶ Sicherheitsprüfung ─▶ Ausführer ─▶ Welt
```

**Ein Vorschlag ist keine Handlung.** Jede Stufe darf ablehnen, und eine Ablehnung
nennt einen Grund. Typische Guardrails sind Parameterbereiche, Pflichtbelege vor
riskanten Aktionen, Budgets für Werkzeug- und Versuchsanzahl, feste
Ausweichaktionen bei Fehlern (fail-safe) und ein Sicherheitsmonitor, der unabhängig
vom Agenten mitprüft. Wichtig ist, dass diese Prüfungen **nicht im Prompt** stehen,
sondern im Programm. Ein Prompt kann ein Modell bitten, ein Programm kann es zwingen.

## 7. Was schiefgeht

| Problem | Beispiel | Woran man es merkt |
|---|---|---|
| **Halluzination** | Das Modell erfindet ein Werkzeugergebnis | Aussage ohne passenden Werkzeugaufruf im Trace |
| **Nichtdeterminismus** | Derselbe Lauf endet verschieden | Streuung bei Wiederholungen |
| **Schleifen** | Derselbe fehlgeschlagene Befehl wird wiederholt | gleiche Einträge im Verlauf |
| **Veraltete Daten** | Entscheidung auf alter Beobachtung | Altersfeld im Ergebnis |
| **Ausfälle** | Werkzeug antwortet nicht | Fehler statt Ergebnis |
| **Manipulation** | Text in den Daten gibt sich als Anweisung aus | Befehl im Datenfeld |
| **Falsche Selbstauskunft** | Ein anderes Modell (etwa der Fahrstack) begründet sein Verhalten überzeugend, aber falsch | Widerspruch zu einer zweiten Quelle |
| **Kosten** | Zu viele Runden, unnötige Eskalation | Token, Latenz, Euro im Bericht |

## 8. Wie bewertet man einen Agenten?

„Hat er die richtige Antwort gegeben?“ reicht nicht. Mindestens vier Fragen:

1. **Sicher?** Gab es Kollisionen oder Personenschäden? Das ist ein hartes Tor, das
   sich nicht durch andere Vorzüge ausgleichen lässt.
2. **Richtig?** War die Entscheidung passend zur Lage?
3. **Wirtschaftlich?** Was hat sie gekostet (Zeit, Anrufe, Schäden)?
4. **Zuverlässig?** Gilt das auch bei Wiederholung und auf unbekannten Varianten?

Ein Agent, der immer eskaliert, ist sicher und unbrauchbar. Ein Agent, der immer
handelt, ist schnell und gefährlich. Gut ist der, der zwischen beidem abwägt. Das
messt ihr in Stufe 6.

## 9. Das Projekt auf einer Seite

Ein autonomer Kleinbus fährt eine Straße entlang und bleibt vor einem Hindernis
stehen (ein **Deadlock**). Jetzt wird euer Agent, „der Autonomy Recovery Agent“, gerufen:

```text
Autopilot fährt ──▶ Deadlock erkannt ──▶ Euer Agent untersucht (Werkzeuge)
                                             │
                                             ▼
                       ein High-Level-Befehl, z. B. WAIT, NUDGE_AROUND_OBSTACLE,
                       REPLAN_ROUTE, REQUEST_REMOTE_ASSISTANCE, SAFE_STOP …
                                             │
                     Schema ─▶ Regeln ─▶ Sicherheit ─▶ Ausführer ─▶ Simulation
                                             │
                                  Ergebnis + Kosten + Einstufung
```

Der Agent **steuert das Fahrzeug nicht**, er wählt nur, was geschehen soll. Wie es
geschieht (Lenken, Bremsen), erledigt der Ausführer. Die Wirtschaftlichkeit zählt mit:
Personenschäden sind am teuersten, dicht gefolgt von Sachschäden; jeder Anruf bei der
Leitstelle und jede Sekunde Stillstand kosten Geld; Kunden wollen schnell und sicher
ankommen.

Zwei Erweiterungen machen die Lage später realistischer:

- **Mehrstufige Lagen:** Nach dem ersten Befehl ändert sich die Situation, und die nächste
  Sitzung verlangt einen anderen Befehl. Bestanden ist ein solcher Fall nur mit dem ganzen
  Lösungsweg.
- **VLA-Fahrstack:** Moderne Fahrzeuge fahren mit einem Vision-Language-Action-Modell, im Labor
  NVIDIA Alpamayo 1.5. Es erklärt seinen Halt in Text („Ein Lieferwagen blockiert die Spur, also
  halte ich“), statt eine Objektliste zu liefern. Im Simulator ist das ein Mock, zuschaltbar
  mit `--vla`. Seine Erklärung ist eine weitere Datenquelle, keine Wahrheit.

**Infrastruktur (fertig):** Autopilot, Deadlock-Erkennung, Wahrnehmung, Werkzeuge,
Regel- und Sicherheitsprüfung, Ausführer, Kostenmodell, Auswertung.
**Eure Aufgabe:** die Untersuchungs- und Entscheidungsstrategie.

## Denkfragen für euer Journal

1. Warum genügt es nicht, dem Modell im Prompt zu sagen „fahre nie bei durchgezogener
   Linie über die Mitte“? Was ist die robustere Lösung?
2. Ein Werkzeug liefert `"conflict": false`. Wovon hängt ab, ob ihr dem Ergebnis
   trauen dürft?
3. Warum ist „das Modell hat richtig entschieden“ bei einer einzelnen Beobachtung ein
   schwacher Beleg?
4. Wo würdet ihr ein Budget für Werkzeugaufrufe setzen, und was passiert, wenn es zu
   klein oder zu groß ist?
5. Welche Aufgabe aus eurem Alltag wäre mit einem Agenten sinnvoll, welche nicht?
6. Der Fahrstack schreibt: „Die Ampel ist rot, also warte ich.“ Was müsstet ihr wissen, um
   ihm zu glauben, und woher bekommt euer Agent diese Information?

## Team-Checkpoint

- Jede Person kann den Agentenloop in eigenen Worten mit Modell, Werkzeug und Programm
  erklären.
- Jede Person kann drei Guardrails nennen und sagen, warum sie im Programm stehen.
- Jede Person kann eines der vier Muster aus Abschnitt 5 an einem Beispiel erklären.
- Jede Person kann sagen, wie sich der Autonomy Recovery Agent von einem Motion Planner unterscheidet.

Weiter mit [Stufe 1: Recovery Agent spielen](01-recovery-agent-spielen.md).
