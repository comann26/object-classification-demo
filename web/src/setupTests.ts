import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// vitest.config.ts doesn't set `test.globals`, so @testing-library/react's
// own auto-cleanup (which detects a global `afterEach`) never registers.
// Do it here once for every test file instead of per-file.
afterEach(cleanup)

// jsdom doesn't implement canvas — VideoView's zone-drawing canvas otherwise
// logs "Not implemented" noise on every render.
HTMLCanvasElement.prototype.getContext = (() => null) as typeof HTMLCanvasElement.prototype.getContext

// jsdom doesn't implement ResizeObserver; radix-ui's Slider (and others)
// use it to measure their track.
class StubResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver ??= StubResizeObserver as unknown as typeof ResizeObserver

// jsdom doesn't implement matchMedia; vaul's Drawer reads it to detect
// mobile vs desktop.
window.matchMedia ??= ((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: () => {},
  removeListener: () => {},
  addEventListener: () => {},
  removeEventListener: () => {},
  dispatchEvent: () => false,
})) as typeof window.matchMedia
