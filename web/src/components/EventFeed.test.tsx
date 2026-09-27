import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EventFeed } from './EventFeed'
import type { Event, TrackUpdated } from '@/api/types'

function trackUpdated(trackId: number): TrackUpdated {
  return {
    event_id: `e-${trackId}`,
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
    track: { track_id: trackId, class: 'person', likelihood: 0.9, bbox: [0, 0, 1, 1], camera_mode: 'fixed' },
    links: [],
    summary: 's',
    threat: { band: 'high', score: 60, evidence: [] },
    confidence: { score: 0.8, dimensions: { detector: 0.8, track_stability: 0.8, image_quality: 0.8 } },
    unknowns: [],
    raw: { in_zone: true, dwell_s: 1, approach: 0, truncated: false },
  }
}

describe('EventFeed', () => {
  it('lists events and selects a track on click', () => {
    const feed: Event[] = [trackUpdated(1)]
    const onSelectTrack = vi.fn()
    render(<EventFeed feed={feed} selectedTrackId={null} onSelectTrack={onSelectTrack} />)
    fireEvent.click(screen.getByText(/Track 1/))
    expect(onSelectTrack).toHaveBeenCalledWith(1)
  })
})
