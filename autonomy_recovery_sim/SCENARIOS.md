# Szenarienkatalog und empfohlener Lernpfad

Der maschinenlesbare Katalog [`scenario_catalog.json`](scenario_catalog.json) ist die
Quelle fuer die didaktische Staffelung. Alle Szenarien sind ohne Sprachmodell nutzbar:
in der Recovery Console, mit dem Regelagenten oder mit einem deterministischen
Testagenten. Ein LLM wird erst fuer den spaeteren Vergleich benoetigt.
**Alle 61 Sprintfälle und alle 18 Familienvarianten sind von Anfang an veröffentlicht**,
einschließlich ihrer Erfolgskriterien. Die Sprintzuordnung empfiehlt eine Reihenfolge.

## Empfohlene Sprintmengen

Die kleinen `sprint*.txt`-Dateien enthalten nur die **neu hinzukommenden** Faelle.
Die `released_sprint*.txt`-Dateien sind kumulativ und eignen sich fuer den
Regressionstest am Sprintende.

| Phase | Neue Faelle | Kumulativ | Neue Schwierigkeit | Primaere Auswertung |
|---|---:|---:|---|---|
| Bootcamp | 3 | 3 | Werkzeuge, Verkehrsregel, einfache Freigabe | begruendete manuelle Entscheidung |
| Sprint 1 | 5 | 8 | Sicht, Abstand, Konflikthorizont, vulnerable Personen | Befehlsgenauigkeit und unerwartete Manoever |
| Sprint 2 | 12 | 20 | Befehlskatalog, Sequenzen, Mission und Kosten | Befreiungsrate, Kosten, Kundenzufriedenheit |
| Sprint 3 | 16 | 36 | Scheindeadlocks, Datenqualitaet, Ausfaelle, Manipulation und VLA-Fahrstack | Fehlalarme und verpasste Eingriffe |
| Sprint 4 | 25 | 61 | OSM-Transfer, Verdeckung, dynamischer Abbruch, Sonderlagen, Lost Cargo und mehrstufige Loesungswege | Robustheit und Regression |

Die Mengen strukturieren den Lernpfad und sind keine Zugangsschranke. Teams können jederzeit
andere Fälle untersuchen. Das Review des vorherigen Sprints ist ein fachlicher Checkpoint;
es hilft bei der Entscheidung, was als Nächstes sinnvoll ist. Der Dateiname
`released_sprintN.txt` bleibt für bestehende Befehle erhalten.

Kalibrierung ohne LLM: Auf der Sprint-1-Menge besteht der absichtlich immer
wartende Starter 6/8 Faelle, die transparente Referenzbaseline 8/8; beide bleiben
kollisionsfrei. Damit belohnt die erste Stufe bereits aktive, aber sichere
Freigabeentscheidungen.

```bash
# Nur die neuen Faelle eines Sprints
python3 -m autonomy_recovery_sim batch \
  autonomy_recovery_sim/scenario_sets/sprint2_decisions.txt \
  --agent autonomy_recovery_sim.student_agent:decide

# Alle bis dahin empfohlenen Faelle als Regression
python3 -m autonomy_recovery_sim batch \
  autonomy_recovery_sim/scenario_sets/released_sprint2.txt \
  --agent autonomy_recovery_sim.student_agent:decide

# Katalog und generierte Sets pruefen
python3 autonomy_recovery_sim/scripts/build_scenario_sets.py --check
```

Die bisherigen thematischen Mengen (`demo.txt`, `commands.txt`, `erkennen.txt`,
`uncertainty.txt`, `hannover.txt`, `public.txt`) bleiben fuer Tutorials und gezielte
Analysen erhalten. `public.txt` ist **keine Sprint-1-Menge**, weil es bereits
Unsicherheits- und Angriffsszenarien enthaelt.


## Beobachtbare Szenenbeschreibungen

Jeder dateibasierte Akteur besitzt eine kurze `description`. Sie beschreibt nur
beobachtbare Merkmale wie Erscheinung, Position, sichtbares Verhalten oder OCR-Text
und nennt weder Referenzbefehl noch erwartetes Ergebnis. Bereits vorhandene
Wahrnehmungswerkzeuge geben den Text als nicht vertrauenswuerdige
`scene_description` nur fuer den jeweils erkannten Akteur weiter. Damit kann spaeter
ein optionales `describe_visible_scene` aus denselben Wahrnehmungsdaten aufgebaut
werden, ohne verdeckte Ground-Truth-Akteure oder Loesungswissen offenzulegen.

## Fachliche Checkpoints

- **Sprint 1:** Die drei Bootcamp-Faelle wurden manuell untersucht; Werkzeuge und
  Ablehnungen koennen erklaert werden.
