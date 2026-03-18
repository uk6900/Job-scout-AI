"""Title and location filters for job listings."""
import re

TITLE_KEYWORDS = [
    "business analyst",
    "business analytics",
    "operations business analyst",
    "business systems analyst",
    "bizops analyst",
]

LOCATION_KEYWORDS = [
    "united states",
    "usa",
    "remote",
    "united states - remote",
    "us remote",
    "anywhere in the u.s",
]


def title_matches(title: str) -> bool:
    t = title.lower().strip()
    return any(kw in t for kw in TITLE_KEYWORDS)


def location_matches(location: str) -> bool:
    if not location:
        return False
    loc = location.lower().strip()
    return any(kw in loc for kw in LOCATION_KEYWORDS)
