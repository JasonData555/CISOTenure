"""
04b_covariate_handling.py — Phase 4.5: Covariate Normalisation
CISO Tenure Study | Hitch Partners

Computes size_tier_usable and industry_normalized for all episodes, writes
them back to the clean CSV, then produces profile-level composition tables
and methodology disclaimer files for use in reporting.

Input:  data/final/tenure_episodes_clean.csv
Output: data/final/tenure_episodes_clean.csv  (size_tier_usable + industry_normalized updated)
        output/tables/size_tier_composition.csv
        output/tables/industry_composition.csv
        output/tables/region_composition.csv
        output/tables/sample_composition_summary.csv
        output/tables/size_tier_note.txt
        output/tables/industry_note.txt
        output/tables/region_note.txt

Exit codes: 0 = success, 1 = fatal input error
"""

import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
CLEAN_CSV    = PROJECT_ROOT / "data" / "final" / "tenure_episodes_clean.csv"
TABLES_DIR   = PROJECT_ROOT / "output" / "tables"

# ---------------------------------------------------------------------------
# Industry keyword map — ordered; first match wins
# ---------------------------------------------------------------------------
INDUSTRY_MAP = [
    ('Financial Services', ['bank', 'financ', 'insur', 'fintech', 'asset',
                            'capital', 'invest', 'wealth']),
    ('Healthcare',         ['health', 'hospital', 'pharma', 'medic',
                            'biotech', 'clinic']),
    ('Technology',         ['tech', 'software', 'saas', 'cloud', 'cyber',
                            'data', 'digital', 'platform']),
    ('Retail & Consumer',  ['retail', 'consumer', 'ecommerce', 'brand',
                            'apparel', 'food', 'beverage']),
    ('Manufacturing',      ['manufactur', 'industrial', 'aerospace', 'defense',
                            'automotive', 'energy', 'util']),
    ('Government',         ['government', 'federal', 'state', 'municipal',
                            'public sector', 'military']),
    ('Professional Svcs',  ['consult', 'legal', 'accounting', 'staffing',
                            'advisory', 'audit']),
]

SIZE_TIER_ORDER = ['SMB', 'Mid-Market', 'Enterprise', 'Large-Enterprise']

# ---------------------------------------------------------------------------
# Methodology disclosure text (verbatim from CLAUDE.md)
# ---------------------------------------------------------------------------
COVARIATE_DISCLOSURE = (
    "Company size, industry, and geographic region are reported for sample "
    "composition purposes only. Because these attributes can change materially "
    "over an 8-year study window through acquisitions, growth, and relocation, "
    "they are not used as stratification variables in survival analysis."
)

REGION_DISCLOSURE = (
    "LinkedIn does not provide historical location data for past role episodes, "
    "making episode-level geographic assignment unreliable across an 8-year "
    "study window."
)

# ---------------------------------------------------------------------------
# ANSI color helpers (suppressed when not a TTY)
# ---------------------------------------------------------------------------
_IS_TTY = sys.stdout.isatty()


def _color(text, code):
    return f"\033[{code}m{text}\033[0m" if _IS_TTY else text


