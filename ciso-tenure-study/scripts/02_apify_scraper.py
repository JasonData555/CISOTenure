"""
02_apify_scraper.py — Phase 2: LinkedIn Profile Scraping
CISO Tenure Study | Hitch Partners

Scrapes full LinkedIn work history for every profile in data/input/profiles.csv
using the Apify LinkedIn Profile Scraper actor.

Usage:
    python3 scripts/02_apify_scraper.py           # dry run — shows plan, does NOT scrape
    python3 scripts/02_apify_scraper.py --run      # live run

Exit codes: 0 = success or dry run, 1 = fatal error
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from apify_client import ApifyClient
from dotenv import load_dotenv
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
INPUT_PATH   = PROJECT_ROOT / "data" / "input" / "profiles.csv"
RAW_DIR      = PROJECT_ROOT / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "scrape_manifest.csv"
MERGED_PATH   = RAW_DIR / "all_profiles_raw.json"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ACTOR_ID    = "harvestapi/linkedin-profile-scraper"
BATCH_SIZE  = 50
BATCH_DELAY = 2        # seconds between batches
MAX_RETRIES = 3
BACKOFF     = [2, 4, 8]   # exponential backoff in seconds
RATE_LIMIT_PAUSE = 60  # seconds to pause on 429

# URL column aliases — mirrors 01_validate_input.py alias logic
URL_ALIASES = {"linkedin", "linkedin_url", "linkedin url", "url", "profile url", "profile_url"}

# ANSI colors — suppressed when not a TTY
_IS_TTY = sys.stdout.isatty()

def _color(text, code):
    return f"\033[{code}m{text}\033[0m" if _IS_TTY else text

def red(t):    return _color(t, "91")
def yellow(t): return _color(t, "93")
def green(t):  return _color(t, "92")
def bold(t):   return _color(t, "1")
def cyan(t):   return _color(t, "96")


# ---------------------------------------------------------------------------
# Token & setup
# ---------------------------------------------------------------------------
def load_token() -> str:
    load_dotenv(PROJECT_ROOT / ".env")
    token = os.environ.get("APIFY_API_TOKEN", "").strip()
    if not token or token == "your_token_here":
        print(red("\nERROR: APIFY_API_TOKEN not set in .env"))
        print(red("  Edit ciso-tenure-study/.env and set:"))
        print(red("  APIFY_API_TOKEN=apify_api_XXXXXXXXXXXXXXXXXXXXXXXX"))
        sys.exit(1)
    return token


def print_actor_banner():
    sep = "=" * 70
    print()
    print(bold(sep))
    print(bold("  CISO TENURE STUDY — PHASE 2: APIFY LINKEDIN SCRAPER"))
    print(bold(sep))
    print()
    print(cyan(f"  ┌─ ACTOR ID ──────────────────────────────────────────────────┐"))
    print(cyan(f"  │  {ACTOR_ID}                                          │"))
    print(cyan(f"  │  *** Verify this in your Apify console before running ***   │"))
    print(cyan(f"  └────────────────────────────────────────────────────────────-┘"))
    print()


# ---------------------------------------------------------------------------
# Load profiles
# ---------------------------------------------------------------------------
def load_profile_urls() -> list[str]:
    if not INPUT_PATH.exists():
        print(red(f"\nERROR: Input file not found: {INPUT_PATH}"))
        print(red("  Run 01_validate_input.py first and ensure profiles.csv is present."))
        sys.exit(1)

    try:
        df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig", dtype=str)
    except UnicodeDecodeError:
        df = pd.read_csv(INPUT_PATH, encoding="latin-1", dtype=str)

    df.columns = [c.strip() for c in df.columns]

    # Alias-detect URL column
    url_col = None
    for col in df.columns:
        if col.lower().strip() in URL_ALIASES or col.strip() == "profile_url":
            url_col = col
            break

    if url_col is None:
        print(red(f"\nERROR: Cannot find LinkedIn URL column in {INPUT_PATH}"))
        print(red(f"  Columns found: {list(df.columns)}"))
        print(red(f"  Expected one of: {sorted(URL_ALIASES)}"))
        sys.exit(1)

    if url_col != "profile_url":
        print(yellow(f"  Column mapping: '{url_col}' → profile_url"))

    urls_raw = df[url_col].dropna().str.strip()
    urls_raw = urls_raw[urls_raw != ""]

    # Normalize: ensure https:// prefix
    def normalize(u: str) -> str:
        u = u.strip().rstrip("/")
        if not u.startswith("http"):
            u = "https://" + u
        elif u.startswith("http://"):
            u = "https://" + u[7:]
        return u

    urls = urls_raw.map(normalize).tolist()

    # Deduplicate (preserve order)
    seen = set()
    unique_urls = []
    dupes = []
    for u in urls:
        key = u.lower()
        if key in seen:
            dupes.append(u)
        else:
            seen.add(key)
            unique_urls.append(u)

    if dupes:
        print(yellow(f"  WARNING: {len(dupes)} duplicate URL(s) removed before batching"))

    print(f"  Profiles loaded : {len(unique_urls):,}")
    return unique_urls


# ---------------------------------------------------------------------------
# Result classification
# ---------------------------------------------------------------------------
def classify_results(
    batch_urls: list[str],
    raw_records: list[dict],
    batch_num: int,
    scraped_at: str,
    was_retry: bool,
) -> list[dict]:
    """
    Match actor output records back to input URLs.
    Returns one manifest row dict per input URL.
    """
    # Build a lookup: normalize URL → record
    def norm(u: str) -> str:
        return u.lower().strip().rstrip("/")

    record_by_url: dict[str, dict] = {}
    for rec in raw_records:
        # Apify LinkedIn scraper returns the URL in various fields
        for field in ("linkedInUrl", "url", "profileUrl", "linkedinUrl"):
            val = rec.get(field)
            if val and isinstance(val, str):
                record_by_url[norm(val)] = rec
                break

    rows = []
    for url in batch_urls:
        rec = record_by_url.get(norm(url))
        if rec is None:
            row = {
                "profile_url": url,
                "batch_number": batch_num,
                "status": "failed",
                "scraped_at": scraped_at,
                "episodes_found": 0,
                "error_message": "not returned by actor",
            }
        else:
            # Count work history episodes
            positions = rec.get("positions", rec.get("experience", rec.get("jobs", [])))
            if not isinstance(positions, list):
                positions = []
            n_episodes = len(positions)
            if n_episodes == 0:
                status = "no_history"
            elif was_retry:
                status = "retry_success"
            else:
                status = "success"
            row = {
                "profile_url": url,
                "batch_number": batch_num,
                "status": status,
                "scraped_at": scraped_at,
                "episodes_found": n_episodes,
                "error_message": "",
            }
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Save batch
# ---------------------------------------------------------------------------
def save_batch(records: list[dict], batch_num: int) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"batch_{batch_num:03d}.json"
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def batch_already_done(batch_num: int) -> bool:
    return (RAW_DIR / f"batch_{batch_num:03d}.json").exists()


# ---------------------------------------------------------------------------
# Actor call with retry
# ---------------------------------------------------------------------------
def call_actor_with_retry(
    client: ApifyClient,
    batch_urls: list[str],
    batch_num: int,
) -> tuple[list[dict], list[dict], bool]:
    """
    Returns (raw_records, manifest_rows, was_retry).
    On total failure, returns ([], manifest_rows_all_failed, False).
    """
    actor_input = {
        "queries": batch_urls,
        "proxy": {"useApifyProxy": True},
    }

    last_error = ""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            run = client.actor(ACTOR_ID).call(run_input=actor_input)
            raw_records = list(
                client.dataset(run["defaultDatasetId"]).iterate_items()
            )
            scraped_at = datetime.now(timezone.utc).isoformat()
            manifest_rows = classify_results(
                batch_urls, raw_records, batch_num, scraped_at, was_retry=(attempt > 1)
            )
            return raw_records, manifest_rows, (attempt > 1)

        except Exception as exc:
            last_error = str(exc)
            is_rate_limit = "429" in last_error or "rate limit" in last_error.lower()

            if is_rate_limit:
                print(yellow(f"\n  [batch {batch_num:03d}] Rate limit (429) — pausing {RATE_LIMIT_PAUSE}s ..."))
                time.sleep(RATE_LIMIT_PAUSE)
            else:
                if attempt < MAX_RETRIES:
                    wait = BACKOFF[attempt - 1]
                    print(yellow(f"\n  [batch {batch_num:03d}] Attempt {attempt} failed: {last_error[:80]}"))
                    print(yellow(f"  Retrying in {wait}s ..."))
                    time.sleep(wait)

    # All retries exhausted
    print(red(f"\n  [batch {batch_num:03d}] All {MAX_RETRIES} attempts failed: {last_error[:120]}"))
    scraped_at = datetime.now(timezone.utc).isoformat()
    manifest_rows = [
        {
            "profile_url": url,
            "batch_number": batch_num,
            "status": "failed",
            "scraped_at": scraped_at,
            "episodes_found": 0,
            "error_message": f"batch failed after {MAX_RETRIES} retries: {last_error[:200]}",
        }
        for url in batch_urls
    ]
    return [], manifest_rows, False


# ---------------------------------------------------------------------------
# Merge all batches
# ---------------------------------------------------------------------------
def merge_batches() -> int:
    batch_files = sorted(RAW_DIR.glob("batch_*.json"))
    merged = []
    for f in batch_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                merged.extend(data)
        except Exception as exc:
            print(yellow(f"  WARNING: Could not read {f.name}: {exc}"))

    MERGED_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(merged)


# ---------------------------------------------------------------------------
# Manifest writer
# ---------------------------------------------------------------------------
def write_manifest(rows: list[dict]) -> None:
    df = pd.DataFrame(rows, columns=[
        "profile_url", "batch_number", "status",
        "scraped_at", "episodes_found", "error_message",
    ])
    df.to_csv(MANIFEST_PATH, index=False)


# ---------------------------------------------------------------------------
# Dry-run plan printer
# ---------------------------------------------------------------------------
def print_dry_run_plan(n_profiles: int, n_batches: int) -> None:
    sep = "-" * 70
    print(bold("\n  DRY RUN — Script loaded successfully. No Apify calls made."))
    print()
    print(f"  {sep}")
    print(f"  SCRAPE PLAN")
    print(f"  {sep}")
    print(f"  Input file       : {INPUT_PATH}")
    print(f"  Total profiles   : {n_profiles:,}")
    print(f"  Batch size       : {BATCH_SIZE}")
    print(f"  Total batches    : {n_batches}")
    print(f"  Inter-batch delay: {BATCH_DELAY}s")
    print(f"  Max retries      : {MAX_RETRIES} (backoff: {BACKOFF[0]}s / {BACKOFF[1]}s / {BACKOFF[2]}s)")
    print(f"  Rate-limit pause : {RATE_LIMIT_PAUSE}s on HTTP 429")
    print()
    print(f"  OUTPUT FILES")
    print(f"  {sep}")
    print(f"  Batch JSON files : {RAW_DIR}/batch_001.json ... batch_{n_batches:03d}.json")
    print(f"  Merged output    : {MERGED_PATH}")
    print(f"  Manifest CSV     : {MANIFEST_PATH}")
    print()
    print(f"  TO RUN THE SCRAPER")
    print(f"  {sep}")
    print()
    print(f"  Step 1 — Set your token in .env:")
    print(f"    Edit: {PROJECT_ROOT / '.env'}")
    print(f"    Set:  APIFY_API_TOKEN=apify_api_XXXXXXXXXXXXXXXXXXXXXXXX")
    print()
    print(bold(f"  Step 2 — Run the scraper (from ciso-tenure-study/):"))
    print(green(f"    python3 scripts/02_apify_scraper.py --run"))
    print()
    print(f"  Note: Re-running is safe — completed batch_NNN.json files are skipped.")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 2: Scrape LinkedIn work history via Apify."
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute the scraper (without this flag, only a dry-run plan is shown)",
    )
    args = parser.parse_args()

    print_actor_banner()

    token = load_token()
    print(green("  APIFY_API_TOKEN : loaded from .env"))

    urls = load_profile_urls()
    n_profiles = len(urls)

    # Split into batches
    batches = [urls[i : i + BATCH_SIZE] for i in range(0, n_profiles, BATCH_SIZE)]
    n_batches = len(batches)

    if not args.run:
        print_dry_run_plan(n_profiles, n_batches)
        return 0

    # -----------------------------------------------------------------------
    # LIVE RUN
    # -----------------------------------------------------------------------
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    client = ApifyClient(token)

    start_time = time.time()
    all_manifest_rows: list[dict] = []
    total_succeeded = 0
    total_failed = 0
    total_no_history = 0
    total_retried = 0
    total_episodes = 0

    print(f"\n  Starting scrape: {n_profiles:,} profiles in {n_batches} batches\n")

    with tqdm(total=n_batches, unit="batch", desc="Scraping", ncols=80) as pbar:
        for batch_idx, batch_urls in enumerate(batches):
            batch_num = batch_idx + 1

            # Skip already-completed batches (resume support)
            if batch_already_done(batch_num):
                pbar.set_postfix_str(f"batch {batch_num:03d} — skipped (exists)")
                pbar.update(1)
                # Load existing manifest rows from already-done batch
                try:
                    existing = json.loads(
                        (RAW_DIR / f"batch_{batch_num:03d}.json").read_text(encoding="utf-8")
                    )
                    scraped_at = datetime.now(timezone.utc).isoformat()
                    rows = classify_results(batch_urls, existing, batch_num, scraped_at, was_retry=False)
                    all_manifest_rows.extend(rows)
                    for r in rows:
                        if r["status"] in ("success", "retry_success"):
                            total_succeeded += 1
                            total_episodes += r["episodes_found"]
                        elif r["status"] == "no_history":
                            total_no_history += 1
                        elif r["status"] == "failed":
                            total_failed += 1
                except Exception:
                    pass
                continue

            pbar.set_postfix_str(f"batch {batch_num:03d} ({len(batch_urls)} profiles)")

            raw_records, manifest_rows, _ = call_actor_with_retry(
                client, batch_urls, batch_num
            )

            if raw_records:
                save_batch(raw_records, batch_num)

            all_manifest_rows.extend(manifest_rows)

            for r in manifest_rows:
                if r["status"] in ("success", "retry_success"):
                    total_succeeded += 1
                    total_episodes += r["episodes_found"]
                    if r["status"] == "retry_success":
                        total_retried += 1
                elif r["status"] == "no_history":
                    total_no_history += 1
                elif r["status"] == "failed":
                    total_failed += 1

            pbar.update(1)

            # Running totals every 10 batches
            if batch_num % 10 == 0:
                tqdm.write(
                    f"  [{batch_num:03d}/{n_batches:03d}] "
                    f"Succeeded: {total_succeeded} | "
                    f"No history: {total_no_history} | "
                    f"Failed: {total_failed} | "
                    f"Retried: {total_retried}"
                )

            # Delay between batches (skip after last)
            if batch_idx < n_batches - 1:
                time.sleep(BATCH_DELAY)

    # -----------------------------------------------------------------------
    # Post-processing
    # -----------------------------------------------------------------------
    write_manifest(all_manifest_rows)
    print(green(f"\n  Manifest written : {MANIFEST_PATH}"))

    n_merged = merge_batches()
    print(green(f"  Merged output    : {MERGED_PATH} ({n_merged:,} records)"))

    elapsed_min = (time.time() - start_time) / 60

    # End summary
    sep = "=" * 70
    print()
    print(bold(sep))
    print(bold("  SCRAPE COMPLETE — SUMMARY"))
    print(bold(sep))
    print(f"  Total profiles attempted : {n_profiles:,}")
    print(f"  Succeeded (incl. retry)  : {total_succeeded:,}")
    print(f"    of which retry_success : {total_retried:,}")
    print(f"  No history returned      : {total_no_history:,}")
    print(f"  Failed (final)           : {total_failed:,}")
    print(f"  Total raw episodes found : {total_episodes:,}")
    print(f"  Scrape duration          : {elapsed_min:.1f} minutes")
    print(bold(sep))

    if total_failed > 0:
        print(yellow(f"\n  {total_failed} profile(s) failed. Review {MANIFEST_PATH}"))
        print(yellow("  Re-run the script to retry — completed batches are skipped automatically."))

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
