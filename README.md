# job_scout 🔍

**job_scout** scrapes multiple ATS job boards directly to find freshly-posted US Business Analyst positions — no Google, no aggregators.

## Sources

| Source | Method |
|--------|--------|
| `job-boards.greenhouse.io` | Greenhouse Boards API (JSON) |
| `jobs.lever.co` | Lever Postings API (JSON) |
| `jobs.ashbyhq.com` | Ashby Posting API (JSON) |
| `myworkdayjobs.com` / `workdayjobs.com` | Workday CXS search API (JSON) |
| `*.bamboohr.com/careers` | BambooHR careers list API (JSON) |

## Title filters (any match)

- `business analyst`
- `business analytics`
- `operations business analyst`
- `business systems analyst`
- `bizops analyst`

## Location filters (any match)

- `United States` / `USA`
- `Remote` / `United States - Remote` / `US Remote`

## Features

- Skips jobs with no reliable `posted_at` timestamp
- SQLite deduplication — new-job alerts only fire once
- `output/results.json` written every run
- SMTP email alerts for new jobs (optional)
- Configurable look-back window with `--hours`

---

## Windows Quick-Start

### 1 — Install Python 3.11

Download from <https://www.python.org/downloads/windows/> and check **"Add Python to PATH"** during setup.

### 2 — Open a Terminal

Press `Win + R`, type `cmd`, press Enter.

### 3 — Clone / copy the project

```
cd %USERPROFILE%\Desktop
```

(paste or unzip the `job_scout` folder here)

### 4 — Create a virtual environment

```
cd job_scout
python -m venv .venv
.venv\Scripts\activate
```

### 5 — Install dependencies

```
pip install -r requirements.txt
```

### 6 — Run the scout

```
python -m job_scout
```

With a custom time window:

```
python -m job_scout --hours 6
```

Verbose/debug mode:

```
python -m job_scout --hours 10 --verbose
```

---

## Email Alerts (optional)

Set environment variables **before** running:

```
set SMTP_HOST=smtp.gmail.com
set SMTP_PORT=587
set SMTP_USER=you@gmail.com
set SMTP_PASS=your_app_password
set SMTP_TLS=true
set EMAIL_FROM=you@gmail.com
set EMAIL_TO=you@gmail.com,colleague@example.com
```

> For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833), not your regular password.

If any variable is missing, the tool continues without sending email.

---

## Output

```
output/results.json      ← all matching jobs from this run
job_scout.db             ← SQLite seen-jobs store
```

### results.json structure

```json
{
  "hours_window": 10,
  "total_found": 5,
  "new_count": 3,
  "jobs": [
    {
      "id": "gh_abc123",
      "title": "Business Analyst",
      "company": "Stripe",
      "location": "Remote",
      "url": "https://job-boards.greenhouse.io/stripe/jobs/...",
      "source": "greenhouse",
      "posted_at": "2025-01-15T14:23:00+00:00"
    }
  ]
}
```

---

## Extending the Company Lists

Each scraper file (`job_scout/scrapers/*.py`) contains a `COMPANIES` list at the top. Add any company slug that uses that ATS to expand coverage.

- **Greenhouse slug** = the part after `job-boards.greenhouse.io/`
- **Lever slug** = the part after `jobs.lever.co/`
- **Ashby slug** = the part after `jobs.ashbyhq.com/`
- **Workday** = update the `TENANTS` list with `(tenant_subdomain, board_name)` tuples
- **BambooHR slug** = the subdomain before `.bamboohr.com`

---

## Project Layout

```
job_scout/
├── job_scout/
│   ├── __init__.py
│   ├── __main__.py          ← python -m job_scout entry point
│   ├── main.py              ← orchestrator
│   ├── db.py                ← SQLite deduplication
│   ├── filters.py           ← title / location matchers
│   ├── http_client.py       ← shared requests session
│   ├── email_alert.py       ← SMTP alerts
│   └── scrapers/
│       ├── __init__.py
│       ├── greenhouse.py
│       ├── lever.py
│       ├── ashby.py
│       ├── workday.py
│       └── bamboohr.py
├── output/                  ← results.json written here
├── requirements.txt
└── README.md
```
