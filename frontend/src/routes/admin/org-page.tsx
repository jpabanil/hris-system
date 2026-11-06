import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import ReactFlow, {
  Background,
  Controls,
  Handle,
  Position,
  type Edge,
  type Node,
  type NodeProps,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { isQuiet, useApiQuery } from '../../api/session.ts'
import { EmptyState } from '../../components/empty-state.tsx'
import { PageHeader } from '../../components/page-header.tsx'
import { SkeletonRows } from '../../components/skeleton.tsx'
import { isRow, personName, readPath, type Row } from '../../lib/records.ts'

type Person = { id: string; label: string; sub: string; parent: string | null }
type NodeData = { label: string; sub: string }

function PersonNode({ data }: NodeProps<NodeData>) {
  return (
    <div className="glass w-48 rounded-xl px-3.5 py-2.5">
      <Handle type="target" position={Position.Top} className="!h-1.5 !w-1.5 !border-0 !bg-accent" />
      <div className="truncate text-sm font-medium text-ink">{data.label}</div>
      <div className="truncate text-xs text-muted">{data.sub}</div>
      <Handle type="source" position={Position.Bottom} className="!h-1.5 !w-1.5 !border-0 !bg-accent" />
    </div>
  )
}

const nodeTypes = { person: PersonNode }

function asRows(data: unknown, key: string): Row[] {
  if (!isRow(data)) return []
  const value = data[key]
  return Array.isArray(value) ? value.filter(isRow) : []
}

function layoutPeople(people: Person[]): { nodes: Node<NodeData>[]; edges: Edge[] } {
  const byId = new Map(people.map((person) => [person.id, person]))
  const children = new Map<string, Person[]>()
  const roots: Person[] = []
  for (const person of people) {
    const parent = person.parent && byId.has(person.parent) && person.parent !== person.id ? person.parent : null
    if (!parent) roots.push(person)
    else {
      const list = children.get(parent) ?? []
      list.push(person)
      children.set(parent, list)
    }
  }

  const width = new Map<string, number>()
  const measure = (person: Person, stack: Set<string>): number => {
    const cached = width.get(person.id)
    if (cached) return cached
    if (stack.has(person.id)) return 1
    stack.add(person.id)
    const kids = children.get(person.id) ?? []
    const total = kids.length ? kids.reduce((sum, kid) => sum + measure(kid, stack), 0) : 1
    width.set(person.id, total)
    stack.delete(person.id)
    return total
  }
  for (const person of people) measure(person, new Set())

  const nodes: Node<NodeData>[] = []
  const edges: Edge[] = []
  const seen = new Set<string>()
  const place = (person: Person, left: number, depth: number) => {
    if (seen.has(person.id)) return
    seen.add(person.id)
    const span = width.get(person.id) ?? 1
    nodes.push({
      id: person.id,
      type: 'person',
      position: { x: left + (span * 200) / 2 - 88, y: depth * 120 },
      data: { label: person.label, sub: person.sub },
    })
    let cursor = left
    for (const kid of children.get(person.id) ?? []) {
      edges.push({ id: `${person.id}-${kid.id}`, source: person.id, target: kid.id, style: { stroke: '#c4622d' } })
      place(kid, cursor, depth + 1)
      cursor += (width.get(kid.id) ?? 1) * 200
    }
  }

  let cursor = 0
  const queue = [...roots]
  for (const person of people) {
    if (!roots.some((root) => root.id === person.id)) queue.push(person)
  }
  for (const person of queue) {
    if (seen.has(person.id)) continue
    place(person, cursor, 0)
    cursor += (width.get(person.id) ?? 1) * 200
  }
  return { nodes, edges }
}

export function OrgPage() {
  const { t } = useTranslation()
  const query = useApiQuery('/org-chart')
  const graph = useMemo(() => {
    const employees = asRows(query.data, 'employees')
    const positions = new Map(asRows(query.data, 'positions').map((row) => [String(row.id ?? ''), readPath(row, 'title')]))
    const people: Person[] = employees
      .map((row) => {
        const id = typeof row.id === 'string' ? row.id : ''
        if (!id) return null
        const title = positions.get(typeof row.position_id === 'string' ? row.position_id : '') ?? ''
        const sub = [title, readPath(row, 'employee_no')].filter(Boolean).join(' · ')
        return {
          id,
          label: personName(row.name) || readPath(row, 'employee_no') || id,
          sub: sub || t('org.unassigned'),
          parent: typeof row.reports_to === 'string' ? row.reports_to : null,
        }
      })
      .filter((person): person is Person => person !== null)

    const source =
      people.length > 0
        ? people
        : asRows(query.data, 'departments')
            .map((row) => {
              const id = typeof row.id === 'string' ? row.id : ''
              if (!id) return null
              return {
                id,
                label: readPath(row, 'name') || id,
                sub: readPath(row, 'code') || t('org.unassigned'),
                parent: typeof row.parent_id === 'string' ? row.parent_id : null,
              }
            })
            .filter((person): person is Person => person !== null)

    return layoutPeople(source)
  }, [query.data, t])

  const quiet = isQuiet(query.data)

  return (
    <div>
      <PageHeader title={t('org.title')} subtitle={t('org.subtitle')} />
      {query.isLoading ? <SkeletonRows rows={6} /> : null}
      {query.isError ? <EmptyState title={t('common.error')} /> : null}
      {query.isSuccess && (quiet || graph.nodes.length === 0) ? (
        <EmptyState title={quiet ? t('common.quiet') : t('org.empty')} />
      ) : null}
      {graph.nodes.length > 0 ? (
        <div className="org-canvas glass h-[34rem] overflow-hidden rounded-2xl">
          <ReactFlow
            nodes={graph.nodes}
            edges={graph.edges}
            nodeTypes={nodeTypes}
            fitView
            nodesDraggable={false}
            nodesConnectable={false}
            proOptions={{ hideAttribution: false }}
          >
            <Background color="rgba(148,163,184,0.45)" gap={20} size={1.2} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
      ) : null}
    </div>
  )
}
