// Exercises the real `--check` behaviour end-to-end (subprocess, real file on
// disk) rather than unit-testing the normalize helper in isolation, since the
// bug this guards against (CRLF vs LF on Windows checkouts) only shows up in
// the actual file comparison.
import { execFileSync } from 'node:child_process'
import { readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const scriptPath = path.join(__dirname, 'gen-types.mjs')
const outFile = path.resolve(__dirname, '../src/api/types.ts')

function runCheck() {
  try {
    execFileSync(process.execPath, [scriptPath, '--check'], { stdio: 'pipe' })
    return 0
  } catch (err) {
    return err.status ?? 1
  }
}

describe('gen-types.mjs --check', () => {
  let original

  beforeAll(() => {
    // Make sure the on-disk file matches the schemas before mutating it below.
    execFileSync(process.execPath, [scriptPath], { stdio: 'pipe' })
    original = readFileSync(outFile, 'utf8')
  })

  afterAll(() => {
    writeFileSync(outFile, original)
  })

  it('passes when the on-disk file is byte-identical (LF)', () => {
    expect(runCheck()).toBe(0)
  })

  it('still passes when the on-disk file has CRLF line endings', () => {
    writeFileSync(outFile, original.replace(/\n/g, '\r\n'))
    expect(runCheck()).toBe(0)
  })

  it('fails on a real content difference', () => {
    writeFileSync(outFile, `${original}\nexport type Bogus = never;\n`)
    expect(runCheck()).toBe(1)
  })
})
