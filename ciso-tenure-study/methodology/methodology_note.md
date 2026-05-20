---
Hitch Partners Research | Methodology Note v1.0
Published: 2026-05-18 | Status: Pre-Analysis Registration
---

## 1. RESEARCH OBJECTIVES

**Primary:** Measure how median CISO tenure has changed across pre-COVID, COVID, and post-COVID periods among North American security leaders.

**Secondary:** Identify the month within a tenure when CISOs are most likely to exit; characterize the sample by company size, industry, and geography.

---

## 2. DATA SOURCES & SAMPLE CONSTRUCTION

Profiles were drawn from Hitch Partners' proprietary database of North American security leaders, including passive candidates with no active interest in career transition. Selection was based on data completeness. Profiles are professionally visible CISOs; individuals with no public professional footprint may be underrepresented.

- **Source:** LinkedIn work history via Apify scraper
- **Sample:** ~1,200 LinkedIn profiles
- **Unit of analysis:** Individual role episodes (not persons). One CISO who held three CISO-level roles contributes three episodes. This is standard in labor economics research and is explicitly disclosed.
- **Study window:** Role episodes with start dates from January 2017 through individual profile scrape date
- **Expected yield:** 2,400–3,600 raw episodes; ~1,800–2,500 after title filtering and QA

---

## 3. INCLUSION / EXCLUSION CRITERIA

**Title inclusion:** CISO, Chief Information Security Officer, Chief Security Officer (CSO), or VP/SVP/EVP of Security where no CISO title existed above them at that company.

**Excluded from main analysis (tracked separately):**

- Deputy CISO, Assistant CISO → tracked as Excluded\_Deputy
- Interim CISO, Acting CISO → tracked as Excluded\_Interim
- Pure IT titles (CIO, CTO, CITO) without an explicit security mandate → tracked as Excluded\_Other

All raw titles are preserved in the dataset. Normalized title categories are: CISO, CSO, VP\_Security, Excluded\_Deputy, Excluded\_Interim, Excluded\_Other.

---

## 4. METRIC DEFINITIONS

**Primary metric:** Median completed tenure, Kaplan-Meier estimator.

**On censoring:** Ongoing roles are treated as right-censored observations and included in survival analysis using the Kaplan-Meier estimator. Censoring date is the individual profile scrape date.

**On within-person correlation:** Multiple role episodes from the same individual are not statistically independent. All survival models cluster standard errors by individual to produce valid confidence intervals.

**On date imputation:** When LinkedIn provides year of employment without month, start and end months are imputed as June. Affected episodes are flagged and this imputation is disclosed in all reporting.

---

## 5. ERA CLASSIFICATION

Era classification is applied to every episode based on role start date:

| Era | Date Range | Rationale |
|---|---|---|
| Pre-COVID | Before March 2020 | Pre-pandemic baseline |
| COVID | March 2020 – December 2021 | WHO pandemic declaration through widespread vaccine rollout |
| Post-COVID | January 2022 or later | Labor market reshuffling period |

**Rationale for COVID boundaries:** The WHO declared a global pandemic on March 11, 2020. The end boundary of December 2021 reflects widespread vaccine rollout completion in North America. Era classification is the primary analytical variable; era comparison is the headline finding.

---

## 6. STATISTICAL METHODS

- **Kaplan-Meier survival analysis** for visual survival curves and era comparison (lifelines library)
- **Cox Proportional Hazards model** with clustered standard errors by individual, used for the primary median estimate
- **Log-rank test (multivariate)** for era comparison statistical significance
- **Nelson-Aalen estimator** with 3-month rolling smoothing for hazard rate analysis
- **Bootstrap confidence intervals** (1,000 iterations, resampled by individual) for cohort trend analysis
- **Primary hypothesis** (era differences in median tenure) specified prior to analysis

---

## 7. COVARIATE HANDLING

Company size, industry, and geographic region are reported for sample composition purposes only. Because these attributes can change materially over an 8-year study window through acquisitions, growth, and relocation, they are not used as stratification variables in survival analysis.

LinkedIn does not provide historical location data for past role episodes, making episode-level geographic assignment unreliable across an 8-year study window.

Covariate attributes (company\_size\_tier, industry\_sector, profile\_region) are captured at scrape time (2025) and appear only in sample composition tables. They are enforced as non-analytical at runtime by analysis\_guards.py.

---

## 8. LIMITATIONS

**Statistical power in recent eras:** COVID and Post-COVID era curves reflect fewer completed episodes (89 and 68 respectively) than the pre-registered 100-episode minimum, a structural consequence of studying periods where many roles remain ongoing. Kaplan-Meier estimates are statistically valid but carry wider confidence intervals. This uncertainty reflects genuine market volatility in recent cohorts rather than a data deficiency.

**Source visibility:** Profiles were drawn from Hitch Partners' proprietary database of North American security leaders, including passive candidates with no active interest in career transition. Selection was based on data completeness. Profiles are professionally visible CISOs; individuals with no public professional footprint may be underrepresented.

**Title normalization:** Inclusion and exclusion decisions for ambiguous titles (e.g., VP of Security where a CISO also existed) involve judgment calls documented in Section 3. All raw titles are preserved for auditability.

**Date imputation:** When LinkedIn provides year of employment without month, start and end months are imputed as June. Affected episodes are flagged and this imputation is disclosed in all reporting.

**Geographic analysis:** Geographic analysis is not performed at the episode level. LinkedIn does not provide historical location data for past role episodes, making episode-level geographic assignment unreliable across an 8-year study window.

**Post-2022 cohort thinning:** Post-2022 cohorts contain fewer completed episodes because many roles begun in that period remain ongoing at scrape time. Cohort trend estimates for 2022–2024 should be interpreted with caution and are displayed with low-confidence indicators in the cohort trend figure.

---

## 9. VERSION HISTORY

| Version | Date | Notes |
|---|---|---|
| v1.0 | 2026-05-18 | Pre-analysis registration |

---

*Hitch Partners Research | Methodology Note v1.0 | CISO Tenure Study, 2025*
