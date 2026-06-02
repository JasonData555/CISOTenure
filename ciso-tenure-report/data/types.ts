// TypeScript interfaces matching CSV column names exactly

export interface KeyFinding {
  metric: string
  value: string
  unit: string
  n_episodes: string
  n_completed: string
  notes: string
}

export interface KmSurvivalRow {
  time_months: number
  survival_prob: number
  ci_lower: number
  ci_upper: number
  // Derived field added by loader for CI band rendering
  ci_upper_delta: number
}

export interface KmEraRow {
  time_months: number
  era: 'Pre-COVID' | 'COVID' | 'Post-COVID'
  survival_prob: number
  ci_lower: number
  ci_upper: number
}

export interface HazardRow {
  time_months: number
  hazard_rate: number
  hazard_smoothed: number
  is_peak: boolean
  is_low_risk_threshold: boolean
}

export interface CohortRow {
  start_year: number
  median_months: number
  ci_lower: number
  ci_upper: number
  n_completed: number
  low_confidence: boolean
}

export interface CompositionRow {
  section_label: string
  category: string
  n: number
  pct: number
}

export interface GroupMedianRow {
  group: string
  median: number
  n: number
}
