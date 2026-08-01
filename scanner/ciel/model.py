"""Data model. Plain dataclasses; nothing here touches the network."""

from dataclasses import dataclass, field


@dataclass
class Evidence:
    """A human sentence plus a link to the filing it came from.

    Every score contribution and every generated sentence carries these. A
    contribution with an empty evidence list is a build failure, asserted in
    test_scoring.py - it is the whole basis of the tool's honesty claim.
    """

    text: str
    source_url: str = ""
    accession: str = ""
    fiscal: str = ""

    def to_json(self):
        out = {"text": self.text}
        if self.source_url:
            out["source_url"] = self.source_url
        if self.accession:
            out["accession"] = self.accession
        if self.fiscal:
            out["fiscal"] = self.fiscal
        return out


@dataclass
class Point:
    """One reported figure for one period.

    `frame` is SEC's normalised calendar key (CY2026Q1, CY2026Q1I, CY2025).
    Labels and year-on-year comparisons both key off it rather than off fy/fp,
    which carry the filer's own fiscal calendar and disagree with it.
    """

    end: str
    val: float
    fy: int = 0
    fp: str = ""
    form: str = ""
    accession: str = ""
    start: str = ""
    frame: str = ""

    @property
    def label(self):
        if self.frame:
            key = self.frame[:-1] if self.frame.endswith("I") else self.frame
            if len(key) >= 8 and "Q" in key:
                return "%s %s" % (key[6:], key[2:6])
            if len(key) == 6:
                return key[2:]
        if self.fy and self.fp:
            return "%s %s" % (self.fp, self.fy)
        return self.end

    @property
    def calendar(self):
        """(year, quarter) from the frame; quarter 0 for annual."""
        key = self.frame[:-1] if self.frame.endswith("I") else self.frame
        if len(key) >= 8 and "Q" in key:
            try:
                return int(key[2:6]), int(key[7:])
            except ValueError:
                return None
        if len(key) == 6:
            try:
                return int(key[2:]), 0
            except ValueError:
                return None
        return None


@dataclass
class Series:
    """A named quarterly or annual series, newest last."""

    concept: str
    unit: str
    points: list = field(default_factory=list)

    def latest(self, n=1):
        return self.points[-n:] if self.points else []

    def by_calendar(self):
        return {p.calendar: p for p in self.points if p.calendar}

    def year_ago(self):
        """(latest, same quarter one year earlier) or (latest, None).

        Positional offsets break whenever a quarter is missing from the frames,
        which is common - many filers fold Q4 into the annual report and never
        tag it as a discrete quarter.
        """
        if not self.points:
            return None, None
        latest = self.points[-1]
        cal = latest.calendar
        if not cal:
            return latest, None
        year, quarter = cal
        return latest, self.by_calendar().get((year - 1, quarter))

    def values(self, n=None):
        pts = self.points if n is None else self.points[-n:]
        return [p.val for p in pts]

    def labels(self, n=None):
        pts = self.points if n is None else self.points[-n:]
        return [p.label for p in pts]


@dataclass
class Company:
    cik: str
    name: str
    slug: str = ""
    tickers: list = field(default_factory=list)
    exchanges: list = field(default_factory=list)
    sic: str = ""
    sic_description: str = ""
    country: str = ""
    state: str = ""
    fiscal_year_end: str = ""
    first_filing: str = ""
    first_annual: str = ""
    last_filing: str = ""
    forms: list = field(default_factory=list)
    is_foreign_filer: bool = False

    # Set by the pipeline; declared here so a bare Company is still usable.
    listed_years: float = None
    annual_only: bool = False
    is_shell: bool = False
    is_leveraged: bool = False
    stale: bool = False
    has_older_filings: bool = False
    entity_category: str = ""
    description: str = ""
    website: str = ""
    recent_filings: list = field(default_factory=list)
    events: list = field(default_factory=list)
    story: list = field(default_factory=list)
    quarterly: list = field(default_factory=list)
    legal: list = field(default_factory=list)
    narrative: dict = field(default_factory=dict)

    # Derived quarterly series, keyed by our own metric name.
    series: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)

    # Populated downstream.
    disqualified: list = field(default_factory=list)
    score = None
    thesis: dict = field(default_factory=dict)
    triggers: list = field(default_factory=list)
    team: list = field(default_factory=list)
    flags: list = field(default_factory=list)

    @property
    def cik10(self):
        return str(self.cik).zfill(10)

    @property
    def primary_ticker(self):
        return self.tickers[0] if self.tickers else ""

    def filing_url(self, accession):
        if not accession:
            return "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=%s" % self.cik10
        plain = accession.replace("-", "")
        return "https://www.sec.gov/Archives/edgar/data/%s/%s/%s-index.htm" % (
            int(self.cik), plain, accession,
        )


@dataclass
class Contribution:
    dimension: str
    signal_id: str
    label: str
    raw_value: float
    scaled: float
    weight: float
    points: float
    confidence: str = "high"
    evidence: list = field(default_factory=list)

    def to_json(self):
        return {
            "dimension": self.dimension,
            "signal_id": self.signal_id,
            "label": self.label,
            "raw_value": _round(self.raw_value),
            "scaled": _round(self.scaled),
            "weight": _round(self.weight),
            "points": _round(self.points),
            "confidence": self.confidence,
            "evidence": [e.to_json() for e in self.evidence],
        }


@dataclass
class Score:
    total: float = 0.0
    dimensions: dict = field(default_factory=dict)
    contributions: list = field(default_factory=list)
    penalties: list = field(default_factory=list)
    rubric_version: str = ""

    def to_json(self):
        return {
            "total": _round(self.total),
            "rubric_version": self.rubric_version,
            "dimensions": {k: _round(v) for k, v in self.dimensions.items()},
            "contributions": [c.to_json() for c in self.contributions],
            "penalties": self.penalties,
        }


def _round(value, places=2):
    try:
        return round(float(value), places)
    except (TypeError, ValueError):
        return 0.0
