const CARDS = [
  {
    label:   'Sample',
    content: `Hitch Partners' proprietary database of North American security leaders. Passive candidates are included; selection was determined by data completeness. Work histories were extracted from LinkedIn profiles via Apify. Only episodes with a confirmed start date and either a confirmed end date or an active role at scrape date were retained. n=1,549 episodes across 776 unique professionals.`,
  },
  {
    label:   'Statistical Method',
    content: `Primary survival analysis uses the Kaplan-Meier estimator with Greenwood confidence intervals. Era comparisons use the log-rank test. Median tenure is the KM estimate (or Cox baseline hazard where convergence was achieved). All models with clustered standard errors use clustering by profile_id to account for within-person correlation across multiple CISO episodes. Hazard rates are estimated via the Nelson-Aalen estimator with a 6-month rolling average smoother.`,
  },
  {
    label:   'Era Definitions',
    content: `Pre-COVID: episode start before January 2020. COVID: episode start between January 2020 and December 2021 (inclusive). Post-COVID: episode start after December 2021. Era classification is based on episode start date, not end date. This classification is the primary analytical variable; all other covariates are treated as descriptive-only.`,
  },
  {
    label:   'Limitations',
    content: `LinkedIn does not provide historical location data per episode; therefore region is descriptive-only and cannot be used for stratification or survival analysis. The COVID era (n=89 completed) and Post-COVID era (n=68 completed) sub-samples are below the 100-episode threshold for high-confidence interval estimation — findings should be interpreted with appropriate uncertainty. Missing month fields in start/end dates were imputed as June 6. Company size and industry are descriptive-only; no causal claims are made.`,
  },
]

export default function Methodology() {
  return (
    <section id="methodology" className="py-20 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="mb-12">
          <p className="section-number">Methodology</p>
          <h2 className="section-heading">How This Study Was Conducted</h2>
          <p className="section-subhead">
            Eight years of work history analyzed under strict statistical protocols
            designed for publication-grade accuracy.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {CARDS.map(card => (
            <div
              key={card.label}
              className="bg-gray-50 rounded-xl p-6 border border-hitchLightGray"
            >
              <p className="eyebrow">{card.label}</p>
              <p className="font-sans text-sm text-hitchDarkTeal leading-relaxed">
                {card.content}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
