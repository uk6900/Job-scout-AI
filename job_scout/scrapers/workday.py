"""
Scraper for myworkdayjobs.com and workdayjobs.com

Workday exposes a REST search API:
  POST https://{tenant}.wd5.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs

Each company has its own tenant subdomain + board name.  We maintain a list of
known tenants.  The API accepts a JSON body with search terms and returns
paginated results with a postedDate field.
"""
import hashlib
import logging
from datetime import datetime, timezone

from dateutil import parser as dp

from ..filters import location_matches, title_matches
from ..http_client import get_session

log = logging.getLogger(__name__)

# (tenant_subdomain, board_name) pairs
# tenant is the subdomain: {tenant}.wd5.myworkdayjobs.com
TENANTS = [
    ("amazon", "External_career_site"),
    ("microsoft", "External"),
    ("google", "google_jobs"),
    ("apple", "apple"),
    ("meta", "meta"),
    ("nvidia", "NVIDIAExternalCareerSite"),
    ("amd", "AMD"),
    ("intel", "External"),
    ("ibm", "External"),
    ("sap", "EPX"),
    ("oracle", "External"),
    ("salesforce", "External"),
    ("servicenow", "External"),
    ("workday", "Workday"),
    ("adobe", "External"),
    ("vmware", "VMware_External"),
    ("cisco", "External"),
    ("qualcomm", "External"),
    ("broadcom", "Broadcom_External"),
    ("ti", "TICareerSite"),
    ("ge", "GE_External"),
    ("honeywell", "Honeywell_External"),
    ("deloitte", "External"),
    ("pwc", "Global_Campus_Experienced"),
    ("ey", "EY_External"),
    ("kpmg", "kpmg"),
    ("accenture", "AccentureCareers"),
    ("mckinsey", "McKinsey"),
    ("bain", "bain"),
    ("booz", "External"),
    ("leidos", "External"),
    ("saic", "External"),
    ("boozallen", "External"),
    ("gartner", "External"),
    ("cognizant", "CognizantCareer"),
    ("infosys", "External"),
    ("wipro", "wipro"),
    ("hcl", "External"),
    ("tcs", "External"),
    ("capgemini", "capgemini"),
    ("atos", "External"),
    ("unilever", "External"),
    ("pg", "P_G_jobs"),
    ("jnj", "JnJExternalCareerSite"),
    ("pfizer", "Pfizer_External"),
    ("merck", "External"),
    ("abbvie", "External"),
    ("lilly", "External"),
    ("bms", "External"),
    ("amgen", "External"),
    ("regeneron", "External"),
    ("medtronic", "External"),
    ("bectondickinson", "External"),
    ("stryker", "StrykerCareers"),
    ("boa", "bofa"),
    ("jpmc", "jpmcjobs"),
    ("wellsfargo", "WellsFargoJobs"),
    ("citigroup", "External"),
    ("gs", "External"),
    ("ms", "Experienced"),
    ("americanexpress", "AmexCareers"),
    ("visa", "External"),
    ("mastercard", "External"),
    ("paypal", "External"),
    ("intuit", "intuit"),
    ("att", "External"),
    ("verizon", "External"),
    ("tmobile", "External"),
    ("comcast", "External"),
    ("charter", "External"),
    ("cox", "External"),
    ("walmart", "WalmartExternalCareers"),
    ("target", "External"),
    ("costco", "External"),
    ("homedepot", "External"),
    ("lowes", "Lowes"),
    ("fedex", "External"),
    ("ups", "External"),
    ("usfoods", "External"),
    ("cardinal", "External"),
    ("mckesson", "External"),
]

SEARCH_TERMS = [
    "Business Analyst",
    "Business Analytics",
    "Business Systems Analyst",
]

API_TEMPLATE = (
    "https://{tenant}.wd5.myworkdayjobs.com"
    "/wday/cxs/{tenant}/{board}/jobs"
)

HEADERS_JSON = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def _make_id(uid: str) -> str:
    return "wd_" + hashlib.md5(uid.encode()).hexdigest()[:16]


def _fetch_tenant(session, tenant: str, board: str, hours: int, cutoff: float) -> list[dict]:
    results = []
    url = API_TEMPLATE.format(tenant=tenant, board=board)

    for search_term in SEARCH_TERMS:
        try:
            resp = session.post(
                url,
                json={
                    "appliedFacets": {},
                    "limit": 20,
                    "offset": 0,
                    "searchText": search_term,
                },
                headers=HEADERS_JSON,
                timeout=15,
            )
            if resp.status_code != 200:
                break  # tenant URL probably wrong, stop trying terms
            data = resp.json()
        except Exception as exc:
            log.debug("Workday %s/%s error: %s", tenant, board, exc)
            break

        postings = data.get("jobPostings", [])
        for job in postings:
            title = job.get("title", "")
            if not title_matches(title):
                continue

            # Location
            location = job.get("locationsText", "") or job.get("primaryLocation", "")
            if not location_matches(location):
                continue

            # Date — Workday returns "postedOn": "Posted X Days Ago" or ISO
            raw_ts = job.get("postedOn", "")
            if not raw_ts:
                continue
            # Workday often returns relative strings like "Posted Today" or ISO
            try:
                if "today" in raw_ts.lower():
                    posted_dt = datetime.now(timezone.utc)
                elif "day" in raw_ts.lower():
                    # "Posted 3 Days Ago" — skip if >hours old (approximate)
                    import re
                    match = re.search(r"(\d+)", raw_ts)
                    days = int(match.group(1)) if match else 999
                    if days * 24 > hours:
                        continue
                    posted_dt = datetime.now(timezone.utc)
                else:
                    posted_dt = dp.parse(raw_ts)
                    if posted_dt.tzinfo is None:
                        posted_dt = posted_dt.replace(tzinfo=timezone.utc)
                    if posted_dt.timestamp() < cutoff:
                        continue
            except Exception:
                continue

            ext_url = job.get("externalPath", "")
            full_url = (
                f"https://{tenant}.wd5.myworkdayjobs.com/en-US/{board}{ext_url}"
                if ext_url
                else f"https://{tenant}.wd5.myworkdayjobs.com"
            )
            uid = job.get("bulletFields", [title])[0] + tenant
            results.append({
                "id": _make_id(uid + search_term),
                "title": title,
                "company": tenant.capitalize(),
                "location": location,
                "url": full_url,
                "source": "workday",
                "posted_at": posted_dt.isoformat(),
            })

    return results


def scrape(hours: int = 10) -> list[dict]:
    session = get_session()
    results = []
    cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600
    seen_ids: set[str] = set()

    for tenant, board in TENANTS:
        jobs = _fetch_tenant(session, tenant, board, hours, cutoff)
        for job in jobs:
            if job["id"] not in seen_ids:
                seen_ids.add(job["id"])
                results.append(job)

    log.info("Workday: %d matching jobs", len(results))
    return results
