'use client'

import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import type { KmSurvivalRow, KeyFinding } from '@/data/types'

interface Props {
  data: KmSurvivalRow[]
  findings: KeyFinding[]
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ dataKey?: string; value?: number }>
  label?: number
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  const survProb = payload.find(p => p.dataKey === 'survival_prob')
  if (!survProb) return null
  const pct = ((survProb.value as number) * 100).toFixed(1)
  return (
    <div className="bg-white border border-[#D3D9D4] rounded-lg px-3 py-2 shadow-sm">
      <p className="font-sans text-xs text-[#0D2426] font-medium">
        Month {Math.round(label as number)}
      </p>
      <p className="font-sans text-xs text-[#6D8B8C]">
        {pct}% probability of remaining in role
      </p>
    </div>
  )
}

export default function SurvivalChart({ data, findings }: Props) {
  // Find median month from key findings
  const medianRow = findings.find(
    f => f.metric === 'Overall Median Tenure' && f.unit === 'months'
  )
  const medianMonths = medianRow ? parseFloat(medianRow.value) : 49

  if (!data.length) {
    return (
      <div className="h-80 flex items-center justify-center text-[#6D8B8C] text-sm font-sans">
        Loading chart data…
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={400}>
      <ComposedChart data={data} margin={{ top: 28, right: 20, bottom: 20, left: 10 }}>
        <CartesianGrid
          horizontal={true}
          vertical={false}
          stroke="#D3D9D4"
          strokeOpacity={0.5}
        />
        <XAxis
          dataKey="time_months"
          type="number"
          domain={[0, 84]}
          ticks={[0, 24, 48, 72, 84]}
          tickFormatter={v => `${v}`}
          label={{
            value: 'Months in Role',
            position: 'insideBottom',
            offset: -10,
            style: { fill: '#0D2426', fontSize: 11, fontFamily: 'var(--font-sans)' },
          }}
          tick={{ fill: '#0D2426', fontSize: 10 }}
          axisLine={{ stroke: '#D3D9D4' }}
          tickLine={false}
        />
        <YAxis
          domain={[0, 1.05]}
          tickFormatter={v => `${Math.round(v * 100)}%`}
          label={{
            value: 'Probability of Remaining',
            angle: -90,
            position: 'insideLeft',
            offset: 15,
            style: { fill: '#0D2426', fontSize: 11, fontFamily: 'var(--font-sans)' },
          }}
          tick={{ fill: '#0D2426', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          width={52}
        />
        <Tooltip content={<CustomTooltip />} />

        {/* CI band: lower fills white (masks below band) */}
        <Area
          dataKey="ci_lower"
          stroke="none"
          fill="white"
          fillOpacity={1}
          isAnimationActive={false}
          stackId="ci"
        />
        {/* CI band: upper_delta fills the band thickness */}
        <Area
          dataKey="ci_upper_delta"
          stroke="none"
          fill="#D3D9D4"
          fillOpacity={0.45}
          isAnimationActive={false}
          stackId="ci"
        />

        {/* Reference lines */}
        <ReferenceLine
          y={0.5}
          stroke="#6D8B8C"
          strokeDasharray="4 4"
          strokeWidth={1}
          label={{
            value: '50%',
            position: 'right',
            style: { fill: '#6D8B8C', fontSize: 9 },
          }}
        />
        <ReferenceLine
          x={medianMonths}
          stroke="#6D8B8C"
          strokeDasharray="4 4"
          strokeWidth={1}
          label={{
            value: `Median: ${medianMonths}mo`,
            position: 'top',
            style: { fill: '#0D2426', fontSize: 13, fontWeight: '500' },
          }}
        />

        {/* Main KM line */}
        <Line
          dataKey="survival_prob"
          stroke="#0D2426"
          strokeWidth={2.5}
          dot={false}
          activeDot={{ r: 4, fill: 'white', stroke: '#0D2426', strokeWidth: 2 }}
          isAnimationActive={false}
          type="stepAfter"
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