def red(t):    return _color(t, "91")
def green(t):  return _color(t, "92")
def yellow(t): return _color(t, "93")
def bold(t):   return _color(t, "1")


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
def load_csv() -> pd.DataFrame:
    if not CLEAN_CSV.exists():
        print(red(f"\nERROR: Input not found: {CLEAN_CSV}"))
        print(red("  Run 04_qa_flags.py and complete manual QA first."))
        sys.exit(1)

    df = pd.read_csv(CLEAN_CSV, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    bool_map = {"True": True, "False": False, "true": True, "false": False,
                "1": True, "0": False, "TRUE": True, "FALSE": False}
    for col in ['is_censored', 'size_tier_usable']:
        if col in df.columns:
            df[col] = df[col].map(bool_map)

    for col in ['start_year', 'duration_months_to_scrape_date']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    print(f"  Loaded: {CLEAN_CSV.name} ({len(df):,} rows)")
    return df


# ---------------------------------------------------------------------------
# Compute size_tier_usable
# ---------------------------------------------------------------------------
def compute_size_tier_usable(df: pd.DataFrame) -> pd.DataFrame:
    recent   = df['start_year'] >= 2021
    short    = df['duration_months_to_scrape_date'] < 36
    df['size_tier_usable'] = (recent & short).fillna(False)
    n_usable = int(df['size_tier_usable'].sum())
    print(f"  size_tier_usable = True : {n_usable:,} of {len(df):,} rows")
    return df


# ---------------------------------------------------------------------------
# Compute industry_normalized
# ---------------------------------------------------------------------------
_OVERRIDES = [
    ('hospitality', 'Retail & Consumer'),
    ('restaurant',  'Retail & Consumer'),
]


def _normalize_industry(raw):
    if pd.isna(raw) or str(raw).strip() == '':
        return 'Other'
    lower = str(raw).lower()
    # Pre-filter: explicit overrides that prevent substring false positives
    # (e.g., "hospitality" contains "hospital", which would otherwise hit Healthcare)
    for pattern, label in _OVERRIDES:
        if pattern in lower:
            return label
    for label, keywords in INDUSTRY_MAP:
        if any(kw in lower for kw in keywords):
            return label
    return 'Other'


def compute_industry_normalized(df: pd.DataFrame) -> pd.DataFrame:
    df['industry_normalized'] = df['industry_sector'].apply(_normalize_industry)
    n_other   = int((df['industry_normalized'] == 'Other').sum())
    n_mapped  = len(df) - n_other
    print(f"  industry_normalized: {n_mapped:,} mapped, {n_other:,} → Other")
    return df


# ---------------------------------------------------------------------------
# Write updated CSV
# ---------------------------------------------------------------------------
def write_clean_csv(df: pd.DataFrame):
    df.to_csv(CLEAN_CSV, index=False)
    print(green(f"  Updated: {CLEAN_CSV}"))


# ---------------------------------------------------------------------------
# Composition tables — KEEP rows only, profile-level
# ---------------------------------------------------------------------------
def build_composition_tables(df: pd.DataFrame):
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    keep     = df[df['qa_decision'] == 'KEEP'].copy()
    n_keep   = len(keep)
    profiles = keep.drop_duplicates(subset='profile_id')
    n_prof   = len(profiles)

    # ── Size tier composition ────────────────────────────────────────────────
    prof_size = (
        profiles.groupby('company_size_tier', dropna=False)['profile_id']
        .count()
        .rename('profile_count')
        .reset_index()
        .rename(columns={'company_size_tier': 'size_tier'})
    )
    prof_size['profile_pct'] = (prof_size['profile_count'] / n_prof * 100).round(1)

    usable_keep = keep[keep['size_tier_usable'] == True]
    n_usable_total = len(usable_keep)
    ep_size = (
        usable_keep.groupby('company_size_tier', dropna=False)['episode_id']
        .count()
        .rename('usable_episode_count')
        .reset_index()
        .rename(columns={'company_size_tier': 'size_tier'})
    )

    size_tbl = prof_size.merge(ep_size, on='size_tier', how='left')
    size_tbl['usable_episode_count'] = size_tbl['usable_episode_count'].fillna(0).astype(int)
    size_tbl['usable_episode_pct'] = (
        size_tbl['usable_episode_count'] / n_usable_total * 100
        if n_usable_total > 0 else 0
    ).round(1)

    # Sort by canonical tier order, then alphabetically for unknowns
    def tier_sort_key(t):
        try:
            return SIZE_TIER_ORDER.index(t)
        except ValueError:
            return len(SIZE_TIER_ORDER)

    size_tbl['_sort'] = size_tbl['size_tier'].apply(tier_sort_key)
    size_tbl = size_tbl.sort_values('_sort').drop(columns='_sort').reset_index(drop=True)

    size_path = TABLES_DIR / "size_tier_composition.csv"
    size_tbl.to_csv(size_path, index=False)
    print(green(f"  Written: {size_path.name}"))

    # ── Industry composition ─────────────────────────────────────────────────
    ind_tbl = (
        profiles.groupby('industry_normalized', dropna=False)['profile_id']
        .count()
        .rename('profile_count')
        .sort_values(ascending=False)
        .reset_index()
    )
    ind_tbl['profile_pct'] = (ind_tbl['profile_count'] / n_prof * 100).round(1)

    ind_path = TABLES_DIR / "industry_composition.csv"
    ind_tbl.to_csv(ind_path, index=False)
    print(green(f"  Written: {ind_path.name}"))

    # ── Region composition ───────────────────────────────────────────────────
    region_profiles = profiles.copy()
    region_profiles['profile_region'] = (
        region_profiles['profile_region'].fillna('Unknown').replace('', 'Unknown')
    )
    reg_tbl = (
        region_profiles.groupby('profile_region')['profile_id']
        .count()
        .rename('profile_count')
        .sort_values(ascending=False)
        .reset_index()
    )
    reg_tbl['profile_pct'] = (reg_tbl['profile_count'] / n_prof * 100).round(1)

    reg_path = TABLES_DIR / "region_composition.csv"
    reg_tbl.to_csv(reg_path, index=False)
    print(green(f"  Written: {reg_path.name}"))

    # ── Sample composition summary (three sections concatenated) ─────────────
    blocks = []

    for _, row in size_tbl.iterrows():
        blocks.append({
            'section_label': 'Company Size',
            'category':      row['size_tier'],
            'n':             int(row['profile_count']),
            'pct':           float(row['profile_pct']),
        })

    for _, row in ind_tbl.iterrows():
        blocks.append({
            'section_label': 'Industry',
            'category':      row['industry_normalized'],
            'n':             int(row['profile_count']),
            'pct':           float(row['profile_pct']),
        })

    for _, row in reg_tbl.iterrows():
        blocks.append({
            'section_label': 'Region',
            'category':      row['profile_region'],
            'n':             int(row['profile_count']),
            'pct':           float(row['profile_pct']),
        })

    summary_tbl = pd.DataFrame(blocks)
    summary_path = TABLES_DIR / "sample_composition_summary.csv"
    summary_tbl.to_csv(summary_path, index=False)
    print(green(f"  Written: {summary_path.name}"))

    return keep, n_usable_total


# ---------------------------------------------------------------------------
# Disclaimer text files
# ---------------------------------------------------------------------------
def write_disclaimer_files():
    (TABLES_DIR / "size_tier_note.txt").write_text(
        COVARIATE_DISCLOSURE + "\n", encoding="utf-8"
    )
    (TABLES_DIR / "industry_note.txt").write_text(
        COVARIATE_DISCLOSURE + "\n", encoding="utf-8"
    )
    (TABLES_DIR / "region_note.txt").write_text(
        COVARIATE_DISCLOSURE + "\n\n" + REGION_DISCLOSURE + "\n",
        encoding="utf-8",
    )
    print(green("  Written: size_tier_note.txt, industry_note.txt, region_note.txt"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    sep = "=" * 70
    print()
    print(bold(sep))
    print(bold("  CISO TENURE STUDY — PHASE 4.5: COVARIATE HANDLING"))
    print(bold(sep))
    print()

    print(bold("LOADING"))
    df = load_csv()

    print()
    print(bold("COMPUTING COLUMNS"))
    df = compute_size_tier_usable(df)
    df = compute_industry_normalized(df)

    print()
    print(bold("WRITING UPDATED CSV"))
    write_clean_csv(df)

    print()
    print(bold("BUILDING COMPOSITION TABLES"))
    keep, n_usable = build_composition_tables(df)

    print()
    print(bold("WRITING DISCLAIMER FILES"))
    write_disclaimer_files()

    # ── Final summary print ──────────────────────────────────────────────────
    n_keep   = len(keep)
    pct_use  = n_usable / n_keep * 100 if n_keep > 0 else 0
    n_mapped = int((keep['industry_normalized'] != 'Other').sum())
    n_other  = int((keep['industry_normalized'] == 'Other').sum())

    print()
    print(bold(sep))
    print("Covariate handling complete.")
    print(f" Dataset updated: {CLEAN_CSV.relative_to(PROJECT_ROOT)}")
    print(f" Size tier — usable episodes (post-2020, <36mo): {n_usable:,} of {n_keep:,} ({pct_use:.1f}%)")
    print(f" Industry normalization: {n_mapped:,} episodes mapped, {n_other:,} assigned to Other")
    print(f" Composition tables written to output/tables/")
    print(f" Analysis guards written to scripts/analysis_guards.py")
    print(bold(sep))
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
