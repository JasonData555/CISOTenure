import {
  loadKeyFindings,
  loadKmSurvival,
  loadKmEra,
  loadHazard,
  loadCohortTrend,
  loadComposition,
} from '@/data/loader'

import Nav               from '@/components/Nav'
import Hero              from '@/components/Hero'
import KeyNumbers        from '@/components/KeyNumbers'
import SurvivalChart     from '@/components/SurvivalChart'
import EraMedians        from '@/components/EraMedians'
import EraChart          from '@/components/EraChart'
import HazardChart       from '@/components/HazardChart'
import CohortChart       from '@/components/CohortChart'
import SampleComposition from '@/components/SampleComposition'
import ShareBar          from '@/components/ShareBar'
import Methodology       from '@/components/Methodology'
import Footer            from '@/components/Footer'

// Render entire page statically at build time from CSV files
export const dynamic = 'force-static'

export default async function Page() {
  const findings    = loadKeyFindings()
  const kmSurvival  = loadKmSurvival()
  const kmEra       = loadKmEra()
  const hazard      = loadHazard()
  const cohort      = loadCohortTrend()
  const composition = loadComposition()

  // Extract p-value for EraChart legend
  const pValueRow = findings.find(f => f.metric === 'Log-rank p-value')
  const pValue    = pValueRow ? parseFloat(pValueRow.value) : 0.0077

  // Era n= completed counts for EraChart legend
  const eraCounts: Record<string, number> = {
    'Pre-COVID':  parseInt(findings.find(f => f.metric === 'Pre-COVID Median' && f.unit === 'months')?.n_completed ?? '1006'),
    'COVID':      parseInt(findings.find(f => f.metric === 'COVID Median' && f.unit === 'months')?.n_completed ?? '89'),
    'Post-COVID': parseInt(findings.find(f => f.metric === 'Post-COVID Median' && f.unit === 'months')?.n_completed ?? '68'),
  }

  return (
    <>
      <Nav />
      <main>
        {/* Hero */}
        <Hero findings={findings} />

        {/* Key Numbers */}
        <KeyNumbers findings={findings} />

        {/* Figure 1 — Overall Survival Curve */}
        <section id="survival" className="py-20 px-6">
          <div className="max-w-6xl mx-auto">
            <div className="mb-10">
              <p className="section-number">01 — Survival Analysis</p>
              <h2 className="section-heading">Overall CISO Tenure Curve</h2>
              <p className="section-subhead">
                Kaplan-Meier estimate across all 1,549 episodes.
                Shaded band shows 95% Greenwood confidence interval.
              </p>
            </div>
            <SurvivalChart data={kmSurvival} findings={findings} />
            <p className="chart-caption">
              Figure 1. Kaplan-Meier survival curve, all episodes. Median tenure:{' '}
              {findings.find(f => f.metric === 'Overall Median Tenure' && f.unit === 'months')?.value ?? '49'}{' '}
              months. n=1,163 completed episodes, 386 censored (ongoing roles at scrape date).
              Clustering by profile_id applied to all standard error estimates.
            </p>
          </div>
        </section>

        {/* Figure 2 — Era Comparison */}
        <section id="eras" className="py-20 px-6 bg-gray-50">
          <div className="max-w-6xl mx-auto">
            <div className="mb-10">
              <p className="section-number">02 — Era Comparison</p>
              <h2 className="section-heading">Tenure Has Shortened Across Eras</h2>
              <p className="section-subhead">
                Pre-COVID, COVID, and Post-COVID cohorts show a statistically significant
                decline in median tenure (log-rank p={pValue.toFixed(4)}).
              </p>
            </div>

            {/* Era medians summary numbers */}
            <EraMedians findings={findings} />

            {/* Era KM chart */}
            <EraChart data={kmEra} pValue={pValue} eraCounts={eraCounts} />
            <p className="chart-caption mt-6">
              Figure 2. Kaplan-Meier curves by era. KM curves shown for visual comparison;
              primary median figures derived from KM estimator.{' '}
              <strong>
                COVID (n=89) and Post-COVID (n=68) completed episodes are below the
                100-episode threshold for high-confidence interval estimation — interpret
                these curves with appropriate uncertainty.
              </strong>
            </p>
          </div>
        </section>

        {/* Figure 3 — Hazard Rate */}
        <section id="hazard" className="py-20 px-6">
          <div className="max-w-6xl mx-auto">
            <div className="mb-10">
              <p className="section-number">03 — Exit Hazard</p>
              <h2 className="section-heading">The Two-Year Cliff</h2>
              <p className="section-subhead">
                Exit probability peaks at month 26 — the 2-year mark — then gradually
                declines. Nelson-Aalen estimator with 6-month rolling average.
              </p>
            </div>
            <HazardChart data={hazard} findings={findings} />
            <p className="chart-caption mt-6">
              Figure 3. Nelson-Aalen incremental hazard, 6-month rolling average smoother.
              Y-axis suppressed to focus on shape. n=1,163 completed exit events.
            </p>
          </div>
        </section>

        {/* Figure 4 — Cohort Trend */}
        <section id="cohort" className="py-20 px-6 bg-gray-50">
          <div className="max-w-6xl mx-auto">
            <div className="mb-10">
              <p className="section-number">04 — Cohort Trend</p>
              <h2 className="section-heading">Shorter Tenures for Recent Cohorts</h2>
              <p className="section-subhead">
                Median completed tenure by start year, with bootstrapped 95% confidence
                intervals. Open circles indicate low-confidence cohorts (n&lt;30).
              </p>
            </div>
            <CohortChart data={cohort} />
            <p className="chart-caption mt-6">
              Figure 4. Median completed tenure (duration_months) by cohort start year.
              Bootstrap 95% CI, profile-level resampling (n=1,000 iterations).
              Completed episodes only — censored observations excluded from this analysis.
            </p>
          </div>
        </section>

        {/* Figure 5 — Sample Composition */}
        <section id="sample" className="py-20 px-6">
          <div className="max-w-6xl mx-auto">
            <div className="mb-10">
              <p className="section-number">05 — Sample Composition</p>
              <h2 className="section-heading">Who&rsquo;s in the Study?</h2>
              <p className="section-subhead">
                Descriptive breakdown of the sample by company size, industry, and region.
                These variables are not used in survival analysis.
              </p>
            </div>
            <SampleComposition data={composition} />
          </div>
        </section>

        {/* Share Bar */}
        <ShareBar />

        {/* Methodology */}
        <Methodology />
      </main>

      <Footer />
    </>
  )
}
