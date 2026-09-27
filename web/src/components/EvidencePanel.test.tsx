import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EvidencePanel } from './EvidencePanel'
import type { TrackUpdated } from '@/api/types'

function track(overrides: Partial<TrackUpdated> = {}): TrackUpdated {
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
    track: {
      track_id: 1,
      class: 'person',
      likelihood: 0.9,
      bbox: [0, 0, 1, 1],
      camera_mode: 'fixed',
    },
    links: [],
    summary: 'A person is approaching the zone.',
    threat: {
      band: 'critical',
      score: 80,
      evidence: [
        {
          rule_id: 'r1',
          rule_version: 1,
          type: 'supporting',
          text: 'Linked to a knife for 3s.',
          contribution: 55,
          observed: 3,
          threshold: 2,
        },
        {
          rule_id: 'r2',
          rule_version: 1,
          type: 'contradictory',
          text: 'Moving away from the zone.',
          contribution: -5,
          observed: 0.1,
          threshold: 0,
        },
      ],
    },
    confidence: {
      score: 0.82,
      dimensions: { detector: 0.9, track_stability: 0.8, image_quality: 0.75 },
    },
    unknowns: [{ code: 'poor_image', detail: 'Frame is dark.' }],
    raw: { in_zone: true, dwell_s: 1, approach: 0.1, truncated: false },
    ...overrides,
  }
}

describe('test_band_label_text_present', () => {
  it('shows the band name as text, not just colour', () => {
    render(<EvidencePanel track={track()} />)
    expect(screen.getByText('Critical')).toBeInTheDocument()
  })

  it('shows a placeholder with no track selected', () => {
    render(<EvidencePanel track={null} />)
    expect(screen.getByText(/select a track/i)).toBeInTheDocument()
  })
})

describe('EvidencePanel contents', () => {
  it('renders the summary, evidence rows with signed contribution and tag, confidence and unknowns', () => {
    render(<EvidencePanel track={track()} />)
    expect(screen.getByText('A person is approaching the zone.')).toBeInTheDocument()
    expect(screen.getByText('Linked to a knife for 3s.')).toBeInTheDocument()
    expect(screen.getByText('+55')).toBeInTheDocument()
    expect(screen.getByText('-5')).toBeInTheDocument()
    expect(screen.getByText('supporting')).toBeInTheDocument()
    expect(screen.getByText('contradictory')).toBeInTheDocument()
    expect(screen.getByText('Confidence: 0.82')).toBeInTheDocument()
    expect(screen.getByText(/poor_image/)).toBeInTheDocument()
  })
})
