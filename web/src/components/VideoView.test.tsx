import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { VideoView } from './VideoView'
import { api } from '@/api/client'

vi.mock('@/api/client', () => ({
  api: {
    videoUrl: () => '/video?t=tok',
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
    render(<VideoView active />)
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
    render(<VideoView active={false} />)
    const img = screen.getByAltText('Live camera feed') as HTMLImageElement
    loadImage(img, 640, 480)
    fireEvent.click(img, { clientX: 10, clientY: 10 })
    expect(screen.getByText('Apply zone')).toBeDisabled()
  })

  it('clears the local polygon without calling the server when no zone was applied', () => {
    render(<VideoView active />)
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
    render(<VideoView active />)
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

describe('test_starting_overlay_and_first_frame', () => {
  it('shows the overlay message when set and hides it when cleared', () => {
    const { rerender } = render(<VideoView active overlayMessage="Starting…" />)
    expect(screen.getByText('Starting…')).toBeInTheDocument()

    rerender(<VideoView active overlayMessage={null} />)
    expect(screen.queryByText('Starting…')).not.toBeInTheDocument()
  })

  it('disables Apply zone while starting even with a valid polygon', () => {
    render(<VideoView active starting />)
    const img = screen.getByAltText('Live camera feed') as HTMLImageElement
    loadImage(img, 640, 480)
    fireEvent.click(img, { clientX: 10, clientY: 10 })
    fireEvent.click(img, { clientX: 600, clientY: 10 })
    fireEvent.click(img, { clientX: 300, clientY: 400 })
    expect(screen.getByText('Apply zone')).toBeDisabled()
  })

  it('calls onFirstFrame when the video image fires its load event', () => {
    const onFirstFrame = vi.fn()
    render(<VideoView active onFirstFrame={onFirstFrame} />)
    const img = screen.getByAltText('Live camera feed') as HTMLImageElement
    loadImage(img, 640, 480)
    expect(onFirstFrame).toHaveBeenCalledTimes(1)
  })
})
