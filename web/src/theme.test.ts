/// <reference types="node" />
import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const dirname = path.dirname(fileURLToPath(import.meta.url))

// Every shadcn/ui theme colour name that a component in components/ui might
// reference as bg-*/text-*/border-*/ring-*. Closed vocabulary (not a bare
// "any word after a dash" regex) so this doesn't false-positive on layout
// utilities like text-sm or border-b.
const TOKEN_NAMES = [
  'background',
  'foreground',
  'card',
  'card-foreground',
  'popover',
  'popover-foreground',
  'primary',
  'primary-foreground',
  'secondary',
  'secondary-foreground',
  'muted',
  'muted-foreground',
  'accent',
  'accent-foreground',
  'destructive',
  'destructive-foreground',
  'border',
  'input',
  'ring',
]

const usedTokenRe = new RegExp(
  `\\b(?:bg|text|border|ring|fill|stroke|outline|decoration|divide|placeholder|caret)-(${TOKEN_NAMES.join('|')})\\b`,
  'g',
)

describe('test_theme_tokens_cover_ui_components', () => {
  it('defines every --color-* token referenced by web/src/components/ui/*.tsx', () => {
    const css = readFileSync(path.resolve(dirname, 'index.css'), 'utf-8')
    const themeBlock = css.match(/@theme inline \{([\s\S]*?)\n\}/)?.[1] ?? ''
    const defined = new Set([...themeBlock.matchAll(/--color-([a-z-]+):/g)].map((m) => m[1]))

    const uiDir = path.resolve(dirname, 'components/ui')
    const used = new Set<string>()
    for (const file of readdirSync(uiDir).filter((f: string) => f.endsWith('.tsx'))) {
      const contents = readFileSync(path.join(uiDir, file), 'utf-8')
      for (const m of contents.matchAll(usedTokenRe)) used.add(m[1])
    }

    // Sanity check the scan itself found real usages (e.g. select.tsx's
    // bg-popover) so a regex typo can't make this test vacuously pass.
    expect(used.size).toBeGreaterThan(5)

    const missing = [...used].filter((name) => !defined.has(name))
    expect(missing).toEqual([])
  })
})
