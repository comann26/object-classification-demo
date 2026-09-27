import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
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
    startSession: vi.fn().mockResolvedValue({ session_id: 's1' }),
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

function send(event: object) {
  act(() => {
    fakeSocket.onmessage?.({ data: JSON.stringify(event) })
  })
}

async function go() {
  await waitFor(() => expect(screen.getByText('Cam 1')).toBeInTheDocument())
  fireEvent.change(screen.getByPlaceholderText('knife, gun'), { target: { value: 'knife' } })
  fireEvent.change(screen.getByLabelText('Camera'), { target: { value: 'cam-1' } })
  fireEvent.click(screen.getByText('Go'))
  expect(await screen.findByText('Active: knife')).toBeInTheDocument()
}

describe('test_session_end_messages', () => {
  beforeEach(() => {
    vi.mocked(api.startSession).mockResolvedValue({ session_id: 's1' })
  })

  it.each([
    ['error', 'Something went wrong — click Go to restart'],
    ['camera_lost', 'Camera disconnected — click Go to restart'],
    ['idle', 'Stopped because the page was closed — click Go to restart'],
  ])('shows a restart message when the session ends with %s', async (reason, message) => {
    render(<App />)
    await go()
    send({ type: 'session.ended', session_id: 's1', reason })
    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(screen.queryByText('Active: knife')).not.toBeInTheDocument()
  })
})

describe('test_apply_zone_keeps_session_active', () => {
  it("stays active when the old session's ended event arrives during Apply zone", async () => {
    vi.mocked(api.startSession).mockResolvedValue({ session_id: 's1' })
    // The server stops s1 (its session.ended reaches the page) before answering with s2.
    vi.mocked(api.applyZone).mockImplementation(async () => {
      send({ type: 'session.ended', session_id: 's1', reason: 'stopped' })
      return { session_id: 's2' }
    })
    render(<App />)
    await go()
    await applyDrawnZone()

    expect(screen.getByText('Active: knife')).toBeInTheDocument()
    expect(screen.getByText('Stop')).not.toBeDisabled()

    // A late ended event for the replaced session is still ignored; the new one's is not.
    send({ type: 'session.ended', session_id: 's1', reason: 'stopped' })
    expect(screen.getByText('Active: knife')).toBeInTheDocument()
    send({ type: 'session.ended', session_id: 's2', reason: 'camera_lost' })
    expect(await screen.findByText('Camera disconnected — click Go to restart')).toBeInTheDocument()
    expect(screen.getByText('Stop')).toBeDisabled()
  })

  it('keeps the old session when Apply zone is refused and it still runs', async () => {
    vi.mocked(api.startSession).mockResolvedValue({ session_id: 's1' })
    vi.mocked(api.applyZone).mockRejectedValue(new Error('Already starting — please wait.'))
    vi.mocked(api.health).mockResolvedValue({
      status: 'running', session_id: 's1', fps: 15, camera: 'Cam 1', model: 's', input_size: 640, device: 'cpu',
    })
    render(<App />)
    await go()
    await applyDrawnZone()

    expect(await screen.findByText('Already starting — please wait.')).toBeInTheDocument()
    expect(screen.getByText('Active: knife')).toBeInTheDocument()
    send({ type: 'session.ended', session_id: 's1', reason: 'idle' })
    expect(await screen.findByText('Stopped because the page was closed — click Go to restart')).toBeInTheDocument()
  })
})

describe('test_go_race_with_early_session_ended', () => {
  it('ends inactive when session.ended for the new id arrives before the POST /session response', async () => {
    let resolveStart!: (v: { session_id: string }) => void
    vi.mocked(api.startSession).mockImplementation(
      () => new Promise((resolve) => { resolveStart = resolve }),
    )
    render(<App />)
    await waitFor(() => expect(screen.getByText('Cam 1')).toBeInTheDocument())
    fireEvent.change(screen.getByPlaceholderText('knife, gun'), { target: { value: 'knife' } })
    fireEvent.change(screen.getByLabelText('Camera'), { target: { value: 'cam-1' } })
    fireEvent.click(screen.getByText('Go'))

    // The new session dies almost immediately; its session.ended reaches the
    // page over the socket before the POST /session response does.
    send({ type: 'session.ended', session_id: 's1', reason: 'camera_lost' })

    await act(async () => {
      resolveStart({ session_id: 's1' })
    })

    expect(await screen.findByText('Camera disconnected — click Go to restart')).toBeInTheDocument()
    expect(screen.queryByText('Active: knife')).not.toBeInTheDocument()
    expect(
      screen.queryByText(/Starting the camera and loading the model/),
    ).not.toBeInTheDocument()
  })
})

