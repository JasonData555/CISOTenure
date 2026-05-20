"""
01_validate_input.py — Phase 1: Input CSV Validation
CISO Tenure Study | Hitch Partners

Validates data/input/profiles.csv before any Apify scraping begins.
Accepts both the canonical column schema (per CLAUDE.md) and the actual
column names found in the Hitch profiles export, mapping them transparently.

Exit codes: 0 = PASS or PASS WITH WARNINGS, 1 = FAIL
"""

import sys
import re
import textwrap
from pathlib import Path
from datetime import datetime
from collections import Counter

import pandas as pd


# ---------------------------------------------------------------------------
# Paths (resolved relative to this script, works from any cwd)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
INPUT_PATH   = PROJECT_ROOT / "data" / "input" / "profiles.csv"
OUTPUT_PATH  = PROJECT_ROOT / "data" / "input" / "validation_report.txt"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CANONICAL_COLUMNS = {
    "profile_url": {
        "required": True,
        "aliases": {"linkedin", "linkedin_url", "linkedin url", "url", "profile url"},
    },
    "company_size_tier": {
        "required": True,
        "aliases": {"current company size", "company size", "size", "company_size", "tier"},
    },
    "industry_sector": {
        "required": True,
        "aliases": {"industry", "sector", "industry sector", "vertical"},
    },
    "profile_region": {
        "required": False,
        "aliases": {"region", "location", "geography", "geo"},
    },
}

COMPANY_SIZE_VALID = {
    "1-10", "11-50", "51-100", "101-250", "251-500",
    "501-1000", "1001-5000", "5001-10000", "10000+",
}

REGION_VALID = {"Northeast", "Southeast", "Midwest", "Southwest", "West", "International"}

URL_PATTERN = re.compile(r"linkedin\.com/in/", re.IGNORECASE)

# ANSI color codes — suppressed when not a TTY
_IS_TTY = sys.stdout.isatty()

def _color(text: str, code: str) -> str:
    if not _IS_TTY:
        return text
    return f"\033[{code}m{text}\033[0m"

def red(t):    return _color(t, "91")
def yellow(t): return _color(t, "93")
def green(t):  return _color(t, "92")
def bold(t):   return _color(t, "1")


