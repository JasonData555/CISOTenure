#!/usr/bin/env python3
"""
audit_verify.py — Independent statistical audit of CISO Tenure Study
Reproduces every key number and checks data integrity without relying on
the original pipeline scripts.

Run from: ciso-tenure-study/
  .venv/bin/python3 audit_verify.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter, NelsonAalenFitter
from lifelines.statistics import multivariate_logrank_test

ROOT        = Path(__file__).parent
CLEAN_CSV   = ROOT / "data" / "final" / "tenure_episodes_clean.csv"
TABLES_DIR  = ROOT / "output" / "tables"

PASS = "\033[92m  PASS\033[0m"
FAIL = "\033[91m  FAIL\033[0m"
WARN = "\033[93m  WARN\033[0m"
INFO = "\033[94m  INFO\033[0m"

results = {"pass": 0, "fail": 0, "warn": 0}


def check(label, ok, detail=""):
    if ok:
        results["pass"] += 1
        print(f"{PASS}  {label}")
    else:
        results["fail"] += 1
        print(f"{FAIL}  {label}" + (f" — {detail}" if detail else ""))


def warn(label, detail=""):
    results["warn"] += 1
    print(f"{WARN}  {label}" + (f" — {detail}" if detail else ""))


def info(label, detail=""):
    print(f"{INFO}  {label}" + (f" — {detail}" if detail else ""))


# ─────────────────────────────────────────────────────────────────────────────
# Load raw clean CSV (dtype=str to avoid silent coercions)
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  CISO TENURE STUDY — INDEPENDENT AUDIT")
print("=" * 70)

if not CLEAN_CSV.exists():
    print(f"\033[91mERROR: {CLEAN_CSV} not found\033[0m")
    sys.exit(1)

raw = pd.read_csv(CLEAN_CSV, dtype=str)
raw.columns = [c.strip() for c in raw.columns]

# ─────────────────────────────────────────────────────────────────────────────
# AREA 1: DATA INTEGRITY
# ─────────────────────────────────────────────────────────────────────────────
print("\n── AREA 1: Data Integrity ───────────────────────────────────────────")

# 1.1 Three-tier count reconciliation
vc = raw["qa_decision"].value_counts(dropna=False)
n_keep    = vc.get("KEEP", 0)
n_exclude = vc.get("EXCLUDE", 0)
n_blank   = int(raw["qa_decision"].isna().sum())
n_total_rows = len(raw)

check("1.1a  Total rows == 1767", n_total_rows == 1767, f"got {n_total_rows}")
check("1.1b  KEEP == 1557",       n_keep == 1557,       f"got {n_keep}")
check("1.1c  EXCLUDE == 208",     n_exclude == 208,     f"got {n_exclude}")
check("1.1d  Blank qa_decision == 2", n_blank == 2,     f"got {n_blank}")

# Build analysis subset (mirrors load_data in 05_survival_analysis.py)
bool_map = {"True": True, "False": False, "TRUE": True, "FALSE": False,
            "1": True, "0": False}

df = raw[raw["qa_decision"] == "KEEP"].copy()
for col in ["is_censored", "size_tier_usable", "imputed_start_month",
            "imputed_end_month", "imputed_duration"]:
    if col in df.columns:
        df[col] = df[col].map(bool_map)
for col in ["duration_months", "duration_months_to_scrape_date",
            "start_year", "start_month", "end_year"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

df["km_duration"] = np.where(
    df["is_censored"],
    df["duration_months_to_scrape_date"],
    df["duration_months"],
)
df["event_observed"] = (~df["is_censored"]).astype(bool)

# 1.2 Zero-duration KEEP rows (silently dropped by pipeline)
zero_dur = df[~(df["km_duration"].notna() & (df["km_duration"] > 0))]
check("1.2a  Zero/null km_duration KEEP rows count matches expectation (≤10)",
      len(zero_dur) <= 10, f"got {len(zero_dur)}")
if len(zero_dur) > 0:
    warn("1.2b  Zero/null km_duration rows are KEEP-coded but silently dropped in pipeline",
         f"n={len(zero_dur)}, start_years: {sorted(zero_dur['start_year'].unique())}")
    info("     Recommendation: code these as EXCLUDE with reason ZERO_DURATION")

# Analysis sample (after dropping zero/null km_duration)
analysis = df[df["km_duration"].notna() & (df["km_duration"] > 0)].copy()

n_analysis  = len(analysis)
n_censored  = int(analysis["is_censored"].sum())
n_completed = int(analysis["event_observed"].sum())
n_profiles  = analysis["profile_id"].nunique()

# 1.3 Analysis sample counts
check("1.3a  Analysis sample == 1549", n_analysis == 1549, f"got {n_analysis}")
check("1.3b  Completed episodes == 1163", n_completed == 1163, f"got {n_completed}")
check("1.3c  Censored episodes == 386",   n_censored == 386,   f"got {n_censored}")

# 1.4 Censoring rate
censor_rate = round(n_censored / n_analysis * 100, 1)
check("1.4   Censoring rate == 24.9%", censor_rate == 24.9, f"got {censor_rate}%")

# 1.5 Unique profile count
info(f"1.5   Unique profiles in analysis: {n_profiles} (key_findings.csv does not report this)")
if n_profiles != 776:
    warn("1.5   Profile count differs from expected 776", f"got {n_profiles}")

# ─────────────────────────────────────────────────────────────────────────────
# AREA 2: ETL CORRECTNESS
# ─────────────────────────────────────────────────────────────────────────────
print("\n── AREA 2: ETL Correctness ──────────────────────────────────────────")

# 2.1 Duration formula spot-check (all completed, non-imputed)
completed = analysis[analysis["event_observed"]].copy()
non_imp = completed[
    ~(completed["imputed_start_month"] | completed["imputed_end_month"])
].copy()
for c in ["end_year", "end_month", "start_year", "start_month", "duration_months"]:
    non_imp[c] = pd.to_numeric(non_imp[c], errors="coerce")
non_imp = non_imp.dropna(subset=["end_year","end_month","start_year","start_month","duration_months"])

recomputed = (non_imp["end_year"]*12 + non_imp["end_month"]) - \
             (non_imp["start_year"]*12 + non_imp["start_month"])
duration_match = np.allclose(recomputed.values, non_imp["duration_months"].values, atol=0)
check("2.1   Duration formula correct for all non-imputed completed episodes",
      duration_match,
      f"mismatches: {(recomputed != non_imp['duration_months']).sum()} of {len(non_imp)}")

# 2.2 Same-year both-imputed = 6-month override
both_imp = analysis[
    analysis["imputed_start_month"] & analysis["imputed_end_month"] &
    (analysis["start_year"] == pd.to_numeric(analysis.get("end_year", pd.Series(dtype=float)), errors="coerce"))
].copy()
# Re-check this by reading from raw df
raw_keep = raw[raw["qa_decision"] == "KEEP"].copy()
for c in ["imputed_start_month","imputed_end_month","start_year","end_year","duration_months"]:
    if c in ["imputed_start_month","imputed_end_month"]:
        raw_keep[c] = raw_keep[c].map(bool_map)
    else:
        raw_keep[c] = pd.to_numeric(raw_keep[c], errors="coerce")
both_imp_same_yr = raw_keep[
    (raw_keep["imputed_start_month"] == True) &
    (raw_keep["imputed_end_month"] == True) &
    (raw_keep["start_year"] == raw_keep["end_year"])
]
if len(both_imp_same_yr) > 0:
    wrong_dur = both_imp_same_yr[both_imp_same_yr["duration_months"] != 6.0]
    check("2.2   Same-year both-imputed episodes have duration_months == 6",
          len(wrong_dur) == 0,
          f"{len(wrong_dur)} violations out of {len(both_imp_same_yr)}")
else:
    info("2.2   No same-year both-imputed episodes found in KEEP set")

# 2.3 No completed KEEP episodes with end_year == 2026 (should have been recasted to censored)
completed_keep_raw = raw_keep[
    raw_keep["is_censored"].map({"True":True,"False":False,"TRUE":True,"FALSE":False}).fillna(False) == False
]
end_yr_2026 = completed_keep_raw[
    pd.to_numeric(completed_keep_raw["end_year"], errors="coerce") == 2026
]
check("2.3   No completed KEEP episodes with end_year == 2026 (should be censored)",
      len(end_yr_2026) == 0,
      f"found {len(end_yr_2026)} rows")

# 2.4 Era boundary: Jan-Feb 2020 episodes are Pre-COVID
era_jan_feb_2020 = analysis[
    (analysis["start_year"] == 2020) &
    (analysis["start_month"].isin([1, 2]))
]
if len(era_jan_feb_2020) > 0:
    all_precovid = (era_jan_feb_2020["episode_start_era"] == "Pre-COVID").all()
    check("2.4   Jan-Feb 2020 episodes classified as Pre-COVID (not COVID)",
          all_precovid,
          f"{len(era_jan_feb_2020)} episodes; "
          + era_jan_feb_2020["episode_start_era"].value_counts().to_dict().__str__())
    warn("2.4b  UI label 'Before Jan 2020' in EraMedians.tsx is WRONG — should be 'Before March 2020'",
         f"{len(era_jan_feb_2020)} Pre-COVID episodes start in Jan-Feb 2020")
else:
    info("2.4   No Jan-Feb 2020 episodes in analysis sample")

# 2.5 DURATION_UNDER_3MO flag: check completed episodes with duration_months < 3
short_completed = completed[completed["duration_months"] < 3]
if len(short_completed) > 0:
    not_flagged = short_completed[
        ~short_completed["qa_flags"].fillna("").str.contains("DURATION_UNDER_3MO")
    ]
    if len(not_flagged) > 0:
        warn("2.5   DURATION_UNDER_3MO flag bug confirmed: completed episodes with "
             "duration_months<3 are not flagged",
             f"{len(not_flagged)} unflagged short episodes: durations = "
             + str(sorted(not_flagged["duration_months"].tolist())))
    else:
        check("2.5   All completed episodes with duration_months<3 are correctly flagged",
              True)
else:
    info("2.5   No completed episodes with duration_months < 3 found in analysis sample")

# 2.6 No excluded titles (interim/deputy/acting) in KEEP rows
bad_titles = analysis[
    analysis["title_raw"].fillna("").str.contains(
        r"\b(deputy|acting|interim)\b", case=False, regex=True
    )
]
if len(bad_titles) > 0:
    check("2.6   No excluded title keywords in KEEP episodes",
          False,
          f"{len(bad_titles)} KEEP rows contain 'deputy/acting/interim': "
          + str(bad_titles["title_raw"].head(5).tolist()))
else:
    check("2.6   No excluded title keywords (deputy/acting/interim) in KEEP episodes", True)

# ─────────────────────────────────────────────────────────────────────────────
# AREA 3: STATISTICAL CALCULATIONS
# ─────────────────────────────────────────────────────────────────────────────
print("\n── AREA 3: Statistical Calculations ────────────────────────────────")

# 3.1 Overall KM median
kmf = KaplanMeierFitter()
kmf.fit(analysis["km_duration"], event_observed=analysis["event_observed"])
km_median = kmf.median_survival_time_
check("3.1   Overall KM median == 49.0 months",
      km_median == 49.0, f"got {km_median}")

# 3.2 KM CI validity: survival_prob always within [ci_lower, ci_upper]
km_data = pd.read_csv(TABLES_DIR / "km_survival_data.csv")
ci_violations = km_data[
    (km_data["survival_prob"] < km_data["ci_lower"] - 1e-9) |
    (km_data["survival_prob"] > km_data["ci_upper"] + 1e-9)
]
check("3.2a  survival_prob always within [ci_lower, ci_upper]",
      len(ci_violations) == 0, f"{len(ci_violations)} violations")
ci_monotone = (km_data["ci_lower"] <= km_data["ci_upper"]).all()
check("3.2b  ci_lower <= ci_upper for all rows", ci_monotone)

# Spot-check 3 time points against lifelines output
km_ci = kmf.confidence_interval_
km_sf = kmf.survival_function_
for t_target in [12, 24, 49]:
    # Get the lifelines value at the largest time <= t_target
    sf_at_t = km_sf[km_sf.index <= t_target].iloc[-1]["KM_estimate"] if not km_sf[km_sf.index <= t_target].empty else None
    csv_row = km_data[km_data["time_months"] == t_target]
    if sf_at_t is not None and len(csv_row) > 0:
        csv_val = csv_row["survival_prob"].iloc[0]
        match = abs(float(sf_at_t) - float(csv_val)) < 0.001
        check(f"3.2c  KM survival_prob at t={t_target} matches lifelines output",
              match, f"lifelines={sf_at_t:.4f}, csv={csv_val:.4f}")

# 3.3 Log-rank p-value
result = multivariate_logrank_test(
    analysis["km_duration"],
    analysis["episode_start_era"],
    event_observed=analysis["event_observed"],
)
lr_pval = result.p_value
lr_rounded = round(lr_pval, 4)
check("3.3a  Log-rank p-value rounds to 0.0077",
      lr_rounded == 0.0077, f"got {lr_pval:.6f} → rounds to {lr_rounded}")
check("3.3b  Log-rank p-value < 0.05 (significant)",
      lr_pval < 0.05, f"p={lr_pval:.4f}")

# 3.4 Era medians
era_expected = {"Pre-COVID": 51.0, "COVID": 42.0, "Post-COVID": 37.0}
era_n = {}
for era, expected in era_expected.items():
    sub = analysis[analysis["episode_start_era"] == era]
    era_n[era] = {"total": len(sub), "completed": int(sub["event_observed"].sum())}
    kmf_era = KaplanMeierFitter()
    kmf_era.fit(sub["km_duration"], event_observed=sub["event_observed"])
    got = kmf_era.median_survival_time_
    check(f"3.4   {era} KM median == {expected} months",
          got == expected, f"got {got}")

# Era sample size cross-check vs key_findings.csv
kf = pd.read_csv(TABLES_DIR / "key_findings.csv")
kf_era_map = {
    "Pre-COVID":  ("Pre-COVID Median",  1190, 1006),
    "COVID":      ("COVID Median",       137,   89),
    "Post-COVID": ("Post-COVID Median",  222,   68),
}
for era, (metric, exp_n_ep, exp_n_comp) in kf_era_map.items():
    actual_n_ep   = era_n[era]["total"]
    actual_n_comp = era_n[era]["completed"]
    check(f"3.4b  {era} n_episodes matches key_findings.csv ({exp_n_ep})",
          actual_n_ep == exp_n_ep, f"got {actual_n_ep}")
    check(f"3.4c  {era} n_completed matches key_findings.csv ({exp_n_comp})",
          actual_n_comp == exp_n_comp, f"got {actual_n_comp}")

# 3.5 Nelson-Aalen peak month
hazard_df = pd.read_csv(TABLES_DIR / "hazard_data.csv")
n_peaks = int(hazard_df["is_peak"].map({"True": 1, "False": 0, True: 1, False: 0}).fillna(0).sum())
peak_rows = hazard_df[hazard_df["is_peak"].astype(str).str.lower() == "true"]
check("3.5a  Exactly one is_peak=True row in hazard_data.csv", n_peaks == 1, f"got {n_peaks}")
if len(peak_rows) > 0:
    peak_month = peak_rows["time_months"].iloc[0]
    check("3.5b  Peak hazard at month 26", float(peak_month) == 26.0, f"got {peak_month}")

# Re-derive Nelson-Aalen peak independently
naf = NelsonAalenFitter()
completed_only = analysis[analysis["event_observed"]]
naf.fit(completed_only["km_duration"], event_observed=completed_only["event_observed"])
cumhaz = naf.cumulative_hazard_
# Compute incremental hazard
times = cumhaz.index.values
ch_vals = cumhaz["NA_estimate"].values
incr_hazard = np.diff(ch_vals) / np.diff(times)
incr_times  = (times[:-1] + times[1:]) / 2
# 6-month rolling mean (approximate with pandas)
h_series = pd.Series(incr_hazard, index=incr_times)
h_smooth = h_series.rolling(window=6, center=True, min_periods=1).mean()
derived_peak_month = h_smooth.idxmax()
check("3.5c  Independently derived Nelson-Aalen peak month == 26",
      abs(derived_peak_month - 26) <= 2,  # allow ±2 months for rolling window edge
      f"got {derived_peak_month:.1f}")

# 3.6 Bootstrap n_completed per cohort matches cohort_trend.csv
cohort_df = pd.read_csv(TABLES_DIR / "cohort_trend.csv")
for _, row in cohort_df.iterrows():
    yr = int(row["start_year"])
    csv_n = int(row["n_completed"])
    actual_n = int(
        analysis[
            (analysis["start_year"] == yr) &
            (analysis["event_observed"])
        ].shape[0]
    )
    check(f"3.6   Cohort {yr} n_completed matches cohort_trend.csv ({csv_n})",
          actual_n == csv_n, f"got {actual_n}")

# 3.7 Clustering guard: verify cph.fit() actually uses cluster_col
script_text = (ROOT / "scripts" / "05_survival_analysis.py").read_text()
cph_fit_has_cluster = "cluster_col='profile_id'" in script_text or 'cluster_col="profile_id"' in script_text
check("3.7a  cph.fit() in 05_survival_analysis.py uses cluster_col='profile_id'",
      cph_fit_has_cluster)
guard_dict_literal = "assert_clustering_enabled({'cluster_col': 'profile_id'})" in script_text
if guard_dict_literal:
    warn("3.7b  assert_clustering_enabled() checks a hardcoded dict, not the actual cph.fit() call",
         "Guard is documentation-only, not a runtime enforcement of the clustering parameter")

# ─────────────────────────────────────────────────────────────────────────────
# AREA 4: CHART DATA AUDIT
# ─────────────────────────────────────────────────────────────────────────────
print("\n── AREA 4: Chart Data ───────────────────────────────────────────────")

# 4.1 KM survival data extends to t=84
km_data_max = km_data["time_months"].max()
check("4.1a  km_survival_data.csv has rows at or near t=84",
      km_data_max >= 80, f"max time_months = {km_data_max}")
rows_at_84 = km_data[km_data["time_months"] == 84]
info(f"4.1b  Rows at exactly t=84: {len(rows_at_84)}")

# 4.2 ci_upper_delta = ci_upper - ci_lower is always >= 0
km_data["ci_upper_delta"] = km_data["ci_upper"] - km_data["ci_lower"]
negative_delta = (km_data["ci_upper_delta"] < -1e-9).sum()
check("4.2   ci_upper_delta >= 0 for all rows (CI band width non-negative)",
      negative_delta == 0, f"{negative_delta} negative values")

# 4.3 EraChart pivot: unique time points per era
km_era = pd.read_csv(TABLES_DIR / "km_era_data.csv")
for era in ["Pre-COVID", "COVID", "Post-COVID"]:
    sub = km_era[km_era["era"] == era]
    n_t = sub["time_months"].nunique()
    info(f"4.3   {era}: {n_t} unique time points in km_era_data.csv, {len(sub)} rows")
check("4.3b  All three eras present in km_era_data.csv",
      set(km_era["era"].unique()) == {"Pre-COVID", "COVID", "Post-COVID"},
      str(km_era["era"].unique()))

# 4.4 Hardcoded fallback audit: key values match CSV
kf_overall = kf[(kf["metric"] == "Overall Median Tenure") & (kf["unit"] == "months")]
kf_precovid = kf[kf["metric"] == "Pre-COVID Median"]
kf_postcovid = kf[kf["metric"] == "Post-COVID Median"]
kf_peak = kf[kf["metric"] == "Peak Hazard Month"]
kf_lr = kf[kf["metric"] == "Log-rank p-value"]

kf_med = float(kf_overall["value"].iloc[0]) if len(kf_overall) > 0 else None
kf_pre = float(kf_precovid["value"].iloc[0]) if len(kf_precovid) > 0 else None
kf_post = float(kf_postcovid["value"].iloc[0]) if len(kf_postcovid) > 0 else None
kf_pk = float(kf_peak["value"].iloc[0]) if len(kf_peak) > 0 else None
kf_p = float(kf_lr["value"].iloc[0]) if len(kf_lr) > 0 else None

check("4.4a  key_findings Overall Median == 49.0", kf_med == 49.0, f"got {kf_med}")
check("4.4b  key_findings Pre-COVID Median == 51.0", kf_pre == 51.0, f"got {kf_pre}")
check("4.4c  key_findings Post-COVID Median == 37.0", kf_post == 37.0, f"got {kf_post}")
check("4.4d  key_findings Peak Hazard Month == 26", kf_pk == 26.0, f"got {kf_pk}")
check("4.4e  key_findings Log-rank p-value == 0.0077", kf_p == 0.0077, f"got {kf_p}")

# 4.5 KeyNumbers % change: (37 - 51) / 51 = -27.45% → displays as 27%
pct_change = (kf_post - kf_pre) / kf_pre * 100
check("4.5   % change Pre→Post-COVID: (37-51)/51 ≈ -27.5% → UI shows ↓27%",
      abs(pct_change - (-27.45)) < 0.1, f"got {pct_change:.2f}%")

# 4.6 HazardChart: low_risk_threshold row
has_lrt = hazard_df["is_low_risk_threshold"].astype(str).str.lower().isin(["true","1"]).any()
info(f"4.6   HazardChart low_risk_threshold present in data: {has_lrt}")
if has_lrt:
    lrt_month = hazard_df[
        hazard_df["is_low_risk_threshold"].astype(str).str.lower().isin(["true","1"])
    ]["time_months"].iloc[0]
    info(f"4.6   Low risk threshold month: {lrt_month}")

# ─────────────────────────────────────────────────────────────────────────────
# AREA 5: PIPELINE CONSISTENCY
# ─────────────────────────────────────────────────────────────────────────────
print("\n── AREA 5: Pipeline Consistency ─────────────────────────────────────")

# 5.1 Diff output/tables vs public/data
frontend_data = ROOT.parent / "ciso-tenure-report" / "public" / "data"
tables_dir = TABLES_DIR

if frontend_data.exists():
    tables_files = {f.name for f in tables_dir.iterdir() if f.suffix == ".csv"}
    frontend_files = {f.name for f in frontend_data.iterdir() if f.suffix == ".csv"}
    shared = tables_files & frontend_files
    info(f"5.1a  CSV files in output/tables: {len(tables_files)}")
    info(f"5.1b  CSV files in public/data: {len(frontend_files)}")
    only_in_tables = tables_files - frontend_files
    only_in_frontend = frontend_files - tables_files
    if only_in_tables:
        warn("5.1c  CSV files in output/tables NOT in public/data", str(only_in_tables))
    if only_in_frontend:
        warn("5.1d  CSV files in public/data NOT in output/tables", str(only_in_frontend))

    # Byte-level comparison for shared files
    import hashlib
    mismatches = []
    for fname in sorted(shared):
        h1 = hashlib.md5((tables_dir / fname).read_bytes()).hexdigest()
        h2 = hashlib.md5((frontend_data / fname).read_bytes()).hexdigest()
        if h1 != h2:
            mismatches.append(fname)
    check("5.1e  All shared CSV files are byte-identical between output/tables and public/data",
          len(mismatches) == 0, f"mismatches: {mismatches}")
else:
    warn("5.1   ciso-tenure-report/public/data not found — skipping pipeline consistency check")

# 5.2 .env.production DATA_PATH
env_prod = ROOT.parent / "ciso-tenure-report" / ".env.production"
if env_prod.exists():
    env_text = env_prod.read_text()
    has_data_path = "public/data" in env_text
    check("5.2   .env.production sets data path to public/data", has_data_path, env_text.strip())
else:
    warn("5.2   .env.production not found")

# 5.3 size_medians.csv and industry_medians.csv: check if generated by any pipeline script
scripts_dir = ROOT / "scripts"
script_names = [s.name for s in scripts_dir.glob("*.py")]
script_texts = {s.name: s.read_text() for s in scripts_dir.glob("*.py")}
all_script_text = "\n".join(script_texts.values())
size_med_origin = "size_medians" in all_script_text
industry_med_origin = "industry_medians" in all_script_text
check("5.3a  size_medians.csv referenced in pipeline scripts", size_med_origin,
      "No script generates size_medians.csv — undocumented origin")
check("5.3b  industry_medians.csv referenced in pipeline scripts", industry_med_origin,
      "No script generates industry_medians.csv — undocumented origin")

# 5.4 CSV parser safety: no embedded commas in loaded CSVs
csv_to_check = [
    "key_findings.csv", "km_survival_data.csv", "km_era_data.csv",
    "hazard_data.csv", "cohort_trend.csv",
]
for fname in csv_to_check:
    fpath = TABLES_DIR / fname
    if fpath.exists():
        text = fpath.read_text()
        has_quoted_comma = '","' in text or '", ' in text
        check(f"5.4   {fname}: no embedded commas that break naive CSV parser",
              not has_quoted_comma, "found potential quoted-comma field")

# ─────────────────────────────────────────────────────────────────────────────
# AREA 6: UI LABEL CROSS-CHECK
# ─────────────────────────────────────────────────────────────────────────────
print("\n── AREA 6: UI Label Cross-Check ─────────────────────────────────────")

components_dir = ROOT.parent / "ciso-tenure-report" / "components"
if components_dir.exists():
    era_medians_path = components_dir / "EraMedians.tsx"
    hero_path        = components_dir / "Hero.tsx"

    if era_medians_path.exists():
        era_text = era_medians_path.read_text()
        has_wrong_jan = "Jan 2020" in era_text or "January 2020" in era_text
        has_correct_march = "March 2020" in era_text or "Mar 2020" in era_text
        check("6.1a  EraMedians.tsx does NOT use 'Jan 2020' label (wrong era boundary)",
              not has_wrong_jan,
              "FOUND 'Jan 2020' — era boundary is March 2020 per ETL code")
        check("6.1b  EraMedians.tsx uses 'March 2020' label (correct boundary)",
              has_correct_march,
              "Missing 'March 2020' label — label may be wrong")

    if hero_path.exists():
        hero_text = hero_path.read_text()
        has_profiles_label = '"Profiles"' in hero_text or "'Profiles'" in hero_text
        if has_profiles_label:
            warn("6.2   Hero.tsx labels n_episodes (1,549) as 'Profiles' — "
                 "these are episodes, not unique individuals (profiles=776)")
        else:
            check("6.2   Hero.tsx uses accurate labels for n_episodes", True)
else:
    warn("6.x   ciso-tenure-report/components not found — skipping UI label checks")

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print(f"  AUDIT RESULTS: {results['pass']} PASS  |  {results['fail']} FAIL  |  {results['warn']} WARN")
print("=" * 70)
if results["fail"] > 0:
    sys.exit(1)
