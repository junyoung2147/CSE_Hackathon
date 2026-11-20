import { useEffect, useMemo, useState } from 'react'
import { Background, Controls, ReactFlow, ReactFlowProvider, useReactFlow, type Node } from '@xyflow/react'
import { ancestorsOf, buildMajorGraph, majors, SEMESTER_LABELS, statusOf } from './data'
import { careers } from './careers'
import { COL_W, colX, layoutBySemester, NODE_W, toFlowEdges } from './layout'
import { COLORS, nodeTypes, type CourseNodeData } from './nodes'
import { hasBackend, loadCompleted, setCompleted } from './api'
import { store, type Grades, type Scale } from './progress'
import SubjectPanel from './SubjectPanel'
import CareerPanel from './CareerPanel'
import StatusPanel from './StatusPanel'
import TimetableView from './TimetableView'

const DEFAULT_MAJOR = majors.includes('심화컴퓨팅전공') ? '심화컴퓨팅전공' : majors[0]

function RoadmapApp() {
  const flow = useReactFlow()
  const [major, setMajor] = useState(DEFAULT_MAJOR)
  const [careerId, setCareerId] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView] = useState<'roadmap' | 'timetable'>('roadmap')
  const [error, setError] = useState<string | null>(null)

  // 내 학업 현황 (브라우저에 저장)
  const [grades, setGrades] = useState<Grades>(store.loadGrades) // 과목코드 → 성적('' = 미입력)
  const [taking, setTaking] = useState<string[]>(store.loadTaking) // 이번 학기 수강 중
  const [extra, setExtra] = useState<number>(store.loadExtra) // 지도에 없는 교양·기타 학점
  const [scale, setScale] = useState<Scale>(store.loadScale)
  useEffect(() => store.saveGrades(grades), [grades])
  useEffect(() => store.saveTaking(taking), [taking])
  useEffect(() => store.saveExtra(extra), [extra])
  useEffect(() => store.saveScale(scale), [scale])
  const completed = useMemo(() => new Set(Object.keys(grades)), [grades])
  const takingSet = useMemo(() => new Set(taking), [taking])

  // 백엔드가 있으면 거기 저장된 이수 과목도 합친다
  useEffect(() => {
    loadCompleted()
      .then((codes) => setGrades((g) => ({ ...Object.fromEntries([...codes].map((c) => [c, ''])), ...g })))
      .catch((e) => setError(`백엔드 연결 실패: ${e.message}`))
  }, [])

  // 1) 전공 → 그 전공 교육과정 그래프 → 학기 열 배치
  const graph = useMemo(() => buildMajorGraph(major), [major])
  const { positions, height } = useMemo(() => layoutBySemester(graph), [graph])
  const career = careers.find((c) => c.id === careerId) ?? null

  // 2) 강조할 과목들: 과목을 골랐으면 그 과목까지, 진로를 골랐으면 그 진로까지 가는 경로
  const targets = useMemo(
    () => (career ? career.targets.filter((c) => graph.courseByCode.has(c)) : []),
    [career, graph],
  )
  const focus = useMemo(() => {
    const roots = selected ? [selected] : targets
    if (!roots.length) return new Set<string>()
    return new Set([...roots, ...ancestorsOf(roots, graph.edges)])
  }, [selected, targets, graph])
  const active = focus.size > 0

  // 3) React Flow 노드: 학기 제목 + 점선 + 과목
  const nodes: Node[] = useMemo(() => {
    const deco: Node[] = SEMESTER_LABELS.flatMap((label, i) => [
      {
        id: `sem-${i}`,
        type: 'semester',
        position: { x: colX(i), y: 0 },
        data: { label: `${label}학기` },
        selectable: false,
        draggable: false,
        style: { width: NODE_W },
      },
      ...(i > 0
        ? [{
            id: `div-${i}`,
            type: 'divider',
            position: { x: colX(i) - (COL_W - NODE_W) / 2, y: 0 },
            data: { height },
            selectable: false,
            draggable: false,
            zIndex: -1,
          } as Node]
        : []),
    ])
    const courseNodes: Node[] = graph.courses.map((c) => {
      const emphasis: CourseNodeData['emphasis'] =
        c.code === selected ? 'selected'
        : !selected && targets.includes(c.code) ? 'target'
        : focus.has(c.code) ? 'path'
        : active ? 'dim'
        : 'normal'
      return {
        id: c.code,
        type: 'course',
        position: positions.get(c.code)!,
        data: {
          name: c.name,
          status: statusOf(c.code, completed, takingSet),
          required: c.required,
          grade: grades[c.code],
          emphasis,
        } satisfies CourseNodeData,
        draggable: false,
      }
    })
    return [...deco, ...courseNodes]
  }, [graph, positions, height, completed, takingSet, grades, selected, targets, focus, active])

  const flowEdges = useMemo(() => toFlowEdges(graph.edges, focus, active), [graph, focus, active])

  // 고른 경로가 한 화면에 들어오게 확대 / 아무것도 안 고르면 전체 보기
  useEffect(() => {
    const t = setTimeout(() => {
      if (active) flow.fitView({ nodes: [...focus].map((id) => ({ id })), duration: 500, padding: 0.2, maxZoom: 1.1 })
      else flow.fitView({ duration: 500, padding: 0.05 })
    }, 50)
    return () => clearTimeout(t)
  }, [focus, active, flow, major])

  const sync = (code: string, done: boolean) =>
    setCompleted(code, done).catch((e) => setError(`저장 실패: ${(e as Error).message}`))

  const toggle = (code: string) => {
    const done = !(code in grades)
    setGrades((g) => {
      const next = { ...g }
      if (done) next[code] = ''
      else delete next[code]
      return next
    })
    if (done) setTaking((t) => t.filter((c) => c !== code))
    sync(code, done)
  }

  const setGrade = (code: string, grade: string) => setGrades((g) => ({ ...g, [code]: grade }))

  // 에브리타임에서 불러온 과목: 이전 학기 → 이수(성적 미입력), 이번 학기 → 수강 중
  const applyTimetable = (done: string[], now: string[]) => {
    setGrades((g) => ({ ...Object.fromEntries(done.map((c) => [c, ''])), ...g }))
    setTaking(now.filter((c) => !(c in grades)))
    done.forEach((c) => sync(c, true))
  }

  const majorCredits = graph.courses.filter((c) => completed.has(c.code)).reduce((s, c) => s + (c.credit ?? 0), 0)

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <strong>컴공지도</strong>
          <div className="tabs">
            <button className={view === 'roadmap' ? 'on' : ''} onClick={() => setView('roadmap')}>로드맵</button>
            <button className={view === 'timetable' ? 'on' : ''} onClick={() => setView('timetable')}>내 시간표</button>
          </div>
          <select value={major} onChange={(e) => { setMajor(e.target.value); setSelected(null) }}>
            {majors.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <span className="sub">교육과정 {graph.courses.length}과목 · 이수 {majorCredits}학점</span>
        </div>
        <div className="legend">
          <span><i style={{ background: COLORS.done.bg, borderColor: COLORS.done.border }} />이수</span>
          <span><i style={{ background: COLORS.taking.bg, borderColor: COLORS.taking.border }} />수강 중</span>
          <span><i style={{ background: COLORS.available.bg, borderColor: COLORS.available.border }} />수강 가능</span>
          <span><i style={{ background: COLORS.locked.bg, borderColor: COLORS.locked.border }} />선수과목 필요</span>
          <span className="mode">{hasBackend ? '백엔드 연결' : '로컬 모드'}</span>
        </div>
      </header>

      {view === 'timetable' && (
        <main className="body">
          <TimetableView onApply={(d, t) => { applyTimetable(d, t) }} />
        </main>
      )}

      {view === 'roadmap' && (<>
      <nav className="careers">
        <span className="label">진로</span>
        {careers.map((c) => (
          <button
            key={c.id}
            className={`career ${careerId === c.id ? 'on' : ''}`}
            onClick={() => { setCareerId(careerId === c.id ? null : c.id); setSelected(null) }}
            title={c.description}
          >
            {c.name}
          </button>
        ))}
      </nav>

      {error && <div className="error" onClick={() => setError(null)}>{error} (닫기)</div>}

      <main className="body">
        <div className="graph">
          <ReactFlow
            nodes={nodes}
            edges={flowEdges}
            nodeTypes={nodeTypes}
            onNodeClick={(_, n) => {
              if (n.type !== 'course') return
              setSelected(n.id === selected ? null : n.id)
            }}
            onPaneClick={() => setSelected(null)}
            nodesDraggable={false}
            nodesConnectable={false}
            fitView
            minZoom={0.15}
          >
            <Background gap={24} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        {selected ? (
          <SubjectPanel
            code={selected}
            course={graph.courseByCode.get(selected)}
            completed={completed}
            grade={grades[selected]}
            scale={scale}
            onToggle={toggle}
            onGrade={setGrade}
            onSelect={setSelected}
            pathCount={focus.size - 1}
          />
        ) : career ? (
          <CareerPanel career={career} graph={graph} focus={focus} completed={completed} onSelect={setSelected} />
        ) : (
          <StatusPanel
            major={major}
            grades={grades}
            scale={scale}
            extra={extra}
            onScale={setScale}
            onExtra={setExtra}
            onSelect={setSelected}
            onOpenTimetable={() => setView('timetable')}
          />
        )}
      </main>
      </>)}
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
