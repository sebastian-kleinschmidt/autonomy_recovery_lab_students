# Bekannte Fehler in AutonomyRecoverySim

## Offen

Derzeit keine.

## Erledigt

- ~~Der Simulationsfaktor wirkt nur nach oben.~~ — `LiveSimulation._run` wartete
  höchstens 0,1 s und schritt danach sofort weiter, auch wenn der nächste Takt
  noch nicht erreicht war. Bei 0,25x und 0,5x lief die Simulation deshalb in
  Echtzeit. Jetzt wird erst geschritten, wenn der Takt erreicht ist; die kurzen
  Wartescheiben bleiben für eine reaktionsfähige Bedienung erhalten. Ein Test
  in `tests/test_console.py` misst die Zeitlupe.

- ~~Der Startbutton geht meistens nicht direkt, während einzelschritte immer
  funktioniert~~ — Der Startknopf war ein reiner Umschalter: Der zweite Klick
  eines Doppelklicks sendete sofort `pause`, die Simulation stand wieder bei
  t ~ 0. `Einzelschritt` ist kein Umschalter und war deshalb nie betroffen.
  Ein umkehrender Klick innerhalb von 450 ms wird jetzt verworfen. Zusaetzlich
  ueberlebt die Zeichenschleife einen einzelnen Renderfehler, statt dauerhaft
  einzufrieren.
- ~~Wenn ein Radfahrer verdeckt wird, wird er als "teilweise" verdeckt im UI
  angezeigt.~~ — Die Wahrnehmung tastete nur Mittelpunkt und vier Ecken ab und
  wertete jeden Treffer als Detektion; eine einzelne streifende Sichtlinie auf
  genau eine Ecke ergab "teilweise sichtbar" samt exakter Position und
  Geschwindigkeit. Jetzt wird die Silhouette dicht abgetastet und erst ab
  `perception.min_detectable_fraction` (Standard 0,3) als erkannt gewertet.
  Im Referenzszenario meldet der Radfahrer dadurch eine Sekunde frueher
  "verdeckt".

  Rest-Effekt, bewusst so belassen: Das Ego misst aus vier Ecksensoren, die
  Kamera der 3D-Ansicht sitzt auf der Mittelachse. Ein Ecksensor blickt
  deshalb knapp am LKW vorbei und meldet den Radfahrer noch rund 1,5 s laenger
  als sichtbar, als die Kamera ihn zeigt. Den seitlichen Versatz zu entfernen
  ist keine Option: Er ist genau das, was dem Ego erlaubt, an einem stehenden
  Blocker vorbei auf die Gegenfahrbahn zu blicken - ohne ihn scheitern acht
  Tests inklusive der kompletten Szenariomatrix. Damit das UI nicht laenger
  widerspricht, wird die tuerkise Sichtflaeche jetzt aus denselben vier
  Sensorurspruengen gezeichnet statt aus der Fahrzeugmitte.
