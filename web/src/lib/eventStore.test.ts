import { describe, expect, it } from 'vitest'
import { eventStoreReducer, initialEventStoreState } from './eventStore'
import type { Event, TrackUpdated } from '@/api/types'

function trackUpdated(trackId: number, band: TrackUpdated['threat']['band']): TrackUpdated {
  return {
    event_id: `e-${trackId}`,
    session_id: 's1',
    source_id: 'cam-1',
    ts: '2026-09-26T18:04:11.231Z',
    type: 'track.updated',
    schema_version: '1.0',
    provenance: {
      scorer_id: 'rules-v1',
      config_sha256: 'x',
      model_sha256: 'y',
      input_size: 640,
      prev_hash: 'a',
      hash: 'b',
    },
    track: {
      track_id: trackId,
      class: 'person',
      likelihood: 0.9,
      bbox: [0, 0, 1, 1],
      camera_mode: 'fixed',
    },
    links: [],
    summary: 'A person is near the zone.',
    threat: { band, score: 50, evidence: [] },
    confidence: {
      score: 0.8,
      dimensions: { detector: 0.8, track_stability: 0.8, image_quality: 0.8 },
    },
    unknowns: [],
    raw: { in_zone: true, dwell_s: 1, approach: 0, truncated: false },
  }
}

describe('test_store_bounded_500', () => {
  it('caps the feed at 500 events, dropping the oldest', () => {
    let state = initialEventStoreState
    for (let i = 0; i < 510; i++) {
      state = eventStoreReducer(state, { type: 'event', event: trackUpdated(1, 'low') })
    }
    expect(state.feed).toHaveLength(500)
    expect(state.feed[0].event_id).toBe('e-1')
  })
})

describe('eventStore tracks', () => {
  it('keeps only the latest update per track, removed on track.ended', () => {
    let state = initialEventStoreState
    state = eventStoreReducer(state, { type: 'event', event: trackUpdated(1, 'low') })
    state = eventStoreReducer(state, { type: 'event', event: trackUpdated(1, 'high') })
    expect(state.tracks[1].threat.band).toBe('high')

    const ended: Event = {
      event_id: 'e-end',
      session_id: 's1',
      source_id: 'cam-1',
      ts: '2026-09-26T18:04:11.231Z',
      type: 'track.ended',
      schema_version: '1.0',
      provenance: {
        scorer_id: 'rules-v1',
        config_sha256: 'x',
        model_sha256: 'y',
        input_size: 640,
        prev_hash: 'a',
        hash: 'b',
      },
      track_id: 1,
      class: 'person',
      duration_s: 5,
      peak_score: 60,
      peak_band: 'high',
    }
    state = eventStoreReducer(state, { type: 'event', event: ended })
    expect(state.tracks[1]).toBeUndefined()
  })
})

describe('test_history_replay_populates_panels', () => {
  it('replay_start rebuilds tracks/feed and marks replay; replay_end clears it', () => {
    const events = [trackUpdated(2, 'medium'), trackUpdated(2, 'critical')]
    let state = eventStoreReducer(initialEventStoreState, { type: 'replay_start', events })
    expect(state.replay).toBe(true)
    expect(state.tracks[2].threat.band).toBe('critical')
    expect(state.feed).toHaveLength(2)

    // Live events are ignored while replaying.
    state = eventStoreReducer(state, { type: 'event', event: trackUpdated(3, 'low') })
    expect(state.tracks[3]).toBeUndefined()

    state = eventStoreReducer(state, { type: 'replay_end' })
    expect(state.replay).toBe(false)
    expect(state.tracks).toEqual({})
    expect(state.feed).toEqual([])
  })
})
