import { describe, expect, it } from 'vitest'
import { parseThreatWords } from './threatWords'

describe('test_parse_threat_words', () => {
  it('parses, trims and drops blanks and duplicates', () => {
    expect(parseThreatWords('Knife,, knife , ')).toEqual({ words: ['knife'] })
  })

  it('rejects person words with the fixed message', () => {
    expect(parseThreatWords('person')).toEqual({
      words: [],
      error: 'People are always tracked — type an object instead.',
    })
  })

  it('rejects any person synonym, case-insensitively', () => {
    expect(parseThreatWords('Children').error).toBe(
      'People are always tracked — type an object instead.',
    )
  })

  it('rejects a word over 50 characters', () => {
    const tooLong = 'a'.repeat(51)
    expect(parseThreatWords(tooLong)).toEqual({
      words: [],
      error: 'Each threat word must be 50 characters or fewer.',
    })
  })

  it('rejects six words', () => {
    expect(parseThreatWords('a,b,c,d,e,f')).toEqual({
      words: [],
      error: 'Enter 1 to 5 threat words.',
    })
  })

  it('rejects zero words', () => {
    expect(parseThreatWords(' , , ')).toEqual({
      words: [],
      error: 'Enter 1 to 5 threat words.',
    })
  })

  it('allows emoji', () => {
    expect(parseThreatWords('🔪')).toEqual({ words: ['🔪'] })
  })

  it('allows exactly 5 words', () => {
    expect(parseThreatWords('a,b,c,d,e')).toEqual({ words: ['a', 'b', 'c', 'd', 'e'] })
  })
})
