# Asset-Spezifikation fuer AutonomyRecoverySim

Die aktuelle Oberflaeche zeichnet alle Fahrzeuge prozedural. Die folgenden
Assets sind fuer die naechste Ausbaustufe mit einem echten WebGL-Renderer
gedacht. Mit denselben 3D-Modellen koennen dann die perspektivische und die
orthografische Top-down-Ansicht erzeugt werden.

## Verbindliches Austauschformat

- Laufzeitformat: **glTF 2.0 Binary (`.glb`)**
- Editierbare Quelle: **Blender (`.blend`)**, optional zusaetzlich FBX
- Vorschau: **WebP (`.webp`)**, 1024 × 1024 px, transparenter Hintergrund
- Lizenz und Urheber: **UTF-8-Text (`LICENSE.txt`)** je Asset-Paket
- Einheit: 1 Blender-/glTF-Einheit = 1 Meter
- Achsen: `+Y` oben, `+Z` Fahrzeugfront, `+X` Fahrzeugrechte Seite
- Ursprung: Mitte der Fahrzeuggrundflaeche auf Fahrbahnhoehe
- Transformationen vor Export anwenden; Skalierung im GLB muss `(1, 1, 1)` sein

Bevorzugt werden wenige PBR-Materialien ohne Texturen. Falls Texturen noetig
sind: PNG fuer Transparenz, JPEG fuer deckende Farb- und Materialkarten. Eine
Textur soll maximal 2048 × 2048 px gross sein.

## Benoetigte Fahrzeugmodelle

| Datei | Rolle | Zielabmessungen | Zielbudget |
|---|---|---:|---:|
| `vehicles/ego_minibus.glb` | Ego, ID.-Buzz-aehnlicher Kleinbus ohne Markenlogo | 4,71 × 1,99 × 1,94 m | max. 20.000 Dreiecke |
| `vehicles/car_compact.glb` | Kompaktwagen | 4,20 × 1,78 × 1,48 m | max. 10.000 Dreiecke |
| `vehicles/car_sedan.glb` | Limousine | 4,70 × 1,84 × 1,45 m | max. 10.000 Dreiecke |
| `vehicles/suv.glb` | SUV/Crossover | 4,65 × 1,90 × 1,70 m | max. 12.000 Dreiecke |
| `vehicles/van.glb` | Lieferwagen | 5,40 × 2,05 × 2,45 m | max. 12.000 Dreiecke |
| `vehicles/truck.glb` | zweiachsiger Lkw | 8,00 × 2,50 × 3,30 m | max. 15.000 Dreiecke |
| `vehicles/city_bus.glb` | Linienbus | 12,00 × 2,55 × 3,20 m | max. 18.000 Dreiecke |
| `vehicles/motorcycle.glb` | Motorrad mit neutraler Fahrerfigur | 2,15 × 0,80 × 1,35 m | max. 8.000 Dreiecke |
| `vehicles/bicycle.glb` | Fahrrad mit neutraler Fahrerfigur | 1,80 × 0,65 × 1,75 m | max. 8.000 Dreiecke |

Der Ego-Kleinbus erhaelt die AutonomyRecoverySim-Farben `#087f73` fuer den unteren Aufbau
und `#ece9df` fuer Dach und obere Karosserie. Alle Fremdfahrzeuge verwenden ein
neutrales Grau um `#9da3a1`. Scheiben duerfen dunkelgrau, aber nicht vollstaendig
schwarz sein. Logos, Schriftzuege und geschuetzte Designmerkmale werden nicht
uebernommen.

## Empfohlene Zusatzobjekte

| Datei | Format | Zweck |
|---|---|---|
| `actors/pedestrian_adult.glb` | GLB | erkannte Person |
| `objects/traffic_cone.glb` | GLB | Baustellen- und Hindernisfall |
| `objects/barrier.glb` | GLB | teilweise oder vollstaendige Sperrung |
| `objects/bollard.glb` | GLB | schmales statisches Hindernis |
| `objects/traffic_light.glb` | GLB | spaetere Kreuzungsszenarien |
| `objects/sign_post.glb` | GLB | spaetere Verkehrszeichenszenarien |

Diese Objekte sollten jeweils unter 5.000 Dreiecken bleiben.

## Aufbau eines Fahrzeug-GLB

Empfohlene Node-Namen:

```text
vehicle_root
├── body
├── windows
├── wheel_front_left
├── wheel_front_right
├── wheel_rear_left
└── wheel_rear_right
```

`vehicle_root` liegt im definierten Ursprung. Raeder muessen getrennte Nodes
sein, damit sie spaeter gelenkt und gedreht werden koennen. Materialnamen:
`body_primary`, `body_secondary`, `glass`, `tire`, `light_front` und
`light_rear`. Animationen sind nicht erforderlich.

## Optionale 2D-Fallbacks

Nur falls die Top-down-Ansicht ohne WebGL weiterbetrieben werden soll:

- pro Fahrzeug `*_top.svg`
- transparenter Hintergrund
- `viewBox="0 0 200 100"`
- Fahrzeugfront zeigt nach rechts
- keine Beschriftung und kein Schatten im Asset
- Formen muessen auch bei 24 px Laenge unterscheidbar bleiben

PNG-Sprites sind nicht erforderlich. SVG bleibt fuer Zoom und Umfaerbung
schaerfer und kann aus den 3D-Modellen als orthografische Draufsicht abgeleitet
werden.

## Abgabe je Asset

```text
ego_minibus/
├── ego_minibus.blend
├── ego_minibus.glb
├── ego_minibus.webp
└── LICENSE.txt
```

Vor der Integration werden Massstab, Ursprung, Achsen, Materialnamen,
Dreieckszahl und transparente Vorschau automatisiert geprueft.

Der Ego-Kleinbus kann auf die verbindliche Zielgroesse normalisiert werden:

```bash
python3 autonomy_recovery_sim/scripts/normalize_vehicle_glb.py \
  autonomy_recovery_sim/vehicles/ego_minibus.glb \
  autonomy_recovery_sim/vehicles/ego_minibus.glb
```

Dabei wird die Geometrie auf `4,71 × 1,99 × 1,94 m` skaliert, der Ursprung in
die Mitte der Grundflaeche gelegt und die Node-Transformation angewendet.
