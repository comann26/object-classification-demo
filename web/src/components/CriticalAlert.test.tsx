import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CriticalAlert } from './CriticalAlert'
import type { TrackUpdated } from '@/api/types'

function track(band: TrackUpdated['threat']['band']): TrackUpdated {
  return {
    event_id: 'e-1',
    session_id: 's1',
    source_id: 'cam-1',
    ts: '2026-09-26T18:04:11.231Z',
    type: 'track.updated',
    provenance: {
      scorer_id: 'rules-v1',
      config_sha256: 'x',
      model_sha256: 'y',
      input_size: 640,
      prev_hash: 'a',
      hash: 'b',
    },
    track: { track_id: 1, class: 'person', likelihood: 0.9, bbox: [0, 0, 1, 1], camera_mode: 'fixed' },
    links: [],
    summary: 's',
    threat: { band, score: 60, evidence: [] },
    confidence: { score: 0.8, dimensions: { detector: 0.8, track_stability: 0.8, image_quality: 0.8 } },
    unknowns: [],
    raw: { in_zone: true, dwell_s: 1, approach: 0, truncated: false },
  }
}

let startMock: (...args: unknown[]) => void

class FakeOscillator {
  type = ''
  frequency = { value: 0 }
  connect = vi.fn()
  start(...args: unknown[]) {
    startMock(...args)
  }
  stop = vi.fn()
  onended: (() => void) | null = null
}

class FakeAudioContext {
  destination = {}
  currentTime = 0
  createOscillator() {
    return new FakeOscillator()
  }
  close = vi.fn()
}

beforeEach(() => {
  startMock = vi.fn()
  vi.stubGlobal('AudioContext', FakeAudioContext)
  localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('test_tone_once_per_entry', () => {
  it('plays once per entry into critical: critical->high->critical plays 2', () => {
    const { rerender } = render(<CriticalAlert tracks={{ 1: track('critical') }} replay={false} />)
    expect(startMock).toHaveBeenCalledTimes(1)
    rerender(<CriticalAlert tracks={{ 1: track('high') }} replay={false} />)
    expect(startMock).toHaveBeenCalledTimes(1)
    rerender(<CriticalAlert tracks={{ 1: track('critical') }} replay={false} />)
    expect(startMock).toHaveBeenCalledTimes(2)
  })

  it('held critical plays only 1 tone', () => {
    const { rerender } = render(<CriticalAlert tracks={{ 1: track('critical') }} replay={false} />)
    expect(startMock).toHaveBeenCalledTimes(1)
    rerender(<CriticalAlert tracks={{ 1: track('critical') }} replay={false} />)
    expect(startMock).toHaveBeenCalledTimes(1)
  })
})

describe('test_mute_respected', () => {
  it('does not play a tone while muted, and persists the toggle', () => {
    render(<CriticalAlert tracks={{ 1: track('critical') }} replay={false} />)
    expect(startMock).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByText('Mute'))
    expect(localStorage.getItem('criticalAlertMuted')).toBe('true')
  })

  it('respects a previously-muted preference on mount', () => {
    localStorage.setItem('criticalAlertMuted', 'true')
    render(<CriticalAlert tracks={{ 1: track('critical') }} replay={false} />)
    expect(startMock).not.toHaveBeenCalled()
  })
})

describe('CriticalAlert banner', () => {
  it('shows nothing when no track is critical', () => {
    render(<CriticalAlert tracks={{ 1: track('low') }} replay={false} />)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('CriticalAlert during history replay', () => {
  it('replay into a critical track plays 0 tones and shows no banner', () => {
    const { rerender } = render(<CriticalAlert tracks={{}} replay={false} />)
    rerender(<CriticalAlert tracks={{ 1: track('critical') }} replay={true} />)
    expect(startMock).not.toHaveBeenCalled()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('back-to-live then a live track entering critical plays 1', () => {
    const { rerender } = render(<CriticalAlert tracks={{}} replay={false} />)
    // A replayed session already showing a critical track — no tone.
    rerender(<CriticalAlert tracks={{ 1: track('critical') }} replay={true} />)
    expect(startMock).not.toHaveBeenCalled()

    // Back to live: the store resets tracks to {} on replay_end.
    rerender(<CriticalAlert tracks={{}} replay={false} />)
    expect(startMock).not.toHaveBeenCalled()

    // A genuinely live track entering critical afterwards plays once.
    rerender(<CriticalAlert tracks={{ 1: track('critical') }} replay={false} />)
    expect(startMock).toHaveBeenCalledTimes(1)
  })
})
