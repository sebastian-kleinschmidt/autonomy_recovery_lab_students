"""Eigenstaendige HTML-Auswertung einer Batch-Auswertung (``batch-report.html``).

Beantwortet die Frage der Abteilung: Arbeitet die Remote Assistance mit ihrem
Agenten wirtschaftlich, und sind die Kunden zufrieden? Keine externen Ressourcen,
die Datei laesst sich offline oeffnen und archivieren.
"""

from __future__ import annotations

from html import escape

COST_LABELS = {
    "personal_injury": "Personenschaden",
    "material_damage": "Sachschaden",
    "remote_assistance": "Remote Assistance",
    "standstill": "Standzeit",
    "detour": "Umweg / Rueckfahrt",
    "recovery": "Bergung",
    "blocking_traffic": "Verkehrsbehinderung",
    "aborted_mission": "Missionsabbruch",
    "stranded_passengers": "Gestrandete Fahrgaeste",
    "passenger_refund": "Fahrgast-Erstattung",
    "rule_engine": "Regel-Engine",
    "rejected_commands": "Abgelehnte Befehle",
}

STYLE = """
:root{--bg:#f6f5f0;--card:#fff;--ink:#17212b;--muted:#5b6672;--line:#dcd9cf;--ok:#0a7a5c;--warn:#b7791f;--bad:#b42318;--bar:#087e8b}
@media (prefers-color-scheme:dark){:root{--bg:#12171c;--card:#1a2129;--ink:#e8ecef;--muted:#9aa5b1;--line:#2c3742;--ok:#3cc19b;--warn:#e0a63d;--bad:#f0655a;--bar:#3aa9b8}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1280px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:1.4rem;margin:0 0 4px}h2{font-size:1.05rem;margin:32px 0 12px}
.sub{color:var(--muted);margin:0 0 24px}
.hero{display:grid;grid-template-columns:auto 1fr;gap:24px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:24px}
.grade{width:112px;height:112px;border-radius:24px;display:grid;place-items:center;font-size:4rem;font-weight:800;color:#fff}
.grade.A{background:var(--ok)}.grade.B{background:#5a9f3a}.grade.C{background:var(--warn)}.grade.D{background:var(--bad)}
.verdicts{display:flex;flex-wrap:wrap;gap:8px 24px;margin:8px 0 0}
.pill{font-weight:600}.pill.yes{color:var(--ok)}.pill.no{color:var(--bad)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:16px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.kpi b{display:block;font-size:1.35rem}.kpi span{color:var(--muted);font-size:.85rem}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:middle;font-size:.9rem}
th{color:var(--muted);font-weight:600;font-size:.8rem;text-transform:uppercase;letter-spacing:.04em}
tr:last-child td{border-bottom:0}td.num{text-align:right;font-variant-numeric:tabular-nums}
td.finding{min-width:240px;font-size:.82rem}td.finding details{margin-top:4px;color:var(--muted)}td.finding ul{margin:4px 0 0;padding-left:18px}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:.78rem;font-weight:700;color:#fff}
.tag.pass{background:var(--ok)}.tag.fail{background:var(--bad)}
.meter{position:relative;height:8px;min-width:90px;background:var(--line);border-radius:4px;overflow:hidden}
.meter i{position:absolute;inset:0 auto 0 0;background:var(--bar)}.meter.over i{background:var(--bad)}
.bars{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px}
.bar{display:grid;grid-template-columns:190px 1fr 96px;gap:12px;align-items:center;padding:4px 0}
.bar .meter{height:12px}.bar em{font-style:normal;text-align:right;font-variant-numeric:tabular-nums}
.note{color:var(--muted);font-size:.85rem;margin-top:8px}
a{color:var(--bar);text-underline-offset:2px}td a{font-weight:600;white-space:nowrap}td.num{white-space:nowrap}
.scroll{overflow-x:auto;border-radius:12px}.scroll table{min-width:1100px}
@media (max-width:640px){.hero{grid-template-columns:1fr}.bar{grid-template-columns:1fr 80px}.bar .meter{grid-column:1/-1;order:3}}
"""


def _eur(value: object) -> str:
    return f"{float(value):,.2f}".replace(",", " ").replace(".", ",") + " €"  # type: ignore[arg-type]


def _pct(value: object) -> str:
    return f"{float(value) * 100:.0f} %"  # type: ignore[arg-type]


