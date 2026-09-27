import type { Threat } from '@/api/types'

// Text label + colour for a threat band — shown together everywhere a band
// appears, never colour alone (docs/design.md §1).
export type Band = Threat['band']

export const BAND_LABEL: Record<Band, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
}

export const BAND_COLOR_CLASS: Record<Band, string> = {
  low: 'text-muted-foreground',
  medium: 'text-primary',
  high: 'text-orange-500',
  critical: 'text-destructive',
}
