'use client'

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { useMemo } from 'react'
import type { CompositionRow } from '@/data/types'

interface Props {
  data: CompositionRow[]
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ payload?: CompositionRow }>
}

const SECTIONS = [
  { key: 'Company Size', label: 'Company Size' },
  { key: 'Industry',     label: 'Industry' },
  { key: 'Region',       label: 'Region' },
]

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.[0]) return null
  const d = payload[0].payload as CompositionRow
  return (
    <div className="bg-white border border-[#D3D9D4] rounded-lg px-3 py-2 shadow-sm">
      <p className="font-sans text-xs text-[#0D2426] font-medium">{d.category}</p>
      <p className="font-sans text-xs text-[#6D8B8C]">{d.pct}% · n={d.n}</p>
    </div>
  )
}

function SectionBar({ rows }: { rows: CompositionRow[] }) {
  const maxPct = Math.max(...rows.map(r => r.pct), 1)
  return (
    <ResponsiveContainer width="100%" height={Math.max(rows.length * 36 + 20, 120)}>
      <BarChart
        data={rows}
        layout="vertical"
        margin={{ top: 0, right: 40, bottom: 0, left: 0 }}
      >
        <XAxis
          type="number"
          domain={[0, Math.ceil(maxPct / 10) * 10]}
          tickFormatter={v => `${v}%`}
          tick={{ fill: '#6D8B8C', fontSize: 9 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          dataKey="category"
          type="category"
          tick={{ fill: '#0D2426', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          width={110}
        />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="pct" radius={[0, 3, 3, 0]} isAnimationActive={false}>
          {rows.map((_, i) => (
            <Cell key={i} fill="#0D2426" fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export default function SampleComposition({ data }: Props) {
  const bySection = useMemo(() => {
    const map: Record<string, CompositionRow[]> = {}
    for (const row of data) {
      if (!map[row.section_label]) map[row.section_label] = []
      map[row.section_label].push(row)
    }
    return map
  }, [data])

  return (
    <div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {SECTIONS.map(section => {
          const rows = bySection[section.key] ?? []
          return (
            <div key={section.key}>
              <p className="eyebrow mb-4">{section.label}</p>
              {rows.length > 0 ? (
                <SectionBar rows={rows} />
              ) : (
                <p className="font-sans text-xs text-hitchBlueGray italic">No data available</p>
              )}
            </div>
          )
        })}
      </div>

      <p className="chart-caption mt-6">
        Company size, industry, and region are <strong>descriptive only</strong> — these
        variables are not used for stratification or survival analysis. Region is 100%
        unknown because LinkedIn does not provide historical location data per episode.
        All survival estimates are derived from era classification (Pre-COVID / COVID /
        Post-COVID) only.
      </p>
    </div>
  )
}
