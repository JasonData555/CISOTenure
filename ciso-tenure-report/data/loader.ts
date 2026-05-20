/**
 * loader.ts — Server-only data loader for CISO Tenure Report
 *
 * Reads CSV files from the data path at build time using Node.js fs.
 * NEVER import this file from any 'use client' component.
 *
 * Data path is controlled by NEXT_PUBLIC_DATA_PATH env var:
 *   Development: public/sample-data  (placeholder CSVs)
 *   Production:  public/data         (copied from Python pipeline output)
 */

import fs from 'fs'
import path from 'path'
import type {
  KeyFinding,
  KmSurvivalRow,
  KmEraRow,
  HazardRow,
  CohortRow,
  CompositionRow,
} from './types'

const DATA_PATH = process.env.NEXT_PUBLIC_DATA_PATH ?? 'public/sample-data'

function resolveDataPath(filename: string): string {
  if (path.isAbsolute(DATA_PATH)) {
    return path.join(DATA_PATH, filename)
  }
  return path.join(process.cwd(), DATA_PATH, filename)
}

function parseBool(val: string): boolean {
  return ['true', 'True', '1', 'yes'].includes((val ?? '').trim())
}

function readCsvRows(filename: string): { headers: string[]; rows: string[][] } {
  const filePath = resolveDataPath(filename)
  if (!fs.existsSync(filePath)) {
    console.warn(`[loader] Missing data file: ${filePath}`)
    return { headers: [], rows: [] }
  }
  const raw = fs.readFileSync(filePath, 'utf-8')
  const lines = raw.trim().split('\n').filter(l => l.trim().length > 0)
  if (lines.length < 2) return { headers: [], rows: [] }
  const headers = lines[0].split(',').map(h => h.trim())
  const rows = lines.slice(1).map(line => line.split(',').map(c => c.trim()))
  return { headers, rows }
}

function col(headers: string[], row: string[], name: string): string {
  const idx = headers.indexOf(name)
  return idx >= 0 ? (row[idx] ?? '') : ''
}

// ---------------------------------------------------------------------------

export function loadKeyFindings(): KeyFinding[] {
  const { headers, rows } = readCsvRows('key_findings.csv')
  if (!headers.length) return []
  return rows.map(row => ({
    metric:      col(headers, row, 'metric'),
    value:       col(headers, row, 'value'),
    unit:        col(headers, row, 'unit'),
    n_episodes:  col(headers, row, 'n_episodes'),
    n_completed: col(headers, row, 'n_completed'),
    notes:       col(headers, row, 'notes'),
  }))
}

export function loadKmSurvival(): KmSurvivalRow[] {
  const { headers, rows } = readCsvRows('km_survival_data.csv')
  if (!headers.length) return []
  return rows
    .map(row => {
      const ci_lower = parseFloat(col(headers, row, 'ci_lower'))
      const ci_upper = parseFloat(col(headers, row, 'ci_upper'))
      return {
        time_months:   parseFloat(col(headers, row, 'time_months')),
        survival_prob: parseFloat(col(headers, row, 'survival_prob')),
        ci_lower,
        ci_upper,
        // Derived: band thickness for stacked Area chart
        ci_upper_delta: isNaN(ci_upper) || isNaN(ci_lower) ? 0 : ci_upper - ci_lower,
      }
    })
    .filter(r => !isNaN(r.time_months))
}

export function loadKmEra(): KmEraRow[] {
  const { headers, rows } = readCsvRows('km_era_data.csv')
  if (!headers.length) return []
  return rows
    .map(row => ({
      time_months:   parseFloat(col(headers, row, 'time_months')),
      era:           col(headers, row, 'era') as KmEraRow['era'],
      survival_prob: parseFloat(col(headers, row, 'survival_prob')),
      ci_lower:      parseFloat(col(headers, row, 'ci_lower')),
      ci_upper:      parseFloat(col(headers, row, 'ci_upper')),
    }))
    .filter(r => !isNaN(r.time_months))
}

export function loadHazard(): HazardRow[] {
  const { headers, rows } = readCsvRows('hazard_data.csv')
  if (!headers.length) return []
  return rows
    .map(row => ({
      time_months:           parseFloat(col(headers, row, 'time_months')),
      hazard_rate:           parseFloat(col(headers, row, 'hazard_rate')),
      hazard_smoothed:       parseFloat(col(headers, row, 'hazard_smoothed')),
      is_peak:               parseBool(col(headers, row, 'is_peak')),
      is_low_risk_threshold: parseBool(col(headers, row, 'is_low_risk_threshold')),
    }))
    .filter(r => !isNaN(r.time_months))
}

export function loadCohortTrend(): CohortRow[] {
  const { headers, rows } = readCsvRows('cohort_trend.csv')
  if (!headers.length) return []
  return rows
    .map(row => ({
      start_year:     parseInt(col(headers, row, 'start_year')),
      median_months:  parseFloat(col(headers, row, 'median_months')),
      ci_lower:       parseFloat(col(headers, row, 'ci_lower')),
      ci_upper:       parseFloat(col(headers, row, 'ci_upper')),
      n_completed:    parseInt(col(headers, row, 'n_completed')),
      low_confidence: parseBool(col(headers, row, 'low_confidence')),
    }))
    .filter(r => !isNaN(r.start_year))
}

export function loadComposition(): CompositionRow[] {
  const { headers, rows } = readCsvRows('sample_composition_summary.csv')
  if (!headers.length) return []
  return rows.map(row => ({
    section_label: col(headers, row, 'section_label'),
    category:      col(headers, row, 'category') || '(Unknown)',
    n:             parseInt(col(headers, row, 'n')),
    pct:           parseFloat(col(headers, row, 'pct')),
  }))
}
