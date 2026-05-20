'use client'

import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { useMemo } from 'react'
import type { KmEraRow } from '@/data/types'

interface Props {
  data: KmEraRow[]
  pValue: number
  eraCounts: Record<string, number>
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ name?: string; value?: number }>
  label?: number
}

const ERA_STYLE = {
  'Pre-COVID': {
    color: '#0D2426',
    dash: undefined as string | undefined,
    width: 2.5,
    label: 'Pre-COVID',
  },
  'COVID': {
    color: '#235857',
    dash: '7 3',
    width: 2,
    label: 'COVID',
  },
  'Post-COVID': {
    color: '#3B8A7F',
    dash: '2 4',
    width: 2,
    label: 'Post-COVID',
  },
}

type EraKey = keyof typeof ERA_STYLE

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-[#D3D9D4] rounded-lg px-3 py-2 shadow-sm min-w-[160px]">
      <p className="font-sans text-xs text-[#0D2426] font-medium mb-1">
        Month {Math.round(label as number)}
      </p>
      {payload.map(p => {
        const style = ERA_STYLE[p.name as EraKey]
        return (
          <p key={p.name} className="font-sans text-xs" style={{ color: style?.color ?? '#6D8B8C' }}>
            {p.name}: {((p.value as number) * 100).toFixed(1)}%
          </p>
        )
      })}
    </div>
  )
}

export default function EraChart({ data, pValue, eraCounts }: Props) {
  // Pivot: one row per time_months with all three era survival_probs
  const pivoted = useMemo(() => {
    const byMonth = new Map<number, Record<string, number>>()
    for (const row of data) {
      if (!byMonth.has(row.time_months)) byMonth.set(row.time_months, {})
      byMonth.get(row.time_months)![row.era] = row.survival_prob
    }
    return Array.from(byMonth.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([time_months, vals]) => ({ time_months, ...vals }))
  }, [data])

  if (!data.length) {
    return (
      <div className="h-80 flex items-center justify-center text-[#6D8B8C] text-sm font-sans">
        Loading chart data…
      </div>
    )
  }

  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={pivoted} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
          <CartesianGrid horizontal={true} vertical={false} stroke="#D3D9D4" strokeOpacity={0.5} />
          <XAxis
            dataKey="time_months"
            type="number"
            domain={[0, 84]}
            ticks={[0, 24, 48, 72, 84]}
            label={{
              value: 'Months in Role',
              position: 'insideBottom',
              offset: -10,
              style: { fill: '#0D2426', fontSize: 11 },
            }}
            tick={{ fill: '#0D2426', fontSize: 10 }}
            axisLine={{ stroke: '#D3D9D4' }}
            tickLine={false}
          />
          <YAxis
            domain={[0, 1.05]}
            tickFormatter={v => `${Math.round(v * 100)}%`}
            tick={{ fill: '#0D2426', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <Tooltip content={<CustomTooltip />} />

          {(Object.keys(ERA_STYLE) as EraKey[]).map(era => (
            <Line
              key={era}
              dataKey={era}
              name={era}
              stroke={ERA_STYLE[era].color}
              strokeWidth={ERA_STYLE[era].width}
              strokeDasharray={ERA_STYLE[era].dash}
              dot={false}
              activeDot={{ r: 4, fill: 'white', stroke: ERA_STYLE[era].color, strokeWidth: 2 }}
              isAnimationActive={false}
              type="stepAfter"
              connectNulls={false}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>

      {/* In-chart legend box — top right */}
      <div className="absolute top-4 right-6 bg-white border border-[#D3D9D4] rounded-lg px-4 py-3 text-xs font-sans shadow-sm">
        {(Object.keys(ERA_STYLE) as EraKey[]).map(era => (
          <div key={era} className="flex items-center gap-2 mb-1 last:mb-0">
            <svg width="20" height="10">
              <line
                x1="0" y1="5" x2="20" y2="5"
                stroke={ERA_STYLE[era].color}
                strokeWidth={ERA_STYLE[era].width}
                strokeDasharray={ERA_STYLE[era].dash ?? ''}
              />
            </svg>
            <span style={{ color: ERA_STYLE[era].color }} className="font-medium">
              {ERA_STYLE[era].label}
            </span>
            <span className="text-[#6D8B8C]">n={eraCounts[era] ?? '—'}</span>
          </div>
        ))}
        <div className="mt-2 pt-2 border-t border-[#D3D9D4] text-[#6D8B8C]">
          Log-rank p = {pValue.toFixed(4)}
        </div>
      </div>
    </div>
  )
}
