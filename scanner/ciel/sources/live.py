"""Fast-moving feeds: companies about to list, policy, and news.

Three sources, all free and keyless, and each with a very different claim on
your attention.

**Coming to market.** A company files an S-1 to register an offering, usually
weeks before it trades, then a 424B4 when the price is set. That is the only
honest reading of "find them early": before an S-1 there is nothing to buy and
nothing published, and after the 424B4 it is an ordinary listed company. This
is the part of this module worth having.

**Policy.** The Federal Register carries rules and notices as they are issued.
A tariff or an FDA rule genuinely changes what a business is worth. Reading it
here beats reading a headline about it, because it is the primary document.

**News.** GDELT indexes world coverage. It is included for context on what you
already hold, and it is the weakest of the three by a distance: prices absorb a
headline in milliseconds, so anything you read has already been paid for. It is
here to explain a move, not to catch one.

Nothing in this module is scored, ranked, or fed into the research queue. It
reports what has happened. The queue is still built from filings.
"""

import json
import re
from xml.etree import ElementTree

ATOM = "{http://www.w3.org/2005/Atom}"

EDGAR_CURRENT = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"
                 "&type=%s&company=&dateb=&owner=include&count=%d&output=atom")
FEDREG = ("https://www.federalregister.gov/api/v1/documents.json"
          "?per_page=%d&order=newest&fields[]=title&fields[]=publication_date"
          "&fields[]=html_url&fields[]=type&fields[]=agencies"
          "&conditions[type][]=RULE&conditions[type][]=PRORULE")
GDELT = ("https://api.gdeltproject.org/api/v2/doc/doc?query=%s"
         "&mode=artlist&format=json&maxrecords=%d&sort=datedesc")

# S-1 is the registration, 424B4 the priced prospectus. Both mean "about to be,
# or has just become, buyable".
LISTING_FORMS = (("S-1", "registration filed — the IPO paperwork has started"),
                 ("424B4", "priced and offered — it lists imminently or just has"))


def _text(node, tag):
    found = node.find(ATOM + tag)
    return (found.text or "").strip() if found is not None else ""


def coming_to_market(session, per_form=20, log=print):
    """Companies that have just filed to go public, newest first."""
    out = []
    for form, meaning in LISTING_FORMS:
        try:
            raw = session.get(EDGAR_CURRENT % (form, per_form), ttl=900)
            root = ElementTree.fromstring(raw)
        except Exception as exc:  # noqa: BLE001 - one dead feed is not a dead run
            log("  %s feed failed: %s" % (form, exc))
            continue
        for entry in root.findall(ATOM + "entry"):
            title = _text(entry, "title")
            # EDGAR titles read "S-1 - ACME INC (0001234567) (Filer)".
            name = re.sub(r"^\S+\s*-\s*", "", title)
            name = re.sub(r"\s*\(\d{7,}\)\s*\(Filer\)\s*$", "", name).strip()
            link = entry.find(ATOM + "link")
            out.append({
                "form": form,
                "meaning": meaning,
                "name": name or title,
                "filed": _text(entry, "updated")[:10],
                "url": link.get("href") if link is not None else "",
            })
    out.sort(key=lambda r: r["filed"], reverse=True)
    return out


def policy(session, limit=12, log=print):
    """Rules and proposed rules, newest first, straight from the source."""
    try:
        raw = session.get(FEDREG % limit, ttl=1800)
        docs = json.loads(raw).get("results", [])
    except Exception as exc:  # noqa: BLE001
        log("  federal register failed: %s" % exc)
        return []
    out = []
    for doc in docs:
        agencies = [a.get("name", "") for a in (doc.get("agencies") or [])]
        out.append({
            "title": doc.get("title", ""),
            "date": doc.get("publication_date", ""),
            "kind": "final rule" if doc.get("type") == "Rule" else "proposed rule",
            "agency": agencies[0] if agencies else "",
            "url": doc.get("html_url", ""),
        })
    return out


def news_for(session, holdings, per_company=4, log=print):
    """Recent coverage of what is actually held. Never the whole queue.

    Searching 150 companies would produce a wall of headlines that reads like a
    reason to act, which is the opposite of what this tool is for.
    """
    out = {}
    for holding in holdings:
        name = (holding.get("name") or "").strip()
        if not name:
            continue
        # Quoted so a two-word company name is not matched as two loose terms.
        query = '"%s"' % re.sub(r'["\\]', "", name)
        try:
            raw = session.get(GDELT % (query.replace(" ", "%20").replace('"', "%22"),
                                       per_company), ttl=1800)
            articles = json.loads(raw).get("articles", [])
        except Exception as exc:  # noqa: BLE001
            log("  news %s failed: %s" % (name, exc))
            continue
        out[holding["slug"]] = [{
            "title": a.get("title", ""),
            "source": a.get("domain", ""),
            "date": (a.get("seendate", "") or "")[:8],
            "url": a.get("url", ""),
        } for a in articles if a.get("title")]
    return out
