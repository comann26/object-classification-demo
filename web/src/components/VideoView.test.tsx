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
