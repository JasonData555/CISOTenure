"""
04_qa_flags.py — Phase 4: QA Flagging
CISO Tenure Study | Hitch Partners

Applies quality-control flags to tenure_episodes.csv. Each row receives a
pipe-separated qa_flags value listing all issues that apply; rows with no
issues get qa_flags = "".

Input:  data/processed/tenure_episodes.csv
Output: data/qa/flagged_for_review.csv
        data/qa/qa_summary.txt
        data/processed/tenure_episodes_with_flags.csv

Exit codes: 0 = success, 1 = fatal input error
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT    = Path(__file__).parent.parent
INPUT_PATH      = PROJECT_ROOT / "data" / "processed" / "tenure_episodes.csv"
QA_DIR          = PROJECT_ROOT / "data" / "qa"
PROCESSED_DIR   = PROJECT_ROOT / "data" / "processed"
FLAGGED_PATH    = QA_DIR / "flagged_for_review.csv"
SUMMARY_PATH    = QA_DIR / "qa_summary.txt"
WITH_FLAGS_PATH = PROCESSED_DIR / "tenure_episodes_with_flags.csv"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CURRENT_YEAR = 2025

BOOL_COLS = [
    "is_censored", "imputed_start_month", "imputed_end_month",
    "imputed_duration", "size_tier_usable",
]

NUMERIC_COLS = [
    "start_year", "start_month", "end_year", "end_month",
    "duration_months", "duration_months_to_scrape_date",
]

# (flag_name, condition_description, recommended_action)
FLAG_DEFS = [
    ("DURATION_UNDER_3MO",   "duration < 3 months",
     "Likely data error — review"),
    ("DURATION_OVER_120MO",  "duration > 120 months",
     "Verify profile is current"),
    ("DURATION_IMPUTED",     "Any imputed date",
     "Disclose in reporting"),
    ("START_BEFORE_2000",    "start_year < 2000",
     "Exclude from era analysis"),
    ("FUTURE_END_DATE",      "end_year > current year",
     "Data error — fix or exclude"),
    ("END_BEFORE_START",     "end < start",
     "Data error — must fix or exclude"),
    ("TITLE_AMBIGUOUS",      "VP_Security title",
     "Human confirm: top security executive?"),
    ("TITLE_INTERIM",        '"interim" or "acting" in title',
     "Include with note"),
    ("SINGLE_MONTH_TENURE",  "start = end month",
     "Verify — likely data error"),
    ("OVERLAPPING_EPISODES", "Two CISO episodes overlap",
     "Profile-level error — resolve"),
    ("NO_END_DATE_OLD_ROLE", "is_censored=True and start_year < 2020",
     "Verify profile is current"),
]

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
# Load & cast input
# ---------------------------------------------------------------------------
def load_input() -> pd.DataFrame:
    if not INPUT_PATH.exists():
        print(red(f"\nERROR: Input not found: {INPUT_PATH}"))
        print(red("  Run 03_etl_normalize.py first to generate it."))
        sys.exit(1)

    df = pd.read_csv(INPUT_PATH, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    bool_map = {"True": True, "False": False, "true": True, "false": False,
                "1": True, "0": False}
    for col in BOOL_COLS:
        if col in df.columns:
            df[col] = df[col].map(bool_map)

    print(f"  Input loaded: {INPUT_PATH.name} ({len(df):,} rows)")
    return df


# ---------------------------------------------------------------------------
# Individual flag masks
# ---------------------------------------------------------------------------
def mask_duration_under_3mo(df: pd.DataFrame) -> pd.Series:
    # Use actual completed duration when available; scrape-relative duration for ongoing roles
    dur = df["duration_months"].where(df["duration_months"].notna(), df["duration_months_to_scrape_date"])
    return dur < 3


def mask_duration_over_120mo(df: pd.DataFrame) -> pd.Series:
    dur = df["duration_months"].where(df["duration_months"].notna(), df["duration_months_to_scrape_date"])
    return dur > 120


def mask_duration_imputed(df: pd.DataFrame) -> pd.Series:
    return (
        df["imputed_start_month"].fillna(False).astype(bool)
        | df["imputed_end_month"].fillna(False).astype(bool)
        | df["imputed_duration"].fillna(False).astype(bool)
    )


def mask_start_before_2000(df: pd.DataFrame) -> pd.Series:
    return df["start_year"] < 2000


def mask_future_end_date(df: pd.DataFrame) -> pd.Series:
    return df["end_year"].notna() & (df["end_year"] > CURRENT_YEAR)


def mask_end_before_start(df: pd.DataFrame) -> pd.Series:
    has_end = df["end_year"].notna() & df["end_month"].notna()
    year_before  = df["end_year"] < df["start_year"]
    same_year_mo = (df["end_year"] == df["start_year"]) & (df["end_month"] < df["start_month"])
    return has_end & (year_before | same_year_mo)


def mask_title_ambiguous(df: pd.DataFrame) -> pd.Series:
    return df["title_normalized"] == "VP_Security"


def mask_title_interim(df: pd.DataFrame) -> pd.Series:
    return df["title_raw"].str.contains(
        r"\binterim\b|\bacting\b", case=False, na=False, regex=True
    )


def mask_single_month_tenure(df: pd.DataFrame) -> pd.Series:
    has_end = df["end_year"].notna() & df["end_month"].notna()
    return has_end & (df["start_year"] == df["end_year"]) & (df["start_month"] == df["end_month"])


def mask_overlapping_episodes(df: pd.DataFrame) -> pd.Series:
    """
    Returns True for any row whose episode date range overlaps with another
    episode on the same profile_id. Uses (year*12 + month) integer encoding.
    Censored episodes are treated as ending at the current month.
    """
    today_mo = datetime.now(timezone.utc).year * 12 + datetime.now(timezone.utc).month
    overlap_mask = pd.Series(False, index=df.index)

    for _, group in df.groupby("profile_id"):
        if len(group) < 2:
            continue

        episodes = []
        for pos, row in group.iterrows():
            if pd.isna(row["start_year"]) or pd.isna(row["start_month"]):
                continue
            s = int(row["start_year"]) * 12 + int(row["start_month"])
            censored = bool(row["is_censored"]) if pd.notna(row["is_censored"]) else False
            if censored or pd.isna(row["end_year"]) or pd.isna(row["end_month"]):
                e = today_mo
            else:
                e = int(row["end_year"]) * 12 + int(row["end_month"])
            episodes.append((pos, s, e))

        for i in range(len(episodes)):
            for j in range(i + 1, len(episodes)):
                pos_i, s_i, e_i = episodes[i]
                pos_j, s_j, e_j = episodes[j]
                if s_i < e_j and s_j < e_i:
                    overlap_mask.loc[pos_i] = True
                    overlap_mask.loc[pos_j] = True

    return overlap_mask


def mask_no_end_date_old_role(df: pd.DataFrame) -> pd.Series:
    is_censored = df["is_censored"].fillna(False).astype(bool)
    return is_censored & (df["start_year"] < 2020)


# ---------------------------------------------------------------------------
# Compute all flags and build qa_flags column
# ---------------------------------------------------------------------------
def compute_flags(df: pd.DataFrame) -> tuple:
    """Returns (df_with_flags, flag_masks_dict)."""
    print()
    print(bold("COMPUTING FLAGS"))

    mask_fns = {
        "DURATION_UNDER_3MO":   mask_duration_under_3mo,
        "DURATION_OVER_120MO":  mask_duration_over_120mo,
        "DURATION_IMPUTED":     mask_duration_imputed,
        "START_BEFORE_2000":    mask_start_before_2000,
        "FUTURE_END_DATE":      mask_future_end_date,
        "END_BEFORE_START":     mask_end_before_start,
        "TITLE_AMBIGUOUS":      mask_title_ambiguous,
        "TITLE_INTERIM":        mask_title_interim,
        "SINGLE_MONTH_TENURE":  mask_single_month_tenure,
        "OVERLAPPING_EPISODES": mask_overlapping_episodes,
        "NO_END_DATE_OLD_ROLE": mask_no_end_date_old_role,
    }

    masks = {}
    for name, fn in mask_fns.items():
        masks[name] = fn(df).fillna(False).astype(bool)
        count = int(masks[name].sum())
        label = yellow(f"{count:>5}") if count > 0 else green(f"{count:>5}")
        print(f"  {name:<22} → {label} rows")

    # Build pipe-separated flag strings per row
    flag_names = list(masks.keys())
    flag_array = pd.DataFrame({n: masks[n] for n in flag_names})
    df["qa_flags"] = flag_array.apply(
        lambda row: "|".join(n for n in flag_names if row[n]), axis=1
    )

    return df, masks


# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------
def write_flagged_csv(df: pd.DataFrame):
    flagged = df[df["qa_flags"] != ""].copy()
    flagged["flag_count"] = flagged["qa_flags"].str.count(r"\|") + 1
    flagged = flagged.sort_values(
        ["flag_count", "profile_id"], ascending=[False, True]
    )
    QA_DIR.mkdir(parents=True, exist_ok=True)
    flagged.to_csv(FLAGGED_PATH, index=False)
    print(green(f"  Written: {FLAGGED_PATH} ({len(flagged):,} rows)"))


def write_full_csv(df: pd.DataFrame):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(WITH_FLAGS_PATH, index=False)
    print(green(f"  Written: {WITH_FLAGS_PATH} ({len(df):,} rows)"))


def write_summary(df: pd.DataFrame, masks: dict):
    total = len(df)
    n_flagged = int((df["qa_flags"] != "").sum())
    pct_flagged = n_flagged / total * 100 if total > 0 else 0
    review_minutes = n_flagged * 2
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    col1 = 22   # flag name
    col2 = 35   # condition
    col3 = 7    # count
    col4 = 7    # pct
    sep = "─" * (col1 + col2 + col3 + col4 + 10)

    lines = [
        "QA FLAG SUMMARY — CISO Tenure Study",
        f"Generated: {generated}",
        "",
        sep,
        f"{'Flag':<{col1}}  {'Condition':<{col2}}  {'Count':>{col3}}  {'Pct':>{col4}}  Action",
        sep,
    ]

    for flag_name, condition, action in FLAG_DEFS:
        count = int(masks[flag_name].sum())
        pct   = count / total * 100 if total > 0 else 0
        lines.append(
            f"{flag_name:<{col1}}  {condition:<{col2}}  {count:>{col3},}  {pct:>{col4}.1f}%  {action}"
        )

    lines += [
        sep,
        "",
        f"Total flagged episodes: {n_flagged:,} of {total:,} ({pct_flagged:.1f}%)",
        f"Estimated manual review time at 2 min/row: {review_minutes:,} minutes",
        "",
        "Next step: Open data/qa/flagged_for_review.csv, resolve each row,",
        "then save the cleaned dataset as data/final/tenure_episodes_clean.csv",
    ]

    QA_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(green(f"  Written: {SUMMARY_PATH}"))


# ---------------------------------------------------------------------------
# Terminal summary
# ---------------------------------------------------------------------------
def print_terminal_summary(df: pd.DataFrame, masks: dict):
    total     = len(df)
    n_flagged = int((df["qa_flags"] != "").sum())
    pct       = n_flagged / total * 100 if total > 0 else 0
    sep       = "=" * 72

    print()
    print(bold(sep))
    print(bold("  QA FLAGS — SUMMARY"))
    print(bold(sep))
    print()
    print(bold(f"  {'Flag':<22}  {'Count':>7}  {'Pct':>6}"))
    print(f"  {'-'*22}  {'-'*7}  {'-'*6}")

    for flag_name, _, _ in FLAG_DEFS:
        count = int(masks[flag_name].sum())
        pct_f = count / total * 100 if total > 0 else 0
        count_str = yellow(f"{count:>7,}") if count > 0 else green(f"{count:>7,}")
        print(f"  {flag_name:<22}  {count_str}  {pct_f:>5.1f}%")

    print()
    flagged_str = yellow(f"{n_flagged:,}") if n_flagged > 0 else green(f"{n_flagged:,}")
    print(f"  Total flagged : {flagged_str} of {total:,} ({pct:.1f}%)")
    print(f"  Review budget : {n_flagged * 2:,} minutes at 2 min/row")
    print()
    print(bold(sep))
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    sep = "=" * 70
    print()
    print(bold(sep))
    print(bold("  CISO TENURE STUDY — PHASE 4: QA FLAGGING"))
    print(bold(sep))
    print()

    print(bold("LOADING INPUT"))
    df = load_input()

    df, masks = compute_flags(df)

    print()
    print(bold("WRITING OUTPUT"))
    write_flagged_csv(df)
    write_full_csv(df)
    write_summary(df, masks)

    print_terminal_summary(df, masks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