- **Sprint 2:** Der Regelagent laeuft auf `released_sprint1.txt` ohne Ausnahme; ein
  Forschungs- und Versuchsplan ist freigegeben.
- **Sprint 3:** Starter und entwickelte Regelbaseline wurden auf denselben 20 Faellen
  verglichen; der Modelladapter wurde separat mit `tutorials.mock_llm_demo` geprueft und
  die Rohberichte sind reproduzierbar. Der echte LLM-Vergleich kann spaeter folgen.
- **Sprint 4:** Die Robustheitsmatrix unterscheidet Fehlalarm, verpassten Eingriff und
  unerwartetes Manoever; Verbesserungen bestehen den Regressionstest.
- **Abschluss:** Agent, Prompt beziehungsweise Regelkonfiguration und Messpipeline
  werden eingefroren. Danach laufen Varianten der veröffentlichten Szenarien mit weiteren
  Seeds. Ausgangsfälle, Generator und Erfolgskriterien sind bekannt; Seeds und Rohberichte
  werden für die Reproduktion dokumentiert.

## Neue Sonderlagen

### Wildunfall

`hannover_wildunfall` kombiniert ein verletztes Tier in der Fahrspur mit einem
weiteren Tier am Fahrbahnrand. Die Lage prueft, ob ein Agent auf ein riskantes
Vorbeifahren verzichtet und nach begrenztem Warten Hilfe koordiniert.

### Sitzblockade

`hannover_sitzblockade` blockiert beide Fahrtrichtungen mit Personen. Die Simulation
bewertet ausschliesslich die sichere Fahrzeugreaktion und trifft keine Aussage ueber
Anliegen oder Rechtmaessigkeit der Versammlung.

### Entlaufene Zootiere

`hannover_zootiere` spielt auf der Adenauerallee unmittelbar am Erlebnis-Zoo
Hannover und nutzt den neuen Akteurstyp `animal`. Gestaffelte, aber deterministische
Bewegungszeitpunkte erzeugen eine reproduzierbare Lage, in der erneutes Anfahren
zu frueh waere.

### Feiernde Fussballfans

`hannover_fussballfans_blockade` ergaenzt den geordneten Abpfiff-Fall um eine
ungeordnet bewegte Gruppe, die den Fahrkorridor mehrfach und zeitversetzt belegt.

### Umgekippter Lkw

`hannover_umgekippter_lkw` bildet eine Vollsperrung durch einen quer liegenden Lkw,
verlorene Ladung und eine unbekannte Fluessigkeit ab. Der Fall prueft die Abgrenzung
zwischen lokalem Manoever und globaler Umplanung.

## Mehrstufige Loesungswege

Manche Lagen brauchen mehr als einen Befehl. Diese Szenarien tragen in `reference.sequence`
ihren Loesungsweg: geordnete Schritte, je Schritt eine Liste gleichwertiger Befehle. Ein Schritt
zaehlt nur, wenn ein Befehl daraus **erfolgreich** war und nach dem vorigen Schritt kam.
Bestanden ist ein solches Szenario nur mit vollstaendigem Weg; der Pruefstand weist zusaetzlich
Teilpunkte aus.

| Szenario | Loesungsweg |
|---|---|
| `hannover_sackgasse` | `REVERSE_SHORT` → `REPLAN_ROUTE` |
| `hannover_karte_veraltet` | `REQUEST_ADDITIONAL_INFORMATION` → `REPLAN_ROUTE` |
| `hannover_passagier_absetzen` | `PULL_OVER` → `DROP_PASSENGER` |
| `hannover_leitstelle_offline` | `PULL_OVER` → `SAFE_STOP` |
| `hannover_fussgaenger_vor_lieferwagen` | `WAIT` → `NUDGE_AROUND_OBSTACLE` |
| `hannover_gegenverkehr_zieht_vorbei` | `WAIT` → `NUDGE_AROUND_OBSTACLE` |
| `hannover_zwei_hindernisse` | `AVOID_TEMPORARY_OBSTRUCTION` → `NUDGE_AROUND_OBSTACLE` |
| `hannover_karte_veraltet_fahrgaeste` | `REQUEST_ADDITIONAL_INFORMATION` → `PULL_OVER` → `DROP_PASSENGER` |
| `hannover_ampel_dunkel_lieferwagen` | `REQUEST_REMOTE_ASSISTANCE` → `NUDGE_AROUND_OBSTACLE` |

Die letzten fuenf (Sprint 4) sind eigens fuer mehrstufiges Vorgehen gebaut: Nach dem ersten
Befehl aendert sich die Lage, und die naechste Sitzung verlangt einen anderen Befehl. Wer
dort nur den ersten Schritt richtig macht, besteht nicht. Die Referenzbaseline schafft zwei
der neun Wege vollstaendig (`sackgasse`, `gegenverkehr_zieht_vorbei`). Alle neun stehen im Set
[`scenario_sets/mehrstufig.txt`](scenario_sets/mehrstufig.txt).

