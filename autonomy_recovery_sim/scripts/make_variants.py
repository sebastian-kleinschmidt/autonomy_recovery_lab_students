#!/usr/bin/env python3
"""Erzeugt Varianten bekannter Szenarien, um die Verallgemeinerung eines Agenten zu pruefen.

Gleiche Schnittstelle und gleiches Label, aber veraenderte Geometrien,
Geschwindigkeiten und Zeitpunkte. Derselbe Seed liefert dieselben Varianten.
Teams koennen damit eigene Varianten erzeugen; die Lehrenden erzeugen die
verdeckten Prueffaelle mit einem eigenen, nicht veroeffentlichten Seed. Beispiel:

    python3 autonomy_recovery_sim/scripts/make_variants.py autonomy_recovery_sim/scenario_sets/public.txt \
        --count 3 --seed 2026 --output artifacts/hidden --check
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from autonomy_recovery_sim.batch import discover_scenarios, run_batch  # noqa: E402
from autonomy_recovery_sim.policy import heuristic_agent  # noqa: E402
from autonomy_recovery_sim.scenario import load_scenario  # noqa: E402

SHIFT_M = 8.0
SPEED_FACTOR = (0.85, 1.15)
TIME_SHIFT_S = 1.5


def make_variant(data: dict, source: Path, output: Path, rng: random.Random, index: int, road_length_m: float) -> dict:
    variant = json.loads(json.dumps(data))
    variant["id"] = f"{data['id']}_v{index}"
    variant["seed"] = rng.randrange(1_000_000)
    for key in ("map_file", "context_file"):
        if variant["road"].get(key):
            target = (source.parent / variant["road"][key]).resolve()
            variant["road"][key] = os.path.relpath(target, output.resolve())
    actors = variant.get("actors", [])
    if actors:
        lowest = min(actor["s_m"] for actor in actors)
        highest = max(actor["s_m"] for actor in actors)
        shift = rng.uniform(-SHIFT_M, SHIFT_M)
        # Akteure bleiben vor dem Ego-Start und innerhalb der Strecke.
        shift = max(shift, variant["ego"]["start_s_m"] + 20.0 - lowest, 5.0 - lowest)
        shift = min(shift, road_length_m - 5.0 - highest)
        factor = rng.uniform(*SPEED_FACTOR)
        time_shift = rng.uniform(-TIME_SHIFT_S, TIME_SHIFT_S)
        for actor in actors:
            actor["s_m"] = round(actor["s_m"] + shift, 2)
            if actor.get("speed_mps"):
                actor["speed_mps"] = round(actor["speed_mps"] * factor, 2)
            if actor.get("target_speed_mps"):
                actor["target_speed_mps"] = round(actor["target_speed_mps"] * factor, 2)
            if actor.get("motion_start_time_s") is not None:
                actor["motion_start_time_s"] = round(max(0.0, actor["motion_start_time_s"] + time_shift), 2)
    return variant


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="Szenariodatei, Verzeichnis oder .txt-Liste")
    parser.add_argument("--count", type=int, default=3, help="Varianten je Szenario")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="Baseline-Lauf zur Kalibrierung der Labels")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    written = []
    for path in discover_scenarios(args.source):
        data = json.loads(path.read_text(encoding="utf8"))
        road_length = load_scenario(path).road.length_m
        for index in range(1, args.count + 1):
            rng = random.Random(f"{args.seed}:{data['id']}:{index}")
            variant = make_variant(data, path, args.output, rng, index, road_length)
            target = args.output / f"{variant['id']}.json"
            target.write_text(json.dumps(variant, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
            load_scenario(target)  # Schema- und Plausibilitaetspruefung
            written.append(target)
    (args.output / "hidden.txt").write_text(
        f"# Varianten mit Seed {args.seed}\n"
        + "".join(f"{target.name}\n" for target in written),
        encoding="utf8",
    )
    print(f"{len(written)} Varianten nach {args.output} geschrieben")
    if args.check:
        batch = run_batch(args.output / "hidden.txt", agent=heuristic_agent, agent_name="baseline")
        summary = batch.to_dict()["summary"]
        print(f"Baseline: {summary['passed_count']}/{summary['scenario_count']} bestanden, Kollisionen {summary['collision_count']}")
        for item in batch.evaluations:
            if not item.passed:
                print(f"  Label pruefen: {item.result.scenario_id} -> {item.result.command}/{item.result.outcome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
