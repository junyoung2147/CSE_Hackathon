import { useEffect, useMemo, useState } from 'react'
import { Background, Controls, ReactFlow, ReactFlowProvider, useReactFlow, type Node } from '@xyflow/react'
import { ancestorsOf, edges, prereqsOf, subjectByCode } from './data'
import { layoutGraph, NODE_H, NODE_W, toFlowEdges } from './layout'
import { hasBackend, loadCompleted, setCompleted } from './api'
import SubjectPanel from './SubjectPanel'

type Status = 'done' | 'available' | 'locked'

const COLORS: Record<Status, { bg: string; border: string; text: string }> = {
  done: { bg: '#dcfce7', border: '#16a34a', text: '#14532d' },
  available: { bg: '#eff6ff', border: '#3b82f6', text: '#1e3a8a' },
  locked: { bg: '#f8fafc', border: '#cbd5e1', text: '#64748b' },
}

/** 이수 / 수강 가능(선수과목을 다 들음) / 아직 */
function statusOf(code: string, completed: Set<string>): Status {
  if (completed.has(code)) return 'done'
  const ok = prereqsOf(code).every((e) => completed.has(e.from) || e.orWith.some((c) => completed.has(c)))
  return ok ? 'available' : 'locked'
}

function RoadmapApp() {
  const flow = useReactFlow()
  const [completed, setCompletedState] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<string | null>(null)
  const [showIsolated, setShowIsolated] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadCompleted()
      .then(setCompletedState)
      .catch((e) => setError(`백엔드 연결 실패: ${e.message}`))
  }, [])

  const { visible, positions } = useMemo(() => layoutGraph(showIsolated), [showIsolated])
  const highlight = useMemo(() => (selected ? ancestorsOf(selected) : new Set<string>()), [selected])

  const nodes: Node[] = useMemo(
    () =>
      visible.map((s) => {
        const st = statusOf(s.code, completed)
        const c = COLORS[st]
        const isSel = s.code === selected
        const onPath = highlight.has(s.code)
        return {
          id: s.code,
          position: positions.get(s.code)!,
          data: { label: s.name },
          sourcePosition: 'right' as never,
          targetPosition: 'left' as never,
          style: {
            width: NODE_W,
            height: NODE_H,
            background: c.bg,
            color: c.text,
            border: `${isSel || onPath ? 3 : 1.5}px solid ${isSel ? '#111827' : onPath ? '#d97706' : c.border}`,
            borderRadius: 10,
            fontSize: 12.5,
            fontWeight: st === 'done' || isSel ? 600 : 500,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            textAlign: 'center' as const,
            padding: 4,
            opacity: selected && !isSel && !onPath ? 0.3 : 1,
          },
        }
      }),
    [visible, positions, completed, selected, highlight],
  )

  const flowEdges = useMemo(() => toFlowEdges(highlight, selected), [highlight, selected])

  // 과목을 고르면 그 과목과 선수과목 경로가 한 화면에 들어오게 확대
  useEffect(() => {
    const ids = selected ? [selected, ...highlight] : null
    const t = setTimeout(() => {
      if (ids) flow.fitView({ nodes: ids.filter((id) => positions.has(id)).map((id) => ({ id })), duration: 500, padding: 0.15, maxZoom: 1.2 })
      else flow.fitView({ duration: 500, padding: 0.05 })
    }, 0)
    return () => clearTimeout(t)
  }, [selected, highlight, positions, flow])

  const toggle = async (code: string) => {
    const next = new Set(completed)
    const willComplete = !next.has(code)
    if (willComplete) next.add(code)
    else next.delete(code)
    setCompletedState(next)
    try {
      await setCompleted(code, willComplete, next)
    } catch (e) {
      setError(`저장 실패: ${(e as Error).message}`)
    }
  }

  const doneCredits = [...completed].reduce((sum, c) => sum + (subjectByCode.get(c)?.credit ?? 0), 0)

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <strong>컴공지도</strong>
          <span className="sub">과목 {visible.length}개 · 선수관계 {edges.length}개 · 이수 {completed.size}과목 ({doneCredits}학점)</span>
        </div>
        <div className="legend">
          <span><i style={{ background: COLORS.done.bg, borderColor: COLORS.done.border }} />이수</span>
          <span><i style={{ background: COLORS.available.bg, borderColor: COLORS.available.border }} />수강 가능</span>
          <span><i style={{ background: COLORS.locked.bg, borderColor: COLORS.locked.border }} />선수과목 필요</span>
          <span><i className="path" />선택한 과목까지의 경로</span>
          <label className="check">
            <input type="checkbox" checked={showIsolated} onChange={(e) => setShowIsolated(e.target.checked)} />
            연결 없는 과목도 보기
          </label>
          <span className="mode">{hasBackend ? '백엔드 연결' : '로컬 모드'}</span>
        </div>
      </header>
      {error && <div className="error" onClick={() => setError(null)}>{error} (닫기)</div>}
      <main className="body">
        <div className="graph">
          <ReactFlow
            nodes={nodes}
            edges={flowEdges}
            onNodeClick={(_, n) => setSelected(n.id === selected ? null : n.id)}
            onPaneClick={() => setSelected(null)}
            nodesDraggable={false}
            fitView
            minZoom={0.1}
          >
            <Background gap={24} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        <SubjectPanel
          code={selected}
          completed={completed}
          onToggle={toggle}
          onSelect={setSelected}
          pathCount={highlight.size}
        />
      </main>
    </div>
  )
}

export default function App() {
  return (
    <ReactFlowProvider>
      <RoadmapApp />
    </ReactFlowProvider>
  )
}
