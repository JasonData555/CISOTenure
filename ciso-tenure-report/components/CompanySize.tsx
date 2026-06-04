'use client'

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  LabelList,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { useMemo } from 'react'
import type { GroupMedianRow } from '@/data/types'

interface Props {
  data: GroupMedianRow[]
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ payload?: GroupMedianRow }>
}

const SIZE_DISPLAY_ORDER = ['Small', 'Mid-Small', 'Mid-Market', 'Large', 'Enterprise']

const CARD_COLORS = [
  'border-l-hitchBlueGray',
  'border-l-hitchMedTeal',
  'border-l-hitchTeal',
  'border-l-hitchDarkTeal',
  'border-l-hitchDarkTeal',
]

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.[0]) return null
  const d = payload[0].payload as GroupMedianRow
  return (
    <div className="bg-white border border-[#D3D9D4] rounded-lg px-3 py-2 shadow-sm">
      <p className="font-sans text-xs text-[#0D2426] font-medium">{d.group}</p>
      <p className="font-sans text-xs text-[#6D8B8C]">{d.median}mo · n={d.n}</p>
    </div>
  )
}

export default function CompanySize({ data }: Props) {
  const chartRows = useMemo(
    () =>
      [...data]
        .sort((a, b) => b.median - a.median)
        .map(r => ({ ...r, label: `${r.median}mo · n=${r.n}` })),
    [data]
  )

  const cardRows = useMemo(
    () =>
      SIZE_DISPLAY_ORDER
        .map(g => data.find(r => r.group === g))
        .filter((r): r is GroupMedianRow => r !== undefined),
    [data]
  )

  const maxMedian = Math.max(...chartRows.map(r => r.median), 1)

  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(chartRows.length * 40 + 20, 120)}>
        <BarChart
          data={chartRows}
          layout="vertical"
          margin={{ top: 0, right: 80, bottom: 0, left: 0 }}
        >
          <XAxis
            type="number"
            domain={[0, Math.ceil(maxMedian / 10) * 10]}
            tickFormatter={v => `${v}mo`}
            tick={{ fill: '#6D8B8C', fontSize: 9 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            dataKey="group"
            type="category"
            tick={{ fill: '#0D2426', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            width={110}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="median" radius={[0, 3, 3, 0]} isAnimationActive={false}>
            {chartRows.map((_, i) => (
              <Cell key={i} fill="#0D2426" fillOpacity={0.85} />
            ))}
            <LabelList
              dataKey="label"
              position="right"
              style={{ fill: '#6D8B8C', fontSize: 9 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Stat callout cards in size order */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mt-8">
        {cardRows.map((row, i) => (
          <div
            key={row.group}
            className={`bg-white rounded-2xl border border-hitchLightGray border-l-4 ${CARD_COLORS[i] ?? 'border-l-hitchDarkTeal'} p-6`}
          >
            <div className="mb-3">
              <span className="font-serif text-4xl text-hitchDarkTeal leading-none">
                {row.median}
                <span className="text-hitchMedTeal text-xl align-super ml-1">mo</span>
              </span>
            </div>
            <p className="font-sans font-medium text-hitchDarkTeal text-sm mb-1">
              {row.group}
            </p>
            <p className="font-sans text-hitchBlueGray text-xs">
              n={row.n} completed episodes
            </p>
          </div>
        ))}
      </div>

      <p className="chart-caption mt-6">
        Figure 6. Kaplan-Meier median tenure by company size tier (all episodes, censoring
        accounted for). Size tiers consolidated from 9 raw categories into 5 groups.
        Directional pattern consistent across datasets; log-rank p=0.60 — treat as
        indicative, not inferential.
      </p>

      <p className="chart-caption mt-4">
        ⚠ Company size data has limited coverage in this dataset. Treat size-based
        findings as directional only. No causal claims are made.
      </p>
    </div>
  )
}
