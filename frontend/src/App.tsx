import { useEffect, useMemo, useState } from 'react'
import { Controls, ReactFlow, ReactFlowProvider, useReactFlow, type Node } from '@xyflow/react'
import { ancestorsOf, buildMajorGraph, COLUMN_LABELS, majors, statusOf } from './data'
import { careers as presetCareers, type Career } from './careers'
import { COL_W, colX, layoutBySemester, NODE_W, toFlowEdges } from './layout'
import { nodeTypes, type CourseNodeData } from './nodes'
import { hasBackend, loadCompleted, setCompleted, type ChatMessage } from './api'
import { store, type Grades, type Scale } from './progress'
import SubjectPanel from './SubjectPanel'
import CareerPanel from './CareerPanel'
import StatusPanel from './StatusPanel'
import TimetableView from './TimetableView'
import ChatView from './ChatView'
import SearchBox from './SearchBox'

const DEFAULT_MAJOR = majors.includes('심화컴퓨팅전공') ? '심화컴퓨팅전공' : majors[0]

function RoadmapApp() {
  const flow = useReactFlow()
  const [major, setMajor] = useState(DEFAULT_MAJOR)
  const [careerId, setCareerId] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView] = useState<'roadmap' | 'timetable' | 'chat'>('roadmap')
  const [chatMsgs, setChatMsgs] = useState<ChatMessage[]>([]) // AI 상담 대화 (탭을 옮겨도 유지)
  const [mine, setMine] = useState(store.loadMine) // AI로 만든 내 로드맵
  useEffect(() => { store.saveMine(mine) }, [mine])
  const [error, setError] = useState<string | null>(null)

  // 내 학업 현황 (브라우저에 저장)
  const [grades, setGrades] = useState<Grades>(store.loadGrades) // 과목코드 → 성적('' = 미입력)
  const [taking, setTaking] = useState<string[]>(store.loadTaking) // 이번 학기 수강 중
  const [extra, setExtra] = useState<number>(store.loadExtra) // 지도에 없는 교양·기타 학점
  const [scale] = useState<Scale>(store.loadScale)
  useEffect(() => { store.saveGrades(grades) }, [grades])
  useEffect(() => { store.saveTaking(taking) }, [taking])
  useEffect(() => { store.saveExtra(extra) }, [extra])
  // F를 받은 과목은 '이수'가 아니다 (성적은 남겨서 재수강 표시용으로 쓴다)
  const completed = useMemo(() => new Set(Object.entries(grades).filter(([, g]) => g !== 'F').map(([c]) => c)), [grades])
  const takingSet = useMemo(() => new Set(taking), [taking])

  // 백엔드가 있으면 거기 저장된 이수 과목도 합친다
  useEffect(() => {
    loadCompleted()
      .then((codes) => setGrades((g) => ({ ...Object.fromEntries([...codes].map((c) => [c, ''])), ...g })))
      .catch((e) => setError(`백엔드 연결 실패: ${e.message}`))
  }, [])

  // 1) 전공 → 그 전공 교육과정 그래프 → 학기 열 배치
  const careers: Career[] = useMemo(
    () => [
      ...(mine.targets.length
        ? [{ id: 'mine', name: '★ 내 로드맵', description: 'AI 상담으로 만든 목표 과목', targets: mine.targets }]
        : []),
      ...presetCareers,
    ],
    [mine],
  )
  const career = careers.find((c) => c.id === careerId) ?? null
  // 내 로드맵에 교육과정 밖 과목이 있으면 지도 오른쪽 끝 열에 같이 보여준다
  const graph = useMemo(() => buildMajorGraph(major, mine.targets), [major, mine])
  const { positions, height, hasOutside } = useMemo(() => layoutBySemester(graph), [graph])

  // 2) 강조할 과목들: 과목을 골랐으면 그 과목까지, 진로를 골랐으면 그 진로까지 가는 경로
  const targets = useMemo(
    () => (career ? career.targets.filter((c) => graph.courseByCode.has(c)) : []),
    [career, graph],
  )
  // 과목을 골랐을 때: 기본은 바로 앞(선수과목)·바로 뒤(다음 과목)만, '전체 경로'를 켜면 선수과목 사슬 전체
  const [showChain, setShowChain] = useState(false)
  useEffect(() => { setShowChain(false) }, [selected])
  const ancestorCount = useMemo(
    () => (selected ? ancestorsOf([selected], graph.edges).size : 0),
    [selected, graph],
  )
  const focus = useMemo(() => {
    if (selected) {
      if (showChain) return new Set([selected, ...ancestorsOf([selected], graph.edges)])
      const near = graph.edges
        .filter((e) => e.type === 'pre' && (e.to === selected || e.from === selected))
        .flatMap((e) => [e.from, e.to])
      return new Set([selected, ...near])
    }
    if (!targets.length) return new Set<string>()
    return new Set([...targets, ...ancestorsOf(targets, graph.edges)])
  }, [selected, showChain, targets, graph])
  // 진하게 그릴 선
  // - 과목을 골랐으면: 그 과목에 바로 붙은 선 (전체 경로를 켜면 그 사슬 전체)
  // - 진로만 골랐으면: 선은 안 그리고 과목만 강조한다 (선이 너무 많아 읽기 어려움)
  const isPathEdge = useMemo(() => {
    if (!selected) return () => false
    if (!showChain) return (e: { from: string; to: string }) => e.to === selected || e.from === selected
    return (e: { from: string; to: string }) => focus.has(e.from) && focus.has(e.to)
  }, [selected, showChain, focus])
  const active = focus.size > 0

  // 3) React Flow 노드: 학기 제목 + 점선 + 과목
  const nodes: Node[] = useMemo(() => {
    const deco: Node[] = COLUMN_LABELS.slice(0, hasOutside ? 9 : 8).flatMap((label, i) => [
      {
        id: `sem-${i}`,
        type: 'semester',
        position: { x: colX(i), y: 0 },
        data: { label },
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
        : selected && active ? 'dim'
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
  }, [graph, positions, height, hasOutside, completed, takingSet, grades, selected, targets, focus, active])

  const flowEdges = useMemo(() => {
    const start = new Set([...completed, ...takingSet])
    const firstYear = new Set(graph.courses.filter((c) => c.col <= 1).map((c) => c.code))
    // 진로만 골랐을 땐 선 규칙을 바꾸지 않는다 (과목을 골랐을 때만 경로 선)
    return toFlowEdges(graph.edges, isPathEdge, selected !== null && active, start, firstYear, selected, positions)
  }, [graph, isPathEdge, active, completed, takingSet, selected, positions])

  // 고른 경로가 한 화면에 들어오게 확대 / 아무것도 안 고르면 전체 보기
  useEffect(() => {
    const t = setTimeout(() => {
      if (active) {
        const ids = selected && !showChain
          ? [selected, ...graph.edges.filter((e) => e.type === 'pre' && e.to === selected).map((e) => e.from)]
          : [...focus]
        const courseIds = ids.filter((id) => graph.courseByCode.has(id))
        // 확대해도 학기 제목이 잘리지 않게, 해당 열의 제목 노드도 같이 맞춘다
        const headerIds = [...new Set(courseIds.map((id) => `sem-${graph.courseByCode.get(id)!.col}`))]
        flow.fitView({ nodes: [...courseIds, ...headerIds].map((id) => ({ id })), duration: 500, padding: 0.2, maxZoom: 1.1 })
      }
      else flow.fitView({ duration: 500, padding: 0.05 })
    }, 50)
    return () => clearTimeout(t)
  }, [focus, active, flow, major, selected, showChain, graph])

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
            <button className={view === 'chat' ? 'on' : ''} onClick={() => setView('chat')}>AI 상담</button>
          </div>
        </div>
        <div className="head-right">
          <select value={major} onChange={(e) => { setMajor(e.target.value); setSelected(null) }}>
            {majors.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <span className="sub">교육과정 {graph.courses.length}과목 · 이수 {majorCredits}학점</span>
        </div>
      </header>

      {view === 'timetable' && (
        <main className="body">
          <TimetableView onApply={(d, t) => { applyTimetable(d, t) }} />
        </main>
      )}

      {view === 'chat' && (
        <main className="body">
          <ChatView
            major={major}
            messages={chatMsgs}
            setMessages={setChatMsgs}
            currentTargets={mine.targets.length ? mine.targets : targets}
            completed={[...completed]}
            taking={taking}
            onApply={(t, reasons) => {
              setMine({ targets: t, reasons: { ...mine.reasons, ...reasons } })
              setCareerId('mine')
              setSelected(null)
              setView('roadmap')
            }}
          />
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
        <SearchBox courses={graph.courses} onPick={(c) => { setCareerId(null); setSelected(c) }} />
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
            <Controls showInteractive={false} position="bottom-right" />
          </ReactFlow>
          <div className="legend">
            <span><i className="lg done" />이수</span>
            <span><i className="lg taking" />수강 중</span>
            <span><i className="lg next" />다음 후보</span>
            <span><i className="lg path" />진로 경로</span>
            <span className="mode">{hasBackend ? '백엔드 연결' : '로컬 모드'}</span>
          </div>
        </div>
        {selected ? (
          <SubjectPanel
            code={selected}
            course={graph.courseByCode.get(selected)}
            completed={completed}
            taking={takingSet}
            inMajor={(c) => graph.courseByCode.has(c)}
            major={major}
            grade={grades[selected]}
            scale={scale}
            onToggle={toggle}
            onGrade={setGrade}
            onSelect={setSelected}
            pathCount={ancestorCount}
            showChain={showChain}
            onToggleChain={() => setShowChain((v) => !v)}
          />
        ) : career ? (
          <CareerPanel career={career} reasons={career.id === 'mine' ? mine.reasons : undefined} onClear={career.id === 'mine' ? () => { setMine({ targets: [], reasons: {} }); setCareerId(null) } : undefined} graph={graph} focus={focus} completed={completed} taking={takingSet} onSelect={setSelected} />
        ) : (
          <StatusPanel
            major={major}
            doneCount={graph.courses.filter((c) => completed.has(c.code)).length}
            takingCount={graph.courses.filter((c) => takingSet.has(c.code) && !completed.has(c.code)).length}
            totalCount={graph.courses.length}
            grades={grades}
            scale={scale}
            extra={extra}
            onExtra={setExtra}
            onSelect={setSelected}
            onOpenTimetable={() => setView('timetable')}
            onReset={() => {
              // 이 브라우저의 기록 전체 초기화 (백엔드 이수 기록도 해제)
              Object.keys(grades).forEach((c) => sync(c, false))
              setGrades({})
              setTaking([])
              setExtra(0)
              setMine({ targets: [], reasons: {} })
              setCareerId(null)
              setSelected(null)
            }}
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