# ---------------------------------------------------------------------------
# Column detection
# ---------------------------------------------------------------------------
def detect_and_map_columns(df_columns: list) -> tuple[dict, list]:
    """
    Returns:
        column_map: {canonical_name: actual_col_name_in_df}
        notes: list of human-readable mapping messages
    """
    normalized = {c.strip().lower(): c.strip() for c in df_columns}
    column_map = {}
    notes = []
    known_mapped = set()

    for canonical, meta in CANONICAL_COLUMNS.items():
        # Exact match first (case-sensitive)
        if canonical in df_columns:
            column_map[canonical] = canonical
            notes.append(f"  '{canonical}' → {canonical} (exact match)")
            known_mapped.add(canonical)
            continue

        # Alias match (case-insensitive, stripped)
        found = None
        for norm_col, actual_col in normalized.items():
            if norm_col == canonical.lower() or norm_col in meta["aliases"]:
                found = actual_col
                break

        if found:
            column_map[canonical] = found
            if found != canonical:
                notes.append(f"  '{found}' → {canonical} (alias match)")
            known_mapped.add(found)
        elif meta["required"]:
            notes.append(f"  *** MISSING required column '{canonical}' — checked aliases: "
                         f"{sorted(meta['aliases'])}")
        else:
            notes.append(f"  '{canonical}' → NOT PRESENT (optional — skipped)")

    # Extra columns not in spec
    extras = [c for c in df_columns if c.strip() not in known_mapped
              and c.strip().lower() not in {a for m in CANONICAL_COLUMNS.values()
                                             for a in m["aliases"]}
              and c.strip() not in CANONICAL_COLUMNS]
    # More robust: anything not mapped
    mapped_actual = set(column_map.values())
    extras = [c.strip() for c in df_columns if c.strip() not in mapped_actual]
    if extras:
        notes.append(f"  Extra columns (not validated, carried through): {', '.join(extras)}")

    return column_map, notes


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------
def validate_profile_url(series: pd.Series) -> tuple[list, list]:
    criticals, warnings = [], []

    total = len(series)
    empty_rows = series[series.isna() | (series.str.strip() == "")].index.tolist()
    if empty_rows:
        sample = _row_list(empty_rows)
        criticals.append(
            f"[URL-001] {len(empty_rows)} rows have empty/missing profile_url — rows: {sample}"
        )

    non_empty = series.dropna()
    non_empty = non_empty[non_empty.str.strip() != ""].str.strip()

    invalid_pattern_rows = []
    bare_url_rows = []
    http_rows = []

    for idx, val in non_empty.items():
        if not URL_PATTERN.search(val):
            invalid_pattern_rows.append((idx, val))
        elif not val.startswith("http"):
            bare_url_rows.append(idx)
        elif val.startswith("http://"):
            http_rows.append(idx)

    for idx, val in invalid_pattern_rows:
        criticals.append(
            f"[URL-002] Row {idx + 2}: URL does not match linkedin.com/in/ pattern:\n"
            f"          '{val}'"
        )

    if bare_url_rows:
        sample = _row_list(bare_url_rows)
        warnings.append(
            f"[URL-W001] {len(bare_url_rows)} rows have bare URLs without https:// prefix "
            f"(e.g. 'linkedin.com/in/...'). Scraper may normalize — but recommend adding "
            f"https:// prefix. Rows: {sample}"
        )

    if http_rows:
        sample = _row_list(http_rows)
        warnings.append(
            f"[URL-W002] {len(http_rows)} rows use http:// (not https://) — "
            f"recommend updating. Rows: {sample}"
        )

    # Duplicate detection — normalize trailing slash before comparing
    def normalize_url(u):
        return u.lower().rstrip("/") if isinstance(u, str) else u

    normalized_series = non_empty.map(normalize_url)
    dupes = normalized_series[normalized_series.duplicated(keep=False)]
    if not dupes.empty:
        dupe_groups = {}
        for idx, val in dupes.items():
            dupe_groups.setdefault(val, []).append(idx + 2)
        for url, rows in dupe_groups.items():
            warnings.append(
                f"[URL-W003] Duplicate URL: '{url}'\n"
                f"           Appears at rows: {', '.join(map(str, rows))}"
            )

    url_summary = {
        "total": total,
        "empty": len(empty_rows),
        "invalid_pattern": len(invalid_pattern_rows),
        "bare_url": len(bare_url_rows),
        "http_only": len(http_rows),
        "duplicates": len(dupe_groups) if not dupes.empty else 0,
    }

    return criticals, warnings, url_summary


def validate_company_size(series: pd.Series) -> tuple[list, list, str, dict]:
    criticals, warnings = [], []
    valid_counts = Counter()
    multival_rows = []
    unrecognized = []

    for idx, val in series.items():
        if pd.isna(val) or str(val).strip() == "":
            criticals.append(f"[SIZE-E] Row {idx + 2}: empty company_size_tier value")
            continue

        val_stripped = str(val).strip()

        # Multi-value check (comma in value)
        if "," in val_stripped:
            multival_rows.append((idx + 2, val_stripped))
            continue

        if val_stripped in COMPANY_SIZE_VALID:
            valid_counts[val_stripped] += 1
        else:
            unrecognized.append((idx + 2, val_stripped))

    for row_num, val in multival_rows:
        criticals.append(
            f"[SIZE-003] Row {row_num}: ambiguous multi-value size '{val}' — "
            f"cannot use a cell with multiple values. Correct manually."
        )

    for row_num, val in unrecognized:
        criticals.append(
            f"[SIZE-004] Row {row_num}: unrecognized value '{val}' — "
            f"not a valid employee-range. Expected one of: {sorted(COMPANY_SIZE_VALID)}"
        )

    size_summary = {
        "canonical": sum(valid_counts.values()),
        "range_values": 0,
        "unknown": 0,
        "multival": len(multival_rows),
        "unrecognized": len(unrecognized),
        "distribution": dict(valid_counts.most_common()),
    }

    return criticals, warnings, "", size_summary


