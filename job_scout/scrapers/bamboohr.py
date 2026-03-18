"""
Scraper for *.bamboohr.com/careers

DISCOVERY STRATEGY:
  BambooHR doesn't have a public master sitemap, but their careers pages
  follow a standard pattern. We use two approaches:
  1. Fetch https://www.bamboohr.com/sitemap.xml to discover company subdomains
  2. Fall back to a curated seed list of known BambooHR customers

  Per-company API:
    GET https://{company}.bamboohr.com/careers/list  (JSON)
"""
import hashlib
import logging
import re
from datetime import datetime, timezone

from dateutil import parser as dp

from ..filters import location_matches, title_matches
from ..http_client import get_session

log = logging.getLogger(__name__)

SITEMAP_URLS = [
    "https://www.bamboohr.com/sitemap.xml",
    "https://www.bamboohr.com/sitemap_index.xml",
]

# Seed list used only as fallback if sitemap discovery fails
SEED_COMPANIES = [
    "squarespace", "qualtrics", "procore", "instructure", "domo",
    "healthequity", "entrata", "lucid", "podium", "pluralsight",
    "ancestry", "momentive", "surveymonkey", "bazaarvoice", "hootsuite",
    "payscale", "namely", "zenefits", "ceridian", "paylocity", "paycom",
    "wex", "fleetcor", "solarwinds", "olo", "lightspeed", "toast",
    "mindbody", "zenoti", "corelogic",
]

LIST_API = "https://{company}.bamboohr.com/careers/list"


def _make_id(uid: str) -> str:
    return "bhr_" + hashlib.md5(uid.encode()).hexdigest()[:16]


def _discover_companies(session) -> list[str]:
    """Try to discover BambooHR company subdomains from sitemaps."""
    slugs = set()
    for sitemap_url in SITEMAP_URLS:
        try:
            resp = session.get(sitemap_url, timeout=15)
            if resp.status_code != 200:
                continue
            # Look for patterns like subdomain.bamboohr.com in sitemap
            found = re.findall(
                r"https?://([^./\"<>\s]+)\.bamboohr\.com/careers",
                resp.text
            )
            slugs.update(found)
        except Exception as exc:
            log.debug("BambooHR sitemap %s error: %s", sitemap_url, exc)

    if slugs:
        log.info("BambooHR: discovered %d companies from sitemap", len(slugs))
        return list(slugs)

    log.info("BambooHR: sitemap discovery failed, using seed list (%d companies)", len(SEED_COMPANIES))
    return SEED_COMPANIES


def scrape(hours: int = 10) -> list[dict]:
    session = get_session()
    results = []
    cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600

    companies = _discover_companies(session)

    for company in companies:
        try:
            resp = session.get(
                LIST_API.format(company=company),
                headers={"Accept": "application/json"},
                timeout=10,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            jobs = data.get("result", [])
        except Exception as exc:
            log.debug("BambooHR %s error: %s", company, exc)
            continue

        for job in jobs:
            title = job.get("jobOpeningName", "") or job.get("title", "")
            if not title_matches(title):
                continue

            location = job.get("location", {})
            if isinstance(location, dict):
                city = location.get("city", "")
                state = location.get("state", "")
                location = f"{city}, {state}".strip(", ")
            location = str(location)

            if not location_matches(location):
                if "remote" not in str(job).lower():
                    continue

            raw_ts = (
                job.get("datePosted")
                or job.get("postingDate")
                or job.get("updatedDate")
                or ""
            )
            if not raw_ts:
                continue
            try:
                posted_dt = dp.parse(str(raw_ts))
                if posted_dt.tzinfo is None:
                    posted_dt = posted_dt.replace(tzinfo=timezone.utc)
                if posted_dt.timestamp() < cutoff:
                    continue
            except Exception:
                continue

            uid = str(job.get("id", title + company))
            url = f"https://{company}.bamboohr.com/careers/{uid}"
            results.append({
                "id": _make_id(uid + company),
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "source": "bamboohr",
                "posted_at": posted_dt.isoformat(),
            })

    log.info("BambooHR: %d matching jobs", len(results))
    return results
