import { z } from 'zod'

export function leaveSchema(required: string, endBefore: string) {
  return z
    .object({
      leave_type_id: z.string().trim().min(1, { error: required }),
      start_date: z.string().min(1, { error: required }),
      end_date: z.string().min(1, { error: required }),
      reason: z.string().trim().min(1, { error: required }),
      half_day: z.boolean(),
    })
    .refine((value) => value.end_date >= value.start_date, {
      path: ['end_date'],
      error: endBefore,
    })
}

export type LeaveValues = z.infer<ReturnType<typeof leaveSchema>>

export function leaveDays(start: string, end: string, half: boolean): string {
  const from = new Date(`${start}T00:00:00`)
  const to = new Date(`${end}T00:00:00`)
  const diff = Math.round((to.getTime() - from.getTime()) / 86_400_000) + 1
  if (!Number.isFinite(diff) || diff < 1) return '0'
  if (half && diff === 1) return '0.5'
  return String(diff)
}
