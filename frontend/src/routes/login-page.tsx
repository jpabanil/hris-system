import { useMemo, useState } from 'react'
import { standardSchemaResolver } from '@hookform/resolvers/standard-schema'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api/client.ts'
import { useSession } from '../api/session.ts'
import { LanguageSwitch } from '../components/language-switch.tsx'
import { ThemeToggle } from '../components/theme-toggle.tsx'
import { BrandMark } from '../components/brand.tsx'
import { Button } from '../components/ui/button.tsx'
import { Input } from '../components/ui/input.tsx'
import { loginSchema, mfaSchema, type LoginValues, type MfaValues } from '../features/auth/schema.ts'

type LoginResult = {
  mfa_required?: boolean
  mfa_token?: string
}

function messageFor(error: unknown, failed: string, locked: string): string {
  if (error instanceof ApiError && error.code === 'locked') return locked
  if (error instanceof ApiError && (error.status === 401 || error.code === 'unauthorized')) return failed
  if (error instanceof ApiError) return error.message
  return failed
}

export function LoginPage() {
  const { t } = useTranslation()
  const session = useSession()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [mfaToken, setMfaToken] = useState<string | null>(null)
  const [formError, setFormError] = useState('')

  const loginFormSchema = useMemo(() => loginSchema(t('common.required'), t('auth.emailInvalid')), [t])
  const codeSchema = useMemo(() => mfaSchema(t('common.required')), [t])

  const loginForm = useForm<LoginValues>({
    resolver: standardSchemaResolver(loginFormSchema),
    defaultValues: { email: '', password: '' },
  })
  const mfaForm = useForm<MfaValues>({
    resolver: standardSchemaResolver(codeSchema),
    defaultValues: { code: '' },
  })

  const login = useMutation({
    mutationFn: (values: LoginValues) =>
      api<LoginResult>('/auth/login', { method: 'POST', body: JSON.stringify(values) }),
    onSuccess: async (result) => {
      if (result.mfa_required && result.mfa_token) {
        setMfaToken(result.mfa_token)
        setFormError('')
        return
      }
      await queryClient.invalidateQueries({ queryKey: ['me'] })
      void navigate('/', { replace: true })
    },
    onError: (error) => setFormError(messageFor(error, t('auth.failed'), t('auth.locked'))),
  })

  const verify = useMutation({
    mutationFn: (values: MfaValues) =>
      api('/auth/2fa/verify', {
        method: 'POST',
        body: JSON.stringify({ mfa_token: mfaToken, code: values.code }),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['me'] })
      void navigate('/', { replace: true })
    },
    onError: (error) => setFormError(messageFor(error, t('auth.failed'), t('auth.locked'))),
  })

  if (session.data) return <Navigate to="/" replace />

  return (
    <main className="grid min-h-svh text-ink lg:grid-cols-[1.1fr_1fr]">
      <aside className="relative hidden overflow-hidden p-10 lg:flex lg:flex-col lg:justify-between">
        <div className="bg-brand-gradient absolute inset-3 rounded-[2rem] opacity-95" aria-hidden="true" />
        <div
          className="absolute inset-3 rounded-[2rem] opacity-60 mix-blend-overlay"
          aria-hidden="true"
          style={{
            background:
              'radial-gradient(30rem 20rem at 20% 10%, rgb(255 255 255 / 0.55), transparent 60%), radial-gradient(26rem 22rem at 90% 90%, rgb(236 72 153 / 0.7), transparent 60%)',
          }}
        />
        <div className="relative flex items-center gap-3 p-4 text-white">
          <BrandMark className="bg-white/20 shadow-none ring-1 ring-white/40 backdrop-blur" />
          <h1 className="text-xl font-extrabold tracking-tight">{t('app.name')}</h1>
        </div>
        <div className="relative max-w-md p-4 text-white">
          <p className="text-5xl leading-[1.05] font-extrabold tracking-tight">{t('app.tagline')}</p>
          <div className="mt-10 grid grid-cols-3 gap-3">
            {['nav.employees', 'nav.attendance', 'nav.payroll'].map((key) => (
              <div key={key} className="rounded-2xl bg-white/15 px-4 py-3 text-sm font-semibold ring-1 ring-white/25 backdrop-blur-md">
                {t(key)}
              </div>
            ))}
          </div>
        </div>
      </aside>
      <div className="flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 lg:invisible">
            <BrandMark />
            <h1 className="text-xl font-extrabold tracking-tight">{t('app.name')}</h1>
          </div>
          <div className="flex items-center gap-2">
            <LanguageSwitch />
            <ThemeToggle />
          </div>
        </div>
        <section className="glass rounded-3xl p-6 sm:p-7">
          <h2 className="text-2xl font-bold tracking-tight">{mfaToken ? t('auth.mfaTitle') : t('auth.welcome')}</h2>
          <p className="mt-1.5 text-sm text-muted">{mfaToken ? t('auth.mfaHint') : t('auth.hint')}</p>
          {formError ? (
            <p role="alert" className="mt-4 rounded-xl border border-danger/30 bg-danger/10 px-3.5 py-2.5 text-sm font-medium text-danger">
              {formError}
            </p>
          ) : null}
          {mfaToken ? (
            <form
              className="mt-6 space-y-4"
              noValidate
              onSubmit={mfaForm.handleSubmit((values) => verify.mutate(values))}
            >
              <Input
                label={t('auth.code')}
                inputMode="numeric"
                autoComplete="one-time-code"
                error={mfaForm.formState.errors.code?.message}
                {...mfaForm.register('code')}
              />
              <Button type="submit" className="w-full" disabled={verify.isPending}>
                {verify.isPending ? t('auth.verifying') : t('auth.verify')}
              </Button>
              <Button
                variant="ghost"
                className="w-full"
                onClick={() => {
                  setMfaToken(null)
                  setFormError('')
                }}
              >
                {t('auth.back')}
              </Button>
            </form>
          ) : (
            <form
              className="mt-6 space-y-4"
              noValidate
              onSubmit={loginForm.handleSubmit((values) => login.mutate(values))}
            >
              <Input
                label={t('auth.email')}
                type="email"
                autoComplete="username"
                error={loginForm.formState.errors.email?.message}
                {...loginForm.register('email')}
              />
              <Input
                label={t('auth.password')}
                type="password"
                autoComplete="current-password"
                error={loginForm.formState.errors.password?.message}
                {...loginForm.register('password')}
              />
              <Button type="submit" className="w-full" disabled={login.isPending}>
                {login.isPending ? t('auth.signingIn') : t('auth.signIn')}
              </Button>
            </form>
          )}
        </section>
        <p className="mt-6 text-center text-xs text-muted lg:hidden">{t('app.tagline')}</p>
      </div>
      </div>
    </main>
  )
}