describe('test_apply_zone_race_with_early_session_ended', () => {
  it('ends inactive when session.ended for the new id arrives before the POST /session/zone response', async () => {
    vi.mocked(api.startSession).mockResolvedValue({ session_id: 's1' })
    let resolveZone!: (v: { session_id: string }) => void
    vi.mocked(api.applyZone).mockImplementation(
      () => new Promise((resolve) => { resolveZone = resolve }),
    )
    render(<App />)
    await go()
    await applyDrawnZone()

    // The replaced session's end, then the new session's near-immediate
    // death, both reach the page over the socket before the response does.
    send({ type: 'session.ended', session_id: 's1', reason: 'stopped' })
    send({ type: 'session.ended', session_id: 's2', reason: 'camera_lost' })

    await act(async () => {
      resolveZone({ session_id: 's2' })
    })

    expect(await screen.findByText('Camera disconnected — click Go to restart')).toBeInTheDocument()
    expect(screen.queryByText('Active: knife')).not.toBeInTheDocument()
  })
})

describe('test_starting_loader', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the loader and disables Go/Stop/Apply zone from the click, keeps it until the first frame', async () => {
    let resolveStart!: (v: { session_id: string }) => void
    vi.mocked(api.startSession).mockImplementation(
      () => new Promise((resolve) => { resolveStart = resolve }),
    )
    render(<App />)
    await waitFor(() => expect(screen.getByText('Cam 1')).toBeInTheDocument())
    fireEvent.change(screen.getByPlaceholderText('knife, gun'), { target: { value: 'knife' } })
    fireEvent.change(screen.getByLabelText('Camera'), { target: { value: 'cam-1' } })
    fireEvent.click(screen.getByText('Go'))

    // Loader visible while the POST is pending; controls disabled.
    expect(
      screen.getByText('Starting the camera and loading the model — the first start can take up to a minute.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Starting…').closest('button')).toBeDisabled()
    expect(screen.getByText('Stop')).toBeDisabled()
    expect(screen.getByText('Apply zone')).toBeDisabled()

    await act(async () => {
      resolveStart({ session_id: 's1' })
    })

    // Still starting after the response arrives — the video hasn't shown a frame yet.
    expect(
      screen.getByText('Starting the camera and loading the model — the first start can take up to a minute.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Stop')).toBeDisabled()

    const img = screen.getByAltText('Live camera feed') as HTMLImageElement
    fireEvent.load(img)

    expect(
      screen.queryByText('Starting the camera and loading the model — the first start can take up to a minute.'),
    ).not.toBeInTheDocument()
    expect(screen.getByText('Stop')).not.toBeDisabled()
  })

  it('hides the loader when health reports fps>0 for the new session, without waiting for a frame', async () => {
    vi.mocked(api.startSession).mockResolvedValue({ session_id: 's1' })
    vi.mocked(api.health).mockResolvedValue({
      status: 'running',
      session_id: 's1',
      fps: 12,
      camera: 'Cam 1',
      model: 's',
      input_size: 640,
      device: 'cpu',
    })
    render(<App />)
    await waitFor(() => expect(screen.getByText('Cam 1')).toBeInTheDocument())
    fireEvent.change(screen.getByPlaceholderText('knife, gun'), { target: { value: 'knife' } })
    fireEvent.change(screen.getByLabelText('Camera'), { target: { value: 'cam-1' } })

    vi.useFakeTimers()
    await act(async () => {
      fireEvent.click(screen.getByText('Go'))
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(
      screen.getByText('Starting the camera and loading the model — the first start can take up to a minute.'),
    ).toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(500)
    })

    expect(
      screen.queryByText('Starting the camera and loading the model — the first start can take up to a minute.'),
    ).not.toBeInTheDocument()
  })

  it('hides the loader and shows the error when startSession rejects', async () => {
    vi.mocked(api.startSession).mockRejectedValueOnce(new Error('Camera busy'))
    render(<App />)
    await waitFor(() => expect(screen.getByText('Cam 1')).toBeInTheDocument())
    fireEvent.change(screen.getByPlaceholderText('knife, gun'), { target: { value: 'knife' } })
    fireEvent.change(screen.getByLabelText('Camera'), { target: { value: 'cam-1' } })
    fireEvent.click(screen.getByText('Go'))

    expect(await screen.findByText('Camera busy')).toBeInTheDocument()
    expect(
      screen.queryByText('Starting the camera and loading the model — the first start can take up to a minute.'),
    ).not.toBeInTheDocument()
    expect(screen.getByText('Go')).toBeInTheDocument()
  })

  it('replaces the loader text after 90s with no frame and re-enables Stop', async () => {
    vi.mocked(api.startSession).mockResolvedValue({ session_id: 's1' })
    // Undo the previous test's health mock so this session never reports fps>0.
    vi.mocked(api.health).mockResolvedValue({
      status: 'ok',
      session_id: null,
      fps: null,
      camera: null,
      model: null,
      input_size: null,
      device: null,
    })
    render(<App />)
    await waitFor(() => expect(screen.getByText('Cam 1')).toBeInTheDocument())
    fireEvent.change(screen.getByPlaceholderText('knife, gun'), { target: { value: 'knife' } })
    fireEvent.change(screen.getByLabelText('Camera'), { target: { value: 'cam-1' } })

    vi.useFakeTimers()
    await act(async () => {
      fireEvent.click(screen.getByText('Go'))
      await vi.advanceTimersByTimeAsync(0)
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(90_000)
    })

    expect(
      screen.getByText('Still starting — check the black console window for messages.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Stop')).not.toBeDisabled()
  })
})

