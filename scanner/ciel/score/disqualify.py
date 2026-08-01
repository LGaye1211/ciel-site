"""Disqualifiers and penalties.

Ellis, The Loser's Game (1975): between amateurs, points are lost through
unforced errors rather than won. So the engine eliminates first and ranks
second, and the UI leads with the elimination count rather than burying it.

A disqualified company is never scored, never ranked, and never shown as a
candidate - but the reason is recorded and displayed, because "387 eliminated"
with no explanation is just a number.
"""

from .signals import money, pct


def check(company, rubric, universe):
    """Return a list of {id, label, detail} - empty means the company survives."""
    m = company.metrics
    out = []
    specs = {d["id"]: d for d in rubric.get("disqualifiers", [])}

    def fail(key, detail):
        spec = specs.get(key, {})
        out.append({"id": key, "label": spec.get("label", key), "detail": detail})

    if getattr(company, "is_shell", False):
        fail("shell_or_blank_check",
             "Name or SEC category marks this as a shell, blank-cheque or non-operating entity.")

    if getattr(company, "is_leveraged", False):
        fail("leveraged_instrument",
             "Name indicates a leveraged, inverse or derivative-based instrument. "
             "Charter rule 6 excludes these in any form.")

    revenue = m.get("revenue_ttm")
    if revenue is None or revenue <= 0:
        fail("no_revenue", "No positive revenue reported over the trailing four quarters.")
    elif revenue < universe.get("min_revenue_ttm_usd", 0):
        fail("no_revenue", "Trailing revenue of %s is below the %s floor." % (
            money(revenue), money(universe.get("min_revenue_ttm_usd", 0))))

    quarters = m.get("quarters_reported") or 0
    if quarters < universe.get("min_quarters_of_data", 3):
        fail("insufficient_history",
             "Only %d quarter(s) of reported revenue - too little to judge." % quarters)

    runway = m.get("runway_months")
    threshold = _threshold(specs, "runway_under_12m", 12)
    if runway is not None and runway < threshold and not m.get("cash_flow_positive"):
        fail("runway_under_12m",
             "About %.0f months of cash at the current burn (%s against %s a year). "
             "Below %d months the company is likely to have to raise on whatever terms it "
             "can get, and that dilution lands on you." % (
                 runway, money(m.get("cash", 0)), money(abs(m.get("ocf_ttm", 0))), threshold))

    dilution = m.get("dilution_yoy")
    dq_threshold = _threshold(specs, "dilution_over_25pct", 0.25)
    if dilution is not None and dilution > dq_threshold:
        fail("dilution_over_25pct",
             "Diluted share count rose %s over the year (%s). At that rate your stake halves "
             "in about three years regardless of what the share price does." % (
                 pct(dilution), m.get("dilution_basis", "")))

    if getattr(company, "stale", False):
        fail("stale_filings",
             "No filing within %d days - the data cannot be relied on."
             % universe.get("max_days_since_last_filing", 400))

    # A company can be filing on time while its XBRL series stopped years ago,
    # usually after a tag change SEC never assigned calendar frames to. Showing
    # four-year-old growth as current is worse than showing nothing.
    age = m.get("data_age_months")
    max_age = universe.get("max_data_age_months", 9)
    if getattr(company, "annual_only", False):
        max_age = universe.get("max_data_age_months_annual", 20)
    if age is None:
        fail("stale_data", "No dated financial figures could be read.")
    elif age > max_age:
        fail("stale_data",
             "The newest reported figure is %s, about %d months old. The company may still be "
             "filing, but its tagged data stops there, so nothing here reflects how it trades "
             "today." % (m.get("data_latest_period", "unknown"), age))

    density = m.get("series_density")
    if density is not None and density < universe.get("min_series_density", 0.6):
        fail("gapped_series",
             "The reported series covers only %d%% of the quarters it spans. Growth measured "
             "across the holes is not growth." % round(density * 100))

    if m.get("going_concern"):
        fail("going_concern",
             "The filing discloses substantial doubt about the company's ability to continue "
             "as a going concern. The auditors are saying it may not survive the year.")

    return out


def _threshold(specs, key, default):
    spec = specs.get(key) or {}
    value = spec.get("threshold")
    return value if value is not None else default


def penalty_applies(penalty_id, company, m):
    """Return an evidence string when the penalty fires, else None."""
    if penalty_id == "negative_equity" and m.get("negative_equity"):
        return "Shareholders' equity is negative (%s)." % money(m.get("equity", 0))

    if penalty_id == "heavy_dilution":
        value = m.get("dilution_yoy")
        if value is not None and value > 0.15:
            return "Diluted share count up %s over the year." % pct(value)

    if penalty_id == "recent_loss_widening":
        change = m.get("operating_income_change")
        income = m.get("operating_income")
        if change is not None and income is not None and income < 0 and change < 0:
            return "Operating loss widened by %s against the same quarter a year earlier." % (
                money(abs(change)))

    if penalty_id == "thin_history":
        quarters = m.get("quarters_reported") or 0
        if quarters < 6:
            return "Only %d quarters of reported revenue." % quarters

    if penalty_id == "foreign_annual_only":
        if getattr(company, "annual_only", False):
            return ("Reports annually rather than quarterly (foreign private issuer), so the "
                    "series is sparser and changes surface later.")

    if penalty_id == "customer_concentration":
        value = m.get("customer_concentration")
        if value is not None and value > 0.5:
            return "Largest customers account for %s of revenue." % pct(value)

    # Legal exposure was extracted and displayed but never scored, so a company
    # disclosing active litigation ranked identically to one stating it has
    # none. Item 3 of the annual report is where a company must describe
    # material proceedings; narrative.legal_material already separates a real
    # disclosure from the "we are not party to any material proceedings"
    # boilerplate, so this scores the distinction rather than the mere presence
    # of the section.
    if penalty_id == "active_litigation":
        narrative = getattr(company, "narrative", None) or {}
        if narrative.get("legal_material"):
            return ("Item 3 of the annual report describes material legal proceedings rather "
                    "than stating there are none. Read it — the dossier quotes it in full.")

    if penalty_id == "legal_event":
        events = [e for e in (getattr(company, "legal", None) or [])]
        if events:
            labels = ", ".join(sorted({e.get("label", "") for e in events if e.get("label")}))
            return ("Reported %d legal or audit event%s in the last two years%s."
                    % (len(events), "" if len(events) == 1 else "s",
                       (": " + labels) if labels else ""))

    # Coverage counts only when it is hostile. Volume of news measures
    # attention, and attention is not a virtue: Barber and Odean (2008) found
    # individual investors buy attention-grabbing stocks and do worse for it.
    # So a company in the headlines for nothing in particular scores neither up
    # nor down, and only sustained negative tone registers here.
    if penalty_id == "hostile_coverage":
        tone = m.get("news_tone")
        volume = m.get("news_volume") or 0
        if tone is not None and volume >= 5 and tone <= -2.5:
            return ("Recent press coverage is materially negative (tone %.1f across %d articles). "
                    "Tone is a crude machine reading, not a judgement — go and read them."
                    % (tone, volume))

    return None
