import type { ReactNode } from 'react'

export function Table({ children }: { children: ReactNode }) {
  return (
    <div className="-mx-1 overflow-x-auto px-1">
      <table className="w-full border-separate border-spacing-0 text-left text-sm">{children}</table>
    </div>
  )
}

export function Th({ children }: { children: ReactNode }) {
  return (
    <th className="border-b border-line px-3 py-2.5 text-left text-[11px] font-semibold tracking-wider text-muted uppercase first:pl-4 last:pr-4">
      {children}
    </th>
  )
}

export function Td({ children }: { children: ReactNode }) {
  return (
    <td className="border-b border-line px-3 py-3 align-top text-ink transition-colors group-last:border-b-0 first:pl-4 last:pr-4">
      {children}
    </td>
  )
}

export function Tr({ children }: { children: ReactNode }) {
  return <tr className="group transition-colors hover:bg-soft">{children}</tr>
}
