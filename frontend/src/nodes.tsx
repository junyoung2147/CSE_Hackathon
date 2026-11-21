import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { Status } from './data'
import { NODE_H, NODE_W } from './layout'

export const COLORS: Record<Status, { bg: string; border: string; text: string }> = {
  done: { bg: '#dcfce7', border: '#16a34a', text: '#14532d' },
  taking: { bg: '#fef3c7', border: '#d97706', text: '#78350f' },
  next: { bg: '#ffffff', border: '#60a5fa', text: '#1e3a8a' },
  none: { bg: '#ffffff', border: '#d1d5db', text: '#374151' },
}

export type CourseNodeData = {
  name: string
  status: Status
  required: boolean
  grade?: string // 이수했으면 성적 (없으면 '')
  emphasis: 'selected' | 'target' | 'path' | 'dim' | 'normal'
}

/** 과목 노드: 이름 + (전공필수 표시). 왼쪽으로 들어오고 오른쪽으로 나간다. */
export function CourseNode({ data }: NodeProps) {
  const d = data as CourseNodeData
  const c = COLORS[d.status]
  const border =
    d.emphasis === 'selected' ? '3px solid #111827'
    : d.emphasis === 'target' ? '3px solid #4f46e5'
    : d.emphasis === 'path' ? '2px solid #4f46e5'
    : `1.5px solid ${c.border}`
  return (
    <div
      className="course-node"
      style={{
        width: NODE_W,
        height: NODE_H,
        background: c.bg,
        color: c.text,
        border,
        opacity: d.emphasis === 'dim' ? 0.25 : 1,
        fontWeight: d.status === 'done' || d.emphasis === 'selected' || d.emphasis === 'target' ? 600 : 500,
      }}
    >
      <Handle type="target" position={Position.Left} />
      <span className="course-name">{d.name}</span>
      {d.required && <span className="badge">필수</span>}
      {d.status === 'done' && d.grade && <span className="grade">{d.grade}</span>}
      {d.status === 'taking' && <span className="grade taking">수강 중</span>}
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

/** 학기 제목 (1-1, 1-2 …) */
export function SemesterHeader({ data }: NodeProps) {
  return <div className="sem-header">{(data as { label: string }).label}</div>
}

/** 학기 사이 점선 */
export function Divider({ data }: NodeProps) {
  return <div className="sem-divider" style={{ height: (data as { height: number }).height }} />
}

export const nodeTypes = { course: CourseNode, semester: SemesterHeader, divider: Divider }
