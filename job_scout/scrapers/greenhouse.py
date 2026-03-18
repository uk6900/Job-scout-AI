"""
Scraper for job-boards.greenhouse.io

DISCOVERY STRATEGY:
  Greenhouse has a sitemap at:
    https://job-boards.greenhouse.io/sitemap.xml
  which lists every active job URL in the format:
    https://job-boards.greenhouse.io/{company}/jobs/{id}

  We parse the sitemap to extract all unique company slugs dynamically —
  no hardcoded list needed. Then we hit the public JSON API per company.
"""
import hashlib
import logging
import re
from datetime import datetime, timezone

from dateutil import parser as dp

from ..filters import location_matches, title_matches
from ..http_client import get_session

log = logging.getLogger(__name__)

SITEMAP_URL = "https://job-boards.greenhouse.io/sitemap.xml"
API = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"


def _make_id(url: str) -> str:
    return "gh_" + hashlib.md5(url.encode()).hexdigest()[:16]


def _discover_companies(session) -> list[str]:
    """Parse Greenhouse sitemap to extract all unique company slugs."""
    try:
        resp = session.get(SITEMAP_URL, timeout=20)
        resp.raise_for_status()
        # Extract slugs from URLs like:
        # https://job-boards.greenhouse.io/SLUG/jobs/12345
        slugs = set(re.findall(
            r"greenhouse\.io/([^/\"<>\s]+)/jobs/",
            resp.text
        ))
        slugs.discard("")
        log.info("Greenhouse: discovered %d companies from sitemap", len(slugs))
        return list(slugs)
    except Exception as exc:
        log.warning("Greenhouse sitemap fetch failed: %s", exc)
        return []


def scrape(hours: int = 10) -> list[dict]:
    session = get_session()
    results = []
    cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600

    companies = _discover_companies(session)
    if not companies:
        log.warning("Greenhouse: no companies discovered, skipping.")
        return []

    for company in companies:
        try:
            resp = session.get(API.format(company=company), timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            jobs = data.get("jobs", [])
        except Exception as exc:
            log.debug("Greenhouse %s error: %s", company, exc)
            continue

        for job in jobs:
            title = job.get("title", "")
            if not title_matches(title):
                continue

            location = ""
            locs = job.get("offices", [])
            if locs:
                location = locs[0].get("name", "")
            if not location:
                location = job.get("location", {}).get("name", "")

            if not location_matches(location):
                continue

            raw_ts = job.get("updated_at") or job.get("created_at") or ""
            if not raw_ts:
                continue
            try:
                posted_dt = dp.parse(raw_ts)
                if posted_dt.tzinfo is None:
                    posted_dt = posted_dt.replace(tzinfo=timezone.utc)
                if posted_dt.timestamp() < cutoff:
                    continue
            except Exception:
                continue

            url = job.get("absolute_url", "")
            results.append({
                "id": _make_id(url or title + company),
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "source": "greenhouse",
                "posted_at": posted_dt.isoformat(),
            })

    log.info("Greenhouse: %d matching jobs", len(results))
    return results
