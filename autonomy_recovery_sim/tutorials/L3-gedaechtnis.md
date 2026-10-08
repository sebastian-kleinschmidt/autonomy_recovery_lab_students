# L3 · Gedächtnis und mehrere Schritte

**Teamzeit:** 90 Minuten · **Phase:** Sprint 1 · **Stufe:** A · **Schlüssel:** nein

Viele Lagen löst kein einzelner Befehl. In einer Sackgasse muss das Fahrzeug erst
zurücksetzen und dann umplanen; mit Fahrgästen erst an den Rand und dann absetzen. Und wer
zum dritten Mal wartet, sollte etwas anderes versuchen. Dafür braucht der Agent ein
Gedächtnis.

## Ziel

- Ihr nutzt den Verlauf (`get_recovery_history`) als Gedächtnis über Sitzungen hinweg.
- Ihr behandelt Ablehnungen: Die Prüfung sagt Nein, der Agent versucht die nächste
  Alternative.
- Ihr baut eine Eskalationsleiter statt endlosen Wartens.

## Startstand

Euer Stand aus L2 oder `l3_start.py` (wird später freigegeben).

## Vorhersage

Euer L2-Agent besteht 1 von 9 Fällen aus `mehrstufig.txt`. Was haben die anderen acht
gemeinsam?

## Bauen

1. **Verlauf lesen.**

   ```python
   history = session.call_tool("get_recovery_history")["attempts"]
   waits = sum(item["command"] == "WAIT" for item in history)
   ```

   Jeder Eintrag nennt Befehl, Status (`SUCCEEDED`, `FAILED`, `ABORTED`) und Ergebnis.

2. **Ablehnungen behandeln.** `session.submit_decision(befehl)` prüft sofort und wirft bei einer
   Ablehnung `AgentContractError`. Wer die Ausnahme fängt, kann die nächste Alternative
   einreichen. Je Sitzung gibt es drei Versuche:

   ```python
   from autonomy_recovery_sim.agent_contract import AgentContractError

   def first_accepted(session, candidates):
       for candidate in candidates[:-1]:
           try:
               return session.submit_decision(candidate)
           except AgentContractError:
               continue
       return candidates[-1]
   ```

   Nutzt das für Ausweichwege, vom schonendsten zum weitesten: `AVOID_TEMPORARY_OBSTRUCTION`
   bei kleinen Hindernissen, `CHANGE_LANE` bei freier Nachbarspur, zuletzt
   `NUDGE_AROUND_OBSTACLE`.

3. **Mehrstufige Lösungen.**
   - Route gesperrt und `reverse_required_m > 0`: erst `REVERSE_SHORT`, dann `REPLAN_ROUTE`.
   - Route gesperrt ohne Alternative: Fahrgäste an Bord? Erst `PULL_OVER`, am Rand
     `DROP_PASSENGER`. Sonst `RETURN_HOME` oder `SAFE_STOP`.

4. **Eskalationsleiter.** Nach zweimaligem Warten: Karte abgleichen
   (`REQUEST_ADDITIONAL_INFORMATION`, `MAP_CONSISTENCY`), dann Leitstelle
   (`REQUEST_REMOTE_ASSISTANCE`), dann an den Rand und `SAFE_STOP`. Eine dunkle Ampel ist ein
   Fall für die Leitstelle.

## Messen

```bash
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/released_sprint2.txt --agent mein_agent:decide
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/mehrstufig.txt --agent mein_agent:decide
```

| Menge | Startstand | Richtwert nach L3 |
|---|---|---|
| `released_sprint2.txt` | 10 von 20 | 18 bis 19 von 20 |
| `mehrstufig.txt` | 1 von 9 | 4 von 9 |

## Was typischerweise schiefgeht

- **Zu viel Geduld kostet.** Wer erst nach zwei Wartezeiten den Kartenabgleich startet, landet
  in knappen Budgets über dem Limit (`hannover_karte_veraltet`). Wann lohnt es sich, sofort
  nachzusehen?
- **Zu wenig Geduld auch.** `hannover_lieferwagen_faehrt_los` fährt nach kurzer Zeit von selbst.
  Wer sofort ausweicht, zahlt Kollisionsrisiko für nichts.
- **Vergessene Versuche.** Jede Ablehnung kostet einen der drei Entscheidungsversuche und
  2 EUR.

## Erweitere selbst

- Lest `additional_information` aus dem Kontext: Was hat ein Kartenabgleich ergeben?
- Unterscheidet Warten auf Fußgänger (kurz) von Warten auf einen geparkten Wagen (sinnlos).
- Rechnet die Kosten mit: Ist die Leitstelle (25 EUR) billiger als weitere 30 s Standzeit?

## Team-Checkpoint

- Ihr könnt den Weg durch die Eskalationsleiter an einem Szenario zeigen.
- Ihr habt eine Ablehnung im Trace gefunden, die euer Agent mit einer Alternative gerettet hat.

Dann folgt der [Forschungsplan](02a-forschungsplan.md); danach weiter mit
[L4 · Selbst wahrnehmen](L4-selbst-wahrnehmen.md).
