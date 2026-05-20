"""
03_etl_normalize.py — Phase 3: ETL & Episode Normalization
CISO Tenure Study | Hitch Partners

Transforms raw Apify LinkedIn JSON into tenure_episodes.csv.
One profile → one or more episode rows (unit of analysis = role episode).

Input:  data/raw/all_profiles_raw.json
        data/raw/scrape_manifest.csv
        data/input/profiles.csv
Output: data/processed/tenure_episodes.csv
        data/processed/tenure_episodes_excluded.csv

Exit codes: 0 = success, 1 = fatal input error
"""

import hashlib
import re
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT   = Path(__file__).parent.parent
RAW_JSON_PATH  = PROJECT_ROOT / "data" / "raw" / "all_profiles_raw.json"
MANIFEST_PATH  = PROJECT_ROOT / "data" / "raw" / "scrape_manifest.csv"
PROFILES_PATH  = PROJECT_ROOT / "data" / "input" / "profiles.csv"
PROCESSED_DIR  = PROJECT_ROOT / "data" / "processed"
OUTPUT_PATH    = PROCESSED_DIR / "tenure_episodes.csv"
EXCLUDED_PATH  = PROCESSED_DIR / "tenure_episodes_excluded.csv"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Field name probes for harvestapi/linkedin-profile-scraper (and fallbacks)
URL_FIELDS      = ["linkedInUrl", "url", "profileUrl", "linkedinUrl", "linkedIn", "publicIdentifier"]
POSITION_FIELDS = ["positions", "experience", "jobs", "workExperience"]

# Title normalization
CISO_TERMS   = ["ciso", "chief information security officer"]
CSO_TERMS    = ["chief security officer"]
VP_SEC_RANKS = ["vp", "svp", "evp", "vice president"]
IT_EXEC      = ["cio", "cto", "cito"]
DEPUTY_TERMS = ["deputy ciso", "assistant ciso"]
INTERIM_TERMS = ["interim", "acting"]

# Era thresholds
COVID_START = (2020, 3)
COVID_END   = (2021, 12)

# Company name legal suffixes to strip (ordered longest first)
LEGAL_SUFFIXES = [
    "technologies", "technology", "solutions", "services", "holdings",
    "company", "limited", "group", "corp.", "corp", "inc.", "inc",
    "ltd.", "ltd", "llc", "co.", "plc",
]

# Output column order (matches CLAUDE.md episode schema exactly)
OUTPUT_COLUMNS = [
    "episode_id", "profile_id", "profile_url",
    "company_name", "company_name_clean",
    "title_raw", "title_normalized",
    "start_year", "start_month", "end_year", "end_month",
    "duration_months", "duration_months_to_scrape_date",
    "is_censored", "scrape_date",
    "imputed_start_month", "imputed_end_month", "imputed_duration",
    "episode_start_era",
    "company_size_tier", "industry_sector", "industry_normalized",
    "profile_region",
    "contributor_episode_count", "size_tier_usable", "qa_flags",
]

EXCLUDED_COLUMNS = OUTPUT_COLUMNS + ["exclusion_reason"]

# ---------------------------------------------------------------------------
# ANSI color helpers (suppressed when not a TTY)
# ---------------------------------------------------------------------------
_IS_TTY = sys.stdout.isatty()

def _color(text, code):
    return f"\033[{code}m{text}\033[0m" if _IS_TTY else text

def red(t):    return _color(t, "91")
def yellow(t): return _color(t, "93")
def green(t):  return _color(t, "92")
def bold(t):   return _color(t, "1")
def cyan(t):   return _color(t, "96")


# ---------------------------------------------------------------------------
# URL normalization (shared join key)
# ---------------------------------------------------------------------------
def normalize_url(u: str) -> str:
    if not u:
        return ""
    u = u.strip().rstrip("/").lower()
    if not u.startswith("http"):
        u = "https://" + u
    elif u.startswith("http://"):
        u = "https://" + u[7:]
    return u


