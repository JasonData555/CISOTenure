'use client'

import {
  ComposedChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  ResponsiveContainer,
} from 'recharts'
import type { CohortRow } from '@/data/types'

interface TooltipPayload {
  payload?: CohortRow
}

interface CustomTooltipProps {
  active?: boolean
  payload?: TooltipPayload[]
}

interface Props {
  data: CohortRow[]
}

// Era color by year
function eraColor(year: number, lowConf: boolean): string {
  if (lowConf) return '#6D8B8C'
  if (year <= 2019) return '#0D2426'
  if (year <= 2021) return '#235857'
  return '#3B8A7F'
}

// Custom dot-and-whisker shape rendered as SVG
interface ShapeProps {
  cx?: number
  cy?: number
  payload?: CohortRow & { yLow?: number; yHigh?: number }
  yAxis?: { scale: (v: number) => number }
}

function DotWhisker({ cx = 0, cy = 0, payload, yAxis }: ShapeProps) {
  if (!payload || !yAxis?.scale) return null

  const color    = eraColor(payload.start_year, payload.low_confidence)
  const yLow     = yAxis.scale(payload.ci_lower)
  const yHigh    = yAxis.scale(payload.ci_upper)
  const capHalf  = 6
  const r        = 6

  return (
    <g>
      {/* Whisker vertical line */}
      <line x1={cx} x2={cx} y1={yHigh} y2={yLow} stroke={color} strokeWidth={1.5} />
      {/* Cap at top (high CI) */}
      <line x1={cx - capHalf} x2={cx + capHalf} y1={yHigh} y2={yHigh} stroke={color} strokeWidth={1.5} />
      {/* Cap at bottom (low CI) */}
      <line x1={cx - capHalf} x2={cx + capHalf} y1={yLow} y2={yLow} stroke={color} strokeWidth={1.5} />
      {/* Median dot */}
      {payload.low_confidence ? (
        <circle
          cx={cx} cy={cy} r={r}
          fill="white"
          stroke={color}
          strokeWidth={1.8}
          strokeDasharray="3 2"
        />
      ) : (
        <circle cx={cx} cy={cy} r={r} fill={color} />
      )}
      {/* n= label above */}
      <text
        x={cx}
        y={yHigh - 8}
        textAnchor="middle"
        fontSize={9}
        fill={color}
        fontFamily="var(--font-sans)"
      >
        n={payload.n_completed}
      </text>
    </g>
  )
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.[0]) return null
  const d = payload[0].payload as CohortRow
  return (
    <div className="bg-white border border-[#D3D9D4] rounded-lg px-3 py-2 shadow-sm">
      <p className="font-sans text-xs text-[#0D2426] font-medium mb-1">{d.start_year}</p>
      <p className="font-sans text-xs text-[#6D8B8C]">Median: {d.median_months}mo</p>
      <p className="font-sans text-xs text-[#6D8B8C]">
        95% CI: [{d.ci_lower?.toFixed(0)}, {d.ci_upper?.toFixed(0)}]
      </p>
      <p className="font-sans text-xs text-[#6D8B8C]">n={d.n_completed} completed</p>
      {d.low_confidence && (
        <p className="font-sans text-xs text-[#3B8A7F] mt-1">⚠ Low confidence (n&lt;30)</p>
      )}
    </div>
  )
}

export default function CohortChart({ data }: Props) {
  const lowConfYears = data.filter(r => r.low_confidence).map(r => r.start_year)

  if (!data.length) {
    return (
      <div className="h-80 flex items-center justify-center text-[#6D8B8C] text-sm font-sans">
        Loading chart data…
      </div>
    )
  }

  return (
    <div>
      <ResponsiveContainer width="100%" height={380}>
        <ComposedChart
          data={data}
          margin={{ top: 30, right: 20, bottom: 20, left: 10 }}
        >
          <CartesianGrid horizontal={true} vertical={false} stroke="#D3D9D4" strokeOpacity={0.5} />

          {/* COVID era shading */}
          <ReferenceArea
            x1={2019.5}
            x2={2021.5}
            fill="#D3D9D4"
            fillOpacity={0.25}
            label={{
              value: 'COVID era',
              position: 'insideTop',
              style: { fill: '#6D8B8C', fontSize: 9, fontStyle: 'italic' },
            }}
          />

          <XAxis
            dataKey="start_year"
            type="number"
            domain={[2016.5, 2024.5]}
            ticks={[2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]}
            tickFormatter={v => String(v)}
            label={{
              value: 'Cohort Start Year',
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
              value: 'Months in Role',
              angle: -90,
              position: 'insideLeft',
              offset: 15,
              style: { fill: '#0D2426', fontSize: 11 },
            }}
            tick={{ fill: '#0D2426', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            width={52}
            domain={['auto', 'auto']}
          />
          <Tooltip content={<CustomTooltip />} />

          <Scatter
            dataKey="median_months"
            shape={(props: unknown) => <DotWhisker {...(props as ShapeProps)} />}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {lowConfYears.length > 0 && (
        <p className="chart-caption mt-4">
          ⚠ Low confidence (n&lt;30 completed episodes):{' '}
          {lowConfYears.join(', ')}. Interpret CI bands for these years with caution.
        </p>
      )}
    </div>
  )
}
