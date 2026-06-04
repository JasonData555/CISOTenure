#!/usr/bin/env python3
"""
05b_subgroup_analysis.py — Phase 5b: Subgroup Survival Analysis
CISO Tenure Study | Hitch Partners

Produces KM median tenure by company size tier and industry group.
Uses Kaplan-Meier estimation (consistent with the rest of the report),
which properly accounts for the ~25% censoring rate.

NOTE: Prior versions of size_medians.csv and industry_medians.csv used
simple median of completed episodes only — this understates median tenure
by 18–36% because censored (ongoing) roles tend to be longer. KM
estimation is the correct method.

Size tier consolidation (5 groups from 9 raw tiers):
  Small      : 1-10, 11-50, 51-100, 101-250
  Mid-Small  : 251-500, 501-1000
  Mid-Market : 1001-5000
  Large      : 5001-10000
  Enterprise : 10000+

Industry consolidation (7 groups from industry_normalized):
  Healthcare/HealthTech, Consumer/Retail, Finance/Insurance,
  Industrial/Energy, Consulting, Enterprise Tech/Cloud, Other
  (Groups with n_completed < 20 are excluded)

Input:  data/final/tenure_episodes_clean.csv
Output: output/tables/size_medians.csv
        output/tables/industry_medians.csv

Exit codes: 0 = success, 1 = fatal input error
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter
from lifelines.statistics import multivariate_logrank_test

PROJECT_ROOT = Path(__file__).parent.parent
CLEAN_CSV    = PROJECT_ROOT / "data" / "final" / "tenure_episodes_clean.csv"
TABLES_DIR   = PROJECT_ROOT / "output" / "tables"

MIN_COMPLETED = 20   # minimum completed episodes to report a subgroup

# ── Size tier consolidation ──────────────────────────────────────────────────
SIZE_MAP = {
    "1-10":        "Small",
    "11-50":       "Small",
    "51-100":      "Small",
    "101-250":     "Small",
    "251-500":     "Mid-Small",
    "501-1000":    "Mid-Small",
    "1001-5000":   "Mid-Market",
    "5001-10000":  "Large",
    "10000+":      "Enterprise",
}
SIZE_ORDER = ["Small", "Mid-Small", "Mid-Market", "Large", "Enterprise"]

# ── Industry label remapping (industry_normalized → display label) ───────────
INDUSTRY_MAP = {
    "Technology":         "Enterprise Tech/Cloud",
    "Financial Services": "Finance/Insurance",
    "Healthcare":         "Healthcare/HealthTech",
    "Retail & Consumer":  "Consumer/Retail",
    "Manufacturing":      "Industrial/Energy",
    "Professional Svcs":  "Consulting",
    "Government":         "Government",
    "Other":              "Other",
}

# ── ANSI helpers ─────────────────────────────────────────────────────────────
_TTY = sys.stdout.isatty()
def _c(t, c): return f"\033[{c}m{t}\033[0m" if _TTY else t
def green(t): return _c(t, "92")
def yellow(t): return _c(t, "93")
def bold(t):   return _c(t, "1")


def load_analysis() -> pd.DataFrame:
    if not CLEAN_CSV.exists():
        print(f"\033[91mERROR: {CLEAN_CSV} not found — run Phase 4 scripts first\033[0m")
        sys.exit(1)

    df = pd.read_csv(CLEAN_CSV, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    bool_map = {"True": True, "False": False, "TRUE": True, "FALSE": False}
    for col in ["is_censored", "imputed_start_month", "imputed_end_month", "imputed_duration"]:
        if col in df.columns:
            df[col] = df[col].map(bool_map)
    for col in ["duration_months", "duration_months_to_scrape_date", "start_year"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[df["qa_decision"] == "KEEP"].copy()
    df["km_duration"] = np.where(
        df["is_censored"], df["duration_months_to_scrape_date"], df["duration_months"]
    )
    df["event_observed"] = (~df["is_censored"]).astype(bool)
    df = df[df["km_duration"].notna() & (df["km_duration"] > 0)].copy()
    print(f"  Analysis sample: {len(df):,} episodes ({int(df['event_observed'].sum()):,} completed)")
    return df


def km_median(sub: pd.DataFrame) -> float:
    kmf = KaplanMeierFitter()
    kmf.fit(sub["km_duration"], event_observed=sub["event_observed"])
    return kmf.median_survival_time_


def subgroup_stats(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    rows = []
    for grp, sub in df.groupby(group_col):
        n_total   = len(sub)
        n_comp    = int(sub["event_observed"].sum())
        if n_comp < MIN_COMPLETED:
            print(yellow(f"    Skipping '{grp}': n_completed={n_comp} < {MIN_COMPLETED}"))
            continue
        med = km_median(sub)
        rows.append({"group": grp, "median": med, "n": n_comp})
    return pd.DataFrame(rows).sort_values("median", ascending=False).reset_index(drop=True)


def main():
    print()
    print(bold("PHASE 5b — SUBGROUP SURVIVAL ANALYSIS"))

    df = load_analysis()

    # ── Size tier analysis ────────────────────────────────────────────────
    print()
    print(bold("Size Tier Subgroups"))
    df["size_group"] = df["company_size_tier"].map(SIZE_MAP)
    df_size = df.dropna(subset=["size_group"])
    n_no_size = df["size_group"].isna().sum()
    if n_no_size > 0:
        print(yellow(f"  {n_no_size} episodes with missing/unknown company_size_tier excluded"))

    size_df = subgroup_stats(df_size, "size_group")
    for _, row in size_df.iterrows():
        print(f"  {row['group']:<15}: median={row['median']} mo, n={row['n']}")

    # Log-rank test across size groups
    df_size_notna = df_size.dropna(subset=["size_group"])
    if df_size_notna["size_group"].nunique() >= 2:
        res = multivariate_logrank_test(
            df_size_notna["km_duration"],
            df_size_notna["size_group"],
            event_observed=df_size_notna["event_observed"],
        )
        print(f"  Log-rank p-value (size groups): {res.p_value:.4f}")

    out_size = TABLES_DIR / "size_medians.csv"
    size_df.to_csv(out_size, index=False)
    print(green(f"  Saved: {out_size}"))

    # ── Industry analysis ────────────────────────────────────────────────
    print()
    print(bold("Industry Subgroups"))
    df["industry_group"] = df["industry_normalized"].map(INDUSTRY_MAP)
    df_ind = df.dropna(subset=["industry_group"])

    ind_df = subgroup_stats(df_ind, "industry_group")
    for _, row in ind_df.iterrows():
        print(f"  {row['group']:<30}: median={row['median']} mo, n={row['n']}")

    # Log-rank test across industry groups
    df_ind_notna = df_ind.dropna(subset=["industry_group"])
    if df_ind_notna["industry_group"].nunique() >= 2:
        res = multivariate_logrank_test(
            df_ind_notna["km_duration"],
            df_ind_notna["industry_group"],
            event_observed=df_ind_notna["event_observed"],
        )
        print(f"  Log-rank p-value (industry groups): {res.p_value:.4f}")

    out_ind = TABLES_DIR / "industry_medians.csv"
    ind_df.to_csv(out_ind, index=False)
    print(green(f"  Saved: {out_ind}"))

    print()
    print(green("Phase 5b complete."))
    print()
    print("  NOTE: Run scripts/copy-data.mjs from ciso-tenure-report/ to sync")
    print("  updated CSVs to public/data/ before rebuilding the frontend.")


if __name__ == "__main__":
    main()
