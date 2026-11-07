"""Text utilities shared by the deterministic engines (also used to sanity-check LLM output)."""
from __future__ import annotations

import re
from datetime import datetime, timezone

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

STOPWORDS = set(
    """a an the and or but if then than that this these those of to in on for with as at by from
    is are was were be been being has have had do does did not no it its their there here which who
    whom whose what when where why how all any each both more most other some such only own same so
    can will just should now also into about over under after before between during while both
    according reports reported stated says said per approximately roughly around""".split()
)


def split_sentences(text: str) -> list[str]:
    text = text.replace("\r", "\n")
    # Protect common abbreviations before splitting on terminal punctuation.
    guarded = re.sub(r"\b(e\.g|i\.e|etc|vs|approx|Inc|Ltd|No)\.", r"\1<DOT>", text)
    guarded = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", guarded)
    parts = re.split(r"(?<=[.!?])\s+|\n{1,}", guarded)
    out: list[str] = []
    for part in parts:
        cleaned = part.replace("<DOT>", ".").strip(" -*\t•")
        cleaned = re.sub(r"^\d+[.)]\s+", "", cleaned)
        if len(cleaned) >= 20 and re.search(r"[a-zA-Z]", cleaned):
            out.append(cleaned)
    return out


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9][a-z0-9.+#-]*", text.lower()) if t not in STOPWORDS]


def token_set(text: str) -> set[str]:
    return set(tokens(text))


def overlap(a: str, b: str) -> float:
    ta, tb = token_set(a), token_set(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def coverage(needle: str, haystack: str) -> float:
    """Fraction of the needle's content tokens present in the haystack."""
    tn = token_set(needle)
    if not tn:
        return 0.0
    return len(tn & token_set(haystack)) / len(tn)


NUMBER_RE = re.compile(r"(?<![\w./-])(\d{1,3}(?:,?\d{3})*(?:\.\d+)?)\s*(%|billion|million|thousand|bn|m|k|x)?")
VERSION_RE = re.compile(r"\b(v(?:ersion)?\s?\d+(?:\.\d+){0,3}|\d+\.\d+(?:\.\d+)?)\b", re.IGNORECASE)
ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
MONTH_YEAR_RE = re.compile(
    r"\b(" + "|".join(MONTHS) + r")\.?\s+(\d{4})\b", re.IGNORECASE
)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
RELATIVE_DATE_RE = re.compile(
    r"\b(as of|since|until|from)\s+(" + "|".join(MONTHS) + r")?\s?(\d{4})\b", re.IGNORECASE
)


def extract_numbers(text: str) -> list[str]:
    found = []
    for value, unit in NUMBER_RE.findall(text):
        token = value + (unit or "")
        if token not in found:
            found.append(token)
    return found


NON_VERSION_PREFIXES = {
    "rfc", "iso", "iec", "section", "chapter", "article", "rule", "regulation", "no", "no.",
    "page", "figure", "table", "example", "annex", "part", "vol", "volume", "step", "case",
    "order", "resolution", "directive", "recital", "paragraph", "clause", "ref", "line",
}
PRODUCT_VERSION_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9.+#-]{1,24})[\s/]+(v?\d{1,4}(?:\.\d{1,3}){0,3})\b"
)


def extract_versions(text: str) -> list[str]:
    """Extract version-like tokens: dotted releases, v-prefixed and product majors.

    Product majors ("React 19", "Node.js 12", "Python 3") count as versions;
    document identifiers (RFC 8446), years and month-day pairs do not.
    """
    out: list[str] = []

    def add(candidate: str) -> None:
        cleaned = candidate.strip().strip(".,;:")
        if not cleaned:
            return
        if re.fullmatch(r"(19|20)\d{2}", cleaned):  # a bare year is not a version
            return
        if re.fullmatch(r"\d{1,2}", cleaned) and int(cleaned) > 31 and len(cleaned) <= 2:
            return
        if cleaned.lower().startswith("version "):
            cleaned = cleaned[8:].strip()
        if cleaned not in out:
            out.append(cleaned)

    for match in VERSION_RE.findall(text):
        add(match)

    for prefix, number in PRODUCT_VERSION_RE.findall(text):
        low = prefix.lower()
        if low in NON_VERSION_PREFIXES or low in MONTHS:
            continue
        if "." not in number and number.lstrip("v").isdigit():
            major = int(number.lstrip("v"))
            # integer product majors are plausible only for small numbers
            if major > 2100 or major == 0:
                continue
        add(number)

    # v-prefixed standalone ("v1.2.3") plus "version 4.0" phrasing
    for match in re.findall(r"\bversion\s+(\d+(?:\.\d+){0,3})\b", text, re.IGNORECASE):
        add(match)
    return out


def extract_dates(text: str) -> list[str]:
    out: list[str] = []
    for y, m, d in ISO_DATE_RE.findall(text):
        out.append(f"{y}-{m}-{d}")
    for month, year in MONTH_YEAR_RE.findall(text):
        label = f"{month.capitalize()} {year}"
        if label not in out:
            out.append(label)
    if not out:
        for year in YEAR_RE.findall(text):
            pass
        years = re.findall(r"\b(19|20)\d{2}\b", text)
        for match in re.finditer(r"\b(?:19|20)\d{2}\b", text):
            out.append(match.group(0))
    return list(dict.fromkeys(out))


def parse_date(value: str | None) -> datetime | None:
    """Parse ISO dates, 'Month YYYY' and bare years into an aware UTC datetime."""
    if not value:
        return None
    value = str(value).strip()
    iso = ISO_DATE_RE.search(value)
    if iso:
        try:
            return datetime(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)), tzinfo=timezone.utc)
        except ValueError:
            return None
    my = MONTH_YEAR_RE.search(value)
    if my:
        return datetime(int(my.group(2)), MONTHS[my.group(1).lower()], 1, tzinfo=timezone.utc)
    year = re.search(r"\b(19|20)\d{2}\b", value)
    if year:
        return datetime(int(year.group(0)), 1, 1, tzinfo=timezone.utc)
    try:
        from dateutil import parser as date_parser

        parsed = date_parser.parse(value, fuzzy=True)
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc)
    except Exception:  # noqa: BLE001
        return None


CAPITALISED = re.compile(r"\b([A-Z][a-zA-Z0-9.+#-]*(?:\s+[A-Z][a-zA-Z0-9.+#-]*)*)")


def extract_entities(text: str) -> list[str]:
    banned = {"The", "This", "These", "Those", "It", "In", "As", "According", "A", "An", "However"}
    found: list[str] = []
    for match in CAPITALISED.findall(text):
        candidate = match.strip()
        if candidate in banned or len(candidate) < 2:
            continue
        if candidate.isupper() and len(candidate) <= 2:
            continue
        # Trim leading determiners / discourse markers ("The EU AI Act" → "EU AI Act")
        candidate = re.sub(
            r"^(The|A|An|This|These|Those|Its|Their|In|As|According to|Since|From|On|By|However|It)\s+",
            "",
            candidate,
        )
        if candidate and candidate not in found:
            found.append(candidate)
    return found[:8]


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if dt else None


def days_between(later: datetime, earlier: datetime) -> float:
    return max(0.0, (later - earlier).total_seconds() / 86400.0)


def truncate(text: str, limit: int = 320) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
