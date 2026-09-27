import { cn } from '@/lib/utils'

interface SwitchProps {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  id?: string
  'aria-label'?: string
}

export function Switch({ checked, onCheckedChange, id, ...rest }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={checked}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border border-border transition-colors',
        checked ? 'bg-primary' : 'bg-muted',
      )}
      {...rest}
    >
      <span
        className={cn(
          'inline-block h-4 w-4 transform rounded-full bg-foreground transition-transform',
          checked ? 'translate-x-6' : 'translate-x-1',
        )}
      />
    </button>
  )
}
