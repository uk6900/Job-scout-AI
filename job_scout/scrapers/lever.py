"""
Scraper for jobs.lever.co

DISCOVERY STRATEGY:
  Lever has a sitemap at:
    https://jobs.lever.co/sitemap.xml
  which lists every active job URL in the format:
    https://jobs.lever.co/{company}/{uuid}

  We parse the sitemap to get all unique company slugs dynamically,
  then hit the public v0 JSON API per company (no auth required).
"""
import hashlib
import logging
import re
from datetime import datetime, timezone

from dateutil import parser as dp

from ..http_client import get_session
from ..filters import location_matches, title_matches

log = logging.getLogger(__name__)

SITEMAP_URL = "https://jobs.lever.co/sitemap.xml"
API = "https://api.lever.co/v0/postings/{company}?mode=json"


def _make_id(lever_id: str) -> str:
    return "lv_" + hashlib.md5(lever_id.encode()).hexdigest()[:16]


def _discover_companies(session) -> list[str]:
    """Parse Lever sitemap to extract all unique company slugs."""
    try:
        resp = session.get(SITEMAP_URL, timeout=20)
        resp.raise_for_status()
        # URLs: https://jobs.lever.co/SLUG/uuid
        slugs = set(re.findall(
            r"jobs\.lever\.co/([^/\"<>\s]+)/[0-9a-f\-]{36}",
            resp.text
        ))
        slugs.discard("")
        log.info("Lever: discovered %d companies from sitemap", len(slugs))
        return list(slugs)
    except Exception as exc:
        log.warning("Lever sitemap fetch failed: %s", exc)
        return []


def scrape(hours: int = 10) -> list[dict]:
    session = get_session()
    results = []
    cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600

    companies = _discover_companies(session)
    if not companies:
        log.warning("Lever: no companies discovered, skipping.")
        return []

    for company in companies:
        try:
            resp = session.get(API.format(company=company), timeout=10)
            if resp.status_code != 200:
                continue
            jobs = resp.json()
            if not isinstance(jobs, list):
                continue
        except Exception as exc:
            log.debug("Lever %s error: %s", company, exc)
            continue

        for job in jobs:
            title = job.get("text", "")
            if not title_matches(title):
                continue

            cats = job.get("categories", {})
            location = cats.get("location", "") or job.get("workplaceType", "")
            if not location_matches(location):
                continue

            # Lever uses milliseconds epoch
            created_ms = job.get("createdAt")
            if not created_ms:
                continue
            try:
                posted_ts = int(created_ms) / 1000
                if posted_ts < cutoff:
                    continue
                posted_dt = datetime.fromtimestamp(posted_ts, tz=timezone.utc)
            except Exception:
                continue

            uid = job.get("id", title + company)
            url = job.get("hostedUrl", f"https://jobs.lever.co/{company}/{uid}")
            results.append({
                "id": _make_id(uid),
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "source": "lever",
                "posted_at": posted_dt.isoformat(),
            })

    log.info("Lever: %d matching jobs", len(results))
    return results
