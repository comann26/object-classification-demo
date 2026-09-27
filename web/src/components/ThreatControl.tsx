import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { api } from '@/api/client'
import type { Camera } from '@/api/client'
import { parseThreatWords } from '@/lib/threatWords'
import type { ActiveSession } from '@/types/session'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'

function errorMessage(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback
}

interface ThreatControlProps {
  active: ActiveSession | null
  // True from the moment Go is clicked until the first video frame (or
  // health fps>0) — App owns the whole "starting" window, not just the
  // POST /session round trip, so Stop stays disabled until a frame shows.
  starting: boolean
  // After 90s of no frame, App re-enables Stop as an escape hatch even
  // though `starting` is still true.
  startingTimedOut: boolean
  onStartBegin: () => void
  onSessionStarted: (session: ActiveSession) => void
  onStartFailed: () => void
  onStopped: () => void
  onQuit: () => void
}

export function ThreatControl({
  active,
  starting,
  startingTimedOut,
  onStartBegin,
  onSessionStarted,
  onStartFailed,
  onStopped,
  onQuit,
}: ThreatControlProps) {
  const [wordsInput, setWordsInput] = useState('')
  const [cameraId, setCameraId] = useState('')
  const [saveStills, setSaveStills] = useState(false)
  const [cameras, setCameras] = useState<Camera[]>([])
  const [actionError, setActionError] = useState<string | null>(null)

  useEffect(() => {
    api.cameras().then(setCameras).catch(() => setCameras([]))
  }, [])

  const parsed = parseThreatWords(wordsInput)
  const wordsError = wordsInput.trim() === '' ? undefined : parsed.error
  const canGo = !parsed.error && cameraId !== '' && !starting

  async function handleGo() {
    if (!canGo) return
    onStartBegin()
    setActionError(null)
    const req = { threat_objects: parsed.words, source: cameraId, save_stills: saveStills }
    try {
      const { session_id } = await api.startSession(req)
      onSessionStarted({ ...req, session_id })
      setWordsInput('')
      setCameraId('')
      setSaveStills(false)
    } catch (e) {
      setActionError(errorMessage(e, 'Failed to start session.'))
      onStartFailed()
    }
  }

  async function handleStop() {
    setActionError(null)
    try {
      await api.stop()
      onStopped()
    } catch (e) {
      setActionError(errorMessage(e, 'Could not stop — try again.'))
    }
  }

  async function handleQuit() {
    setActionError(null)
    try {
      await api.quit()
      onQuit()
    } catch (e) {
      setActionError(errorMessage(e, 'Could not quit — try again.'))
    }
  }

  return (
    <div className="flex flex-col gap-3 border-b border-border p-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Threat words
          <input
            className="rounded-md border border-border bg-transparent px-3 py-2 text-sm"
            placeholder="knife, gun"
            value={wordsInput}
            onChange={(e) => setWordsInput(e.target.value)}
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Camera
          <select
            className="rounded-md border border-border bg-transparent px-3 py-2 text-sm"
            value={cameraId}
            onChange={(e) => setCameraId(e.target.value)}
          >
            <option value="">Select a camera</option>
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-2 text-sm">
          Save stills
          <Switch checked={saveStills} onCheckedChange={setSaveStills} aria-label="Save stills" />
        </label>

        <Button onClick={handleGo} disabled={!canGo}>
          {starting ? (
            <>
              <Loader2 className="animate-spin" /> Starting…
            </>
          ) : (
            'Go'
          )}
        </Button>
        <Button
          variant="outline"
          onClick={handleStop}
          disabled={!active || (starting && !startingTimedOut)}
        >
          Stop
        </Button>
        <Button variant="destructive" onClick={handleQuit}>
          Quit
        </Button>
      </div>

      {wordsError && <p className="text-sm text-destructive">{wordsError}</p>}
      {actionError && <p className="text-sm text-destructive">{actionError}</p>}

      {active && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>Active: {active.threat_objects.join(', ')}</span>
          {active.save_stills && <Badge>Recording stills</Badge>}
        </div>
      )}
    </div>
  )
}
