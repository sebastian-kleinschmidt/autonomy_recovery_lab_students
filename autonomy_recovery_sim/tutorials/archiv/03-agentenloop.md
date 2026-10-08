# Stufe 3: Der Agentenloop von innen

**Teamzeit:** 45 Minuten Pflichtkern · **Phase:** Sprint 1 · **Modus:** arbeitsteilig ·
**Voraussetzung:** Stufe 2 und Forschungsplan · **Schlüssel:** nein

Bevor ihr ein echtes Sprachmodell anschließt, öffnet ihr die Mechanik. Ein **gespieltes
Modell** antwortet mit festen Nachrichten. Der echte Adapter führt die
Werkzeugaufrufe aus und reicht die Ergebnisse zurück. Ihr seht jede Nachricht, ohne
Zufall, ohne Kosten und ohne Schlüssel. Danach ist ein echtes Modell nur noch ein
Baustein, der andere Antworten liefert.

## Teammodus und Pflichtumfang

Teilt den Trace in Modellnachrichten, Werkzeugaufrufe, Werkzeugantworten und
Validierung auf. Jede Person markiert ihren Teil; anschließend setzt ihr gemeinsam den
Ablauf zusammen. Experiment A und ein weiteres Experiment nach Wahl sind Pflicht. Die
übrigen Experimente sind Vertiefungen.

Die gemeinsame Abgabe ist ein kommentierter Trace, in dem Ursprung, Prüfung und Wirkung
jeder relevanten Nachricht erkennbar sind.

## Der Versuch

```bash
python3 -m autonomy_recovery_sim.tutorials.mock_llm_demo
```

Das Skript ([mock_llm_demo.py](../mock_llm_demo.py)) lässt ein gespieltes Modell im
Szenario `hannover_frei` erst sieben Werkzeuge abfragen und dann `submit_decision`
aufrufen. Es druckt in jeder Runde, was der Simulator ans Modell schickt und was das
Modell antwortet. Ihr solltet etwa Folgendes sehen (gekürzt):

```text
=== Runde 1: Der Simulator schickt 2 Nachrichten ans Modell ===
    (dazu 13 Werkzeugbeschreibungen; das Modell sieht sie als Auswahlmenue)
  [system] Du bist der Autonomy Recovery Agent eines autonomen Kleinbusses …
  [user] Der Deadlock wurde erkannt. Untersuche diese Ausgangslage und waehle einen Befehl: {…
  <- Das Modell antwortet mit Werkzeugaufrufen: check_oncoming_traffic, …, get_visibility

=== Runde 2: Der Simulator schickt 10 Nachrichten ans Modell ===
  [tool] {"ok": true, "result": {"type": "dashed", …}}
  <- Das Modell antwortet mit Werkzeugaufrufen: submit_decision

=== Ergebnis ===
Befehl:  NUDGE_AROUND_OBSTACLE (korrekt)
Ausgang: liberated, Kosten 1.55 EUR
```

## So liest man das Protokoll

Jede Runde ist ein Aufruf an den Endpunkt mit der **vollständigen Nachrichtenliste**.
Vier Rollen kommen vor:

| Rolle | Wer schreibt sie | Inhalt |
|---|---|---|
| `system` | euer Programm | Verhaltensregeln (der Systemprompt) |
| `user` | euer Programm | die Aufgabe und die Ausgangslage (Deadlock-Kontext) |
| `assistant` | das Modell | Werkzeugaufrufe, oder eine Antwort ohne Aufruf |
| `tool` | euer Programm | das Ergebnis genau eines Werkzeugaufrufs |

Bei jedem `assistant`-Beitrag mit `tool_calls` führt *euer Programm* die Aufrufe aus, hängt
für jeden ein `tool`-Ergebnis an und fragt erneut. Eine Runde kann mehrere Aufrufe
enthalten (Runde 1 hat sieben). Fragen zum Protokoll, die ihr anhand der Ausgabe
beantworten könnt:

1. Wie viele Nachrichten schickt der Simulator in Runde 2, und woraus bestehen sie?
   Warum wächst die Liste?
2. Was würde passieren, wenn der Simulator nur die *neuen* Nachrichten schickte?
3. `submit_decision` ist selbst ein **Werkzeug**. Was folgt daraus für den Ablauf?
4. Wo steht, welche Werkzeuge das Modell überhaupt kennt?

