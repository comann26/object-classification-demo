import type { ComponentProps } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ThreatControl } from './ThreatControl'
import { api } from '@/api/client'

vi.mock('@/api/client', () => ({
  api: {
    cameras: vi.fn().mockResolvedValue([{ id: 'cam-1', name: 'Cam 1' }]),
    startSession: vi.fn().mockResolvedValue({ session_id: 's1' }),
    stop: vi.fn().mockResolvedValue(undefined),
    quit: vi.fn().mockResolvedValue(undefined),
  },
}))

function renderControl(overrides: Partial<ComponentProps<typeof ThreatControl>> = {}) {
  return render(
    <ThreatControl
      active={null}
      onSessionStarted={vi.fn()}
      onStopped={vi.fn()}
      onQuit={vi.fn()}
      {...overrides}
    />,
  )
}

describe('test_go_disabled_until_valid_words_and_camera', () => {
  it('is disabled until words are valid and a camera is chosen', async () => {
    renderControl()
    const go = screen.getByText('Go') as HTMLButtonElement
    expect(go).toBeDisabled()

    fireEvent.change(screen.getByPlaceholderText('knife, gun'), { target: { value: 'knife' } })
    expect(go).toBeDisabled()

    await waitFor(() => expect(screen.getByText('Cam 1')).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Camera'), { target: { value: 'cam-1' } })
    expect(go).not.toBeDisabled()
  })
})

describe('test_save_stills_resets_after_go', () => {
  it('resets Save stills to off after a successful Go', async () => {
    renderControl()
    await waitFor(() => expect(screen.getByText('Cam 1')).toBeInTheDocument())
    fireEvent.change(screen.getByPlaceholderText('knife, gun'), { target: { value: 'knife' } })
    fireEvent.change(screen.getByLabelText('Camera'), { target: { value: 'cam-1' } })

    const toggle = screen.getByRole('switch')
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-checked', 'true')

    fireEvent.click(screen.getByText('Go'))
    await waitFor(() => expect(api.startSession).toHaveBeenCalled())

    expect(toggle).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByPlaceholderText('knife, gun')).toHaveValue('')
  })
})

describe('test_stop_shows_error_on_rejection', () => {
  it('shows the error and does not clear the active session when Stop fails', async () => {
    vi.mocked(api.stop).mockRejectedValueOnce(new Error('Camera busy'))
    const onStopped = vi.fn()
    renderControl({
      active: { threat_objects: ['knife'], source: 'cam-1', save_stills: false, session_id: 's1' },
      onStopped,
    })

    fireEvent.click(screen.getByText('Stop'))

    expect(await screen.findByText('Camera busy')).toBeInTheDocument()
    expect(onStopped).not.toHaveBeenCalled()
  })
})

describe('test_quit_shows_error_on_rejection', () => {
  it('shows the error and does not close the page when Quit fails', async () => {
    vi.mocked(api.quit).mockRejectedValueOnce(new Error('Could not reach the server'))
    const onQuit = vi.fn()
    renderControl({ onQuit })

    fireEvent.click(screen.getByText('Quit'))

    expect(await screen.findByText('Could not reach the server')).toBeInTheDocument()
    expect(onQuit).not.toHaveBeenCalled()
  })
})

describe('test_camera_select_is_themed', () => {
  it('gives the native camera select dark, readable colours', async () => {
    renderControl()
    await waitFor(() => expect(screen.getByText('Cam 1')).toBeInTheDocument())
    const select = screen.getByLabelText('Camera')
    expect(select.className).toContain('bg-card')
    expect(select.className).toContain('text-foreground')
    expect(select.className).toContain('border-input')
    expect(select.className).not.toContain('bg-transparent')
  })
})

describe('test_recording_badge_visible_when_on', () => {
  it('shows the Recording stills badge for an active session with save_stills', () => {
    renderControl({
      active: { threat_objects: ['knife'], source: 'cam-1', save_stills: true, session_id: 's1' },
    })
    expect(screen.getByText('Recording stills')).toBeInTheDocument()
  })

  it('hides the badge when the active session has save_stills off', () => {
    renderControl({
      active: { threat_objects: ['knife'], source: 'cam-1', save_stills: false, session_id: 's1' },
    })
    expect(screen.queryByText('Recording stills')).not.toBeInTheDocument()
  })
})
