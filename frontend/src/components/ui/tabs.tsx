import { cn } from '../../lib/cn.ts'

type Tab = { id: string; label: string }

export function Tabs({
  tabs,
  value,
  onChange,
}: {
  tabs: Tab[]
  value: string
  onChange: (id: string) => void
}) {
  return (
    <div role="tablist" className="glass mb-5 inline-flex max-w-full gap-1 overflow-x-auto rounded-xl p-1">
      {tabs.map((tab) => {
        const selected = value === tab.id
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(tab.id)}
            className={cn(
              'rounded-lg px-3.5 py-1.5 text-sm font-medium whitespace-nowrap transition-all',
              selected ? 'bg-brand-gradient text-white shadow-sm' : 'text-muted hover:bg-soft hover:text-ink',
            )}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
