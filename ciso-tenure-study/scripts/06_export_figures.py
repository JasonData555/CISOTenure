"""
06_export_figures.py — Phase 6: Final Figure Export
CISO Tenure Study | Hitch Partners

Verifies all publication figures meet final export spec (300 DPI, ≥8×5 in),
produces km_overall_print.png (10×6 in, with logo placeholder), and prints
a final manifest confirming readiness for design polish.

Input:  output/figures/{km_overall,km_by_era,hazard_rate,cohort_trend}.png
        data/final/tenure_episodes_clean.csv  (for km_overall_print)
Output: output/figures/km_overall_print.png
        Console manifest

Exit codes: 0 = success, 1 = fatal error
"""

import sys
import subprocess
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from lifelines import KaplanMeierFitter, CoxPHFitter

sys.path.insert(0, str(Path(__file__).parent))
from analysis_guards import assert_clustering_enabled

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
FIGURES_DIR  = PROJECT_ROOT / "output" / "figures"
CLEAN_CSV    = PROJECT_ROOT / "data" / "final" / "tenure_episodes_clean.csv"

COLOR_PRIMARY = '#0D2426'
COLOR_CI_BAND = '#D3D9D4'
COLOR_GRID    = '#6D8B8C'
SOURCE_TEXT   = "Source: Hitch Partners CISO Tenure Study, 2025"

REQUIRED_FIGURES = [
    "km_overall.png",
    "km_by_era.png",
    "hazard_rate.png",
    "cohort_trend.png",
]

MIN_DPI    = 299.0   # matplotlib saves as ~299.9994; allow minor float tolerance
MIN_W_IN   = 8.0
MIN_H_IN   = 5.0

# ---------------------------------------------------------------------------
# ANSI helpers (suppressed when not a TTY)
# ---------------------------------------------------------------------------
_IS_TTY = sys.stdout.isatty()

def _color(text, code):
    return f"\033[{code}m{text}\033[0m" if _IS_TTY else text

def red(t):    return _color(t, "91")
def green(t):  return _color(t, "92")
def yellow(t): return _color(t, "93")
def bold(t):   return _color(t, "1")


# ---------------------------------------------------------------------------
# Figure verification
# ---------------------------------------------------------------------------
def check_figure(name: str) -> dict:
    """Return a dict with ok=True/False and metadata about the figure."""
    path = FIGURES_DIR / name
    if not path.exists():
        return {"ok": False, "reason": "MISSING", "size_kb": 0, "dpi": 0,
                "w_in": 0, "h_in": 0}

    size_kb = path.stat().st_size / 1024
    img = Image.open(path)
    dpi_xy = img.info.get("dpi", (0.0, 0.0))
    dpi_x = float(dpi_xy[0])
    dpi_y = float(dpi_xy[1]) if len(dpi_xy) > 1 else dpi_x
    w_px, h_px = img.size

    w_in = w_px / dpi_x if dpi_x else 0.0
    h_in = h_px / dpi_y if dpi_y else 0.0

    dpi_ok = dpi_x >= MIN_DPI and dpi_y >= MIN_DPI
    dim_ok = w_in >= MIN_W_IN and h_in >= MIN_H_IN

    reason = ""
    if not dpi_ok:
        reason = f"DPI={dpi_x:.0f} < 300"
    elif not dim_ok:
        reason = f"size={w_in:.1f}×{h_in:.1f}in < 8×5in"

    return {
        "ok":      dpi_ok and dim_ok,
        "reason":  reason,
        "size_kb": size_kb,
        "dpi":     dpi_x,
        "w_in":    w_in,
        "h_in":    h_in,
    }


def verify_all(figures: list[str]) -> bool:
    """Print spec table for each figure. Returns True if all pass."""
    print()
    print(bold("FIGURE VERIFICATION"))
    print(f"{'Filename':<30} {'Size':>9} {'DPI':>5} {'Dimensions':>14}  Status")
    print("─" * 70)

    all_ok = True
    for name in figures:
        r = check_figure(name)
        if r["ok"]:
            dims = f"{r['w_in']:.1f}×{r['h_in']:.1f} in"
            print(f"{name:<30} {r['size_kb']:>7.1f}KB {r['dpi']:>5.0f} {dims:>14}  {green('✓ OK')}")
        else:
            print(f"{name:<30} {'':>9} {'':>5} {'':>14}  {red('✗ ' + r['reason'])}")
            all_ok = False

    return all_ok


# ---------------------------------------------------------------------------
# Regenerate figures by re-running Phase 5
# ---------------------------------------------------------------------------
def regenerate_figures():
    script = PROJECT_ROOT / "scripts" / "05_survival_analysis.py"
    print(yellow(f"\nRe-running {script.name} to regenerate figures..."))
    result = subprocess.run([sys.executable, str(script)])
    if result.returncode != 0:
        print(red("ERROR: Regeneration failed. Fix 05_survival_analysis.py and retry."))
        sys.exit(1)