describe('test_apply_zone_starting_overlay', () => {
  it('shows the overlay while Apply zone is in flight and hides it once the response resolves', async () => {
    vi.mocked(api.startSession).mockResolvedValue({ session_id: 's1' })
    let resolveZone!: (v: { session_id: string }) => void
    vi.mocked(api.applyZone).mockImplementation(
      () => new Promise((resolve) => { resolveZone = resolve }),
    )
    render(<App />)
    await go()

    const img = screen.getByAltText('Live camera feed') as HTMLImageElement
    Object.defineProperty(img, 'naturalWidth', { value: 640, configurable: true })
    Object.defineProperty(img, 'naturalHeight', { value: 480, configurable: true })
    img.getBoundingClientRect = () =>
      ({ left: 0, top: 0, right: 640, bottom: 480, width: 640, height: 480, x: 0, y: 0, toJSON() {} }) as DOMRect
    fireEvent.load(img) // first frame — clears the Go loader so it doesn't mask this assertion
    fireEvent.click(img, { clientX: 10, clientY: 10 })
    fireEvent.click(img, { clientX: 600, clientY: 10 })
    fireEvent.click(img, { clientX: 300, clientY: 400 })

    fireEvent.click(screen.getByText('Apply zone'))

    expect(await screen.findByText('Applying the new zone…')).toBeInTheDocument()

    await act(async () => {
      resolveZone({ session_id: 's2' })
    })

    expect(screen.queryByText('Applying the new zone…')).not.toBeInTheDocument()
  })
})

async function applyDrawnZone() {
  const img = screen.getByAltText('Live camera feed') as HTMLImageElement
  Object.defineProperty(img, 'naturalWidth', { value: 640, configurable: true })
  Object.defineProperty(img, 'naturalHeight', { value: 480, configurable: true })
  img.getBoundingClientRect = () =>
    ({ left: 0, top: 0, right: 640, bottom: 480, width: 640, height: 480, x: 0, y: 0, toJSON() {} }) as DOMRect
  fireEvent.load(img)
  fireEvent.click(img, { clientX: 10, clientY: 10 })
  fireEvent.click(img, { clientX: 600, clientY: 10 })
  fireEvent.click(img, { clientX: 300, clientY: 400 })
  fireEvent.click(screen.getByText('Apply zone'))
  await waitFor(() => expect(api.applyZone).toHaveBeenCalled())
  await act(async () => {})
}