# ---------------------------------------------------------------------------
# Load inputs
# ---------------------------------------------------------------------------
def load_raw_json() -> list:
    if not RAW_JSON_PATH.exists():
        print(red(f"\nERROR: Raw JSON not found: {RAW_JSON_PATH}"))
        print(red("  Run 02_apify_scraper.py --run first to generate it."))
        sys.exit(1)

    import json
    data = json.loads(RAW_JSON_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print(red(f"\nERROR: Expected a JSON array in {RAW_JSON_PATH}, got {type(data).__name__}"))
        sys.exit(1)

    print(f"  Raw JSON loaded   : {len(data):,} profile records")
    return data


def load_manifest() -> dict:
    """Returns {normalized_url: scraped_at_datetime}"""
    if not MANIFEST_PATH.exists():
        print(yellow(f"  WARNING: Manifest not found at {MANIFEST_PATH}"))
        print(yellow("  scrape_date will be set to today for all profiles."))
        return {}

    df = pd.read_csv(MANIFEST_PATH, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    manifest = {}
    for _, row in df.iterrows():
        url = row.get("profile_url", "")
        scraped_at = row.get("scraped_at", "")
        status = row.get("status", "")
        if url and status != "failed":
            try:
                dt = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now(timezone.utc)
            manifest[normalize_url(url)] = dt

    print(f"  Manifest loaded   : {len(manifest):,} profiles (non-failed)")
    return manifest


def load_metadata() -> dict:
    """Returns {normalized_url: {company_size_tier, industry_sector, profile_region}}"""
    if not PROFILES_PATH.exists():
        print(yellow(f"  WARNING: profiles.csv not found — metadata columns will be empty"))
        return {}

    df = pd.read_csv(PROFILES_PATH, encoding="utf-8-sig", dtype=str)
    df.columns = [c.strip() for c in df.columns]

    # Alias detection for URL column
    url_col = None
    for col in df.columns:
        if col.lower().strip() in {"linkedin", "linkedin_url", "linkedin url", "url",
                                   "profile url", "profile_url"}:
            url_col = col
            break
    if url_col is None:
        print(yellow("  WARNING: Cannot find URL column in profiles.csv — metadata join skipped"))
        return {}

    # Alias detection for metadata columns
    def find_col(aliases):
        for col in df.columns:
            if col.lower().strip() in aliases:
                return col
        return None

    size_col    = find_col({"company_size_tier", "current company size", "company size", "size"})
    industry_col = find_col({"industry_sector", "industry", "sector", "vertical"})
    region_col  = find_col({"profile_region", "region", "location", "geography"})

    meta = {}
    for _, row in df.iterrows():
        url = str(row.get(url_col, "") or "").strip()
        if not url:
            continue
        meta[normalize_url(url)] = {
            "company_size_tier": str(row.get(size_col, "") or "").strip() if size_col else "",
            "industry_sector":   str(row.get(industry_col, "") or "").strip() if industry_col else "",
            "profile_region":    str(row.get(region_col, "") or "").strip() if region_col else "",
        }

    print(f"  Metadata loaded   : {len(meta):,} profiles from profiles.csv")
    return meta


# ---------------------------------------------------------------------------
# Title normalization
# ---------------------------------------------------------------------------
_WORD_BOUNDARY = re.compile(r'\b')


def _contains(text: str, terms: list) -> bool:
    t = text.lower()
    return any(term in t for term in terms)


def _whole_word(text: str, word: str) -> bool:
    return bool(re.search(rf'\b{re.escape(word)}\b', text, re.IGNORECASE))


def normalize_title(title: str) -> tuple:
    """
    Returns (title_normalized_or_None, exclusion_reason_or_None, is_vp_candidate).
    title_normalized values: CISO, CSO, VP_Security, None (skip), or exclusion label.
    """
    if not title or not isinstance(title, str):
        return None, None, False

    t = title.lower().strip()

    # 1. Excluded_Deputy (check before CISO to catch "Deputy CISO")
    if _contains(t, DEPUTY_TERMS):
        return None, "Excluded_Deputy", False

    # 2. Excluded_Interim
    if _contains(t, INTERIM_TERMS):
        return None, "Excluded_Interim", False

    # 3. CISO
    if _contains(t, CISO_TERMS):
        return "CISO", None, False

    # 4. CSO — "Chief Security Officer" or standalone "CSO" (not part of "CISO")
    if _contains(t, CSO_TERMS) or (
        _whole_word(t, "cso") and "ciso" not in t
    ):
        return "CSO", None, False

    # 5. VP_Security — candidate (per-company gate applied later)
    if "security" in t and any(_whole_word(t, rank) for rank in VP_SEC_RANKS):
        return None, None, True  # is_vp_candidate=True

    # 6. Excluded_Other — pure IT executive, no security keyword
    if any(_whole_word(t, role) for role in IT_EXEC) and "security" not in t:
        return None, "Excluded_Other", False

    # 7. No match — skip
    return None, None, False


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------
_MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_date(date_val) -> tuple:
    """
    Returns (year: int|None, month: int|None, imputed: bool).
    month=6 and imputed=True when month cannot be determined.
    (None, None, False) when date is entirely absent (censored end date).
    """
    if date_val is None:
        return None, None, False

    # Format A/B: dict with year/month keys
    if isinstance(date_val, dict):
        year  = date_val.get("year")  or date_val.get("Year")
        month = date_val.get("month") or date_val.get("Month")
        if year is None:
            return None, None, False
        try:
            year = int(year)
        except (ValueError, TypeError):
            return None, None, False
        if month:
            try:
                return year, int(month), False
            except (ValueError, TypeError):
                # Handle named months: "Jan", "January", etc.
                if isinstance(month, str):
                    m = _MONTH_NAMES.get(month[:3].lower())
                    if m:
                        return year, m, False
        return year, 6, True  # month missing or unrecognized → impute

    # String formats
    s = str(date_val).strip()
    if not s or s.lower() in ("null", "none", "present", "current"):
        return None, None, False

    # Format C: ISO "2020-03" or "2020-03-15"
    iso_match = re.match(r'^(\d{4})-(\d{1,2})(?:-\d{1,2})?$', s)
    if iso_match:
        return int(iso_match.group(1)), int(iso_match.group(2)), False

    # Format D: "March 2020" / "Mar 2020" / "2020 March"
    named_match = re.search(
        r'(?:^|\s)([A-Za-z]{3,9})\s+(\d{4})|(\d{4})\s+([A-Za-z]{3,9})(?:$|\s)', s
    )
    if named_match:
        if named_match.group(1):
            mon_str, year_str = named_match.group(1), named_match.group(2)
        else:
            year_str, mon_str = named_match.group(3), named_match.group(4)
        mon = _MONTH_NAMES.get(mon_str[:3].lower())
        if mon:
            return int(year_str), mon, False

    # Format E: year only "2020"
    year_only = re.match(r'^(\d{4})$', s)
    if year_only:
        return int(year_only.group(1)), 6, True

    return None, None, False


# ---------------------------------------------------------------------------
# Company name cleaning
# ---------------------------------------------------------------------------
def clean_company_name(name: str) -> str:
    if not name or not isinstance(name, str):
        return ""
    s = name.lower().strip()
    # Strip trailing punctuation repeatedly, then known legal suffixes
    changed = True
    while changed:
        changed = False
        s = s.rstrip(".,;: ")
        for suffix in LEGAL_SUFFIXES:
            pattern = rf'\s+{re.escape(suffix)}$'
            new_s = re.sub(pattern, "", s, flags=re.IGNORECASE)
            if new_s != s:
                s = new_s.rstrip(".,;: ")
                changed = True
                break
    return s.strip()


# ---------------------------------------------------------------------------
# Era classification
# ---------------------------------------------------------------------------
def classify_era(year: int, month: int) -> str:
    pt = (year, month)
    if pt < COVID_START:
        return "Pre-COVID"
    elif pt <= COVID_END:
        return "COVID"
    else:
        return "Post-COVID"


# ---------------------------------------------------------------------------
# Duration calculation
# ---------------------------------------------------------------------------
def calc_durations(
    start_year: int, start_month: int,
    end_year, end_month,
    is_censored: bool,
    imputed_start_month: bool, imputed_end_month: bool,
    scrape_dt: datetime,
) -> tuple:
    """
    Returns (duration_months, duration_months_to_scrape_date, imputed_duration).
    duration_months is None for censored rows.
    """
    def months(y, m):
        return y * 12 + m

    scrape_total = months(scrape_dt.year, scrape_dt.month)
    start_total  = months(start_year, start_month)

    duration_months_to_scrape = max(0, scrape_total - start_total)

    if is_censored:
        return None, duration_months_to_scrape, False

    end_total = months(end_year, end_month)
    dur = end_total - start_total

    # Same year, both months imputed → collapse to 6
    imputed_dur = False
    if start_year == end_year and imputed_start_month and imputed_end_month:
        dur = 6
        imputed_dur = True

    return dur, duration_months_to_scrape, imputed_dur


# ---------------------------------------------------------------------------
# size_tier_usable flag
# ---------------------------------------------------------------------------
def compute_size_tier_usable(start_year: int, duration_to_scrape: int) -> bool:
    return start_year >= 2021 and duration_to_scrape < 36


# ---------------------------------------------------------------------------
# Resolve profile URL from a raw record
# ---------------------------------------------------------------------------
def resolve_url(record: dict) -> str:
    for field in URL_FIELDS:
        val = record.get(field)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return ""


# ---------------------------------------------------------------------------
# Resolve positions list from a raw record
# ---------------------------------------------------------------------------
def resolve_positions(record: dict) -> list:
    for field in POSITION_FIELDS:
        val = record.get(field)
        if isinstance(val, list):
            return val
    return []


# ---------------------------------------------------------------------------
# Core extraction loop
# ---------------------------------------------------------------------------
def extract_all_episodes(
    raw_profiles: list,
    manifest: dict,
    metadata: dict,
) -> tuple:
    """
    Returns (included_rows: list[dict], excluded_rows: list[dict], counters: dict).
    """
    included = []
    excluded = []
    fallback_scrape_dt = datetime.now(timezone.utc)

    counters = {
        "profiles_processed": 0,
        "profiles_skipped_no_url": 0,
        "profiles_skipped_failed": 0,
        "raw_positions_total": 0,
        "no_match_skipped": 0,
        "no_start_date_skipped": 0,
        "metadata_miss": 0,
        "title_counts": Counter(),
        "exclusion_counts": Counter(),
    }

    for record in raw_profiles:
        raw_url = resolve_url(record)
        if not raw_url:
            counters["profiles_skipped_no_url"] += 1
            continue

        norm = normalize_url(raw_url)
        profile_url = raw_url  # preserve original casing for output

        # Skip profiles that fully failed scraping
        if norm not in manifest and len(manifest) > 0:
            # Manifest exists but this profile isn't in it — may be a failed scrape
            # Still process if we have position data; just use fallback date
            pass

        scrape_dt = manifest.get(norm, fallback_scrape_dt)
        profile_id = hashlib.sha256(norm.encode()).hexdigest()[:12]
        meta = metadata.get(norm, {})
        if not meta:
            counters["metadata_miss"] += 1

        positions = resolve_positions(record)
        counters["raw_positions_total"] += len(positions)
        counters["profiles_processed"] += 1

        # First pass: classify each position
        profile_candidates = []  # (position_dict, title_norm, excl_reason, is_vp_cand, company_clean)
        for pos in positions:
            title_raw = (
                pos.get("title") or pos.get("jobTitle") or
                pos.get("position") or pos.get("role") or ""
            )
            company_raw = (
                pos.get("companyName") or pos.get("company") or
                pos.get("organizationName") or pos.get("employer") or ""
            )
            company_clean = clean_company_name(company_raw)

            title_norm, excl_reason, is_vp_cand = normalize_title(title_raw)
            profile_candidates.append(
                (pos, title_raw, company_raw, company_clean,
                 title_norm, excl_reason, is_vp_cand)
            )

        # Build per-company CISO presence lookup for VP_Security gate
        ciso_companies: set = set()
        for (_, _, _, cc, tn, _, _) in profile_candidates:
            if tn in ("CISO", "CSO"):
                ciso_companies.add(cc)

        # Second pass: finalize VP_Security candidates
        for (pos, title_raw, company_raw, company_clean,
             title_norm, excl_reason, is_vp_cand) in profile_candidates:

            if is_vp_cand:
                if company_clean in ciso_companies:
                    title_norm = None
                    excl_reason = "VP_below_CISO_at_same_company"
                else:
                    title_norm = "VP_Security"
                    excl_reason = None

            # Skip non-matching, non-excluded roles silently
            if title_norm is None and excl_reason is None:
                counters["no_match_skipped"] += 1
                continue

            # Parse dates
            start_raw = (
                pos.get("startDate") or pos.get("start_date") or
                pos.get("dateStarted") or pos.get("startedOn") or {}
            )
            end_raw = (
                pos.get("endDate") or pos.get("end_date") or
                pos.get("dateEnded") or pos.get("finishedOn")
            )

            start_year, start_month, imp_start = parse_date(start_raw)
            end_year,   end_month,   imp_end   = parse_date(end_raw)

            # Skip if no start date — cannot compute duration
            if start_year is None:
                counters["no_start_date_skipped"] += 1
                continue

            is_censored = (end_year is None)

            # Reclassify end dates in the scrape year as censored — the actor
            # sometimes returns the scrape date instead of "Present" for current
            # roles, producing a spurious completed episode dated to 2026.
            if end_year == scrape_dt.year and not is_censored:
                end_year    = None
                end_month   = None
                imp_end     = False
                is_censored = True

            # Duration
            dur_months, dur_to_scrape, imp_dur = calc_durations(
                start_year, start_month,
                end_year, end_month,
                is_censored,
                imp_start, imp_end,
                scrape_dt,
            )

            era = classify_era(start_year, start_month)
            size_usable = compute_size_tier_usable(start_year, dur_to_scrape)

            row = {
                "episode_id":                   str(uuid.uuid4()),
                "profile_id":                   profile_id,
                "profile_url":                  profile_url,
                "company_name":                 company_raw,
                "company_name_clean":           company_clean,
                "title_raw":                    title_raw,
                "title_normalized":             title_norm,
                "start_year":                   start_year,
                "start_month":                  start_month,
                "end_year":                     end_year,
                "end_month":                    end_month,
                "duration_months":              dur_months,
                "duration_months_to_scrape_date": dur_to_scrape,
                "is_censored":                  is_censored,
                "scrape_date":                  scrape_dt.date().isoformat(),
                "imputed_start_month":          imp_start,
                "imputed_end_month":            imp_end,
                "imputed_duration":             imp_dur,
                "episode_start_era":            era,
                "company_size_tier":            meta.get("company_size_tier", ""),
                "industry_sector":              meta.get("industry_sector", ""),
                "industry_normalized":          "",
                "profile_region":               meta.get("profile_region", ""),
                "contributor_episode_count":    0,   # filled later
                "size_tier_usable":             size_usable,
                "qa_flags":                     "",
            }

            if excl_reason:
                counters["exclusion_counts"][excl_reason] += 1
                row["exclusion_reason"] = excl_reason
                excluded.append(row)
            else:
                counters["title_counts"][title_norm] += 1
                included.append(row)

    return included, excluded, counters


# ---------------------------------------------------------------------------
# Compute contributor_episode_count
# ---------------------------------------------------------------------------
def apply_contributor_counts(rows: list) -> list:
    counts = Counter(r["profile_id"] for r in rows)
    for r in rows:
        r["contributor_episode_count"] = counts[r["profile_id"]]
    return rows


# ---------------------------------------------------------------------------
# Sample size checkpoints
# ---------------------------------------------------------------------------
CHECKPOINTS = [
    ("Valid CISO episodes (post-filtering)",   1500),
    ("Completed episodes (non-censored)",       400),
    ("Completed — Pre-COVID era",               100),
    ("Completed — COVID era",                   100),
    ("Completed — Post-COVID era",              100),
    ("Profiles contributing 2+ episodes",       400),
]


def run_checkpoints(df: pd.DataFrame) -> bool:
    completed = df[~df["is_censored"]]

    counts = [
        len(df),
        len(completed),
        len(completed[completed["episode_start_era"] == "Pre-COVID"]),
        len(completed[completed["episode_start_era"] == "COVID"]),
        len(completed[completed["episode_start_era"] == "Post-COVID"]),
        df.groupby("profile_id").size().ge(2).sum(),
    ]

    all_pass = True
    sep = "-" * 72

    print()
    print(bold("SAMPLE SIZE CHECKPOINTS"))
    print(sep)
    print(f"  {'Checkpoint':<42} {'Min':>6}  {'Count':>7}  Status")
    print(sep)

    for (label, minimum), count in zip(CHECKPOINTS, counts):
        status = "PASS" if count >= minimum else "FAIL"
        line = f"  {label:<42} {minimum:>6,}  {count:>7,}  {status}"
        if status == "FAIL":
            print(red(line))
            all_pass = False
        else:
            print(green(line))

    print(sep)

    if not all_pass:
        print(red("\n  *** One or more checkpoints FAILED."))
        print(red("  *** Consider expanding the sample before publishing results."))
        print(red("  *** Processing continues — do not submit Phase 5 until resolved."))

    return all_pass


# ---------------------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------------------
def print_summary(included: list, excluded: list, counters: dict, all_pass: bool):
    n_inc = len(included)
    n_exc = len(excluded)
    df = pd.DataFrame(included) if included else pd.DataFrame(columns=OUTPUT_COLUMNS)
    sep = "=" * 72

    n_censored  = int(df["is_censored"].sum()) if not df.empty else 0
    n_completed = n_inc - n_censored

    print()
    print(bold(sep))
    print(bold("  ETL COMPLETE — SUMMARY"))
    print(bold(sep))

    print()
    print(bold("EXTRACTION"))
    print(f"  Total raw position entries found    : {counters['raw_positions_total']:,}")
    print(f"  Profiles processed                  : {counters['profiles_processed']:,}")
    print(f"  Profiles skipped (no URL in record) : {counters['profiles_skipped_no_url']:,}")
    print(f"  Positions skipped (no start date)   : {counters['no_start_date_skipped']:,}")
    print(f"  Positions skipped (no title match)  : {counters['no_match_skipped']:,}")
    print(f"  Profiles with missing metadata      : {counters['metadata_miss']:,}")

    print()
    print(bold("TITLE CLASSIFICATION — INCLUDED"))
    for label in ("CISO", "CSO", "VP_Security"):
        print(f"  {label:<36}: {counters['title_counts'].get(label, 0):,}")
    print(f"  {'Total included':<36}: {n_inc:,}")

    print()
    print(bold("TITLE CLASSIFICATION — EXCLUDED"))
    excl_labels = [
        "Excluded_Deputy", "Excluded_Interim", "Excluded_Other",
        "VP_below_CISO_at_same_company",
    ]
    for label in excl_labels:
        print(f"  {label:<36}: {counters['exclusion_counts'].get(label, 0):,}")
    print(f"  {'Total excluded':<36}: {n_exc:,}")

    print()
    print(bold("CENSORING"))
    if n_inc > 0:
        print(f"  Completed (non-censored)            : {n_completed:,} ({n_completed/n_inc*100:.1f}%)")
        print(f"  Censored (current role)             : {n_censored:,} ({n_censored/n_inc*100:.1f}%)")
    else:
        print(f"  No included episodes to report")

    print()
    print(bold("ERA DISTRIBUTION (included only)"))
    if not df.empty:
        for era in ("Pre-COVID", "COVID", "Post-COVID"):
            n = int((df["episode_start_era"] == era).sum())
            pct = n / n_inc * 100 if n_inc > 0 else 0
            print(f"  {era:<36}: {n:,} ({pct:.1f}%)")

    print()
    print(bold("EPISODE CONTRIBUTIONS PER PROFILE"))
    if not df.empty:
        eps_per_profile = df.groupby("profile_id").size()
        for bucket, label in [(1, "1 episode"), (2, "2 episodes"), (3, "3 episodes")]:
            n = int((eps_per_profile == bucket).sum())
            print(f"  {label:<36}: {n:,} profiles")
        n_4plus = int((eps_per_profile >= 4).sum())
        print(f"  {'4+ episodes':<36}: {n_4plus:,} profiles")

    print()
    print(bold("OUTPUT"))
    print(f"  {str(OUTPUT_PATH)}")
    print(f"    → {n_inc:,} rows")
    print(f"  {str(EXCLUDED_PATH)}")
    print(f"    → {n_exc:,} rows")

    print()
    overall = green("ALL CHECKPOINTS PASSED") if all_pass else red("ONE OR MORE CHECKPOINTS FAILED")
    print(f"  {overall}")
    print(bold(sep))
    print()


# ---------------------------------------------------------------------------
# Write output files
# ---------------------------------------------------------------------------
def write_outputs(included: list, excluded: list):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    if included:
        df_inc = pd.DataFrame(included)[OUTPUT_COLUMNS]
    else:
        df_inc = pd.DataFrame(columns=OUTPUT_COLUMNS)
    df_inc.to_csv(OUTPUT_PATH, index=False)

    if excluded:
        df_exc = pd.DataFrame(excluded)
        # Ensure exclusion_reason is present; reorder columns
        cols = [c for c in EXCLUDED_COLUMNS if c in df_exc.columns]
        df_exc = df_exc[cols]
    else:
        df_exc = pd.DataFrame(columns=EXCLUDED_COLUMNS)
    df_exc.to_csv(EXCLUDED_PATH, index=False)

    print(green(f"  Written: {OUTPUT_PATH} ({len(included):,} rows)"))
    print(green(f"  Written: {EXCLUDED_PATH} ({len(excluded):,} rows)"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    sep = "=" * 70
    print()
    print(bold(sep))
    print(bold("  CISO TENURE STUDY — PHASE 3: ETL & NORMALIZATION"))
    print(bold(sep))
    print()

    print(bold("LOADING INPUTS"))
    raw_profiles = load_raw_json()
    manifest     = load_manifest()
    metadata     = load_metadata()
    print()

    print(bold("EXTRACTING EPISODES"))
    included, excluded, counters = extract_all_episodes(raw_profiles, manifest, metadata)
    print(f"  Included episodes (pre-count): {len(included):,}")
    print(f"  Excluded episodes            : {len(excluded):,}")
    print()

    # Apply contributor counts
    included = apply_contributor_counts(included)

    # Write outputs
    print(bold("WRITING OUTPUT"))
    write_outputs(included, excluded)
    print()

    # Checkpoints
    if included:
        df = pd.DataFrame(included)
        all_pass = run_checkpoints(df)
    else:
        print(red("\n  ERROR: No included episodes produced. Check raw JSON and title rules."))
        all_pass = False

    # Final summary
    print_summary(included, excluded, counters, all_pass)

    return 0


if __name__ == "__main__":
    sys.exit(main())
