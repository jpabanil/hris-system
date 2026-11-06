export type SessionUser = {
  id: string
  email: string
  company_id: string | null
  employee_id: string | null
  permissions: string[]
  roles: string[]
  is_superadmin: boolean
  is_impersonating: boolean
  impersonator_id: string | null
  locale: string
  must_change_password: boolean
  totp_enabled: boolean
}

export function portalOnly(user: SessionUser): boolean {
  if (user.is_superadmin) return false
  return user.permissions.length > 0 && user.permissions.every((permission) => permission === 'self.service')
}

export function canSee(user: SessionUser, permissions: string[]): boolean {
  if (permissions.length === 0 || user.is_superadmin) return true
  return permissions.some((permission) => user.permissions.includes(permission))
}
