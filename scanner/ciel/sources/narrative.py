"""Business description and legal proceedings, from the 10-K text.

This is the only place the scanner reads prose rather than tagged data, and it
is where "the idea" comes from - everything else describes a company by its SIC
code, which tells you almost nothing.

The trap here: "Item 1. Business" appears at least twice in every 10-K, first in
the table of contents and then as the real section. Taking the first match
returns a list of page numbers. Candidates are therefore scored for
prose-likeness and the best one wins.
"""

import re

ARCHIVE = "https://www.sec.gov/Archives/edgar/data/%d/%s/%s"

TAG = re.compile(r"<[^>]+>")
ENTITY = re.compile(r"&(?:nbsp|#160|#32|amp|#38|apos|#39|#8217|#8216|quot|#34|#8220|#8221|"
                    r"rsquo|lsquo|ldquo|rdquo|mdash|#8212|ndash|#8211|#151|#147|#148);")
ENTITY_MAP = {"amp": "&", "#38": "&", "apos": "'", "#39": "'", "#8217": "'",
              "#8216": "'", "quot": '"', "#34": '"', "#8220": '"', "#8221": '"',
              "rsquo": "'", "lsquo": "'", "ldquo": '"', "rdquo": '"',
              "mdash": "-", "#8212": "-", "ndash": "-", "#8211": "-",
              "#151": "-", "#147": '"', "#148": '"'}

ITEM_REF = re.compile(r"Item\s+\d+[A-C]?\.", re.I)
SENTENCE_END = re.compile(r"[.!?]\s")


def _plain(html):
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = TAG.sub(" ", text)
    text = ENTITY.sub(lambda m: ENTITY_MAP.get(m.group(0)[1:-1], " "), text)
    return re.sub(r"\s+", " ", text)


def _prose_score(chunk, minimum):
    """Higher is more like prose and less like a table of contents.

    A contents block is dense with 'Item N.' references and page numbers and has
    almost no sentences. The minimum length is a parameter because a legal
    section can legitimately be two lines - "we are not party to any material
    proceedings" is a real finding, not a parse failure.
    """
    if len(chunk) < minimum:
        return -1.0
    items = len(ITEM_REF.findall(chunk))
    digits = sum(c.isdigit() for c in chunk) / len(chunk)
    sentences = len(SENTENCE_END.findall(chunk))
    return (min(len(chunk), 20000) / 1000.0
            + sentences * 0.5
            - items * 8.0
            - digits * 200.0)


def _section(text, start_pattern, end_patterns, cap=9000, minimum=400):
    starts = [m.end() for m in re.finditer(start_pattern, text, re.I)]
    if not starts:
        return ""
    best, best_score = "", -99.0
    for pos in starts:
        window = text[pos:pos + 200000]
        end = None
        for pattern in end_patterns:
            found = re.search(pattern, window, re.I)
            if found and (end is None or found.start() < end):
                end = found.start()
        chunk = window[:end if end else cap][:cap].strip()
        score = _prose_score(chunk, minimum)
        if score > best_score:
            best, best_score = chunk, score
    return best if best_score > 0 else ""


def _tidy(chunk, limit):
    chunk = chunk.strip(" .:;-")
    if len(chunk) <= limit:
        return chunk
    cut = chunk[:limit]
    stop = cut.rfind(". ")
    return (cut[:stop + 1] if stop > limit * 0.5 else cut).strip() + " …"


def fetch_narrative(session, company, business_chars=1800, legal_chars=1200):
    """Return {business, legal, source_url, source_form, source_date} or {}."""
    annual = [f for f in (company.recent_filings or [])
              if f["form"] in ("10-K", "20-F", "40-F") and f.get("primary_document")]
    if not annual:
        return {}
    filing = annual[0]
    url = ARCHIVE % (int(company.cik), filing["accession"].replace("-", ""),
                     filing["primary_document"])
    try:
        raw = session.get(url, ttl=None)
    except Exception:  # noqa: BLE001 - a missing document must not stop the scan
        return {}

    text = _plain(raw)
    business = _section(
        text,
        r"Item\s*1\.?\s*[-–—:]?\s*Business\b",
        [r"Item\s*1A\.?\s*[-–—:]?\s*Risk", r"\bRisk\s+Factors\b",
         r"Item\s*1B\.?\s*[-–—:]?\s*Unresolved"],
        minimum=400)
    legal = _section(
        text,
        r"Item\s*3\.?\s*[-–—:]?\s*Legal\s+Proceedings\b",
        [r"Item\s*4\.?\s*[-–—:]?\s*(Mine|Submission)", r"\bMine\s+Safety\b",
         r"Item\s*5\.?\s*[-–—:]?\s*Market"],
        # A two-line "no material proceedings" is a finding, not a failure.
        minimum=90)

    out = {"source_url": company.filing_url(filing["accession"]),
           "source_form": filing["form"], "source_date": filing["date"]}
    if business:
        out["business"] = _tidy(business, business_chars)
    if legal:
        cleaned = _tidy(legal, legal_chars)
        out["legal"] = cleaned
        # Boilerplate "we are not currently a party to any material proceedings"
        # is a genuine finding, so it is distinguished rather than dropped.
        out["legal_material"] = not re.search(
            r"\bnot\b[^.]{0,40}?(?:a party to|involved in|subject to|aware of)"
            r"[^.]{0,60}?\b(any|material)\b", cleaned, re.I)
    return out
