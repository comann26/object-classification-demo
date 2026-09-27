import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

function setLocation(search: string) {
  Object.defineProperty(window, 'location', {
    configurable: true,
    writable: true,
    value: {
      ...window.location,
      search,
      host: '127.0.0.1:8000',
      protocol: 'http:',
    },
  })
}

describe('test_token_attached_to_every_request', () => {
  const originalLocation = window.location

  beforeEach(() => {
    vi.resetModules()
    setLocation('?t=secret-token')
  })

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: originalLocation,
    })
    vi.unstubAllGlobals()
  })

  it('attaches X-Demo-Token to every fetch call', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
    })
    vi.stubGlobal('fetch', fetchMock)

    const { api } = await import('./client')
    await api.health()
    await api.cameras()
    await api.getConfig()
    await api.sessions()
    await api.startSession({ threat_objects: ['knife'], source: 'cam-1' })
    await api.applyZone(null)
    await api.stop()
    await api.quit()

    expect(fetchMock).toHaveBeenCalledTimes(8)
    for (const call of fetchMock.mock.calls) {
      const init = call[1] as RequestInit
      const headers = new Headers(init.headers)
      expect(headers.get('X-Demo-Token')).toBe('secret-token')
    }
  })

  it('uses the exact route paths', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
    })
    vi.stubGlobal('fetch', fetchMock)

    const { api } = await import('./client')
    await api.startSession({ threat_objects: ['knife'], source: 'cam-1' })
    await api.applyZone([[0.1, 0.6]])
    await api.stop()
    await api.quit()
    await api.sessionEvents('abc-123')

    const [[startUrl, startInit], [zoneUrl], [stopUrl, stopInit], [quitUrl, quitInit], [eventsUrl]] =
      fetchMock.mock.calls
    expect(startUrl).toBe('/session')
    expect(startInit.method).toBe('POST')
    expect(zoneUrl).toBe('/session/zone')
    expect(stopUrl).toBe('/session')
    expect(stopInit.method).toBe('DELETE')
    expect(quitUrl).toBe('/quit')
    expect(quitInit.method).toBe('POST')
    expect(eventsUrl).toBe('/sessions/abc-123/events')
  })

  it('appends the token as a query param on videoUrl and eventsSocket', async () => {
    const { api } = await import('./client')
    expect(api.videoUrl()).toBe('/video?t=secret-token')

    class FakeWebSocket {
      url: string
      constructor(url: string) {
        this.url = url
      }
    }
    vi.stubGlobal('WebSocket', FakeWebSocket)

    const socket = api.eventsSocket() as unknown as FakeWebSocket
    expect(socket.url).toBe('ws://127.0.0.1:8000/events?t=secret-token')
  })
})
