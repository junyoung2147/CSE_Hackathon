import type { Career } from './careers'
import { COLUMN_LABELS, type MajorGraph } from './data'

type Props = {
  career: Career
  reasons?: Record<string, string> // AI가 넣은 과목이면 이유
  onClear?: () => void // 내 로드맵 지우기
  graph: MajorGraph
  focus: Set<string>
  completed: Set<string>
  onSelect: (code: string) => void
}

/** 진로를 고르면: 그 진로까지 가는 과목을 학기별로 정리해서 보여준다 */
export default function CareerPanel({ career, reasons, onClear, graph, focus, completed, onSelect }: Props) {
  const courses = graph.courses.filter((c) => focus.has(c.code)).sort((a, b) => a.col - b.col)
  const targets = new Set(career.targets)
  const done = courses.filter((c) => completed.has(c.code))
  const remainCredits = courses
    .filter((c) => !completed.has(c.code))
    .reduce((s, c) => s + (c.credit ?? 0), 0)

  return (
    <aside className="panel">
      <h2>{career.name}</h2>
      <p className="meta">{career.description}</p>
      <div className="stats">
        <div><b>{courses.length}</b><span>경로 과목</span></div>
        <div><b>{done.length}</b><span>이수</span></div>
        <div><b>{remainCredits}</b><span>남은 학점</span></div>
      </div>
      {courses.length === 0 && <p className="muted">이 전공 교육과정에는 이 진로의 도착 과목이 없어요.</p>}
      {COLUMN_LABELS.map((label, col) => {
        const inCol = courses.filter((c) => c.col === col)
        if (!inCol.length) return null
        return (
          <section key={label}>
            <h3>{label}</h3>
            <div className="chips">
              {inCol.map((c) => (
                <button
                  key={c.code}
                  className={`chip ${completed.has(c.code) ? 'done' : ''} ${targets.has(c.code) ? 'target' : ''}`}
                  onClick={() => onSelect(c.code)}
                >
                  {completed.has(c.code) ? '✓ ' : ''}{c.name}
                </button>
              ))}
            </div>
          </section>
        )
      })}
      {reasons && Object.keys(reasons).length > 0 && (
        <section>
          <h3>AI가 고른 이유</h3>
          <ul className="reasons">
            {courses.filter((c) => reasons[c.code]).map((c) => (
              <li key={c.code}><b>{c.name}</b> {reasons[c.code]}</li>
            ))}
          </ul>
        </section>
      )}
      <p className="muted small">굵은 테두리 과목이 이 진로의 도착점이고, 나머지는 거기까지 가는 선수과목이에요. 과목을 누르면 선수관계 선이 보여요.</p>
      {onClear && <button className="link" onClick={onClear}>내 로드맵 지우기</button>}
    </aside>
  )
}