# ---------------------------------------------------------------------------
# Data loading (mirrors load_data() in 05_survival_analysis.py)
# ---------------------------------------------------------------------------
def _load_clean_data() -> pd.DataFrame:
    if not CLEAN_CSV.exists():
        print(red(f"\nERROR: Clean data not found: {CLEAN_CSV}"))
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

    df['km_duration'] = np.where(
        df['is_censored'],
        df['duration_months_to_scrape_date'],
        df['duration_months'],
    )
    df['event_observed'] = (~df['is_censored']).astype(bool)

    df = df[df['km_duration'].notna() & (df['km_duration'] > 0)].copy()
    return df


# ---------------------------------------------------------------------------
# Shared figure style (mirrors apply_style() in 05_survival_analysis.py)
# ---------------------------------------------------------------------------
def _apply_style(fig, ax):
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


# ---------------------------------------------------------------------------
# Build km_overall_print.png
# ---------------------------------------------------------------------------
def build_print_figure():
    """
    Produce km_overall_print.png — identical analysis to km_overall.png but
    wider (10×6 in) with a Hitch Partners logo placeholder in the top-right.
    """
    print()
    print(bold("BUILDING km_overall_print.png"))

    assert_clustering_enabled({'cluster_col': 'profile_id'})

    df = _load_clean_data()
    n_total    = len(df)
    n_profiles = df['profile_id'].nunique()

    # ── Cox null model (clustered SE) ─────────────────────────────────────────
    fit_df = df[['km_duration', 'event_observed', 'profile_id']].copy()
    fit_df['_const'] = 1.0

    cox_median = None
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
                if i > 0:
                    t0, s0 = float(sf_idx[i - 1]), float(sf_vals[i - 1])
                    t1, s1 = float(sf_idx[i]),     float(sf_vals[i])
                    cox_median = t0 + (0.5 - s0) / (s1 - s0) * (t1 - t0)
                else:
                    cox_median = float(sf_idx[i])
    except Exception as exc:
        print(yellow(f"  Cox model note: {exc}. Falling back to KM median."))

    # ── KM curve ──────────────────────────────────────────────────────────────
    kmf = KaplanMeierFitter()
    kmf.fit(df['km_duration'], event_observed=df['event_observed'], label='All CISOs')
    km_median = float(kmf.median_survival_time_)

    reported_median = cox_median if (cox_median is not None and not np.isnan(cox_median)) \
                      else km_median
    print(f"  Reported median: {reported_median:.1f} months ({reported_median / 12:.1f} years)")

    # ── Plot (10×6 — wider print format) ─────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.subplots_adjust(top=0.88)

    ax.step(kmf.timeline, kmf.survival_function_['All CISOs'],
            where='post', color=COLOR_PRIMARY, linewidth=2)

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

    # Logo placeholder — top-right of axes area
    ax.text(0.98, 0.97, "[HITCH LOGO]",
            transform=ax.transAxes,
            ha='right', va='top',
            fontsize=10, color='#0D2426', fontweight='bold')

    _apply_style(fig, ax)

    out_path = FIGURES_DIR / "km_overall_print.png"
    fig.savefig(out_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(green(f"  Saved: {out_path}"))


# ---------------------------------------------------------------------------
# Final manifest
# ---------------------------------------------------------------------------
def print_manifest(all_figures: list[str]):
    print()
    print(bold("Export complete. Files ready for design polish:"))
    for name in all_figures:
        rel = f"output/figures/{name}"
        print(f"  {rel:<46} {green('✓')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(bold("\n── CISO Tenure Study | Phase 6: Export Figures ──"))

    # Verify required figures
    ok = verify_all(REQUIRED_FIGURES)
    if not ok:
        regenerate_figures()
        ok = verify_all(REQUIRED_FIGURES)
        if not ok:
            print(red("\nERROR: Figures still fail spec after regeneration. Aborting."))
            sys.exit(1)

    # Produce print-layout variant
    build_print_figure()

    # Verify the new print figure
    print()
    r = check_figure("km_overall_print.png")
    if r["ok"]:
        print(green(f"  km_overall_print.png verified: {r['w_in']:.1f}×{r['h_in']:.1f} in @ {r['dpi']:.0f} DPI"))
    else:
        print(red(f"  km_overall_print.png FAILED spec: {r['reason']}"))
        sys.exit(1)

    # Print final manifest
    manifest_figures = [
        "km_overall.png",
        "km_overall_print.png",
        "km_by_era.png",
        "hazard_rate.png",
        "cohort_trend.png",
    ]
    print_manifest(manifest_figures)


if __name__ == "__main__":
    main()