`reference.commands` bleibt die Menge zulaessiger **erster** Befehle; `reference.sequence`
beschreibt den ganzen Weg. Neue mehrstufige Faelle brauchen beides.

## VLA-Fahrstack: Selbstauskunft pruefen

Drei Sprint-3-Faelle ersetzen den stummen Spurfolger durch einen Mock eines
Vision-Language-Action-Fahrstacks, angelehnt an NVIDIA Alpamayo 1.5 (siehe
[`vla_mock.py`](vla_mock.py) und den README-Abschnitt dazu). Der Fahrstack begruendet
seinen Halt in Text (`get_vla_output`) und beschreibt Kamerabilder
(`get_camera_caption`). Im Modus `perception_interface: "vla"` liefern die Lagewerkzeuge
nur noch Geometrie; Objektklasse, Hindernisprofil und Signalzustand gibt es dann
ausschliesslich als Modelltext. Jeder Fall enthaelt einen typischen Modellfehler:

| Szenario | Fehlerbild | Was der Agent abgleichen muss |
|---|---|---|
| `hannover_vla_phantom` | `OVERCONFIDENT`: Text nennt ein Objekt mit 0,97 Konfidenz | `track_confidence` 0,3 in `get_blocker`, undeutliche Kamerabeschreibung |
| `hannover_vla_ampel_dunkel` | `HALLUCINATED_CAUSE`: Text behauptet Rot | Frontkamera beschreibt eine dunkle Ampel |
| `hannover_vla_karton` | `VAGUE_CAUSE`: Text nennt nur ein unbekanntes Hindernis | Nahbeschreibung der Frontkamera zeigt flachen, weichen Karton |

Die Referenzbaseline besteht keinen der drei Faelle: Ohne Objektklasse umfaehrt sie
Phantom und Karton, an der dunklen Ampel wartet sie zu lange. Das Set
[`scenario_sets/vla.txt`](scenario_sets/vla.txt) enthaelt die drei Faelle; Lektion
[L6](tutorials/L6-alpamayo-misstrauen.md) behandelt sie im Wahrnehmungsmodell `tracked`.

## Lost Cargo: unterschiedliche Handlungsoptionen

Die fuenf Varianten erzwingen keine pauschale Reaktion auf `debris`. Sichtbarer
Freitext dient nur der spaeteren Szenenbeschreibung; die sicherheitsrelevanten
Objekteigenschaften stehen strukturiert in `obstacle_profile`.

| Szenario | Objekt und Risiko | Erwartete Entscheidung |
|---|---|---|
| `hannover_ladung_karton` | flacher, weicher Karton; hochkonfident, ohne Kanten oder Fluessigkeit | `CROSS_LOW_RISK_OBJECT` |
| `hannover_ladung_reifen` | hoher, formstabiler Reifen mit Platz in der eigenen Spur | `AVOID_TEMPORARY_OBSTRUCTION` |
| `hannover_ladung_holzbalken` | starrer, scharfkantiger Holzbalken; lokales Passieren moeglich | `NUDGE_AROUND_OBSTACLE` |
| `hannover_ladung_scherben` | Glas und unbekannte Fluessigkeit ueber beide Richtungen | `REPLAN_ROUTE` |
| `hannover_ladung_verstreut` | Palette und Metallteile als Vollsperrung | `REPLAN_ROUTE` |

## Szenariofamilien F1 bis F6: Lagen, die sich ändern

