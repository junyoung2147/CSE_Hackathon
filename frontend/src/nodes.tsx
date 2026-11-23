import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { Status } from './data'
import { NODE_H, NODE_W } from './layout'

export const COLORS: Record<Status, { bg: string; border: string; text: string }> = {
  done: { bg: '#3d6a98', border: '#3d6a98', text: '#ffffff' },
  taking: { bg: '#ffffff', border: '#3d6a98', text: '#1c2430' },
  next: { bg: '#ffffff', border: '#aab4c0', text: '#6b7686' },
  none: { bg: '#eef2f6', border: 'transparent', text: '#a3adba' },
}
const ORANGE = '#e08a1e'

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
  const lit = d.emphasis === 'target' || d.emphasis === 'path' // 진로 경로
  const border =
    d.emphasis === 'selected' ? '2px solid #1c2430'
    : d.emphasis === 'target' ? `2px solid ${ORANGE}`
    : d.emphasis === 'path' ? `1.5px solid ${ORANGE}`
    : d.status === 'next' ? `1.5px dashed ${c.border}`
    : d.status === 'taking' ? `1.5px solid ${c.border}`
    : `1px solid ${c.border}`
  const plain = lit && d.status === 'none' // 경로 위의 미이수 과목은 흰 바탕
  return (
    <div
      className="course-node"
      style={{
        width: NODE_W,
        height: NODE_H,
        background: plain ? '#fff' : c.bg,
        color: plain ? '#1c2430' : c.text,
        border,
        opacity: d.emphasis === 'dim' ? 0.25 : 1,
        fontWeight: d.status === 'none' && !lit ? 400 : 600,
      }}
    >
      <Handle type="target" position={Position.Left} id="t-left" />
      {/* 같은 학기 열 안에서 잇는 선은 위·아래로 연결 (옆으로 나갔다 돌아오면 다른 과목을 가림) */}
      <Handle type="target" position={Position.Top} id="t-top" />
      <Handle type="target" position={Position.Bottom} id="t-bottom" />
      <Handle type="source" position={Position.Top} id="s-top" />
      <Handle type="source" position={Position.Bottom} id="s-bottom" />
      <span className="course-name">{d.name}</span>
      {d.required && <span className="badge">필수</span>}
      {d.status === 'done' && d.grade && <span className="grade">{d.grade}</span>}
      {d.grade === 'F' && <span className="grade fail">F 재수강</span>}
      {d.status === 'taking' && <span className="grade taking">수강 중</span>}
      <Handle type="source" position={Position.Right} id="s-right" />
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
