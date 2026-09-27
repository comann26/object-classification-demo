import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { HistoryDrawer } from './HistoryDrawer'
import { api } from '@/api/client'
import type { Event } from '@/api/types'

vi.mock('@/api/client', () => ({
  api: {
    sessions: vi.fn(),
    sessionEvents: vi.fn(),
  },
}))

describe('HistoryDrawer', () => {
  it('lists sessions with started_at, threat words, peak band and ended state', async () => {
    vi.mocked(api.sessions).mockResolvedValue([
      {
        session_id: 's1',
        started_at: '2026-09-26T10:00:00.000Z',
        threat_objects: ['knife'],
        peak_band: 'high',
        truncated: false,
      },
      {
        session_id: 's2',
        started_at: '2026-09-26T11:00:00.000Z',
        threat_objects: ['gun'],
        peak_band: 'critical',
        truncated: true,
      },
    ])
    render(<HistoryDrawer dispatch={vi.fn()} />)
    fireEvent.click(screen.getByText('History'))
    expect(await screen.findByText('ended normally', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('truncated', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('High', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Critical', { exact: false })).toBeInTheDocument()
  })

  describe('test_history_replay_populates_panels', () => {
    it('opening a session loads its events and dispatches replay_start', async () => {
      vi.mocked(api.sessions).mockResolvedValue([
        {
          session_id: 's1',
          started_at: '2026-09-26T10:00:00.000Z',
          threat_objects: ['knife'],
          peak_band: 'high',
          truncated: false,
        },
      ])
      const events: Event[] = [
        {
          event_id: 'e1',
          session_id: 's1',
          source_id: 'cam-1',
          ts: '2026-09-26T10:00:00.000Z',
          type: 'session.started',
          provenance: {
            scorer_id: 'rules-v1',
            config_sha256: 'x',
            model_sha256: 'y',
            input_size: 640,
            prev_hash: 'a',
            hash: 'b',
          },
          app_version: '1.0',
          camera_name: 'cam-1',
          config: {},
          device: 'cpu',
          input_size: 640,
          model: 'yolo-world',
          model_sha256: 'y',
          save_stills: false,
          source: 'cam-1',
          threat_objects: ['knife'],
          zone: null,
        },
      ]
      vi.mocked(api.sessionEvents).mockResolvedValue(events)
      const dispatch = vi.fn()
      render(<HistoryDrawer dispatch={dispatch} />)
      fireEvent.click(screen.getByText('History'))
      const row = await screen.findByText('knife', { exact: false })
      fireEvent.click(row)
      await waitFor(() =>
        expect(dispatch).toHaveBeenCalledWith({ type: 'replay_start', events }),
      )
    })
  })
})
