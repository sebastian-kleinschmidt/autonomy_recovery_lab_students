#!/usr/bin/env python3
"""Erzeugt die inkrementellen und kumulativen Sprint-Sets aus dem Szenarienkatalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "scenario_catalog.json"
SET_DIR = ROOT / "scenario_sets"
FILENAMES = {
    "bootcamp": "bootcamp.txt",
    "sprint1": "sprint1_foundations.txt",
    "sprint2": "sprint2_decisions.txt",
    "sprint3": "sprint3_robustness.txt",
    "sprint4": "sprint4_transfer.txt",
}


def load_catalog() -> tuple[list[str], list[dict[str, object]]]:
    data = json.loads(CATALOG.read_text(encoding="utf8"))
    order = list(data["release_order"])
    scenarios = list(data["scenarios"])
    ids = [str(item["id"]) for item in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("scenario_catalog.json enthaelt doppelte IDs")
    unknown = sorted({str(item["release"]) for item in scenarios} - set(order))
    if unknown:
        raise ValueError(f"Unbekannte Release-Stufen: {', '.join(unknown)}")
    disk = {path.stem for path in (ROOT / "scenarios").glob("*.json")}
    if set(ids) != disk:
        missing = sorted(disk - set(ids))
        extra = sorted(set(ids) - disk)
        raise ValueError(f"Katalogabweichung: fehlen={missing}, unbekannt={extra}")
    return order, scenarios


def render(title: str, ids: list[str]) -> str:
    lines = [f"# {title}"]
    lines.extend(f"../scenarios/{scenario_id}.json" for scenario_id in ids)
    return "\n".join(lines) + "\n"


def expected_files() -> dict[Path, str]:
    order, scenarios = load_catalog()
    by_release = {
        release: [str(item["id"]) for item in scenarios if item["release"] == release]
        for release in order
    }
    files: dict[Path, str] = {}
    for release in order:
        files[SET_DIR / FILENAMES[release]] = render(
            f"Neue Szenarien in {release}; nicht kumulativ.", by_release[release]
        )
    cumulative: list[str] = []
    for release in order:
        cumulative.extend(by_release[release])
        if release != "bootcamp":
            files[SET_DIR / f"released_{release}.txt"] = render(
                f"Kumulative Freigabe bis einschliesslich {release}.", cumulative
            )
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="nur auf Abweichungen pruefen")
    args = parser.parse_args(argv)
    problems: list[str] = []
    for path, expected in expected_files().items():
        actual = path.read_text(encoding="utf8") if path.exists() else None
        if actual == expected:
            continue
        if args.check:
            problems.append(str(path.relative_to(ROOT)))
        else:
            path.write_text(expected, encoding="utf8")
            print(f"geschrieben: {path.relative_to(ROOT)}")
    if problems:
        print("Nicht aktuell: " + ", ".join(problems))
        return 1
    if args.check:
        print("Szenarienkatalog und Sprint-Sets sind konsistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
