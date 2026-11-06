import type { ComponentProps } from 'react'
import { cn } from '../../lib/cn.ts'

type ButtonProps = ComponentProps<'button'> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
}

const variants = {
  primary:
    'bg-brand-gradient text-white shadow-[0_8px_20px_-8px_var(--color-brand)] hover:brightness-110 hover:shadow-[0_10px_24px_-8px_var(--color-brand)]',
  secondary: 'glass text-ink hover:bg-soft',
  ghost: 'text-ink hover:bg-soft',
  danger: 'bg-danger text-white shadow-[0_8px_20px_-10px_var(--color-danger)] hover:brightness-110',
}

const sizes = {
  sm: 'h-8 px-3 text-xs',
  md: 'h-10 px-4 text-sm',
}

export function Button({ variant = 'primary', size = 'md', className, type = 'button', ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-all duration-200 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  )
}