def _progress_section(payload: dict[str, object]) -> str:
    """Fortschritt gegenueber dem vorigen Lauf und kurzer Verlauf (progress.py)."""
    progress: dict = payload.get("progress") or {}  # type: ignore[assignment]
    if not progress:
        return ""
    if not progress.get("available") or not progress.get("comparable"):
        head = f'<p class="note">{escape(str(progress.get("reason", "kein Vergleich")))}.</p>'
    else:
        delta = int(progress["passed_now"]) - int(progress["passed_before"])
        lists = "".join(
            f"<p><strong>{label}:</strong> {escape(', '.join(progress[key]))}</p>"
            for label, key in (("Neu bestanden", "newly_passed"), ("Neu gescheitert", "newly_failed"))
            if progress[key]
        ) or "<p>Dieselben Fälle bestanden wie zuvor.</p>"
        head = (
            f"<p><strong>{progress['passed_before']} → {progress['passed_now']} bestanden ({delta:+d})</strong> · "
            f"Kollisionen {progress['collisions_before']} → {progress['collisions_now']} · "
            f"Kosten {_eur(progress['cost_before_eur'])} → {_eur(progress['cost_now_eur'])} · "
            f"Einstufung {escape(str(progress['rating_before']))} → {escape(str(progress['rating_now']))}</p>{lists}"
        )
    history = progress.get("history") or []
    rows = "".join(
        f"<tr><td>{escape(str(entry.get('time', '')).replace('T', ' ')[:16])}</td><td>{escape(str(entry.get('agent')))}</td>"
        f"<td class=num>{entry.get('passed')} / {entry.get('scenarios')}</td><td class=num>{entry.get('collisions')}</td>"
        f"<td class=num>{_eur(entry.get('cost_eur', 0.0))}</td><td>{escape(str(entry.get('rating')))}</td></tr>"
        for entry in reversed(history)
    )
    table = (
        "<table><thead><tr><th>Lauf</th><th>Agent</th><th>Bestanden</th><th>Kollisionen</th><th>Kosten</th>"
        f"<th>Einstufung</th></tr></thead><tbody>{rows}</tbody></table>"
        if len(history) > 1
        else ""
    )
    return f"<h2>Fortschritt seit dem letzten Lauf</h2>{head}{table}"


