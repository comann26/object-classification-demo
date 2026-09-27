import type { ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

type Variant = 'default' | 'destructive' | 'outline'

export function Button({
  className,
  variant = 'default',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      className={cn(
        'inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50',
        variant === 'default' && 'bg-primary text-primary-foreground hover:opacity-90',
        variant === 'destructive' && 'bg-destructive text-foreground hover:opacity-90',
        variant === 'outline' && 'border border-border bg-transparent hover:bg-muted',
        className,
      )}
      {...props}
    />
  )
}
