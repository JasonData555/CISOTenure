import type { KeyFinding } from '@/data/types'

interface Props {
  findings: KeyFinding[]
}

function findValue(findings: KeyFinding[], metric: string, unit?: string): string {
  const row = findings.find(
    f => f.metric === metric && (!unit || f.unit === unit)
  )
  return row?.value ?? '—'
}

export default function Hero({ findings }: Props) {
  const nEpisodes     = findValue(findings, 'Overall Median Tenure', 'months')
  const totalEpisodes = findings.find(f => f.metric === 'Overall Median Tenure' && f.unit === 'months')
  const nEp           = totalEpisodes?.n_episodes ?? '1,549'
  const nComp         = totalEpisodes?.n_completed ?? '1,163'
  const pValue        = findValue(findings, 'Log-rank p-value')
  const censorRate    = findValue(findings, 'Censoring Rate')

  const META = [
    { label: 'Episodes',   value: nEp },
    { label: 'Completed',  value: nComp },
    { label: 'Window',     value: '2017–2025' },
    { label: 'Method',     value: 'Kaplan-Meier' },
    { label: 'Published',  value: 'May 2025' },
  ]

  return (
    <section className="bg-white pt-16 pb-14 px-6">
      <div className="max-w-4xl mx-auto">
        {/* Eyebrow */}
        <div className="flex items-center gap-3 mb-6">
          <div className="w-5 h-px bg-hitchMedTeal" />
          <p className="text-hitchMedTeal font-sans font-medium text-xs tracking-widest uppercase">
            CISO Tenure Study · North America · 2025
          </p>
        </div>

        {/* Headline */}
        <h1 className="font-serif text-hitchDarkTeal text-4xl md:text-[52px] leading-[1.08] mb-6">
          How Long Does a CISO{' '}
          <em className="not-italic italic text-hitchTeal">Actually</em> Last?
        </h1>

        {/* Subhead */}
        <p className="font-sans font-light text-hitchBlueGray text-base md:text-[17px] leading-relaxed max-w-[540px] mb-10">
          Eight years of work history across 1,200 North American security leaders
          — the most rigorous study of CISO tenure ever published.
        </p>

        {/* Meta strip */}
        <div className="inline-flex border border-hitchLightGray rounded-lg overflow-hidden">
          {META.map((item, i) => (
            <div
              key={item.label}
              className={`px-4 py-3 flex flex-col items-center ${
                i < META.length - 1 ? 'border-r border-hitchLightGray' : ''
              }`}
            >
              <span className="font-sans font-medium text-hitchDarkTeal text-sm leading-none">
                {item.value}
              </span>
              <span className="font-sans text-[10px] text-hitchBlueGray tracking-wide uppercase mt-1">
                {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
