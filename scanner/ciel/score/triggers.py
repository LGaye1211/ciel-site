"""Auto-generated sell triggers.

Charter rule 9 asks for "what would make me sell", quantified. Prose triggers
("if the story changes") cannot be checked by anything; these are machine-
checkable predicates over the same XBRL metrics the scan already computes, so
the weekly run re-evaluates every one against each new filing.

Thresholds are derived from the company's *own* current figures, so they are
calibrated rather than generic - a 52% margin floor means something different
for a company at 61% than for one at 22%.

The tool never says what to do. It says what you said you would do.
"""

from .signals import money, pct

# metric -> (comparison, human unit formatter)
FORMATTERS = {
    "gross_margin": pct,
    "revenue_growth_yoy": pct,
    "dilution_yoy": pct,
    "operating_margin": pct,
    "runway_months": lambda v: "%.0f months" % v,
    "net_cash": money,
    "ocf_ttm": money,
}


def _fmt(metric, value):
    return FORMATTERS.get(metric, lambda v: "%.2f" % v)(value)


def _round_to(value, step):
    return round(value / step) * step


def build(company):
    """Return trigger dicts, each independently evaluable against metrics."""
    m = company.metrics
    out = []

    margin = m.get("gross_margin")
    if margin is not None:
        floor = max(0.0, _round_to(margin - 0.08, 0.01))
        out.append(_trigger(
            "gross_margin_floor", "gross_margin", "below", floor, margin,
            consecutive=2,
            rationale="Eight points of margin is a real deterioration rather than noise. Two "
                      "consecutive quarters stops one bad quarter from forcing a sale."))

    growth = m.get("revenue_growth_yoy")
    if growth is not None:
        floor = _round_to(min(growth - 0.15, growth / 2 if growth > 0 else -0.05), 0.01)
        out.append(_trigger(
            "growth_floor", "revenue_growth_yoy", "below", floor, growth,
            consecutive=2,
            rationale="If growth halves and stays there, the reason you looked at this company "
                      "has gone."))

    runway = m.get("runway_months")
    if runway is not None and not m.get("cash_flow_positive"):
        out.append(_trigger(
            "runway_floor", "runway_months", "below", 12.0, runway,
            rationale="Below twelve months the company raises on whatever terms it can get, and "
                      "that dilution lands on you."))

    dilution = m.get("dilution_yoy")
    if dilution is not None:
        ceiling = max(0.10, _round_to(dilution + 0.07, 0.01))
        out.append(_trigger(
            "dilution_ceiling", "dilution_yoy", "above", ceiling, dilution,
            rationale="Share count growth above this rate transfers your stake to new holders "
                      "faster than the business is likely to compound."))

    d2e = m.get("debt_to_equity")
    if d2e is not None:
        ceiling = max(1.0, round(d2e + 0.5, 1))
        out.append(_trigger(
            "leverage_ceiling", "debt_to_equity", "above", ceiling, d2e,
            rationale="Past this point creditors, not shareholders, decide what happens next."))

    # Non-numeric conditions the weekly scan detects from filings directly.
    out.append({
        "id": "going_concern",
        "kind": "event",
        "label": "Going-concern doubt appears in any filing",
        "metric": "going_concern",
        "comparison": "is_true",
        "threshold": True,
        "current": bool(m.get("going_concern")),
        "current_display": "not present",
        "fired": bool(m.get("going_concern")),
        "rationale": "The auditors saying the company may not survive the year is not a signal "
                     "to interpret. It is the exit.",
        "editable": False,
    })

    return out


def _trigger(trigger_id, metric, comparison, threshold, current, consecutive=1, rationale=""):
    direction = "falls below" if comparison == "below" else "rises above"
    return {
        "id": trigger_id,
        "kind": "metric",
        "label": "%s %s %s%s" % (
            _label(metric), direction, _fmt(metric, threshold),
            " for %d consecutive quarters" % consecutive if consecutive > 1 else ""),
        "metric": metric,
        "comparison": comparison,
        "threshold": threshold,
        "consecutive": consecutive,
        "current": current,
        "current_display": _fmt(metric, current),
        "threshold_display": _fmt(metric, threshold),
        "fired": evaluate_one(comparison, current, threshold),
        "rationale": rationale,
        "editable": True,
    }


LABELS = {
    "gross_margin": "Gross margin",
    "revenue_growth_yoy": "Revenue growth",
    "dilution_yoy": "Diluted share count growth",
    "runway_months": "Cash runway",
    "debt_to_equity": "Debt to equity",
    "operating_margin": "Operating margin",
}


def _label(metric):
    return LABELS.get(metric, metric.replace("_", " ").capitalize())


def evaluate_one(comparison, current, threshold):
    if current is None:
        return False
    if comparison == "below":
        return current < threshold
    if comparison == "above":
        return current > threshold
    if comparison == "is_true":
        return bool(current)
    return False


def evaluate(triggers, metrics):
    """Re-check accepted triggers against fresh metrics. Used by the weekly run."""
    fired = []
    for trigger in triggers:
        current = metrics.get(trigger["metric"])
        hit = evaluate_one(trigger["comparison"], current, trigger["threshold"])
        trigger["current"] = current
        trigger["current_display"] = (
            _fmt(trigger["metric"], current) if isinstance(current, (int, float)) else str(current))
        trigger["fired"] = hit
        if hit:
            fired.append(trigger)
    return fired
