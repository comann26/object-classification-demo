import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { VideoView } from './VideoView'
import { api } from '@/api/client'

vi.mock('@/api/client', () => ({
  api: {
    videoUrl: (sessionId: string) => `/video?t=tok&s=${sessionId}`,
    applyZone: vi.fn().mockResolvedValue(undefined),
  },
}))

function loadImage(img: HTMLImageElement, w: number, h: number) {
  Object.defineProperty(img, 'naturalWidth', { value: w, configurable: true })
  Object.defineProperty(img, 'naturalHeight', { value: h, configurable: true })
  img.getBoundingClientRect = () =>
    ({ left: 0, top: 0, right: w, bottom: h, width: w, height: h, x: 0, y: 0, toJSON() {} }) as DOMRect
  fireEvent.load(img)
}

describe('test_apply_zone_sends_polygon_only', () => {
  beforeEach(() => {
    vi.mocked(api.applyZone).mockClear()
  })

  it('sends only the polygon points to applyZone, nothing else', async () => {
    render(<VideoView active sessionId="s1" />)
    const img = screen.getByAltText('Live camera feed') as HTMLImageElement
    loadImage(img, 640, 480)

    fireEvent.click(img, { clientX: 10, clientY: 10 })
    fireEvent.click(img, { clientX: 600, clientY: 10 })
    fireEvent.click(img, { clientX: 300, clientY: 400 })

    fireEvent.click(screen.getByText('Apply zone'))

    expect(api.applyZone).toHaveBeenCalledTimes(1)
    expect(api.applyZone).toHaveBeenCalledWith([
      [10 / 640, 10 / 480],
      [600 / 640, 10 / 480],
      [300 / 640, 400 / 480],
    ])
  })

  it('ignores clicks while no session is active', () => {
    render(<VideoView active={false} sessionId="s1" />)
    const img = screen.getByAltText('Live camera feed') as HTMLImageElement
    loadImage(img, 640, 480)
    fireEvent.click(img, { clientX: 10, clientY: 10 })
    expect(screen.getByText('Apply zone')).toBeDisabled()
  })

  it('clears the local polygon without calling the server when no zone was applied', () => {
    render(<VideoView active sessionId="s1" />)
    const img = screen.getByAltText('Live camera feed') as HTMLImageElement
    loadImage(img, 640, 480)
    fireEvent.click(img, { clientX: 10, clientY: 10 })
    fireEvent.click(img, { clientX: 600, clientY: 10 })
    fireEvent.click(img, { clientX: 300, clientY: 400 })

    fireEvent.click(screen.getByText('Clear zone'))

    expect(api.applyZone).not.toHaveBeenCalled()
    expect(screen.getByText('Apply zone')).toBeDisabled()
  })
})

describe('test_apply_zone_error_keeps_polygon_and_leaves_zone_unapplied', () => {
  beforeEach(() => {
    vi.mocked(api.applyZone).mockClear()
  })

  it('shows the error, keeps the drawn polygon, and does not mark the zone applied', async () => {
    vi.mocked(api.applyZone).mockRejectedValueOnce(new Error('Zone rejected: self-intersecting'))
    render(<VideoView active sessionId="s1" />)
    const img = screen.getByAltText('Live camera feed') as HTMLImageElement
    loadImage(img, 640, 480)

    fireEvent.click(img, { clientX: 10, clientY: 10 })
    fireEvent.click(img, { clientX: 600, clientY: 10 })
    fireEvent.click(img, { clientX: 300, clientY: 400 })
    fireEvent.click(screen.getByText('Apply zone'))

    expect(await screen.findByText('Zone rejected: self-intersecting')).toBeInTheDocument()
    // The polygon is kept (still 3 points, so Apply zone stays enabled).
    expect(screen.getByText('Apply zone')).not.toBeDisabled()

    // Not marked applied server-side, so Clear must not send a needless null.
    vi.mocked(api.applyZone).mockClear()
    fireEvent.click(screen.getByText('Clear zone'))
    expect(api.applyZone).not.toHaveBeenCalled()
  })
})

// Task: a cache-busting per-session src, so the feed can't be served from
// the browser's cached (possibly empty, pre-session) response for an
// identical URL (web/src/api/client.ts videoUrl).
describe('test_video_src_is_per_session', () => {
  afterEach(cleanup)

  it('renders no live-stream img with no session', () => {
    render(<VideoView active={false} />)
    expect(screen.queryByAltText('Live camera feed')).not.toBeInTheDocument()
  })

  it('gives the img a src derived from the session id, and updates it when the id changes', () => {
    const { rerender } = render(<VideoView active sessionId="s1" />)
    const img = screen.getByAltText('Live camera feed') as HTMLImageElement
    const srcBefore = img.src
    expect(srcBefore).toContain('s=s1')

    // Go -> a new session id (App remounts VideoView on Go, but the src
    // must differ from the pre-session/previous-session state regardless).
    rerender(<VideoView active sessionId="s2" />)
    expect(img.src).toContain('s=s2')
    expect(img.src).not.toBe(srcBefore)
  })
})