def validate_industry(series: pd.Series) -> tuple[list, list, dict]:
    criticals, warnings = [], []

    missing = series[series.isna() | (series.str.strip() == "")].shape[0]
    multival = series.dropna()
    multival = multival[multival.str.strip() != ""]
    multival_count = multival[multival.str.contains(",", na=False)].shape[0]

    if multival_count:
        warnings.append(
            f"[IND-W001] {multival_count} rows have comma-separated values in industry_sector "
            f"(e.g. 'Enterprise SaaS,AdTech / MarTech'). Only the first value will be usable "
            f"as a single industry tag. Consider cleaning before Phase 4.5."
        )

    ind_summary = {
        "total": len(series),
        "missing": missing,
        "multival": multival_count,
        "unique": series.dropna().nunique(),
    }

    return criticals, warnings, ind_summary


def validate_region(series: pd.Series) -> tuple[list, list, dict]:
    criticals, warnings = [], []

    non_null = series.dropna()
    non_null = non_null[non_null.str.strip() != ""].str.strip()

    invalid = non_null[~non_null.isin(REGION_VALID)]
    if not invalid.empty:
        vals = invalid.value_counts().to_dict()
        warnings.append(
            f"[REG-W001] {len(invalid)} rows have invalid profile_region values: "
            f"{dict(list(vals.items())[:10])}"
        )

    distribution = non_null[non_null.isin(REGION_VALID)].value_counts().to_dict()
    region_summary = {
        "total": len(series),
        "missing": series.isna().sum() + (series.str.strip() == "").sum(),
        "invalid": len(invalid),
        "distribution": distribution,
    }

    return criticals, warnings, region_summary


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------
def build_report(
    timestamp: str,
    input_path: str,
    n_rows: int,
    col_notes: list,
    url_summary: dict,
    size_summary: dict,
    fix_table: str,
    ind_summary: dict,
    region_summary: dict | None,
    all_criticals: list,
    all_warnings: list,
    status: str,
) -> str:
    SEP  = "=" * 80
    DASH = "-" * 80

    lines = [
        SEP,
        "CISO TENURE STUDY — INPUT VALIDATION REPORT",
        SEP,
        f"Generated : {timestamp}",
        f"Input file: {input_path}",
        f"Total rows: {n_rows:,}",
        "",
        DASH,
        "COLUMN DETECTION",
        DASH,
    ]
    lines += col_notes
    lines += [
        "",
        DASH,
        "COLUMN SUMMARY",
        DASH,
        "",
        "[profile_url]",
        f"  Total values              : {url_summary['total']:,}",
        f"  Empty / missing           : {url_summary['empty']}  {'← CRITICAL' if url_summary['empty'] else ''}",
        f"  Invalid pattern           : {url_summary['invalid_pattern']}  {'← CRITICAL' if url_summary['invalid_pattern'] else ''}",
        f"  Bare URL (no https://)    : {url_summary['bare_url']}  {'← WARNING' if url_summary['bare_url'] else ''}",
        f"  http:// (not https://)    : {url_summary['http_only']}  {'← WARNING' if url_summary['http_only'] else ''}",
        f"  Duplicate URLs            : {url_summary['duplicates']} pair(s) found  {'← WARNING' if url_summary['duplicates'] else ''}",
        "",
        "[company_size_tier]",
        f"  Valid employee-range values: {size_summary['canonical']:,}",
        f"  Multi-value (ambiguous)    : {size_summary['multival']}  {'← CRITICAL' if size_summary['multival'] else ''}",
        f"  Unrecognized values        : {size_summary['unrecognized']}  {'← CRITICAL' if size_summary['unrecognized'] else ''}",
    ]

    if size_summary["distribution"]:
        lines.append("")
        lines.append("  Distribution:")
        total_dist = sum(size_summary["distribution"].values())
        range_order = [
            "10000+", "5001-10000", "1001-5000", "501-1000",
            "251-500", "101-250", "51-100", "11-50", "1-10",
        ]
        for r in range_order:
            c = size_summary["distribution"].get(r, 0)
            if c:
                pct = c / total_dist * 100
                lines.append(f"    {r:<12}: {c:>5} ({pct:.1f}%)")
        other_keys = [k for k in size_summary["distribution"] if k not in range_order]
        for k in other_keys:
            c = size_summary["distribution"][k]
            pct = c / total_dist * 100
            lines.append(f"    {k:<12}: {c:>5} ({pct:.1f}%)")

    if fix_table:
        lines.append("")
        lines.append(fix_table)

    lines += [
        "[industry_sector]",
        f"  Total values              : {ind_summary['total']:,}",
        f"  Missing / empty           : {ind_summary['missing']}",
        f"  Unique values             : {ind_summary['unique']}",
        f"  Multi-value cells         : {ind_summary['multival']}  {'← WARNING' if ind_summary['multival'] else ''}",
        "",
    ]

    if region_summary is not None:
        lines += [
            "[profile_region]",
            f"  Total values              : {region_summary['total']:,}",
            f"  Missing / empty           : {region_summary['missing']}",
            f"  Invalid values            : {region_summary['invalid']}  {'← WARNING' if region_summary['invalid'] else ''}",
        ]
        if region_summary["distribution"]:
            lines.append("  Distribution:")
            for r, c in sorted(region_summary["distribution"].items()):
                lines.append(f"    {r:<15}: {c}")
        lines.append("")
    else:
        lines += [
            "[profile_region]",
            "  Status: Column not present in file (optional — no action required)",
            "",
        ]

    lines += [
        DASH,
        f"CRITICAL ERRORS ({len(all_criticals)} total)",
        DASH,
    ]
    if all_criticals:
        lines += [f"  {e}" for e in all_criticals]
    else:
        lines.append("  None.")
    lines.append("")

    lines += [
        DASH,
        f"WARNINGS ({len(all_warnings)} total)",
        DASH,
    ]
    if all_warnings:
        lines += [f"  {w}" for w in all_warnings]
    else:
        lines.append("  None.")
    lines.append("")

    lines += [
        DASH,
        f"FINAL STATUS: {status}",
        DASH,
    ]
    if status == "FAIL":
        lines += [
            "  CRITICAL errors prevent scraping from proceeding.",
            "  Fix all CRITICAL errors in profiles.csv and re-run this script.",
            "  Resolve warnings before Phase 5 (survival analysis).",
        ]
    elif status == "PASS WITH WARNINGS":
        lines += [
            "  No blocking errors found. Scraping may proceed.",
            "  Resolve warnings before Phase 5 (survival analysis).",
        ]
    else:
        lines.append("  All checks passed. Proceed to Phase 2 (scraping).")

    lines.append(SEP)
    return "\n".join(lines)


