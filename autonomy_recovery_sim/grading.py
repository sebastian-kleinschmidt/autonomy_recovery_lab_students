"""Einstufung A bis D fuer eine Batch-Auswertung.

Das Labor ist unbenotet; die Einstufung ist Rueckmeldung, keine Note. Sie beantwortet
die zwei Fragen der Abteilung: Arbeitet die Remote Assistance mit ihrem Agenten
wirtschaftlich, und sind die Kunden zufrieden?
Sicherheit ist ein hartes Tor: Kollision oder Personenschaden ergeben immer D,
egal wie billig oder erfolgreich der Rest ist.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class GradeThresholds:
    a_pass_rate: float = 0.90
    a_budget_rate: float = 0.90
    a_remote_assistance_rate: float = 0.25
    a_satisfaction: float = 0.70
    b_pass_rate: float = 0.75
    b_budget_rate: float = 0.75
    b_satisfaction: float = 0.50
    c_pass_rate: float = 0.50


DEFAULT_THRESHOLDS = GradeThresholds()


def grade_summary(summary: dict[str, object], thresholds: GradeThresholds = DEFAULT_THRESHOLDS) -> dict[str, object]:
    total = int(summary["scenario_count"])  # type: ignore[arg-type]
    if total == 0:
        return {"grade": "D", "reasons": ["Keine Szenarien ausgewertet"], "economic": False, "customers_satisfied": False}
    pass_rate = int(summary["passed_count"]) / total  # type: ignore[arg-type]
    budget_rate = int(summary["within_budget_count"]) / total  # type: ignore[arg-type]
    ra_rate = int(summary["remote_assistance_episodes"]) / total  # type: ignore[arg-type]
    satisfaction = summary["average_customer_satisfaction"]
    satisfaction_value = None if satisfaction is None else float(satisfaction)  # type: ignore[arg-type]
    unsafe = (
        int(summary["collision_count"])  # type: ignore[arg-type]
        + int(summary["personal_injury_count"])  # type: ignore[arg-type]
        + int(summary.get("hit_and_run_count", 0))  # type: ignore[arg-type]
    )

    def satisfied(minimum: float) -> bool:
        return satisfaction_value is None or satisfaction_value >= minimum

    criteria = {
        "pass_rate": round(pass_rate, 3),
        "budget_rate": round(budget_rate, 3),
        "remote_assistance_rate": round(ra_rate, 3),
        "average_customer_satisfaction": satisfaction_value,
        "safety_incidents": unsafe,
    }
    reasons: list[str] = []
    if unsafe:
        grade = "D"
        reasons.append(f"Sicherheitstor verletzt: {unsafe} Kollision(en), Personenschaeden bzw. Unfallflucht")
    elif (
        pass_rate >= thresholds.a_pass_rate
        and budget_rate >= thresholds.a_budget_rate
        and ra_rate <= thresholds.a_remote_assistance_rate
        and satisfied(thresholds.a_satisfaction)
    ):
        grade = "A"
    elif (
        pass_rate >= thresholds.b_pass_rate
        and budget_rate >= thresholds.b_budget_rate
        and satisfied(thresholds.b_satisfaction)
    ):
        grade = "B"
        reasons.append("Fuer A fehlt mindestens eines von: Bestehensquote, Budgetquote, wenige Remote-Assistance-Faelle, Kundenzufriedenheit")
    elif pass_rate >= thresholds.c_pass_rate:
        grade = "C"
        reasons.append("Fuer B reichen Bestehens-, Budgetquote oder Kundenzufriedenheit nicht")
    else:
        grade = "D"
        reasons.append(f"Weniger als {thresholds.c_pass_rate:.0%} der Szenarien bestanden")
    return {
        "grade": grade,
        "reasons": reasons,
        "economic": budget_rate >= thresholds.b_budget_rate and not unsafe,
        "customers_satisfied": satisfied(thresholds.b_satisfaction) and not unsafe,
        "criteria": criteria,
        "thresholds": asdict(thresholds),
    }
