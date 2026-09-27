import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import App from '../App'
import { api } from '@/api/client'

class FakeSocket {
  onmessage: ((ev: { data: string }) => void) | null = null
  close = vi.fn()
}

let fakeSocket: FakeSocket

vi.mock('@/api/client', () => ({
  api: {
    cameras: vi.fn().mockResolvedValue([{ id: 'cam-1', name: 'Cam 1' }]),
    startSession: vi.fn().mockResolvedValue(undefined),
    applyZone: vi.fn().mockResolvedValue(undefined),
    stop: vi.fn().mockResolvedValue(undefined),
    quit: vi.fn().mockResolvedValue(undefined),
    health: vi.fn().mockResolvedValue({
      status: 'ok',
      session_id: null,
      fps: null,
      camera: null,
      model: null,
      input_size: null,
      device: null,
    }),
    videoUrl: () => '/video?t=tok',
    eventsSocket: vi.fn(),
  },
}))

beforeEach(() => {
  fakeSocket = new FakeSocket()
  vi.mocked(api.eventsSocket).mockReturnValue(fakeSocket as unknown as WebSocket)
})

describe('test_quit_shows_closed_message', () => {
  it('shows the closed message after Quit', async () => {
    render(<App />)
    fireEvent.click(screen.getByText('Quit'))
    await waitFor(() => expect(api.quit).toHaveBeenCalled())
    expect(await screen.findByText('Demo closed — you can close this tab')).toBeInTheDocument()
  })
})

describe('test_error_end_shows_restart_message', () => {
  it('shows the restart message when a session ends in error', async () => {
    render(<App />)
    act(() => {
      fakeSocket.onmessage?.({ data: JSON.stringify({ type: 'session.ended', reason: 'error' }) })
    })
    expect(await screen.findByText('Something went wrong — click Go to restart')).toBeInTheDocument()
  })
})
