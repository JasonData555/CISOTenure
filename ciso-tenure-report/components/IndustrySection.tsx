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
  payload?: Array<{ payload?: GroupMedianRow & { label: string } }>
}

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

export default function IndustrySection({ data }: Props) {
  const chartRows = useMemo(
    () =>
      [...data]
        .sort((a, b) => b.median - a.median)
        .map(r => ({ ...r, label: `${r.median}mo · n=${r.n}` })),
    [data]
  )

  const maxMedian = Math.max(...chartRows.map(r => r.median), 1)

  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(chartRows.length * 40 + 20, 120)}>
        <BarChart
          data={chartRows}
          layout="vertical"
          margin={{ top: 0, right: 100, bottom: 0, left: 0 }}
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
            width={140}
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

      <p className="chart-caption mt-6">
        Figure 7. Kaplan-Meier median tenure by industry group (all episodes, censoring
        accounted for). Sectors consolidated from 31 raw categories. Healthcare/HealthTech
        vs. Enterprise Tech/Cloud pairwise log-rank p=0.014. Industry and company size are
        partially correlated — regulated industries skew toward larger organizations. No
        independent causal claim is made for industry in isolation.
      </p>

      <p className="chart-caption mt-4">
        ⚠ Industry and company size are correlated variables. The industry signal
        partially reflects organizational scale and governance maturity in regulated
        sectors, not industry membership alone.
      </p>
    </div>
  )
}
