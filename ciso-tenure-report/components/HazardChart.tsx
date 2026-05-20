'use client'

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import type { HazardRow, KeyFinding } from '@/data/types'

interface Props {
  data: HazardRow[]
  findings: KeyFinding[]
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ dataKey?: string; value?: number }>
  label?: number
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  const val = payload.find(p => p.dataKey === 'hazard_smoothed')
  return (
    <div className="bg-white border border-[#D3D9D4] rounded-lg px-3 py-2 shadow-sm">
      <p className="font-sans text-xs text-[#0D2426] font-medium">
        Month {Math.round(label as number)}
      </p>
      <p className="font-sans text-xs text-[#6D8B8C]">
        Hazard: {val ? (val.value as number).toFixed(5) : '—'}
      </p>
    </div>
  )
}

function LowYAxisTick({ x, y, index, visibleTicksCount }: {
  x?: number; y?: number; index?: number; visibleTicksCount?: number
}) {
  const isBottom = index === 0
  const isTop    = index === (visibleTicksCount ?? 1) - 1
  if (!isBottom && !isTop) return null
  return (
    <text
      x={x}
      y={y}
      dy={isBottom ? 4 : 4}
      textAnchor="end"
      fill="#0D2426"
      fontSize={10}
      fontFamily="var(--font-sans)"
    >
      {isTop ? 'High' : 'Low'}
    </text>
  )
}

export default function HazardChart({ data, findings }: Props) {
  const peakRow     = data.find(r => r.is_peak)
  const peakMonth   = peakRow?.time_months ?? 26
  const lowRiskRow  = data.find(r => r.is_low_risk_threshold)
  const lowRiskMonth = lowRiskRow?.time_months ?? null

  const completedRow = findings.find(f => f.metric === 'Peak Hazard Month')
  const nCompleted   = completedRow?.n_completed ?? '1,163'

  if (!data.length) {
    return (
      <div className="h-80 flex items-center justify-center text-[#6D8B8C] text-sm font-sans">
        Loading chart data…
      </div>
    )
  }

  return (
    <div>
      <ResponsiveContainer width="100%" height={360}>
        <AreaChart data={data} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
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
            label={{
              value: 'Exit hazard',
              angle: -90,
              position: 'insideLeft',
              offset: 15,
              style: { fill: '#0D2426', fontSize: 11 },
            }}
            tick={<LowYAxisTick />}
            axisLine={false}
            tickLine={false}
            width={52}
          />
          <Tooltip content={<CustomTooltip />} />

          {/* Peak reference line */}
          <ReferenceLine
            x={peakMonth}
            stroke="#3B8A7F"
            strokeDasharray="4 4"
            strokeWidth={1.5}
            label={{
              value: `Peak: Month ${peakMonth}`,
              position: 'top',
              style: { fill: '#0D2426', fontSize: 9, fontWeight: '600' },
            }}
          />

          {/* Low-risk reference line */}
          {lowRiskMonth !== null && (
            <ReferenceLine
              x={lowRiskMonth}
              stroke="#6D8B8C"
              strokeDasharray="3 3"
              strokeWidth={1}
              label={{
                value: `Risk subsides: Mo ${lowRiskMonth}`,
                position: 'top',
                style: { fill: '#0D2426', fontSize: 9 },
              }}
            />
          )}

          <Area
            dataKey="hazard_smoothed"
            stroke="#0D2426"
            strokeWidth={2.5}
            fill="#0D2426"
            fillOpacity={0.06}
            dot={false}
            isAnimationActive={false}
            type="monotone"
          />
        </AreaChart>
      </ResponsiveContainer>

      {/* Stat tiles */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
        <div className="bg-gray-50 border border-hitchLightGray rounded-xl px-4 py-3">
          <p className="eyebrow">Peak exit month</p>
          <p className="font-serif text-hitchDarkTeal text-2xl">Month {peakMonth}</p>
          <p className="font-sans text-hitchBlueGray text-xs mt-1">Highest exit probability</p>
        </div>
        <div className="bg-gray-50 border border-hitchLightGray rounded-xl px-4 py-3">
          <p className="eyebrow">Risk subsides</p>
          <p className="font-serif text-hitchDarkTeal text-2xl">
            {lowRiskMonth !== null ? `Month ${lowRiskMonth}` : '—'}
          </p>
          <p className="font-sans text-hitchBlueGray text-xs mt-1">
            Below 50% of peak, sustained
          </p>
        </div>
        <div className="bg-gray-50 border border-hitchLightGray rounded-xl px-4 py-3">
          <p className="eyebrow">Completed episodes</p>
          <p className="font-serif text-hitchDarkTeal text-2xl">n={nCompleted}</p>
          <p className="font-sans text-hitchBlueGray text-xs mt-1">Observed exit events</p>
        </div>
      </div>
    </div>
  )
}