Der Adapter ist [`llm_agent.py`](../../llm_agent.py). Die Methode `__call__` von
`OpenAICompatibleAgent` ist die Schleife in knapp hundert Zeilen. Lest sie mit der Ausgabe
neben euch.

## Experimente: das Drehbuch ändern

Öffnet [mock_llm_demo.py](../mock_llm_demo.py). Die Funktion `scripted_model()` ist das
Drehbuch des Modells. Ändert es und **sagt vorher, was passiert**. Zum Zurücksetzen
gilt: Das Drehbuch steckt allein in dieser einen Funktion.

### Experiment A: Entscheiden ohne Belege

Lasst das Modell nur drei Werkzeuge abfragen (z. B. `get_blocker`, `get_visibility`,
`check_rear_traffic`) und dann sofort `submit_decision` mit dem Manöver aufrufen.

Beobachtet: Welche Nachricht kommt als `tool`-Ergebnis zurück? Die Ablehnung nennt den
**Code** und die **fehlenden Werkzeuge**. Ein echtes Modell könnte darauf reagieren und
nachfragen. Das gespielte Modell hat keine weitere Antwort und meldet „Drehbuch zu
Ende“. Was macht der Simulator dann? *(Antwort: Er weicht fail-safe auf `WAIT` aus und
öffnet später eine neue Sitzung.)*

### Experiment B: Ein Werkzeug, das es nicht gibt

Lasst das Modell `get_ground_truth` aufrufen (nicht im Katalog). Wie sieht die
Fehlermeldung aus, die als `tool`-Nachricht zurückgeht? Warum ist es klug, Fehler als
Nachricht zurückzugeben statt das Programm abstürzen zu lassen?

### Experiment C: Ungültige Parameter

Reicht `NUDGE_AROUND_OBSTACLE` mit `side="UP"` oder `max_longitudinal_distance_m=500` ein.
Welche der drei Prüfstufen (Schema, Regeln, Sicherheit) lehnt ab? Und woran seht ihr es
am Code?

### Experiment D: Zwei Entscheidungen

Sendet zwei `submit_decision` in einer Runde. Was gilt? Warum lässt der Simulator nach der
ersten gültigen Entscheidung keine Werkzeugaufrufe mehr zu?

### Experiment E: Ein anderes Szenario

```bash
python3 -m autonomy_recovery_sim.tutorials.mock_llm_demo autonomy_recovery_sim/scenarios/hannover_gegenverkehr.json
```

Das Drehbuch macht dieselbe Entscheidung, aber die Lage ist eine andere. Was ist das
Ergebnis, und **was sagt es über einen Agenten, der nicht auf die Werkzeugergebnisse
schaut**? (Ein Modell, das die Ergebnisse nicht liest, ist ein Zufallsgenerator mit
guter Grammatik.)

## Was ein Agentenloop ohne Framework braucht

Damit ihr versteht, dass nichts Magisches dahintersteckt, hier die Schleife in Pseudocode:

```python
messages = [system_prompt, aufgabe_und_lage]
for runde in range(MAX_RUNDEN):
    antwort = modell(messages, werkzeuge)        # HTTP-Aufruf
    messages.append(antwort)
    if not antwort.tool_calls:
        messages.append(erinnerung)              # „nutze die Werkzeuge“
        continue
    for aufruf in antwort.tool_calls:
        if aufruf.name == "submit_decision":
            return pruefen_und_ausfuehren(aufruf.arguments)
        ergebnis = werkzeug_ausfuehren(aufruf)   # kann fehlschlagen
        messages.append(tool_nachricht(ergebnis))
raise "Modell hat nicht entschieden"             # -> fail-safe im Simulator
```

Vier Dinge sind kein Beiwerk, sondern der Kern der Zuverlässigkeit: die **Obergrenze**
(`MAX_RUNDEN`), die **Fehlerbehandlung** bei jedem Werkzeug, die **Prüfung** vor der
Ausführung und das **fail-safe**, wenn das Modell nicht liefert.

## Team-Checkpoint

- Jede Person kann die vier Nachrichtenrollen und ihre Absender nennen.
- Jede Person kann erklären, warum in jeder Runde die gesamte Nachrichtenliste gesendet wird.
- Das Team hat Experiment A und mindestens ein weiteres durchgeführt und seine Vorhersagen
  mit der Beobachtung verglichen.
- Jede Person kann drei Gründe nennen, warum ein Agentenloop ein Rundenlimit braucht.

Weiter mit [Stufe 3b: Euren eigenen Agenten schreiben](03b-eigener-agent.md).
