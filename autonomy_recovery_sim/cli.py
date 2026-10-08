from __future__ import annotations

import argparse
from pathlib import Path

from .agent_loader import load_agent
from .batch import run_batch
from .render import write_svg
from .scenario import GUARDRAILS, PERCEPTION_MODELS, with_guardrails, load_scenario, with_perception_model, with_vla_mode
from .simulation import run_scenario


def _single_main(argv: list[str] | None) -> int:
    parser = argparse.ArgumentParser(description="Deterministischer 2D-Simulator fuer Agentic Autonomy Recovery")
    parser.add_argument("scenario", type=Path, help="Szenario als JSON")
    parser.add_argument("--output", type=Path, default=Path("artifacts/autonomy-recovery-sim"))
    parser.add_argument(
        "--agent",
        default="none",
        help="none, baseline, llm oder python_modul:funktion (Standard: none)",
    )
    parser.add_argument("--vla", action="store_true", help="Szenario mit VLA-Fahrstack ausfuehren")
    parser.add_argument(
        "--perception",
        choices=PERCEPTION_MODELS,
        help="Wahrnehmungsmodell erzwingen (tracked: Objektliste mit Messunsicherheit)",
    )
    parser.add_argument(
        "--guardrails",
        choices=GUARDRAILS,
        help="Pruefmodus erzwingen (off: keine vorausschauenden Abbrueche, Unfaelle moeglich)",
    )
    args = parser.parse_args(argv)
    try:
        loaded_agent = load_agent(args.agent)
    except ValueError as exc:
        parser.error(str(exc))

    scenario = load_scenario(args.scenario)
    if args.perception:
        scenario = with_perception_model(scenario, args.perception)
    if args.guardrails:
        scenario = with_guardrails(scenario, args.guardrails)
    result = run_scenario(
        with_vla_mode(scenario) if args.vla else scenario,
        agent=loaded_agent.policy,
        agent_name=loaded_agent.name,
    )
    target = args.output / result.scenario_id
    result.write_json(target / "result.json")
    write_svg(result, target / "replay.svg")

    print(f"Szenario:   {result.scenario_id}")
    print(f"Agent:      {result.agent_name} ({result.agent_status})")
    print(f"Befehl:     {result.command} ({'korrekt' if result.command_correct else 'falsch'})")
    print(f"Ausgang:    {result.outcome}")
    print(f"Kosten:     {float(result.costs['total_eur']):.2f} EUR")
    print(f"Kollision:  {'ja' if result.collision else 'nein'}")
    print(f"Ergebnis:   {target / 'result.json'}")
    print(f"Darstellung:{target / 'replay.svg'}")
    return 0 if result.command_correct and not result.collision else 1


RELEASE_SETS = {
    "bootcamp": "bootcamp.txt",
    "sprint1": "released_sprint1.txt",
    "sprint2": "released_sprint2.txt",
    "sprint3": "released_sprint3.txt",
    "sprint4": "released_sprint4.txt",
}


def _batch_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Alle AutonomyRecoverySim-Szenarien reproduzierbar auswerten")
    parser.add_argument(
        "source",
        type=Path,
        nargs="?",
        help="Szenario, Ordner oder Set-Datei (Standard: alle Szenarien)",
    )
    parser.add_argument(
        "--release",
        choices=[*RELEASE_SETS, "all"],
        help="statt source: die bis zu dieser Stufe empfohlenen Szenarien (all = alle Sprintfälle)",
    )
    parser.add_argument(
        "--vla",
        action="store_true",
        help="alle Szenarien mit VLA-Fahrstack: Objektklassen, Profile und Signalzustaende nur als Modelltext",
    )
    parser.add_argument(
        "--perception",
        choices=PERCEPTION_MODELS,
        help="Wahrnehmungsmodell fuer alle Szenarien erzwingen (tracked: Objektliste mit Messunsicherheit)",
    )
    parser.add_argument(
        "--guardrails",
        choices=GUARDRAILS,
        help="Pruefmodus fuer alle Szenarien erzwingen (off: keine vorausschauenden Abbrueche)",
    )
    parser.add_argument(
        "--hide-reference",
        action="store_true",
        help="Referenzbefehle und -begruendungen nicht in die Berichte schreiben (Versuch ohne Referenzanzeige)",
    )
    parser.add_argument("--output", type=Path, default=Path("artifacts/autonomy-recovery-sim/batch"))
    parser.add_argument(
        "--agent",
        default="none",
        help="none, baseline, llm oder python_modul:funktion (Standard: none)",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Laeufe je Szenario, fuer nichtdeterministische LLM-Agenten (Standard: 1)",
    )
    args = parser.parse_args(argv)
    if args.source is not None and args.release is not None:
        parser.error("source und --release nicht gleichzeitig angeben")
    package = Path(__file__).resolve().parent
    if args.release in RELEASE_SETS:
        source = package / "scenario_sets" / RELEASE_SETS[args.release]
    elif args.source is not None:
        source = args.source
    else:
        source = package / "scenarios"
    try:
        loaded_agent = load_agent(args.agent)
    except ValueError as exc:
        parser.error(str(exc))
    if args.repeats < 1:
        parser.error("--repeats muss mindestens 1 sein")
    result = run_batch(
        source,
        agent=loaded_agent.policy,
        agent_name=loaded_agent.name,
        repeats=args.repeats,
        hide_reference=args.hide_reference,
        vla_mode=args.vla,
        perception_model=args.perception,
        guardrails=args.guardrails,
    )
    progress = result.write(args.output)
    summary = result.to_dict()["summary"]
    assert isinstance(summary, dict)
    print(f"Szenarien:  {summary['passed_count']}/{summary['scenario_count']} bestanden")
    print(f"Agent:      {loaded_agent.name}")
    if args.vla:
        print("Fahrstack:  VLA-Modus fuer alle Szenarien")
    if args.perception:
        print(f"Wahrnehmung:{args.perception} fuer alle Szenarien")
    print(f"Genauigkeit:{float(summary['decision_accuracy']):.1%}")
    print(f"Kollisionen:{summary['collision_count']}")
    grading = summary["grading"]
    assert isinstance(grading, dict)
    print(f"Einstufung: {grading['grade']} (Kosten {float(summary['total_cost_eur']):.2f} EUR, "
          f"im Budget {summary['within_budget_count']}/{summary['scenario_count']})")
    for row in result.to_dict()["releases"]:  # type: ignore[union-attr]
        print(f"  {row['release']:<12} {row['passed_count']}/{row['scenario_count']} bestanden")
    from .progress import summary_lines

    for line in summary_lines(progress):
        print(line)
    print(f"Bericht:    {args.output / 'batch-report.md'}")
    print(f"Website:    {args.output / 'batch-report.html'}")
    print(f"Details:    {args.output / 'scenarios'}/<szenario>/report.md")
    return 0 if result.passed else 1


def _validate_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="AutonomyRecoverySim-Szenarien validieren")
    parser.add_argument("source", type=Path, nargs="?", default=Path("autonomy_recovery_sim/scenarios"))
    args = parser.parse_args(argv)
    paths = [args.source] if args.source.is_file() else sorted(args.source.glob("*.json"))
    if not paths:
        parser.error(f"Keine Szenarien unter {args.source} gefunden")
    for path in paths:
        scenario = load_scenario(path)
        print(f"OK {scenario.scenario_id}: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv is not None else None
    if args is None:
        import sys

        args = sys.argv[1:]
    if args and args[0] == "batch":
        return _batch_main(args[1:])
    if args and args[0] == "validate":
        return _validate_main(args[1:])
    return _single_main(args)
