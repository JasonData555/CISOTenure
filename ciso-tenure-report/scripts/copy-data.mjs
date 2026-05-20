/**
 * copy-data.mjs — prebuild script
 * Copies CSV outputs from the Python analysis pipeline into public/data/
 * so Next.js can read them at build time.
 *
 * Source: ../ciso-tenure-study/output/tables/
 * Dest:   ./public/data/
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const src  = path.resolve(__dirname, '..', '..', 'ciso-tenure-study', 'output', 'tables')
const dest = path.resolve(__dirname, '..', 'public', 'data')

if (fs.existsSync(src)) {
  fs.mkdirSync(dest, { recursive: true })
  fs.cpSync(src, dest, { recursive: true })
  console.log(`✓ Data copied from ${src} → ${dest}`)
} else {
  console.warn(`⚠ Python output not found at ${src} — using existing public/data/`)
}
