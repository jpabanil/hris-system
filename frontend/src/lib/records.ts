export type Row = Record<string, unknown>

export function isRow(value: unknown): value is Row {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

export function itemsOf(data: unknown): Row[] {
  if (Array.isArray(data)) return data.filter(isRow)
  if (isRow(data) && Array.isArray(data.items)) return data.items.filter(isRow)
  return []
}

export function totalOf(data: unknown): number {
  if (isRow(data) && typeof data.total === 'number') return data.total
  return itemsOf(data).length
}

export function readPath(row: Row, path: string): string {
  const parts = path.split('.')
  let current: unknown = row
  for (const part of parts) {
    if (!isRow(current)) return ''
    current = current[part]
  }
  if (typeof current === 'string' || typeof current === 'number' || typeof current === 'boolean') {
    return String(current)
  }
  return ''
}

export function personName(value: unknown): string {
  if (typeof value === 'string') return value
  if (!isRow(value)) return ''
  return [value.first, value.middle, value.last, value.suffix]
    .filter((part): part is string => typeof part === 'string' && part.length > 0)
    .join(' ')
}

export function display(value: unknown): string {
  if (value == null || value === '') return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  const name = personName(value)
  return name || '—'
}

export function idOf(row: Row): string {
  const id = row.id ?? row._id
  return typeof id === 'string' ? id : ''
}

export function labelState(translate: (key: string, options: { defaultValue: string }) => string, value: string) {
  if (!value) return '—'
  return translate(`states.${value}`, { defaultValue: value })
}

export function statusCounts(rows: Row[]): { status: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const row of rows) {
    const status = readPath(row, 'employment_status') || readPath(row, 'status') || '—'
    counts.set(status, (counts.get(status) ?? 0) + 1)
  }
  return [...counts.entries()].map(([status, count]) => ({ status, count }))
}

export function openPeriodCount(data: unknown): number {
  const items = itemsOf(data)
  if (!items.length) return totalOf(data)
  return items.filter((row) => {
    const status = readPath(row, 'status')
    return status !== 'released' && status !== 'locked'
  }).length
}
