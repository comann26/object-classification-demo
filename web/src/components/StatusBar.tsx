import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { HealthResponse } from '@/api/client'
import type { SourceHealth } from '@/api/types'

interface StatusBarProps {
  sourceHealth: Pick<SourceHealth, 'code' | 'detail'> | null
}

export function StatusBar({ sourceHealth }: StatusBarProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null)

  useEffect(() => {
    let cancelled = false
    function poll() {
      api
        .health()
        .then((h) => {
          if (!cancelled) setHealth(h)
        })
        .catch(() => {})
    }
    poll()
    const id = setInterval(poll, 1000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return (
    <div className="flex flex-wrap gap-4 border-t border-border px-4 py-2 text-xs text-muted-foreground">
      <span>Session: {health?.session_id ?? '—'}</span>
      <span>FPS: {health?.fps ?? '—'}</span>
      <span>Camera: {health?.camera ?? '—'}</span>
      <span>Model: {health?.model ?? '—'}</span>
      <span>Input size: {health?.input_size ?? '—'}</span>
      <span>Device: {health?.device ?? '—'}</span>
      {sourceHealth && (
        <span className="text-destructive">
          {sourceHealth.code}: {sourceHealth.detail}
        </span>
      )}
    </div>
  )
}
