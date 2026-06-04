"""
05_survival_analysis.py — Phase 5: Survival Analysis
CISO Tenure Study | Hitch Partners

Produces four publication-grade figures and a key-findings summary table.

Input:  data/final/tenure_episodes_clean.csv
Output: output/figures/km_overall.png
        output/figures/km_by_era.png
        output/figures/hazard_rate.png
        output/figures/cohort_trend.png
        output/tables/key_findings.csv

Exit codes: 0 = success, 1 = fatal input error
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from lifelines import KaplanMeierFitter, CoxPHFitter, NelsonAalenFitter
from lifelines.statistics import multivariate_logrank_test

sys.path.insert(0, str(Path(__file__).parent))
from analysis_guards import (
    assert_clustering_enabled,
    assert_no_covariate_stratification,
    assert_sufficient_completed_episodes,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
CLEAN_CSV    = PROJECT_ROOT / "data" / "final" / "tenure_episodes_clean.csv"
FIGURES_DIR  = PROJECT_ROOT / "output" / "figures"
TABLES_DIR   = PROJECT_ROOT / "output" / "tables"

# ---------------------------------------------------------------------------
# Brand colors
# ---------------------------------------------------------------------------
COLOR_PRIMARY = '#0D2426'   # Dark Teal — main KM line
COLOR_ERA2    = '#235857'   # Teal — COVID era line
COLOR_ERA3    = '#3B8A7F'   # Medium Teal — Post-COVID era line
COLOR_CI_BAND = '#D3D9D4'   # Light Warm Gray — confidence bands (alpha=0.4)
COLOR_GRID    = '#6D8B8C'   # Blue Gray — gridlines

SOURCE_TEXT = "Source: Hitch Partners CISO Tenure Study, 2025"

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
# Load & prepare data
# ---------------------------------------------------------------------------
def load_data() -> pd.DataFrame:
    if not CLEAN_CSV.exists():
        print(red(f"\nERROR: Input not found: {CLEAN_CSV}"))
        print(red("  Run 04_qa_flags.py and 04b_covariate_handling.py first."))
        sys.exit(1)

    df = pd.read_csv(CLEAN_CSV, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    bool_map = {"True": True, "False": False, "TRUE": True, "FALSE": False,
                "1": True, "0": False}
    for col in ['is_censored', 'size_tier_usable', 'imputed_start_month',
                'imputed_end_month', 'imputed_duration']:
        if col in df.columns:
            df[col] = df[col].map(bool_map)

    for col in ['duration_months', 'duration_months_to_scrape_date',
                'start_year', 'start_month']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df[df['qa_decision'] == 'KEEP'].copy()

    # Build KM working columns per CLAUDE.md CENSORING section
    df['km_duration'] = np.where(
        df['is_censored'],
        df['duration_months_to_scrape_date'],
        df['duration_months'],
    )
    df['event_observed'] = (~df['is_censored']).astype(bool)

    before = len(df)
    df = df[df['km_duration'].notna() & (df['km_duration'] > 0)].copy()
    dropped = before - len(df)
    if dropped > 0:
        # These are roles that started the same month as the scrape date (2026-05)
        # and therefore have duration_months_to_scrape_date = 0. They cannot
        # contribute to survival analysis and are excluded here. They should
        # ideally be coded qa_decision='EXCLUDE' in tenure_episodes_clean.csv
        # to keep the KEEP count consistent with the analysis sample.
        print(yellow(f"  Dropped {dropped} rows with null/zero km_duration (roles starting in scrape month)"))

    n_total     = len(df)
    n_censored  = int(df['is_censored'].sum())
    n_completed = int(df['event_observed'].sum())
    n_profiles  = df['profile_id'].nunique()
    print(f"  KEEP episodes : {n_total:,}")
    print(f"  Completed     : {n_completed:,}   Censored: {n_censored:,}")
    print(f"  Unique profiles: {n_profiles:,}")
    return df


# ---------------------------------------------------------------------------
# Shared figure style
# ---------------------------------------------------------------------------
def apply_style(fig, ax):
    ax.set_facecolor('white')
    fig.patch.set_facecolor('white')
    ax.yaxis.grid(True, color=COLOR_GRID, alpha=0.3, linewidth=0.5)
    ax.xaxis.grid(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cccccc')
    ax.spines['bottom'].set_color('#cccccc')
    ax.tick_params(colors='#444444', labelsize=9)
    fig.text(0.99, 0.01, SOURCE_TEXT,
             ha='right', va='bottom', fontsize=7,
             color=COLOR_GRID, style='italic')


def save_fig(fig, path: Path):
    fig.savefig(path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(green(f"  Saved: {path}"))


# ---------------------------------------------------------------------------
# Analysis 1 — Overall KM Curve
# ---------------------------------------------------------------------------
def analysis_1_overall_km(df: pd.DataFrame) -> dict:
    print()
    print(bold("ANALYSIS 1 — OVERALL KM CURVE"))

    assert_clustering_enabled({'cluster_col': 'profile_id'})

    n_total     = len(df)
    n_profiles  = df['profile_id'].nunique()
    n_completed = int(df['event_observed'].sum())

    # ── Cox null model (clustered SE) ───────────────────────────────────────
    fit_df = df[['km_duration', 'event_observed', 'profile_id']].copy()
    fit_df['_const'] = 1.0   # single constant feature for null/baseline model

    cox_median = None
    cox_used   = False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            cph = CoxPHFitter(penalizer=0.1)
            cph.fit(fit_df,
                    duration_col='km_duration',
                    event_col='event_observed',
                    cluster_col='profile_id')

        bsf = cph.baseline_survival_
        if bsf is not None and not bsf.empty:
            sf_vals = bsf.values.flatten()
            sf_idx  = bsf.index.values
            below   = np.where(sf_vals <= 0.5)[0]
            if len(below) > 0:
                i = int(below[0])
                # Linear interpolation between the two bracketing points
                if i > 0:
                    t0, s0 = float(sf_idx[i - 1]), float(sf_vals[i - 1])
                    t1, s1 = float(sf_idx[i]),     float(sf_vals[i])
                    cox_median = t0 + (0.5 - s0) / (s1 - s0) * (t1 - t0)
                else:
                    cox_median = float(sf_idx[i])
            cox_used = True
    except Exception as exc:
        print(yellow(f"  Cox model note: {exc}. Falling back to KM median."))

    # ── KM for visual curve ──────────────────────────────────────────────────
    kmf = KaplanMeierFitter()
    kmf.fit(df['km_duration'], event_observed=df['event_observed'], label='All CISOs')
    km_median = float(kmf.median_survival_time_)

    reported_median = cox_median if (cox_median is not None and not np.isnan(cox_median)) \
                      else km_median
    print(f"  KM median    : {km_median:.1f} months")
    if cox_used:
        print(f"  Cox median   : {cox_median:.1f} months (clustered SE)")
    print(f"  Reported     : {reported_median:.1f} months ({reported_median / 12:.1f} years)")

    # ── Plot ─────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.subplots_adjust(top=0.88)

    # KM curve (no built-in CI — draw manually for color control)
    ax.step(kmf.timeline, kmf.survival_function_['All CISOs'],
            where='post', color=COLOR_PRIMARY, linewidth=2, label='All CISOs')

    ci_lower = kmf.confidence_interval_['All CISOs_lower_0.95']
    ci_upper = kmf.confidence_interval_['All CISOs_upper_0.95']
    ax.fill_between(kmf.timeline, ci_lower, ci_upper,
                    alpha=0.4, color=COLOR_CI_BAND, step='post')

    ax.axhline(0.5, ls='--', color=COLOR_GRID, lw=1, alpha=0.7)
    ax.axvline(reported_median, ls='--', color=COLOR_GRID, lw=1, alpha=0.7)
    ax.annotate(
        f"Median: {reported_median:.0f} mo\n({reported_median / 12:.1f} yrs)",
        xy=(reported_median, 0.5),
        xytext=(reported_median + 3, 0.62),
        fontsize=9, color=COLOR_PRIMARY,
        arrowprops=dict(arrowstyle='->', color=COLOR_GRID, lw=0.8),
    )

    ax.set_xlim(0, 84)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Months in Role", fontsize=11)
    ax.set_ylabel("Probability of Remaining in Role", fontsize=11)

    subtitle = (f"n={n_total:,} episodes ({n_profiles:,} CISOs)  |  "
                f"Median: {reported_median:.0f} months ({reported_median / 12:.1f} years)")
    ax.set_title(f"CISO Tenure Survival Curve\n{subtitle}",
                 fontsize=13, fontweight='bold', pad=10, loc='left')

    apply_style(fig, ax)
    save_fig(fig, FIGURES_DIR / "km_overall.png")

    # ── CSV export for web report ────────────────────────────────────────────
    km_export = pd.DataFrame({
        'time_months':    kmf.timeline,
        'survival_prob':  kmf.survival_function_['All CISOs'].values,
        'ci_lower':       kmf.confidence_interval_['All CISOs_lower_0.95'].values,
        'ci_upper':       kmf.confidence_interval_['All CISOs_upper_0.95'].values,
    })
    km_export.to_csv(TABLES_DIR / "km_survival_data.csv", index=False)
    print(green(f"  Saved: {TABLES_DIR / 'km_survival_data.csv'}"))

    return {
        'median_months': reported_median,
        'n_episodes':    n_total,
        'n_completed':   n_completed,
        'n_profiles':    n_profiles,
        'cox_used':      cox_used,
    }


# ---------------------------------------------------------------------------
# Analysis 2 — Era Comparison
# ---------------------------------------------------------------------------
def analysis_2_era_comparison(df: pd.DataFrame) -> dict:
    print()
    print(bold("ANALYSIS 2 — ERA COMPARISON"))

    eras       = ['Pre-COVID', 'COVID', 'Post-COVID']
    era_colors = [COLOR_PRIMARY, COLOR_ERA2, COLOR_ERA3]

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.subplots_adjust(top=0.88)

    era_medians = {}
    era_counts  = {}
    legend_handles = []
    era_rows = []  # accumulator for web report CSV export

    for era, color in zip(eras, era_colors):
        n_completed = assert_sufficient_completed_episodes(
            df, 'episode_start_era', era, minimum=30
        )
        subset = df[df['episode_start_era'] == era]
        n_total_era = len(subset)
        era_counts[era] = {'total': n_total_era, 'completed': n_completed}

        kmf = KaplanMeierFitter()
        kmf.fit(subset['km_duration'], event_observed=subset['event_observed'])
        med = kmf.median_survival_time_
        era_medians[era] = med

        med_str = f"{med:.0f} mo" if not (isinstance(med, float) and np.isnan(med)) else ">84 mo"
        print(f"  {era:<14}: total={n_total_era:>4,}  completed={n_completed:>4,}  median={med_str}")

        ax.step(kmf.timeline, kmf.survival_function_.iloc[:, 0],
                where='post', color=color, linewidth=2)
        ci_lower = kmf.confidence_interval_.iloc[:, 0]
        ci_upper = kmf.confidence_interval_.iloc[:, 1]
        ax.fill_between(kmf.timeline, ci_lower, ci_upper,
                        alpha=0.12, color=color, step='post')

        # Accumulate rows for km_era_data.csv
        for t, s, lo_v, hi_v in zip(
            kmf.timeline,
            kmf.survival_function_.iloc[:, 0].values,
            ci_lower.values,
            ci_upper.values,
        ):
            era_rows.append({
                'time_months':   t,
                'era':           era,
                'survival_prob': s,
                'ci_lower':      lo_v,
                'ci_upper':      hi_v,
            })

        patch = mpatches.Patch(
            color=color,
            label=f"{era}  (n={n_completed:,} completed)"
        )
        legend_handles.append(patch)

    # Log-rank test across all three eras
    result  = multivariate_logrank_test(
        df['km_duration'], df['episode_start_era'], df['event_observed']
    )
    p_value = float(result.p_value)
    print(f"  Log-rank p-value: {p_value:.4f}")

    ax.text(0.03, 0.08,
            f"Log-rank  p = {p_value:.4f}",
            transform=ax.transAxes, fontsize=9, color=COLOR_PRIMARY,
            bbox=dict(boxstyle='round,pad=0.35', facecolor='white',
                      edgecolor=COLOR_GRID, alpha=0.85))

    ax.legend(handles=legend_handles, loc='upper right', fontsize=9,
              framealpha=0.9, edgecolor=COLOR_GRID)

    n1 = era_counts['Pre-COVID']['completed']
    n2 = era_counts['COVID']['completed']
    n3 = era_counts['Post-COVID']['completed']
    subtitle = (f"Pre-COVID n={n1:,}  |  COVID n={n2:,}  |  "
                f"Post-COVID n={n3:,}  |  Log-rank p={p_value:.4f}")

    ax.set_xlim(0, 84)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Months in Role", fontsize=11)
    ax.set_ylabel("Probability of Remaining in Role", fontsize=11)
    ax.set_title(f"CISO Tenure by Era\n{subtitle}",
                 fontsize=13, fontweight='bold', pad=10, loc='left')

    apply_style(fig, ax)
    save_fig(fig, FIGURES_DIR / "km_by_era.png")

    # ── CSV export for web report ────────────────────────────────────────────
    pd.DataFrame(era_rows).to_csv(TABLES_DIR / "km_era_data.csv", index=False)
    print(green(f"  Saved: {TABLES_DIR / 'km_era_data.csv'}"))

    return {'era_medians': era_medians, 'p_value': p_value, 'era_counts': era_counts}


# ---------------------------------------------------------------------------
# Analysis 3 — Hazard Rate
# ---------------------------------------------------------------------------
def analysis_3_hazard_rate(df: pd.DataFrame) -> dict:
    print()
    print(bold("ANALYSIS 3 — HAZARD RATE"))

    n_completed = int(df['event_observed'].sum())

    naf = NelsonAalenFitter()
    naf.fit(df['km_duration'], event_observed=df['event_observed'])

    # Restrict to 0–84 months before smoothing
    cumhaz = naf.cumulative_hazard_
    cumhaz = cumhaz[cumhaz.index <= 84]

    times   = cumhaz.index.values.astype(float)
    ch_vals = cumhaz.values.flatten()

    # Incremental hazard: dH / dt at each observed event time
    delta_H = np.diff(ch_vals, prepend=0.0)
    delta_t = np.diff(times,   prepend=times[0] if len(times) > 0 else 0.0)
    delta_t = np.where(delta_t == 0.0, 1.0, delta_t)

    raw_hazard = delta_H / delta_t

    # 6-month rolling average
    smoothed = (pd.Series(raw_hazard, index=times)
                .rolling(window=6, center=True, min_periods=1)
                .mean())
    smoothed = smoothed.dropna()

    peak_month = int(smoothed.idxmax())
    peak_val   = float(smoothed.max())
    print(f"  Peak hazard : month {peak_month}  ({peak_val:.5f} per month)")
    print(f"  Completed   : {n_completed:,}")

    # Compute low-risk threshold (first month post-peak where smoothed stays
    # below 50% of peak for 3+ consecutive observations)
    half_peak = peak_val * 0.5
    post_peak = smoothed[smoothed.index > peak_month]
    low_risk_month = None
    for _i in range(len(post_peak) - 2):
        if all(post_peak.iloc[_i:_i + 3] < half_peak):
            low_risk_month = int(post_peak.index[_i])
            break

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.subplots_adjust(top=0.88)

    ax.plot(smoothed.index, smoothed.values, color=COLOR_PRIMARY, linewidth=2)
    raw_series = pd.Series(raw_hazard, index=times)
    ax.plot(raw_series.index, raw_series.values,
            color=COLOR_PRIMARY, linewidth=1, alpha=0.20)
    ax.fill_between(smoothed.index, 0, smoothed.values,
                    color=COLOR_PRIMARY, alpha=0.06)

    ax.axvline(peak_month, ls='--', color=COLOR_ERA3, lw=1.5, alpha=0.9)
    ax.text(peak_month + 1, peak_val * 0.92,
            f"Peak: Month {peak_month}",
            fontsize=9, color=COLOR_ERA3, fontweight='bold')

    ax.set_xlim(0, 84)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Months in Role", fontsize=11)
    ax.set_ylabel("Hazard Rate (exit probability per month)", fontsize=11)
    ax.set_title(
        f"CISO Exit Hazard Rate\n"
        f"Peak exit risk at month {peak_month}  |  n={n_completed:,} completed episodes",
        fontsize=13, fontweight='bold', pad=10, loc='left',
    )

    apply_style(fig, ax)
    save_fig(fig, FIGURES_DIR / "hazard_rate.png")

    # ── CSV export for web report ────────────────────────────────────────────
    raw_series = pd.Series(raw_hazard, index=times).reindex(smoothed.index)
    hazard_export = pd.DataFrame({
        'time_months':     smoothed.index,
        'hazard_rate':     raw_series.values,
        'hazard_smoothed': smoothed.values,
    })
    hazard_export['is_peak'] = hazard_export['time_months'] == peak_month
    hazard_export['is_low_risk_threshold'] = (
        hazard_export['time_months'] == low_risk_month
        if low_risk_month is not None else False
    )
    hazard_export.to_csv(TABLES_DIR / "hazard_data.csv", index=False)
    print(green(f"  Saved: {TABLES_DIR / 'hazard_data.csv'}"))

    return {'peak_month': peak_month, 'n_completed': n_completed}


# ---------------------------------------------------------------------------
# Analysis 4 — Cohort Trend
# ---------------------------------------------------------------------------
def _bootstrap_median_ci(subset_df: pd.DataFrame, n_iter: int = 1000) -> tuple:
    """Profile-level bootstrap 95% CI for median duration_months."""
    unique_profiles = subset_df['profile_id'].unique()
    if len(unique_profiles) == 0:
        return (np.nan, np.nan)
    rng     = np.random.default_rng(42)
    medians = []
    for _ in range(n_iter):
        sampled_pids = rng.choice(unique_profiles,
                                  size=len(unique_profiles), replace=True)
        # Concatenate episodes for all sampled profiles (duplicates allowed)
        parts = [subset_df.loc[subset_df['profile_id'] == pid, 'duration_months']
                 for pid in sampled_pids]
        vals = np.concatenate([p.dropna().values for p in parts])
        if len(vals) > 0:
            medians.append(float(np.median(vals)))
    if not medians:
        return (np.nan, np.nan)
    return float(np.percentile(medians, 2.5)), float(np.percentile(medians, 97.5))


def analysis_4_cohort_trend(df: pd.DataFrame) -> dict:
    print()
    print(bold("ANALYSIS 4 — COHORT TREND"))

    completed = df[df['event_observed'] == True].copy()

    results = []
    for yr in range(2017, 2025):
        subset = completed[completed['start_year'] == yr]
        n = len(subset)
        if n == 0:
            print(f"  {yr}: no completed episodes — skipped")
            continue
        med    = float(subset['duration_months'].median())
        lo, hi = _bootstrap_median_ci(subset)
        lc     = n < 30
        results.append({
            'year': yr, 'n': n, 'median': med,
            'ci_low': lo, 'ci_high': hi,
            'low_confidence': lc,
        })
        flag = yellow(" [LOW CONF <30]") if lc else ""
        print(f"  {yr}: n={n:>4,}  median={med:.0f}mo  CI=[{lo:.0f}, {hi:.0f}]{flag}")

    if not results:
        print(red("  No cohort data to plot."))
        return {}

    low_conf_years = [r['year'] for r in results if r['low_confidence']]

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.subplots_adjust(top=0.88, bottom=0.12)

    # COVID shading (March 2020 – December 2021)
    ax.axvspan(2020 + 2 / 12, 2021 + 11 / 12,
               color=COLOR_CI_BAND, alpha=0.5, zorder=0)

    # Plot each year
    for row in results:
        yr  = row['year']
        med = row['median']
        lo  = row['ci_low']
        hi  = row['ci_high']
        n   = row['n']
        lc  = row['low_confidence']

        err_lo = max(med - lo, 0) if not np.isnan(lo) else 0
        err_hi = max(hi - med, 0) if not np.isnan(hi) else 0
        yerr   = [[err_lo], [err_hi]]

        color  = COLOR_GRID if lc else COLOR_PRIMARY
        mfc    = 'none'     if lc else COLOR_PRIMARY
        alpha  = 0.55       if lc else 1.0

        ax.errorbar(yr, med, yerr=yerr,
                    fmt='o', color=color, markerfacecolor=mfc,
                    markeredgewidth=1.8, markeredgecolor=color,
                    capsize=5, elinewidth=1.5, markersize=10,
                    alpha=alpha, linestyle='none', zorder=3)

        label_y = (hi + 3) if not np.isnan(hi) else (med + 5)
        ax.text(yr, label_y, f"n={n}", ha='center', va='bottom',
                fontsize=8, color=color)

    # COVID label (set after first plot so y-limits are real)
    ylim = ax.get_ylim()
    covid_label_y = ylim[0] + (ylim[1] - ylim[0]) * 0.90
    ax.text(2020.95, covid_label_y, "COVID\nera",
            ha='center', va='top', fontsize=8,
            color=COLOR_GRID, style='italic')

    # Legend patches
    solid_patch  = mpatches.Patch(color=COLOR_PRIMARY,
                                  label="High confidence (n≥30)")
    dashed_patch = mpatches.Patch(facecolor='none', edgecolor=COLOR_GRID,
                                  linewidth=1.5, label="Low confidence (n<30)")
    ax.legend(handles=[solid_patch, dashed_patch], loc='upper right',
              fontsize=9, framealpha=0.9, edgecolor=COLOR_GRID)

    ax.set_xticks(range(2017, 2025))
    ax.set_xlabel("Cohort Start Year", fontsize=11)
    ax.set_ylabel("Tenure (months)", fontsize=11)
    ax.set_title(
        "CISO Tenure by Cohort Start Year\n"
        "Completed episodes only  |  Dashed points = n<30, low confidence",
        fontsize=13, fontweight='bold', pad=10, loc='left',
    )

    if low_conf_years:
        footnote = ("Low confidence (<30 completed episodes): "
                    + ", ".join(str(y) for y in low_conf_years))
        fig.text(0.12, 0.01, footnote, fontsize=8, color=COLOR_GRID)

    apply_style(fig, ax)
    save_fig(fig, FIGURES_DIR / "cohort_trend.png")

    # ── CSV export for web report ────────────────────────────────────────────
    cohort_df = pd.DataFrame([{
        'start_year':     r['year'],
        'median_months':  r['median'],
        'ci_lower':       r['ci_low'],
        'ci_upper':       r['ci_high'],
        'n_completed':    r['n'],
        'low_confidence': r['low_confidence'],
    } for r in results])
    cohort_df.to_csv(TABLES_DIR / "cohort_trend.csv", index=False)
    print(green(f"  Saved: {TABLES_DIR / 'cohort_trend.csv'}"))

    return {'results': results, 'low_conf_years': low_conf_years}


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------
def write_summary_table(df: pd.DataFrame, stats: dict):
    print()
    print(bold("KEY FINDINGS TABLE"))

    n_total     = len(df)
    n_censored  = int(df['is_censored'].sum())
    n_completed = int(df['event_observed'].sum())
    censor_rate = n_censored / n_total * 100 if n_total > 0 else 0

    overall = stats['overall']
    era     = stats['era']
    hazard  = stats['hazard']

    def _fmt(v):
        if v is None:
            return '>84'
        try:
            if np.isnan(float(v)):
                return '>84'
        except (TypeError, ValueError):
            pass
        return str(v)

    rows = [
        {
            'metric':      'Overall Median Tenure',
            'value':       f"{overall['median_months']:.1f}",
            'unit':        'months',
            'n_episodes':  overall['n_episodes'],
            'n_completed': overall['n_completed'],
            'notes':       'Cox clustered SE' if overall['cox_used'] else 'KM estimate',
        },
        {
            'metric':      'Overall Median Tenure',
            'value':       f"{overall['median_months'] / 12:.1f}",
            'unit':        'years',
            'n_episodes':  overall['n_episodes'],
            'n_completed': overall['n_completed'],
            'notes':       'Cox clustered SE' if overall['cox_used'] else 'KM estimate',
        },
        {
            'metric':      'Pre-COVID Median',
            'value':       _fmt(era['era_medians'].get('Pre-COVID')),
            'unit':        'months',
            'n_episodes':  era['era_counts']['Pre-COVID']['total'],
            'n_completed': era['era_counts']['Pre-COVID']['completed'],
            'notes':       'KM estimate',
        },
        {
            'metric':      'COVID Median',
            'value':       _fmt(era['era_medians'].get('COVID')),
            'unit':        'months',
            'n_episodes':  era['era_counts']['COVID']['total'],
            'n_completed': era['era_counts']['COVID']['completed'],
            'notes':       'KM estimate',
        },
        {
            'metric':      'Post-COVID Median',
            'value':       _fmt(era['era_medians'].get('Post-COVID')),
            'unit':        'months',
            'n_episodes':  era['era_counts']['Post-COVID']['total'],
            'n_completed': era['era_counts']['Post-COVID']['completed'],
            'notes':       'KM estimate',
        },
        {
            'metric':      'Log-rank p-value',
            'value':       f"{era['p_value']:.4f}",
            'unit':        '—',
            'n_episodes':  '—',
            'n_completed': '—',
            'notes':       'Era comparison',
        },
        {
            'metric':      'Peak Hazard Month',
            'value':       str(hazard['peak_month']),
            'unit':        'months',
            'n_episodes':  '—',
            'n_completed': hazard['n_completed'],
            'notes':       'Nelson-Aalen smoothed',
        },
        {
            'metric':      'Censored Episodes',
            'value':       str(n_censored),
            'unit':        'count',
            'n_episodes':  n_total,
            'n_completed': '—',
            'notes':       'Ongoing roles at scrape',
        },
        {
            'metric':      'Censoring Rate',
            'value':       f"{censor_rate:.1f}",
            'unit':        '%',
            'n_episodes':  n_total,
            'n_completed': '—',
            'notes':       '',
        },
    ]

    result_df = pd.DataFrame(rows)
    out_path  = TABLES_DIR / "key_findings.csv"
    result_df.to_csv(out_path, index=False)
    print(green(f"  Written: {out_path}"))
    print()
    print(result_df.to_string(index=False))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    sep = "=" * 70
    print()
    print(bold(sep))
    print(bold("  CISO TENURE STUDY — PHASE 5: SURVIVAL ANALYSIS"))
    print(bold(sep))
    print()

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    print(bold("LOADING DATA"))
    df = load_data()

    overall_stats = analysis_1_overall_km(df)
    era_stats     = analysis_2_era_comparison(df)
    hazard_stats  = analysis_3_hazard_rate(df)
    _             = analysis_4_cohort_trend(df)

    write_summary_table(df, {
        'overall': overall_stats,
        'era':     era_stats,
        'hazard':  hazard_stats,
    })

    print()
    print(bold(sep))
    print(green("  Phase 5 complete. Figures: output/figures/  Table: output/tables/key_findings.csv"))
    print(bold(sep))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
