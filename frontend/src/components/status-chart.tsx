import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export function StatusChart({ data }: { data: { status: string; count: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="status-bar" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-brand-2)" />
            <stop offset="100%" stopColor="var(--color-brand)" stopOpacity={0.75} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="var(--color-line)" strokeDasharray="4 4" vertical={false} />
        <XAxis dataKey="status" tick={{ fill: 'var(--color-muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
        <YAxis
          allowDecimals={false}
          width={32}
          tick={{ fill: 'var(--color-muted)', fontSize: 12 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip cursor={{ fill: 'var(--color-soft)', radius: 8 }} />
        <Bar dataKey="count" fill="url(#status-bar)" radius={[8, 8, 4, 4]} maxBarSize={56} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}
