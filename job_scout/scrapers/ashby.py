"""
Scraper for jobs.ashbyhq.com

DISCOVERY STRATEGY:
  Ashby has a sitemap at:
    https://jobs.ashbyhq.com/sitemap.xml
  which lists every active job URL in the format:
    https://jobs.ashbyhq.com/{company}/{uuid}

  We parse the sitemap to get all unique company slugs dynamically,
  then hit the public posting API per company (no auth required).
"""
import hashlib
import logging
import re
from datetime import datetime, timezone

from dateutil import parser as dp

from ..filters import location_matches, title_matches
from ..http_client import get_session

log = logging.getLogger(__name__)

SITEMAP_URL = "https://jobs.ashbyhq.com/sitemap.xml"
API = "https://api.ashbyhq.com/posting-api/job-board/{company}"


def _make_id(uid: str) -> str:
    return "ab_" + hashlib.md5(uid.encode()).hexdigest()[:16]


def _discover_companies(session) -> list[str]:
    """Parse Ashby sitemap to extract all unique company slugs."""
    try:
        resp = session.get(SITEMAP_URL, timeout=20)
        resp.raise_for_status()
        # URLs: https://jobs.ashbyhq.com/SLUG/uuid
        slugs = set(re.findall(
            r"ashbyhq\.com/([^/\"<>\s]+)/[0-9a-f\-]{36}",
            resp.text
        ))
        slugs.discard("")
        log.info("Ashby: discovered %d companies from sitemap", len(slugs))
        return list(slugs)
    except Exception as exc:
        log.warning("Ashby sitemap fetch failed: %s", exc)
        return []


def scrape(hours: int = 10) -> list[dict]:
    session = get_session()
    results = []
    cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600

    companies = _discover_companies(session)
    if not companies:
        log.warning("Ashby: no companies discovered, skipping.")
        return []

    for company in companies:
        try:
            resp = session.post(
                API.format(company=company),
                json={"includeCompensation": False},
                timeout=10,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            jobs = data.get("jobs", [])
        except Exception as exc:
            log.debug("Ashby %s error: %s", company, exc)
            continue

        for job in jobs:
            title = job.get("title", "")
            if not title_matches(title):
                continue

            location = job.get("location", "") or job.get("locationName", "")
            if not location_matches(location):
                continue

            raw_ts = job.get("publishedAt") or job.get("updatedAt") or ""
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

            uid = job.get("id", title + company)
            url = job.get("jobUrl") or f"https://jobs.ashbyhq.com/{company}/{uid}"
            results.append({
                "id": _make_id(str(uid)),
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "source": "ashby",
                "posted_at": posted_dt.isoformat(),
            })

    log.info("Ashby: %d matching jobs", len(results))
    return results
