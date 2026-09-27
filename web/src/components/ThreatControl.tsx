import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { Camera } from '@/api/client'
import { parseThreatWords } from '@/lib/threatWords'
import type { ActiveSession } from '@/types/session'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'

interface ThreatControlProps {
  active: ActiveSession | null
  onSessionStarted: (session: ActiveSession) => void
  onStopped: () => void
  onQuit: () => void
}

export function ThreatControl({ active, onSessionStarted, onStopped, onQuit }: ThreatControlProps) {
  const [wordsInput, setWordsInput] = useState('')
  const [cameraId, setCameraId] = useState('')
  const [saveStills, setSaveStills] = useState(false)
  const [cameras, setCameras] = useState<Camera[]>([])
  const [startError, setStartError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.cameras().then(setCameras).catch(() => setCameras([]))
  }, [])

  const parsed = parseThreatWords(wordsInput)
  const wordsError = wordsInput.trim() === '' ? undefined : parsed.error
  const canGo = !parsed.error && cameraId !== '' && !busy

  async function handleGo() {
    if (!canGo) return
    setBusy(true)
    setStartError(null)
    const session: ActiveSession = {
      threat_objects: parsed.words,
      source: cameraId,
      save_stills: saveStills,
    }
    try {
      await api.startSession(session)
      onSessionStarted(session)
      setWordsInput('')
      setCameraId('')
      setSaveStills(false)
    } catch (e) {
      setStartError(e instanceof Error ? e.message : 'Failed to start session.')
    } finally {
      setBusy(false)
    }
  }

  async function handleStop() {
    await api.stop()
    onStopped()
  }

  async function handleQuit() {
    await api.quit()
    onQuit()
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
          Go
        </Button>
        <Button variant="outline" onClick={handleStop} disabled={!active}>
          Stop
        </Button>
        <Button variant="destructive" onClick={handleQuit}>
          Quit
        </Button>
      </div>

      {wordsError && <p className="text-sm text-destructive">{wordsError}</p>}
      {startError && <p className="text-sm text-destructive">{startError}</p>}

      {active && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>Active: {active.threat_objects.join(', ')}</span>
          {active.save_stills && <Badge>Recording stills</Badge>}
        </div>
      )}
    </div>
  )
}
