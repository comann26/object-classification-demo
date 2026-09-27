// Mirrors demo/contracts.py's SessionRequest._normalise_threat_objects exactly
// (same PERSON_WORDS list, same order of checks, same dedupe-to-lowercase
// behaviour), but with the shorter messages the UI wants.
const PERSON_WORDS = new Set([
  'person',
  'persons',
  'people',
  'human',
  'humans',
  'man',
  'men',
  'woman',
  'women',
  'child',
  'children',
  'kid',
  'kids',
  'boy',
  'boys',
  'girl',
  'girls',
])

const MAX_WORD_LEN = 50
const MAX_WORDS = 5

export interface ParsedThreatWords {
  words: string[]
  error?: string
}

export function parseThreatWords(input: string): ParsedThreatWords {
  const seen = new Map<string, null>()

  for (const raw of input.split(',')) {
    const word = raw.trim()
    if (!word) continue

    if (word.length > MAX_WORD_LEN) {
      return { words: [], error: 'Each threat word must be 50 characters or fewer.' }
    }

    const key = word.toLowerCase()
    if (PERSON_WORDS.has(key)) {
      return { words: [], error: 'People are always tracked — type an object instead.' }
    }

    if (!seen.has(key)) seen.set(key, null)
  }

  const words = [...seen.keys()]
  if (words.length < 1 || words.length > MAX_WORDS) {
    return { words: [], error: 'Enter 1 to 5 threat words.' }
  }

  return { words }
}
