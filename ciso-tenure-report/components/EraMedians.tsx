import type { KeyFinding } from '@/data/types'

interface Props {
  findings: KeyFinding[]
}

function findMonths(findings: KeyFinding[], metric: string): number {
  const row = findings.find(f => f.metric === metric && f.unit === 'months')
  return row ? parseFloat(row.value) : 0
}

function findCompleted(findings: KeyFinding[], metric: string): string {
  const row = findings.find(f => f.metric === metric && f.unit === 'months')
  return row?.n_completed ?? '—'
}

const ERA_CONFIG = [
  {
    key:    'Pre-COVID Median',
    label:  'Pre-COVID',
    sub:    'Before March 2020',
    color:  'text-hitchDarkTeal',
    bg:     'bg-hitchDarkTeal',
    border: 'border-hitchDarkTeal',
  },
  {
    key:    'COVID Median',
    label:  'COVID Era',
    sub:    'Mar 2020 – Dec 2021',
    color:  'text-hitchTeal',
    bg:     'bg-hitchTeal',
    border: 'border-hitchTeal',
  },
  {
    key:    'Post-COVID Median',
    label:  'Post-COVID',
    sub:    'After Dec 2021',
    color:  'text-hitchMedTeal',
    bg:     'bg-hitchMedTeal',
    border: 'border-hitchMedTeal',
  },
]

export default function EraMedians({ findings }: Props) {
  const values = ERA_CONFIG.map(e => findMonths(findings, e.key))
  const maxVal = Math.max(...values.filter(v => v > 0), 1)

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12">
      {ERA_CONFIG.map((era, i) => {
        const months    = values[i]
        const barWidth  = maxVal > 0 ? (months / maxVal) * 100 : 0
        const completed = findCompleted(findings, era.key)
        const years     = (months / 12).toFixed(1)

        return (
          <div key={era.key} className="flex flex-col">
            <p className={`font-sans font-medium text-xs tracking-widest uppercase mb-1 ${era.color}`}>
              {era.label}
            </p>
            <p className="font-sans text-hitchBlueGray text-xs mb-3">{era.sub}</p>
            <div className="flex items-baseline gap-2 mb-3">
              <span className={`font-serif text-5xl leading-none ${era.color}`}>
                {months > 0 ? months : '—'}
              </span>
              <span className="font-sans text-hitchBlueGray text-sm">
                mo&nbsp;·&nbsp;{years}&nbsp;yrs
              </span>
            </div>
            {/* Proportional bar */}
            <div className="h-2 bg-hitchLightGray rounded-full overflow-hidden mb-2">
              <div
                className={`h-full rounded-full ${era.bg} transition-all duration-500`}
                style={{ width: `${barWidth}%` }}
              />
            </div>
            <p className="font-sans text-hitchBlueGray text-xs">
              n={completed} completed episodes
            </p>
          </div>
        )
      })}
    </div>
  )
}
