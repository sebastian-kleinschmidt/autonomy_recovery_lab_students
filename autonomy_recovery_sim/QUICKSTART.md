# AutonomyRecoverySim in zehn Minuten

Neu in agentischer KI? Beginnt als Viererteam mit dem
[Team-Lernpfad](tutorials/README.md): Er erklärt die Grundlagen und führt euch über eine
Regelbaseline und einen Forschungsplan zum LLM-Agenten und zum reproduzierbaren Vergleich.
Diese Seite ist nur der schnelle technische Einstieg.

Dieser Pfad führt vom frischen Checkout bis zum ersten werkzeugnutzenden
LLM-Lauf. AutonomyRecoverySim benötigt Python 3.10 oder neuer und läuft mit
der Standardbibliothek unter Linux, macOS und Windows ohne GPU.
Die optionale virtuelle Umgebung und plattformspezifische Startbefehle stehen
im [Repository-Einstieg](../README.md#schnellstart).

## 1. Installation prüfen

Im Wurzelverzeichnis des Repositories:

```bash
python3 -m unittest discover -s tests -p 'test_autonomy_recovery_sim.py'
python3 -m autonomy_recovery_sim validate autonomy_recovery_sim/scenarios
```

Die kumulativen, ohne LLM nutzbaren Sprint-Freigaben sind in
[`SCENARIOS.md`](SCENARIOS.md) beschrieben. Beispiel für Sprint 1:

```bash
python3 -m autonomy_recovery_sim batch \
  autonomy_recovery_sim/scenario_sets/released_sprint1.txt \
  --agent autonomy_recovery_sim.student_agent:decide
```

## 2. Den Deadlock beobachten

```bash
python3 -m autonomy_recovery_sim.live \
  --scenario autonomy_recovery_sim/scenarios/hannover_frei.json
```

Die Seite `http://127.0.0.1:8765` öffnen und **Starten** wählen. Das Fahrzeug
fährt autonom bis zur Blockade. Ohne Agent bleibt es dort sicher stehen und die
**Recovery Console** in der rechten Spalte öffnet sich: Dort können Sie selbst die
Lage abfragen und jeden Befehl des Katalogs auslösen, um Wirkung, Kosten und
Ablehnungscodes kennenzulernen (siehe [COMMANDS.md](COMMANDS.md)).

Zum Vergleich kann die transparente Referenzheuristik geladen werden:

```bash
python3 -m autonomy_recovery_sim.live \
  --scenario autonomy_recovery_sim/scenarios/hannover_frei.json \
  --agent baseline
```

## 3. Modellzugang setzen

Der Adapter spricht die OpenAI-kompatible Chat-Completions-API. Für GWDG
Chat AI gelten standardmäßig diese Werte:

```bash
export AUTONOMY_RECOVERY_BASE_URL=https://chat-ai.academiccloud.de/v1
export AUTONOMY_RECOVERY_MODEL=glm-4.7
```

Den Schlüssel verdeckt einlesen. Für zsh:

```zsh
read -rs "AUTONOMY_RECOVERY_API_KEY?Chat-AI-Schluessel: " && echo
export AUTONOMY_RECOVERY_API_KEY
```

Für bash:

```bash
read -rsp "Chat-AI-Schluessel: " AUTONOMY_RECOVERY_API_KEY && echo
export AUTONOMY_RECOVERY_API_KEY
```

Der Schlüssel gehört weder in das Repository noch in ein Chatfenster. Die
verfügbaren Variablen stehen auch in [`.env.example`](.env.example); diese
Datei wird nicht automatisch geladen.

## 4. Referenzadapter prüfen

```bash
python3 -m autonomy_recovery_sim \
  autonomy_recovery_sim/scenarios/hannover_frei.json \
  --agent llm
```

Der Modellaufruf beginnt erst nach dem erkannten Deadlock. Netzwerkfehler,
Zeitüberschreitungen und ungültige Entscheidungen führen fail-safe zu
`WAIT` und werden in `result.json` protokolliert.

## 5. Den eigenen Agenten bearbeiten

Der Einstieg liegt in [`student_llm_agent.py`](student_llm_agent.py). Zuerst
den Systemprompt verändern, danach Werkzeugstrategie, Modell und
Entscheidungsgrenzen systematisch untersuchen.

```bash
python3 -m autonomy_recovery_sim \
  autonomy_recovery_sim/scenarios/hannover_frei.json \
  --agent autonomy_recovery_sim.student_llm_agent:decide

python3 -m autonomy_recovery_sim batch \
  autonomy_recovery_sim/scenario_sets/demo.txt \
  --agent autonomy_recovery_sim.student_llm_agent:decide
```

Erst danach folgt die grössere öffentliche Menge:

```bash
python3 -m autonomy_recovery_sim batch \
  autonomy_recovery_sim/scenario_sets/public.txt \
  --agent autonomy_recovery_sim.student_llm_agent:decide
```

Die Auswertung steht unter `artifacts/autonomy-recovery-sim/batch/`. Sie enthält
Entscheidungen, Sicherheitsausgänge, Werkzeugreihenfolge, Modellrunden,
Latenz und – sofern der Endpunkt sie meldet – Tokenzahlen.

Den eigenen Agentenloop schreibt ihr in [`student_loop_agent.py`](student_loop_agent.py)
(Anleitung: [Stufe 3b im Archiv](tutorials/archiv/03b-eigener-agent.md); im Tutorial-Track baut
[L5](tutorials/L5-llm-agent.md) einen hybriden Agenten). Wie ihr ihn gegen alle Szenarien
testet und den Bericht lest, steht im [Prüfstand](PRUEFSTAND.md):

```bash
python3 -m autonomy_recovery_sim batch --release sprint2 \
  --agent autonomy_recovery_sim.student_loop_agent:decide
```

## Typische Fehler

- **API-Schlüssel fehlt:** `AUTONOMY_RECOVERY_API_KEY` im selben Terminal exportieren.
- **HTTP 401:** Bearer-Schlüssel oder Gültigkeit prüfen.
- **Modell nicht gefunden:** Namen mit `GET /v1/models` des Dienstes abgleichen.
- **Befehl abgelehnt:** Manöver (`NUDGE_AROUND_OBSTACLE`, `CHANGE_LANE`,
  `AVOID_TEMPORARY_OBSTRUCTION`, `CROSS_LOW_RISK_OBJECT`) brauchen im Prüfmodus `strict` Evidenz aus allen
  sieben Lagewerkzeugen (im Wahrnehmungsmodell `tracked`: aus den drei Messwerkzeugen).
  Der Fehlercode (`RULE_REJECTED`, `SAFETY_REJECTED`, `NOT_AVAILABLE`,
  `INVALID_ARGUMENT`) nennt den Grund; der Agent darf innerhalb von drei Versuchen
  korrigieren.
- **Agent bleibt bei Prosa:** Der Prompt muss den Aufruf von `submit_decision`
  ausdrücklich verlangen.

Alle 24 Befehle mit Parametern, Regeln und Kosten stehen in
[COMMANDS.md](COMMANDS.md), die vollständige Aufgabenbeschreibung in
[ASSIGNMENT.md](ASSIGNMENT.md). Weitere Fälle für die übrigen Befehle liegen in
[`scenario_sets/commands.txt`](scenario_sets/commands.txt):

```bash
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/commands.txt --agent baseline
```

Für Datenqualität und Robustheit (veraltete Daten, Phantomobjekt, Werkzeug-Timeout,
Prompt-Injection) gibt es `scenario_sets/uncertainty.txt`; siehe
[COMMANDS.md](COMMANDS.md#unsicherheit-werkzeugausfaelle-und-manipulation).

Der Batchlauf schreibt neben `batch-report.md` die Auswertungsseite
`batch-report.html` mit Einstufung A bis D (Rückmeldung, keine Note), Kosten,
Kundenzufriedenheit und dem Fortschritt gegenüber dem vorigen Lauf im selben Ausgabeordner. Da ein
LLM-Agent nicht deterministisch ist, wiederholt `--repeats 3` jedes Szenario und
zeigt Bestehensquote und Kostenstreuung.
