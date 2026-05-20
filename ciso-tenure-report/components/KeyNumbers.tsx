import type { KeyFinding } from '@/data/types'

interface Props {
  findings: KeyFinding[]
}

function findRow(findings: KeyFinding[], metric: string, unit?: string): KeyFinding | undefined {
  return findings.find(f => f.metric === metric && (!unit || f.unit === unit))
}

export default function KeyNumbers({ findings }: Props) {
  const overallRow = findRow(findings, 'Overall Median Tenure', 'months')
  const preCovidRow = findRow(findings, 'Pre-COVID Median', 'months')
  const postCovidRow = findRow(findings, 'Post-COVID Median', 'months')
  const hazardRow  = findRow(findings, 'Peak Hazard Month')

  const median   = overallRow ? parseFloat(overallRow.value) : 49
  const preMed   = preCovidRow ? parseFloat(preCovidRow.value) : 51
  const postMed  = postCovidRow ? parseFloat(postCovidRow.value) : 37
  const peakMonth = hazardRow ? parseInt(hazardRow.value) : 26

  // Era change: Post-COVID vs Pre-COVID
  const eraChangePct = Math.round(((postMed - preMed) / preMed) * 100)
  const eraDecreased = eraChangePct < 0

  const cards = [
    {
      borderColor: 'border-l-hitchDarkTeal',
      number: (
        <span className="font-serif text-5xl md:text-6xl text-hitchDarkTeal leading-none">
          {median}
          <span className="text-hitchMedTeal text-2xl align-super ml-1">mo</span>
        </span>
      ),
      label: 'Median CISO Tenure',
      context: `Across ${overallRow?.n_completed ?? '1,163'} completed episodes`,
    },
    {
      borderColor: 'border-l-hitchMedTeal',
      number: (
        <span className={`font-serif text-5xl md:text-6xl leading-none ${eraDecreased ? 'text-hitchMedTeal' : 'text-hitchTeal'}`}>
          {eraDecreased ? '↓' : '↑'}{Math.abs(eraChangePct)}
          <span className="text-2xl align-super ml-1">%</span>
        </span>
      ),
      label: 'Tenure Change Since Pre-COVID',
      context: `Pre-COVID ${preMed}mo → Post-COVID ${postMed}mo`,
    },
    {
      borderColor: 'border-l-hitchTeal',
      number: (
        <span className="font-serif text-5xl md:text-6xl text-hitchDarkTeal leading-none">
          Mo&nbsp;{peakMonth}
        </span>
      ),
      label: 'Peak Exit Hazard',
      context: 'Highest exit probability by month',
    },
  ]

  return (
    <section className="bg-gray-50 border-y border-hitchLightGray py-12 px-6">
      <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6">
        {cards.map((card, i) => (
          <div
            key={i}
            className={`bg-white rounded-2xl border border-hitchLightGray border-l-4 ${card.borderColor} p-8`}
          >
            <div className="mb-3">{card.number}</div>
            <p className="font-sans font-medium text-hitchDarkTeal text-sm mb-1">
              {card.label}
            </p>
            <p className="font-sans text-hitchBlueGray text-xs">{card.context}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
