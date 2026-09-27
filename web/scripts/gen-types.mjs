#!/usr/bin/env node
// Generates web/src/api/types.ts from the JSON Schemas in ../../schemas.
// Usage: node scripts/gen-types.mjs [--check]
import { compile } from 'json-schema-to-typescript'
import { existsSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const schemasDir = path.resolve(__dirname, '../../schemas')
const outFile = path.resolve(__dirname, '../src/api/types.ts')
const fieldsOutFile = path.resolve(__dirname, '../src/api/scoringConfigFields.ts')

const BANNER = `/* eslint-disable */
/**
 * Generated from ../../schemas/*.json by \`npm run gen:types\`.
 * Do not edit by hand — edit the JSON Schema and run \`npm run gen:types\` again.
 */
`

// json-schema-to-typescript 16.x predates JSON Schema 2020-12 and doesn't
// understand "prefixItems" tuples (it falls back to untyped `unknown[]`
// elements). Pydantic emits prefixItems for every fixed-size tuple (bbox,
// zone points), so rewrite it to the older `items: [schema, ...]` tuple form
// it does understand.
function convertPrefixItems(node) {
  if (Array.isArray(node)) {
    for (const item of node) convertPrefixItems(item)
    return
  }
  if (!node || typeof node !== 'object') return
  if (Array.isArray(node.prefixItems)) {
    if (node.items === undefined) node.items = node.prefixItems
    delete node.prefixItems
  }
  for (const value of Object.values(node)) convertPrefixItems(value)
}

// Pydantic gives every field its own "title" (e.g. "App Version"), which makes
// json-schema-to-typescript hoist each one into its own top-level type alias
// (AppVersion, CameraName, ...). Across 3 schema files that collides on shared
// field names (source, zone, ...). Stripping titles below the root and below
// each $defs entry keeps those fields inlined instead, so there is nothing to
// collide.
function stripNestedTitles(node, keepTitle) {
  if (Array.isArray(node)) {
    for (const item of node) stripNestedTitles(item, false)
    return
  }
  if (!node || typeof node !== 'object') return
  if (!keepTitle) delete node.title
  if (node.$defs) {
    for (const value of Object.values(node.$defs)) stripNestedTitles(value, true)
  }
  for (const [key, value] of Object.entries(node)) {
    if (key === '$defs') continue
    stripNestedTitles(value, false)
  }
}

// Flattens ScoringConfig.json's nested {section: {field: {minimum, maximum,
// exclusiveMinimum, default, type, enum}}} shape into one array the
// SettingsDrawer can loop over to render sliders/selects — see
// task-19-brief.md's ruling on slider ranges.
function extractScoringFields(schema) {
  const defs = schema.$defs ?? {}
  const fields = []
  for (const [section, ref] of Object.entries(schema.properties)) {
    const defName = ref.$ref.replace('#/$defs/', '')
    const sectionSchema = defs[defName]
    for (const [field, f] of Object.entries(sectionSchema.properties)) {
      if (f.enum) {
        fields.push({ section, field, kind: 'enum', options: f.enum, default: f.default })
        continue
      }
      const isInt = f.type === 'integer'
      const step = isInt ? 1 : f.maximum <= 1 ? 0.01 : 0.1
      const min = f.minimum ?? f.exclusiveMinimum + step
      fields.push({ section, field, kind: 'number', min, max: f.maximum, step, default: f.default })
    }
  }
  return fields
}

function renderScoringFields(fields) {
  return `${BANNER}
export interface ScoringConfigNumberField {
  section: string
  field: string
  kind: 'number'
  min: number
  max: number
  step: number
  default: number
}
export interface ScoringConfigEnumField {
  section: string
  field: string
  kind: 'enum'
  options: string[]
  default: string
}
export type ScoringConfigField = ScoringConfigNumberField | ScoringConfigEnumField

export const SCORING_CONFIG_FIELDS: ScoringConfigField[] = ${JSON.stringify(fields, null, 2)}
`
}

async function generate() {
  const files = readdirSync(schemasDir)
    .filter((f) => f.endsWith('.json'))
    .sort()

  const parts = []
  let scoringFields = null
  for (const file of files) {
    const schema = JSON.parse(readFileSync(path.join(schemasDir, file), 'utf8'))
    if (file === 'ScoringConfig.json') scoringFields = extractScoringFields(schema)
    convertPrefixItems(schema)
    stripNestedTitles(schema, true)
    const name = path.basename(file, '.json')
    const ts = await compile(schema, name, { bannerComment: '' })
    parts.push(ts.trimEnd())
  }
  return { types: `${BANNER}\n${parts.join('\n\n')}\n`, scoringFields }
}

const check = process.argv.includes('--check')
const { types: output, scoringFields } = await generate()
const fieldsOutput = renderScoringFields(scoringFields)

// Git on Windows commonly checks files out with CRLF (core.autocrlf=true)
// while the freshly generated strings always use LF, so compare normalized
// to \n on both sides rather than raw bytes.
const normalize = (s) => s.replace(/\r\n/g, '\n')

if (check) {
  const existing = existsSync(outFile) ? readFileSync(outFile, 'utf8') : ''
  const existingFields = existsSync(fieldsOutFile) ? readFileSync(fieldsOutFile, 'utf8') : ''
  let drift = false
  if (normalize(existing) !== normalize(output)) {
    console.error('src/api/types.ts is out of date. Run `npm run gen:types`.')
    drift = true
  }
  if (normalize(existingFields) !== normalize(fieldsOutput)) {
    console.error('src/api/scoringConfigFields.ts is out of date. Run `npm run gen:types`.')
    drift = true
  }
  if (drift) process.exit(1)
  console.log('src/api/types.ts is up to date.')
} else {
  writeFileSync(outFile, output)
  writeFileSync(fieldsOutFile, fieldsOutput)
  console.log(`Wrote ${path.relative(process.cwd(), outFile)}`)
  console.log(`Wrote ${path.relative(process.cwd(), fieldsOutFile)}`)
}
