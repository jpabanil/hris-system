import { z } from 'zod'

const employmentTypes = ['regular', 'probationary', 'contractual', 'project', 'part_time'] as const
const employmentStatuses = ['active', 'inactive', 'separated'] as const

export function employeeSchema(required: string, emailInvalid: string) {
  return z.object({
    employee_no: z.string().trim().min(1, { error: required }),
    first: z.string().trim().min(1, { error: required }),
    middle: z.string(),
    last: z.string().trim().min(1, { error: required }),
    suffix: z.string(),
    employment_type: z.enum(employmentTypes),
    employment_status: z.enum(employmentStatuses),
    date_hired: z.string().min(1, { error: required }),
    work_email: z.union([z.literal(''), z.email({ error: emailInvalid })]),
    mobile: z.string(),
  })
}

export type EmployeeValues = z.infer<ReturnType<typeof employeeSchema>>
export const employmentTypeOptions = employmentTypes
export const employmentStatusOptions = employmentStatuses
