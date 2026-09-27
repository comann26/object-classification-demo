import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { SettingsDrawer } from './SettingsDrawer'
import { api } from '@/api/client'
import type { ScoringConfig } from '@/api/types'

vi.mock('@/api/client', () => ({
  api: {
    getConfig: vi.fn(),
    putConfig: vi.fn(),
  },
}))

function fakeConfig(): ScoringConfig {
  return {
    weights: { link: 55, unattended: 30, unattended_after_s: 2, in_zone: 25, loiter: 15, motion_cap: 20, approach_min: 0.05, approach_max: 0.25, run_min: 1, run_max: 2, moving_away_shrink: 0.05, contradictory: 5 },
    bands: { hysteresis: 5 },
    confidence: { sharp_ref: 100, luma_lo: 60, luma_hi: 200 },
    detect: { person_min: 0.35, object_min: 0.15, threat_nms_iou: 0.5 },
    eligibility: { person_min_age_s: 1, person_min_hit_ratio: 0.6, object_min_detections: 3 },
    emit: { heartbeat_s: 2 },
    health: { black_luma: 10, frozen_diff: 1, frozen_s: 2, blur_var: 20, scene_change_diff: 60 },
    link: { expand_side: 0.15, expand_top: 0.15, min_overlap: 0.3, form_s: 0.5, break_s: 1, fade_s: 3, strength_full_s: 2 },
    motion: { smoothing_s: 1, approach_window_s: 2, truncation_margin: 0.01, camera_flow_threshold: 0.01, camera_moving_s: 1 },
    restart: { window_s: 1, max_distance: 0.1 },
    runtime: { model: 'auto' as const, fps_floor: 10, stepdown_after_s: 5, idle_stop_s: 30 },
    tracker: { person_activation: 0.35, object_activation: 0.15, lost_track_buffer: 30, minimum_matching_threshold: 0.8 },
    zone: { dwell_gap_s: 1, loiter_s: 10 },
  }
}

describe('test_settings_ranges_from_schema', () => {
  it('renders a slider for a numeric field with min/max from the schema', async () => {
    vi.mocked(api.getConfig).mockResolvedValue(fakeConfig())
    render(<SettingsDrawer />)
    fireEvent.click(screen.getByText('Settings'))
    const wrapper = await screen.findByTestId('weights.link')
    const slider = wrapper.querySelector('[role="slider"]')
    expect(slider).toHaveAttribute('aria-valuemin', '0')
    expect(slider).toHaveAttribute('aria-valuemax', '100')
  })

  it('shows "Applies on next Go" after Save, and reports ApiError on failure', async () => {
    vi.mocked(api.getConfig).mockResolvedValue(fakeConfig())
    vi.mocked(api.putConfig).mockResolvedValue(undefined)
    render(<SettingsDrawer />)
    fireEvent.click(screen.getByText('Settings'))
    await screen.findByTestId('weights.link')
    fireEvent.click(screen.getByText('Save'))
    expect(await screen.findByText('Applies on next Go')).toBeInTheDocument()
  })

  it('shows the ApiError message when Save fails', async () => {
    vi.mocked(api.getConfig).mockResolvedValue(fakeConfig())
    vi.mocked(api.putConfig).mockRejectedValue(new Error('luma_lo must be < luma_hi'))
    render(<SettingsDrawer />)
    fireEvent.click(screen.getByText('Settings'))
    await screen.findByTestId('weights.link')
    fireEvent.click(screen.getByText('Save'))
    expect(await screen.findByText('luma_lo must be < luma_hi')).toBeInTheDocument()
  })

  it('Reset to defaults restores the schema default', async () => {
    vi.mocked(api.getConfig).mockResolvedValue(fakeConfig())
    render(<SettingsDrawer />)
    fireEvent.click(screen.getByText('Settings'))
    await screen.findByTestId('weights.link')
    fireEvent.click(screen.getByText('Reset to defaults'))
    await waitFor(() => expect(screen.getByText('weights.link: 55')).toBeInTheDocument())
  })
})