def render_html_report(payload: dict[str, object]) -> str:
    summary: dict = payload["summary"]  # type: ignore[assignment]
    grading: dict = summary["grading"]
    criteria: dict = grading["criteria"]
    scenarios: list[dict] = payload["scenarios"]  # type: ignore[assignment]
    stats: list[dict] = payload["scenario_stats"]  # type: ignore[assignment]

    def yes_no(flag: bool) -> str:
        return f'<span class="pill {"yes" if flag else "no"}">{"ja" if flag else "nein"}</span>'

    satisfaction = summary["average_customer_satisfaction"]
    kpis = [
        ("Gesamtkosten", _eur(summary["total_cost_eur"])),
        ("Im Budget", f"{summary['within_budget_count']} / {summary['scenario_count']}"),
        ("Remote-Assistance-Anrufe", str(summary["remote_assistance_calls"])),
        ("Kundenzufriedenheit", "–" if satisfaction is None else f"{float(satisfaction):.2f}"),
        ("Kollisionen", str(summary["collision_count"])),
        ("Personenschäden", str(summary["personal_injury_count"])),
        ("Fehlalarme", f"{summary['false_alarm_count']} / {summary['no_intervention_scenarios']}"),
        ("Verpasste Eingriffe", f"{summary['missed_intervention_count']} / {summary['intervention_scenarios']}"),
        ("Bestanden", f"{summary['passed_count']} / {summary['scenario_count']}"),
    ]
    if summary.get("sequence_scenario_count"):
        kpis.append(
            (
                "Lösungswege vollständig",
                f"{summary['sequence_complete_count']} / {summary['sequence_scenario_count']}"
                f" · Ø {_pct(summary['average_sequence_score'])}",
            )
        )

    totals: dict[str, float] = dict(payload["cost_items"])  # type: ignore[call-overload]
    biggest = max(totals.values(), default=0.0) or 1.0
    bars = "".join(
        f'<div class="bar"><span>{escape(COST_LABELS.get(name, name))}</span>'
        f'<div class="meter"><i style="width:{min(100.0, value / biggest * 100):.1f}%"></i></div>'
        f"<em>{_eur(value)}</em></div>"
        for name, value in sorted(totals.items(), key=lambda item: -item[1])
    ) or '<p class="note">Keine Kosten angefallen.</p>'

    rows = []
    for item in scenarios:
        budget = float(item["budget_eur"])
        cost = float(item["total_cost_eur"])
        share = min(100.0, cost / budget * 100) if budget else 100.0
        run = f" · Lauf {item['run']}" if int(summary["repeats"]) > 1 else ""
        findings = [str(finding) for finding in item.get("diagnosis") or []]
        finding_html = ""
        if findings:
            rest = "".join(f"<li>{escape(finding)}</li>" for finding in findings[1:])
            finding_html = escape(findings[0]) + (
                f"<details><summary>{len(findings) - 1} weitere</summary><ul>{rest}</ul></details>" if rest else ""
            )
        details = item.get("details")
        name = escape(str(item["scenario_id"])) + run
        link = f'<a href="{escape(str(details))}">{name}</a>' if details else name
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('release') or '–'))}</td>"
            f"<td>{link}</td>"
            f"<td>{escape(str(item['command']))}</td>"
            + (
                f"<td>{escape(str(item['outcome']))}</td>"
                if payload.get("hide_reference")
                else f"<td>{escape(str(item['expected_outcome']))} → {escape(str(item['outcome']))}</td>"
            )
            + ""
            f'<td><div class="meter {"over" if cost > budget else ""}"><i style="width:{share:.1f}%"></i></div></td>'
            f'<td class="num">{_eur(cost)} / {_eur(budget)}</td>'
            f'<td><span class="tag {"pass" if item["passed"] else "fail"}">'
            f'{"bestanden" if item["passed"] else "fehlgeschlagen"}</span></td>'
            f'<td class="finding">{finding_html}</td>'
            "</tr>"
        )

    stat_table = ""
    if int(summary["repeats"]) > 1:
        stat_rows = "".join(
            f"<tr><td>{escape(str(stat['scenario_id']))}</td><td class=num>{_pct(stat['pass_rate'])}</td>"
            f"<td class=num>{_eur(stat['cost_mean_eur'])}</td><td class=num>± {_eur(stat['cost_std_eur'])}</td>"
            f"<td>{escape(', '.join(stat['commands']))}</td></tr>"
            for stat in stats
        )
        stat_table = (
            f"<h2>Streuung über {summary['repeats']} Läufe</h2><table><thead><tr><th>Szenario</th>"
            "<th>Bestehensquote</th><th>Kosten Mittel</th><th>Streuung</th><th>Befehle</th></tr></thead>"
            f"<tbody>{stat_rows}</tbody></table>"
        )

    releases: list[dict] = payload.get("releases") or []  # type: ignore[assignment]
    release_table = ""
    if releases:
        release_rows = "".join(
            f"<tr><td>{escape(str(row['release']))}</td>"
            f"<td class=num>{row['passed_count']} / {row['scenario_count']}</td>"
            f"<td class=num>{_eur(row['total_cost_eur'])}</td><td class=num>{row['collision_count']}</td></tr>"
            for row in releases
        )
        release_table = (
            "<h2>Nach Freigabestufe</h2><table><thead><tr><th>Freigabe</th><th>Bestanden</th>"
            f"<th>Kosten</th><th>Kollisionen</th></tr></thead><tbody>{release_rows}</tbody></table>"
        )

    reasons = "".join(f"<li>{escape(reason)}</li>" for reason in grading["reasons"])
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AutonomyRecoverySim Auswertung</title><style>{STYLE}</style></head>
<body><main>
<h1>Remote-Assistance-Auswertung</h1>
<p class="sub">Arbeitet die Abteilung mit ihrem Agenten wirtschaftlich, und sind die Kunden zufrieden?</p>
<section class="hero">
<div class="grade {escape(str(grading['grade']))}" aria-label="Einstufung {escape(str(grading['grade']))}">{escape(str(grading['grade']))}</div>
<div><strong>Einstufung {escape(str(grading['grade']))}</strong>
<div class="verdicts"><span>Wirtschaftlich: {yes_no(bool(grading['economic']))}</span>
<span>Kunden zufrieden: {yes_no(bool(grading['customers_satisfied']))}</span></div>
<p class="note">Bestehensquote {_pct(criteria['pass_rate'])} · Budgetquote {_pct(criteria['budget_rate'])} ·
Episoden mit Remote Assistance {_pct(criteria['remote_assistance_rate'])}</p>
<ul class="note">{reasons}</ul></div>
</section>
<div class="kpis">{''.join(f'<div class="kpi"><b>{escape(value)}</b><span>{escape(label)}</span></div>' for label, value in kpis)}</div>
{_progress_section(payload)}
<h2>Kosten nach Position</h2><div class="bars">{bars}</div>
{release_table}
<h2>Szenarien</h2>
<p class="note">Der Befund nennt den wichtigsten Grund zuerst. Ein Klick auf das Szenario öffnet die Detailseite
mit Befehlsfolge und Agent-Trace (<code>report.md</code>).</p>
<div class="scroll"><table><thead><tr><th>Freigabe</th><th>Szenario</th><th>Befehl</th><th>Ausgang</th><th>Budget</th><th>Kosten / Budget</th><th>Ergebnis</th><th>Befund</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
{stat_table}
<p class="note">Einstufung als Rückmeldung, keine Note: D bei jeder Kollision oder jedem Personenschaden. A ab 90 % Bestehens- und Budgetquote,
höchstens 25 % Episoden mit Remote Assistance und Zufriedenheit ≥ 0,70. B ab 75 % / 75 % und Zufriedenheit ≥ 0,50.
C ab 50 % Bestehensquote. Beträge sind Modellannahmen (costs.py).</p>
</main></body></html>
"""
