import type { ComponentProps } from 'react'
import { cn } from '../../lib/cn.ts'

export const fieldClass =
  'w-full rounded-xl border border-line bg-card px-3.5 py-2.5 text-sm text-ink shadow-[inset_0_1px_2px_rgb(0_0_0/0.04)] outline-none backdrop-blur-md transition-all placeholder:text-muted/80 hover:border-accent/40 focus:border-accent/60 focus:ring-4 focus:ring-accent/15 aria-[invalid=true]:border-danger/60 aria-[invalid=true]:ring-danger/15'

type InputProps = ComponentProps<'input'> & {
  label: string
  error?: string
}

export function Input({ label, error, id, className, ...props }: InputProps) {
  const inputId = id ?? props.name
  return (
    <label className="block text-sm" htmlFor={inputId}>
      <span className="mb-1.5 block text-xs font-semibold text-muted">{label}</span>
      <input
        id={inputId}
        aria-invalid={error ? true : undefined}
        className={cn(fieldClass, className)}
        {...props}
      />
      {error ? <span className="mt-1.5 block text-xs font-medium text-danger">{error}</span> : null}
    </label>
  )
}

type SelectProps = ComponentProps<'select'> & {
  label: string
  error?: string
}

export function Select({ label, error, id, className, children, ...props }: SelectProps) {
  const inputId = id ?? props.name
  return (
    <label className="block text-sm" htmlFor={inputId}>
      <span className="mb-1.5 block text-xs font-semibold text-muted">{label}</span>
      <select
        id={inputId}
        aria-invalid={error ? true : undefined}
        className={cn(fieldClass, 'appearance-none bg-[length:16px] bg-[right_0.75rem_center] bg-no-repeat pr-9', className)}
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2398a2b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E\")",
        }}
        {...props}
      >
        {children}
      </select>
      {error ? <span className="mt-1.5 block text-xs font-medium text-danger">{error}</span> : null}
    </label>
  )
}

type CheckProps = Omit<ComponentProps<'input'>, 'type'> & {
  label: string
}

export function Checkbox({ label, className, ...props }: CheckProps) {
  return (
    <label className={cn('flex cursor-pointer items-center gap-2.5 text-sm text-ink', className)}>
      <input type="checkbox" className="size-4 rounded accent-[var(--color-brand)]" {...props} />
      {label}
    </label>
  )
}
