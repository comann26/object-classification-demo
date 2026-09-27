import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { SourceHealth } from '@/api/types'
import type { ActiveSession } from '@/types/session'
import { ThreatControl } from '@/components/ThreatControl'
import { VideoView } from '@/components/VideoView'
import { StatusBar } from '@/components/StatusBar'

type WsEvent = { type?: string; reason?: string; code?: string; detail?: string }

function App() {
  const [active, setActive] = useState<ActiveSession | null>(null)
  // Remounts VideoView on Go/Stop so its polygon resets, per design.md §1
  // ("the drawn zone stays visible until the next Go or Stop").
  const [sessionKey, setSessionKey] = useState(0)
  const [closed, setClosed] = useState(false)
  const [restartMessage, setRestartMessage] = useState<string | null>(null)
  const [sourceHealth, setSourceHealth] = useState<Pick<SourceHealth, 'code' | 'detail'> | null>(
    null,
  )

  useEffect(() => {
    const socket = api.eventsSocket()
    socket.onmessage = (event: { data: string }) => {
      let data: WsEvent
      try {
        data = JSON.parse(event.data)
      } catch {
        return
      }
      if (data.type === 'session.ended') {
        setActive(null)
        setRestartMessage(
          data.reason === 'error' ? 'Something went wrong — click Go to restart' : null,
        )
      } else if (data.type === 'source.health' && data.code && data.detail) {
        setSourceHealth({ code: data.code as SourceHealth['code'], detail: data.detail })
      }
    }
    return () => socket.close()
  }, [])

  if (closed) {
    return (
      <div className="flex min-h-svh items-center justify-center bg-background text-foreground">
        <p className="font-heading text-xl">Demo closed — you can close this tab</p>
      </div>
    )
  }

  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="border-b border-border px-6 py-4">
        <h1 className="font-heading text-2xl font-semibold tracking-wide">
          Object Classification Demo
        </h1>
      </header>

      <ThreatControl
        active={active}
        onSessionStarted={(session) => {
          setActive(session)
          setRestartMessage(null)
          setSessionKey((k) => k + 1)
        }}
        onStopped={() => {
          setActive(null)
          setSessionKey((k) => k + 1)
        }}
        onQuit={() => setClosed(true)}
      />

      {restartMessage && <p className="px-6 py-2 text-sm text-destructive">{restartMessage}</p>}

      <VideoView key={sessionKey} active={active !== null} />

      <StatusBar sourceHealth={sourceHealth} />
    </div>
  )
}

export default App
