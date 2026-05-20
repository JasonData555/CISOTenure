"""
analysis_guards.py — Runtime statistical constraint enforcement
CISO Tenure Study | Hitch Partners

Import at the top of every analysis script. Guards raise ValueError or emit
warnings before a model call can produce silently biased results.

Usage:
    from analysis_guards import (
        assert_no_covariate_stratification,
        assert_clustering_enabled,
        assert_sufficient_completed_episodes,
    )
"""

import warnings


PROTECTED_COVARIATES = [
    'company_size_tier',
    'industry_sector',
    'industry_normalized',
    'profile_region',
    'size_tier_usable',
]


def assert_no_covariate_stratification(column_name: str):
    """Raises ValueError if a time-varying covariate is passed to a KM fitter."""
    if column_name in PROTECTED_COVARIATES:
        raise ValueError(
            f"COVARIATE GUARD: '{column_name}' is a time-varying covariate captured "
            f"at scrape time (2025) and cannot be used as a KM stratification variable. "
            f"See CLAUDE.md COVARIATE RULES. Use episode_start_era for temporal stratification."
        )


def assert_clustering_enabled(fit_kwargs: dict):
    """Raises ValueError if cluster_col is missing from a survival model call."""
    if fit_kwargs.get('cluster_col') != 'profile_id':
        raise ValueError(
            "CLUSTERING GUARD: All survival models must cluster standard errors "
            "by profile_id to account for within-person correlation across episodes. "
            "Add cluster_col='profile_id' to your fitter call. See CLAUDE.md "
            "WITHIN-PERSON CORRELATION section."
        )


def assert_sufficient_completed_episodes(df, group_col=None, group_val=None, minimum=30):
    """Warns if a subgroup has fewer than minimum completed episodes."""
    subset = df[df['is_censored'] == False]
    if group_col:
        subset = subset[subset[group_col] == group_val]
    n = len(subset)
    if n < minimum:
        warnings.warn(
            f"LOW POWER WARNING: Only {n} completed episodes "
            f"{'overall' if not group_col else f'for {group_col}={group_val}'}. "
            f"Minimum recommended: {minimum}. KM curve will have wide confidence intervals. "
            f"This group should be footnoted as low-confidence in the report."
        )
    return n