def write_report(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------
def print_console_summary(
    n_rows: int,
    all_criticals: list,
    all_warnings: list,
    status: str,
    fix_table: str,
    report_path: Path,
) -> None:
    print()
    print(bold("CISO TENURE STUDY — INPUT VALIDATION"))
    print(f"  Rows loaded : {n_rows:,}")
    print(f"  Report      : {report_path}")
    print()

    if all_criticals:
        print(red(f"  ✗ CRITICAL ERRORS ({len(all_criticals)})"))
        for err in all_criticals[:20]:
            for line in err.split("\n"):
                print(red(f"    {line}"))
        if len(all_criticals) > 20:
            print(red(f"    ... and {len(all_criticals) - 20} more (see full list in report file)"))
        print()

    if fix_table:
        print(yellow("  HOW TO FIX company_size_tier — replace employee ranges with canonical tier names:"))
        short_fix = [
            "    10000+      → Large-Enterprise",
            "    5001-10000  → Enterprise",
            "    1001-5000   → Enterprise",
            "    501-1000    → Mid-Market",
            "    251-500     → Mid-Market",
            "    101-250     → SMB",
            "    51-100      → SMB",
            "    11-50       → SMB",
            "    1-10        → SMB",
            "    unknown     → (research required)",
            "    Multi-value cells → split to single value manually",
            f"  Then re-run: python3 scripts/01_validate_input.py",
        ]
        for line in short_fix:
            print(yellow(line))
        print()

    if all_warnings:
        print(yellow(f"  ⚠ WARNINGS ({len(all_warnings)})"))
        for w in all_warnings:
            for line in w.split("\n"):
                print(yellow(f"    {line}"))
        print()

    status_line = f"  FINAL STATUS: {status}"
    if status == "FAIL":
        print(red(status_line))
        print(red("  Fix CRITICAL errors and re-run before proceeding to Phase 2."))
    elif status == "PASS WITH WARNINGS":
        print(yellow(status_line))
        print(yellow("  Scraping may proceed. Resolve warnings before Phase 5."))
    else:
        print(green(status_line))
        print(green("  All checks passed. Proceed to Phase 2 (scraping)."))
    print()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _row_list(rows: list, limit: int = 20) -> str:
    displayed = [str(r + 2) for r in rows[:limit]]
    result = ", ".join(displayed)
    if len(rows) > limit:
        result += f" ... and {len(rows) - limit} more (see report)"
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not INPUT_PATH.exists():
        msg = (
            f"ERROR: Input file not found: {INPUT_PATH}\n"
            f"Copy profiles.csv to data/input/profiles.csv and re-run."
        )
        print(red(msg))
        write_report(
            f"{'=' * 80}\nCISO TENURE STUDY — INPUT VALIDATION REPORT\n{'=' * 80}\n"
            f"Generated : {timestamp}\n"
            f"ERROR: Input file not found: {INPUT_PATH}\n",
            OUTPUT_PATH,
        )
        return 1

    # Load CSV
    try:
        df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig", dtype=str)
    except UnicodeDecodeError:
        df = pd.read_csv(INPUT_PATH, encoding="latin-1", dtype=str)
        print(yellow("  Warning: File decoded using latin-1 fallback — verify characters in data."))

    df.columns = [c.strip() for c in df.columns]
    n_rows = len(df)

    # Column detection and mapping
    column_map, col_notes = detect_and_map_columns(list(df.columns))

    # Rename to canonical names for uniform processing
    working_df = df.rename(columns={v: k for k, v in column_map.items()})

    all_criticals: list = []
    all_warnings:  list = []

    # Check for missing required columns
    for canonical, meta in CANONICAL_COLUMNS.items():
        if meta["required"] and canonical not in column_map:
            all_criticals.append(
                f"[COL-001] Required column '{canonical}' not found in file. "
                f"Aliases checked: {sorted(meta['aliases'])}"
            )

    # Validate profile_url
    url_summary = {"total": n_rows, "empty": 0, "invalid_pattern": 0,
                   "bare_url": 0, "http_only": 0, "duplicates": 0}
    if "profile_url" in working_df.columns:
        c, w, url_summary = validate_profile_url(working_df["profile_url"])
        all_criticals += c
        all_warnings  += w

    # Validate company_size_tier
    size_summary = {"canonical": 0, "range_values": 0, "unknown": 0,
                    "multival": 0, "unrecognized": 0, "distribution": {}}
    fix_table = ""
    if "company_size_tier" in working_df.columns:
        c, w, fix_table, size_summary = validate_company_size(working_df["company_size_tier"])
        all_criticals += c
        all_warnings  += w

    # Validate industry_sector
    ind_summary = {"total": n_rows, "missing": 0, "multival": 0, "unique": 0}
    if "industry_sector" in working_df.columns:
        c, w, ind_summary = validate_industry(working_df["industry_sector"])
        all_criticals += c
        all_warnings  += w

    # Validate profile_region (optional)
    region_summary = None
    if "profile_region" in working_df.columns:
        c, w, region_summary = validate_region(working_df["profile_region"])
        all_criticals += c
        all_warnings  += w

    # Determine status
    if all_criticals:
        status = "FAIL"
        exit_code = 1
    elif all_warnings:
        status = "PASS WITH WARNINGS"
        exit_code = 0
    else:
        status = "PASS"
        exit_code = 0

    # Build and write report
    report_text = build_report(
        timestamp=timestamp,
        input_path=str(INPUT_PATH),
        n_rows=n_rows,
        col_notes=col_notes,
        url_summary=url_summary,
        size_summary=size_summary,
        fix_table=fix_table,
        ind_summary=ind_summary,
        region_summary=region_summary,
        all_criticals=all_criticals,
        all_warnings=all_warnings,
        status=status,
    )
    write_report(report_text, OUTPUT_PATH)

    # Console output
    print_console_summary(n_rows, all_criticals, all_warnings, status, fix_table, OUTPUT_PATH)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
