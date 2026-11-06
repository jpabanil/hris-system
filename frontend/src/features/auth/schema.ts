import { z } from 'zod'

export function loginSchema(required: string, emailInvalid: string) {
  return z.object({
    email: z.email({
      error: (issue) => (typeof issue.input === 'string' && issue.input.length > 0 ? emailInvalid : required),
    }),
    password: z.string().min(1, { error: required }),
  })
}

export function mfaSchema(required: string) {
  return z.object({
    code: z.string().trim().min(6, { error: required }).max(8, { error: required }),
  })
}

export type LoginValues = z.infer<ReturnType<typeof loginSchema>>
export type MfaValues = z.infer<ReturnType<typeof mfaSchema>>
