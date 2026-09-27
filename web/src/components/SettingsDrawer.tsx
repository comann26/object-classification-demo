import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { ScoringConfig } from '@/api/types'
import { SCORING_CONFIG_FIELDS } from '@/api/scoringConfigFields'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Drawer,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from '@/components/ui/drawer'

type ConfigSection = Record<string, number | string>
type ConfigDraft = Record<string, ConfigSection>

// Every ScoringConfig field has a `default` in the schema (task-19-brief.md
// ruling), so "Reset to defaults" just rebuilds the draft from those.
function defaultsConfig(): ConfigDraft {
  const draft: ConfigDraft = {}
  for (const f of SCORING_CONFIG_FIELDS) {
    draft[f.section] ??= {}
    draft[f.section][f.field] = f.default
  }
  return draft
}

function errorMessage(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback
}

// One slider (or select, for the runtime.model enum) per ScoringConfig
// field, ranges taken from the schema — task-19-brief.md's SettingsDrawer.
export function SettingsDrawer() {
  const [open, setOpen] = useState(false)
  const [config, setConfig] = useState<ConfigDraft | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || config) return
    api
      .getConfig()
      .then((cfg) => setConfig(cfg as unknown as ConfigDraft))
      .catch((e) => setError(errorMessage(e, 'Failed to load settings.')))
  }, [open, config])

  function update(section: string, field: string, value: number | string) {
    if (!config) return
    setMessage(null)
    setConfig({ ...config, [section]: { ...config[section], [field]: value } })
  }

  async function handleSave() {
    if (!config) return
    setError(null)
    setMessage(null)
    try {
      await api.putConfig(config as unknown as ScoringConfig)
      setMessage('Applies on next Go')
    } catch (e) {
      setError(errorMessage(e, 'Failed to save settings.'))
    }
  }

  function handleReset() {
    setConfig(defaultsConfig())
    setMessage(null)
    setError(null)
  }

  return (
    <Drawer open={open} onOpenChange={setOpen} direction="right">
      <DrawerTrigger asChild>
        <Button variant="outline">Settings</Button>
      </DrawerTrigger>
      <DrawerContent>
        <DrawerHeader>
          <DrawerTitle>Settings</DrawerTitle>
        </DrawerHeader>

        <div className="flex flex-col gap-4 overflow-y-auto p-4">
          {!config && <p className="text-sm text-muted-foreground">Loading…</p>}
          {config &&
            SCORING_CONFIG_FIELDS.map((f) => {
              const key = `${f.section}.${f.field}`
              const value = config[f.section]?.[f.field] ?? f.default
              if (f.kind === 'enum') {
                return (
                  <label key={key} className="flex flex-col gap-1 text-sm">
                    {key}
                    <Select
                      value={String(value)}
                      onValueChange={(v) => update(f.section, f.field, v)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {f.options.map((o) => (
                          <SelectItem key={o} value={o}>
                            {o}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </label>
                )
              }
              return (
                <label key={key} data-testid={key} className="flex flex-col gap-1 text-sm">
                  <span>
                    {key}: {value}
                  </span>
                  <Slider
                    aria-label={key}
                    min={f.min}
                    max={f.max}
                    step={f.step}
                    value={[Number(value)]}
                    onValueChange={([v]) => update(f.section, f.field, v)}
                  />
                </label>
              )
            })}
        </div>

        <DrawerFooter>
          {message && <p className="text-sm text-primary">{message}</p>}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex gap-2">
            <Button onClick={handleSave} disabled={!config}>
              Save
            </Button>
            <Button variant="outline" onClick={handleReset}>
              Reset to defaults
            </Button>
          </div>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  )
}
