import { useEffect, useRef, useState } from 'react'
import type { MouseEvent } from 'react'
import { api } from '@/api/client'
import { clientToFrame } from '@/lib/zoneMap'
import { Button } from '@/components/ui/button'

interface VideoViewProps {
  active: boolean
  // The current session's id, so the <img> src is unique per session (see
  // api.videoUrl). No session -> no id -> no live-stream <img> is rendered,
  // so a page load with no session never caches an empty stream.
  sessionId?: string | null
  // Sends the zone (null clears it). App passes its own so it can follow the
  // restarted session's id; defaults to the plain API call.
  onApplyZone?: (zone: [number, number][] | null) => Promise<unknown>
}

export function VideoView({ active, sessionId, onApplyZone = api.applyZone }: VideoViewProps) {
  const imgRef = useRef<HTMLImageElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [frameSize, setFrameSize] = useState<{ w: number; h: number } | null>(null)
  const [points, setPoints] = useState<[number, number][]>([])
  const [zoneApplied, setZoneApplied] = useState(false)
  const [zoneError, setZoneError] = useState<string | null>(null)

  function handleLoad() {
    const img = imgRef.current
    if (img) setFrameSize({ w: img.naturalWidth, h: img.naturalHeight })
  }

  // ponytail: canvas size is (re)synced on load and whenever the polygon
  // changes, not on window resize — add a ResizeObserver if the demo window
  // becomes resizable mid-session.
  useEffect(() => {
    const canvas = canvasRef.current
    const img = imgRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !img || !ctx) return
    canvas.width = img.clientWidth
    canvas.height = img.clientHeight
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    if (points.length === 0) return
    ctx.strokeStyle = '#d4af37'
    ctx.fillStyle = 'rgba(212, 175, 55, 0.2)'
    ctx.lineWidth = 2
    ctx.beginPath()
    points.forEach(([x, y], i) => {
      const px = x * canvas.width
      const py = y * canvas.height
      if (i === 0) ctx.moveTo(px, py)
      else ctx.lineTo(px, py)
    })
    ctx.closePath()
    ctx.fill()
    ctx.stroke()
  }, [points, frameSize])

  function handleClick(e: MouseEvent<HTMLImageElement>) {
    if (!active || !frameSize) return
    const box = e.currentTarget.getBoundingClientRect()
    const pt = clientToFrame(e.clientX, e.clientY, box, frameSize.w, frameSize.h)
    if (pt) setPoints((prev) => [...prev, pt])
  }

  async function handleApply() {
    setZoneError(null)
    try {
      await onApplyZone(points)
      setZoneApplied(true)
    } catch (e) {
      // Keep the drawn polygon and do NOT mark the zone applied: the server
      // never accepted it, so a later Clear must not send a needless null.
      setZoneError(e instanceof Error ? e.message : 'Could not apply zone — try again.')
    }
  }

  async function handleClear() {
    setPoints([])
    if (zoneApplied) {
      try {
        await onApplyZone(null)
        setZoneApplied(false)
      } catch (e) {
        setZoneError(e instanceof Error ? e.message : 'Could not clear zone — try again.')
      }
    }
  }

  return (
    <div className="flex flex-col gap-2 p-4">
      <div className="relative inline-block">
        {sessionId && (
          <img
            ref={imgRef}
            src={api.videoUrl(sessionId)}
            onLoad={handleLoad}
            onClick={handleClick}
            alt="Live camera feed"
            className="max-w-full"
          />
        )}
        <canvas ref={canvasRef} className="pointer-events-none absolute inset-0" />
      </div>
      <div className="flex gap-2">
        <Button onClick={handleApply} disabled={points.length < 3}>
          Apply zone
        </Button>
        <Button variant="outline" onClick={handleClear} disabled={points.length === 0}>
          Clear zone
        </Button>
      </div>
      {zoneError && <p className="text-sm text-destructive">{zoneError}</p>}
    </div>
  )
}