Getrennt von den 61 Sprintfällen liegen unter [`families/`](families/) sechs Familien mit je
drei Varianten. Innerhalb einer Familie ist das Startbild gleich, die richtige Antwort aber
verschieden; Akteure reagieren über Auslöser auf das, was das Fahrzeug tut (siehe
[README](README.md#ausloeser-akteure-reagieren-auf-das-ego)). Alle laufen im
Wahrnehmungsmodell `tracked`; die Stufe legt Prüfmodus und Rauschen fest.

| Familie | Stufe | Startbild | Varianten | Lernziel |
|---|---|---|---|---|
| F1 Verdeckte Ursache | C | Transporter steht ohne erkennbaren Grund | Müllabfuhr mit Müllwerker (warten) · Unfallstelle (wenden) · Umzug (vorbeifahren) | Erst Information kaufen, dann handeln |
| F2 Hindernis reagiert | B | Lieferwagen in zweiter Reihe | Fahrer weg (vorbeifahren) · Fahrer am Steuer (warten) · Bote kommt (warten) | Hinweise auf einen Fahrer ernst nehmen |
| F3 Gegenverkehr aus der Verdeckung | C | breiter Lkw verdeckt die Gegenspur | Pkw kommt · Radfahrer kommt (jeweils zurück, vorbeilassen, dann vorbei) · niemand kommt | Am Checkpoint neu entscheiden |
| F4 Rückweg verbaut | D | wie F1, dazu Verkehr von hinten | früh zu · spät zu (wenden) · nur Stau (vorbeifahren) | Früh entscheiden, solange Wenden geht |
| F5 Wende mit Tücken | D | Absperrung der eigenen Spur | frei · Radfahrer von hinten · Gegenverkehr (jeweils wenden, aber zur richtigen Zeit) | Wenden ist selbst riskant |
| F6 Lage entspannt sich | B | stehende Fahrzeuge | Stau löst sich · Stau fährt an, sobald man ausschert (jeweils warten) · Panne (vorbeifahren) | Nicht übervorsichtig, aber vor dem Punkt ohne Rückkehr neu prüfen |

Alle drei Varianten jeder Familie sind veröffentlicht, einschließlich ihrer Referenzbefehle
und Erfolgskriterien. [`scenario_sets/familien_alle.txt`](scenario_sets/familien_alle.txt)
enthält alle 18 Fälle. Die kleine Menge
[`scenario_sets/familien_sichtbar.txt`](scenario_sets/familien_sichtbar.txt) enthält weiterhin
je Familie einen empfohlenen Einstiegsfall; der Name ist historisch und bedeutet keine
Zugriffsbeschränkung. Im Katalog markiert `introductory` diese sechs Fälle, `visible` ist
für alle Varianten wahr. Die Dateien erzeugt [`scripts/build_families.py`](scripts/build_families.py).

**Fairness:** Der Szenariolader prüft die drei Regeln für Auslöser (nichts aus dem Nichts, jede
Überraschung hat einen Hinweis, plausibles Verhalten). Ein Referenzagent, der nur die
Agentenwerkzeuge nutzt, löst alle Varianten über mehrere Seeds ohne Unfall. Einfache Strategien scheitern dagegen: Immer warten löst 5,
immer überholen 8, immer wenden 4 der 18 Varianten.

```bash
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/familien_sichtbar.txt --agent mein_agent:decide
python3 -m autonomy_recovery_sim batch autonomy_recovery_sim/scenario_sets/familien_alle.txt --agent mein_agent:decide
```

## Robustheit mit Seed-Variationen

Alle Ausgangsfälle bleiben transparent. [`scripts/make_variants.py`](scripts/make_variants.py)
erzeugt mit einem festen Seed reproduzierbare Varianten: Akteurpositionen werden um bis zu
8 m verschoben, Geschwindigkeiten um bis zu 15 % und Bewegungsstartzeiten um bis zu 1,5 s
verändert, jeweils innerhalb der Streckengrenzen. Zusätzlich wird der Wahrnehmungs-Seed
gesetzt. Die inhaltliche Variante bleibt gleich: Ein anderer Seed macht aus einer
Müllabfuhr keine Unfallstelle. Deshalb gehören alle drei Varianten zum veröffentlichten Katalog.

```bash
# Entwicklungsvarianten: gleicher Seed erzeugt dieselben Dateien
python3 autonomy_recovery_sim/scripts/make_variants.py \
  autonomy_recovery_sim/scenario_sets/familien_alle.txt \
  --count 3 --seed 2026 --output artifacts/varianten/familien-seed-2026
python3 -m autonomy_recovery_sim batch artifacts/varianten/familien-seed-2026/variants.txt \
  --agent mein_agent:decide --output artifacts/experiments/familien-seed-2026
```

Messt ebenso die 61 Sprintfälle mit `released_sprint4.txt` als Quelle und verwendet für jeden
Seed einen eigenen Ordner. Legt Entwicklungs-Seeds im Versuchsplan fest; nach dem Freeze
folgen weitere Seeds, die ebenfalls dokumentiert werden. `--repeats` wiederholt denselben
Fall und ersetzt keine Seed-Variation. Bei dynamischen Fällen können Verschiebungen die
Plausibilität der Referenzlabels verändern; `--check` zeigt auffällige Baseline-Ergebnisse,
die am Trace untersucht werden müssen. Ein Fehlschlag der Baseline beweist kein falsches Label.

Der Agent entscheidet anhand seiner Beobachtungen. Szenario-IDs und Referenzlabels dürfen
nicht als Entscheidungstabelle verwendet werden; ein neuer Seed verhindert solche
Abkürzungen nicht zuverlässig. Mehrere Seeds prüfen Robustheit innerhalb der bekannten
Falltypen und belegen keine Verallgemeinerung auf beliebige neue Situationen.
