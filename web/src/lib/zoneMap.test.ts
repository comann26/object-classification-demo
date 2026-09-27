import { describe, expect, it } from 'vitest'
import { clientToFrame } from './zoneMap'

describe('test_zone_click_maps_through_letterbox', () => {
  it('maps a click in the left/right bars to null for a 4:3 frame in a 16:9 box', () => {
    const box = new DOMRect(0, 0, 1600, 900)
    // frame 4:3 in a 16:9 box is letterboxed left/right: content is 1200x900, offset x = 200
    expect(clientToFrame(100, 450, box, 4, 3)).toBeNull()
  })

  it('maps the image centre to [0.5, 0.5] for a 4:3 frame in a 16:9 box', () => {
    const box = new DOMRect(0, 0, 1600, 900)
    expect(clientToFrame(800, 450, box, 4, 3)).toEqual([0.5, 0.5])
  })

  it('maps a click in the left/right bars to null for a portrait 9:16 frame', () => {
    const box = new DOMRect(0, 0, 1600, 900)
    // 9:16 frame in a 16:9 box is letterboxed left/right: content is 506.25x900, offset x = 546.875
    expect(clientToFrame(100, 450, box, 9, 16)).toBeNull()
  })

  it('maps the image centre to [0.5, 0.5] for a portrait 9:16 frame', () => {
    const box = new DOMRect(0, 0, 1600, 900)
    expect(clientToFrame(800, 450, box, 9, 16)).toEqual([0.5, 0.5])
  })

  it('returns null when the click is outside the box entirely', () => {
    const box = new DOMRect(0, 0, 1600, 900)
    expect(clientToFrame(-10, 450, box, 4, 3)).toBeNull()
  })
})
