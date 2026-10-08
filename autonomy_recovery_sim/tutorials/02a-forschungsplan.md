# Team-Checkpoint: Vom Agenten zur Forschungsfrage

**Teamzeit:** 60 Minuten · **Phase:** Sprint 1 · **Modus:** Pflicht, gemeinsam ·
**Voraussetzung:** erste Messung des Regelagenten aus L2 oder L3

Bevor ihr den Agenten weiter optimiert oder einen LLM-Agenten anschließt, legt ihr als
Team fest, **was ihr herausfinden wollt**. Ein besserer Score allein ist keine
Forschungsfrage. Gesucht ist eine Aussage darüber, unter welchen Bedingungen eine
Agentenstrategie zuverlässig, sicher oder wirtschaftlich funktioniert.

Nutzt die Vorlage [`vorlagen/versuchsplan.md`](vorlagen/versuchsplan.md). Der Plan ist
ein lebendes Dokument, seine erste Version muss aber vor der Promptoptimierung von der
Betreuung geprüft werden.

## 1. Beobachtung aus der Regelbaseline

Wählt einen belegten Fehler oder Zielkonflikt aus eurem ersten Batchlauf. Notiert
Szenario, Entscheidung, relevante Werkzeugdaten und Messwert. Beispiele für
Zielkonflikte sind Fehlalarm gegen verpassten Eingriff oder Befreiungsrate gegen Kosten.

## 2. Forschungsfrage und Hypothese

Formuliert eine Frage, die ein Vergleich beantworten kann, zum Beispiel:

> Unter welchen Datenqualitätsbedingungen senkt eine explizite Unsicherheitsprüfung die
> Zahl unerwarteter Manöver, ohne die Zahl verpasster Eingriffe stark zu erhöhen?

Leitet mindestens eine gerichtete, widerlegbare Hypothese ab. Vermeidet Formulierungen
wie „Wir bauen einen guten Agenten“ oder „LLMs sind besser“.

## 3. Vergleich festlegen

Definiert vor dem nächsten Lauf:

- Regelbaseline und LLM-Baseline,
- genau eine zunächst veränderte Einflussgröße,
- feste Entwicklungs- und spätere Evaluationsmengen,
- primäre Sicherheitskennzahl und sekundäre Leistungskennzahlen,
- mindestens drei Wiederholungen für Modellagenten,
- Abbruch- und Ausschlusskriterien.

Alle Ausgangsfälle und Erfolgskriterien sind öffentlich. Legt Entwicklungs-Seeds vorab
fest und verwendet nach dem Freeze weitere Seeds für den Abschlussvergleich. Dokumentiert
auch diese Seeds; die Abschlussläufe dienen nicht zum Nachjustieren derselben Agentenversion.
So trennt ihr Entwicklung und Evaluation, ohne Szenariotypen zurückzuhalten.

## 4. Teamarbeit planen

Verteilt für den nächsten Sprint vorläufig die Arbeitsfelder Regelagent, LLM-Agent,
Szenarien/Tests und Evaluation/Reproduzierbarkeit. Legt außerdem je Bereich eine
Reviewperson fest. Die Reviewperson darf nicht mit der hauptverantwortlichen Person
identisch sein.

Die Aufteilung entbindet niemanden vom Gesamtverständnis. Plant einen gemeinsamen
Walkthrough, in dem jede Person einen fremden Bereich erklärt.

## 5. Integrations- und Freeze-Regel

Definiert eine gemeinsame Agentenschnittstelle und benennt die Dateien, Prompts und
Konfigurationen, die ein Versuch benötigt. Legt fest, wann eine Variante eingefroren
ist. Rohberichte werden nie überschrieben oder nachträglich verändert.

## Gemeinsame Abgabe

- ausgefüllter Versuchsplan,
- ein belegter Ausgangsfehler der Regelbaseline,
- Forschungsfrage und mindestens eine Hypothese,
- Rollen- und Reviewzuordnung für den nächsten Sprint,
- Reproduktionsbefehl für den Ausgangslauf.

## Team-Checkpoint

- Jede Person kann Forschungsfrage, Baseline und primäre Kennzahl erklären.
- Die Hypothese könnte durch ein Ergebnis widerlegt werden.
- Entwicklung und Evaluation sind getrennt.
- Pro Vergleich wird zunächst nur eine Einflussgröße verändert.
- Eine Review- und Integrationszeit ist vereinbart.

Nach Freigabe arbeitet ihr mit [L4 · Selbst wahrnehmen](L4-selbst-wahrnehmen.md) und parallel
an der geplanten Architektur weiter.
