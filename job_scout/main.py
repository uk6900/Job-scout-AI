"""
job_scout main runner.

Usage:
    python -m job_scout [--hours 10] [--verbose]
"""
import argparse
import json
import logging
import sys
from pathlib import Path

from . import db
from .email_alert import send_alerts
from .scrapers import greenhouse, lever, ashby, workday, bamboohr

OUTPUT_DIR = Path(__file__).parent.parent / "output"
RESULTS_FILE = OUTPUT_DIR / "results.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("job_scout")


def collect_jobs(hours: int) -> list[dict]:
    """Run all scrapers and return combined, deduplicated job list."""
    all_jobs: list[dict] = []
    seen_ids: set[str] = set()

    scrapers = [
        ("Greenhouse", greenhouse.scrape),
        ("Lever", lever.scrape),
        ("Ashby", ashby.scrape),
        ("Workday", workday.scrape),
        ("BambooHR", bamboohr.scrape),
    ]

    for name, scraper in scrapers:
        log.info("Running %s scraper…", name)
        try:
            jobs = scraper(hours=hours)
        except Exception as exc:
            log.error("%s scraper failed: %s", name, exc)
            jobs = []

        for job in jobs:
            jid = job["id"]
            if jid not in seen_ids:
                seen_ids.add(jid)
                all_jobs.append(job)

    return all_jobs


def print_jobs(jobs: list[dict]) -> None:
    if not jobs:
        print("\n  No matching jobs found.\n")
        return
    print(f"\n{'─'*80}")
    print(f"  {'#':<4} {'Title':<40} {'Company':<20} {'Source':<12}")
    print(f"{'─'*80}")
    for i, j in enumerate(jobs, 1):
        print(
            f"  {i:<4} {j['title'][:38]:<40} "
            f"{j['company'][:18]:<20} {j['source']:<12}"
        )
        print(f"       📍 {j['location']}")
        print(f"       🕐 {j['posted_at']}")
        print(f"       🔗 {j['url']}")
        print()
    print(f"{'─'*80}")
    print(f"  Total: {len(jobs)} job(s)\n")


def run(hours: int = 10) -> None:
    db.init_db()
    OUTPUT_DIR.mkdir(exist_ok=True)

    log.info("Scanning for BA jobs posted in the last %d hour(s)…", hours)
    all_jobs = collect_jobs(hours)

    # Separate new vs already-seen
    new_jobs = [j for j in all_jobs if not db.is_seen(j["id"])]
    old_jobs = [j for j in all_jobs if db.is_seen(j["id"])]

    # Mark new jobs as seen
    for job in new_jobs:
        db.mark_seen(job)

    log.info(
        "Found %d total matching job(s): %d new, %d already seen.",
        len(all_jobs), len(new_jobs), len(old_jobs),
    )

    # Console output
    if new_jobs:
        print(f"\n{'='*80}")
        print(f"  🆕  {len(new_jobs)} NEW Job(s) Found")
        print(f"{'='*80}")
        print_jobs(new_jobs)
    else:
        print("\n  ✅  No new jobs since last run.\n")

    if old_jobs:
        print(f"  ℹ️   {len(old_jobs)} previously seen job(s) also matched (not re-alerted).\n")

    # Write results.json (all matching jobs this run)
    output_data = {
        "hours_window": hours,
        "total_found": len(all_jobs),
        "new_count": len(new_jobs),
        "jobs": all_jobs,
    }
    RESULTS_FILE.write_text(json.dumps(output_data, indent=2, ensure_ascii=False))
    log.info("Results written to %s", RESULTS_FILE)

    # Email alerts
    send_alerts(new_jobs)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="job_scout — Find recent US Business Analyst jobs."
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=10,
        metavar="N",
        help="Only include jobs posted within the last N hours (default: 10)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    run(hours=args.hours)


if __name__ == "__main__":
    main()
