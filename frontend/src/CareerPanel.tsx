import type { Career } from './careers'
import { COLUMN_LABELS, SEMESTER_LABELS, type Course, type MajorGraph } from './data'

type Props = {
  career: Career
  reasons?: Record<string, string> // AI가 넣은 과목이면 이유
  onClear?: () => void // 내 로드맵 지우기
  graph: MajorGraph
  focus: Set<string>
  completed: Set<string>
  taking: Set<string>
  onSelect: (code: string) => void
}

/** 진로를 고르면: 도착점과 진행도를 먼저 보여주고, 선수과목은 접어서 둔다 */
export default function CareerPanel({ career, reasons, onClear, graph, focus, completed, taking, onSelect }: Props) {
  const courses = graph.courses.filter((c) => focus.has(c.code)).sort((a, b) => a.col - b.col)
  const targetSet = new Set(career.targets)
  const targets = courses.filter((c) => targetSet.has(c.code))
  const rest = courses.filter((c) => !targetSet.has(c.code))
  const remain = rest.filter((c) => !completed.has(c.code))
  const doneRest = rest.filter((c) => completed.has(c.code))
  const doneCount = courses.filter((c) => completed.has(c.code)).length
  const remainCredits = courses.filter((c) => !completed.has(c.code)).reduce((s, c) => s + (c.credit ?? 0), 0)
  const pct = courses.length ? (doneCount / courses.length) * 100 : 0
  const state = (code: string) => (completed.has(code) ? 'done' : taking.has(code) ? 'taking' : '')

  const termOf = (c: Course) => (c.col < SEMESTER_LABELS.length ? SEMESTER_LABELS[c.col] : '교육과정 밖')

  return (
    <aside className="panel">
      <h2>{career.name}</h2>
      <p className="meta">{career.description}</p>

      {courses.length === 0 ? (
        <p className="muted">이 전공 교육과정에는 이 진로의 도착 과목이 없어요.</p>
      ) : (
        <div className="career-progress">
          <div className="bar"><i style={{ width: `${pct}%` }} /></div>
          <p className="meta">이수 {doneCount} / {courses.length}과목 · 남은 학점 {remainCredits}</p>
        </div>
      )}

      {targets.length > 0 && (
        <section>
          <h3>도착점</h3>
          <ul className="rows">
            {targets.map((c) => (
              <li key={c.code}>
                <button className="row" onClick={() => onSelect(c.code)}>
                  <i className={`dot ${state(c.code)}`} />
                  <span>{c.name}</span>
                  <span className="term">{termOf(c)}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {remain.length > 0 && (
        <details className="more">
          <summary>남은 선수과목 {remain.length}</summary>
          {COLUMN_LABELS.map((label, col) => {
            const inCol = remain.filter((c) => c.col === col)
            if (!inCol.length) return null
            return (
              <section key={label}>
                <h3>{label}</h3>
                <div className="chips">
                  {inCol.map((c) => (
                    <button key={c.code} className={`chip ${state(c.code)}`} onClick={() => onSelect(c.code)}>
                      {c.name}
                    </button>
                  ))}
                </div>
              </section>
            )
          })}
        </details>
      )}

      {doneRest.length > 0 && (
        <details className="more">
          <summary>이수한 선수과목 {doneRest.length}</summary>
          <div className="chips">
            {doneRest.map((c) => (
              <button key={c.code} className="chip done" onClick={() => onSelect(c.code)}>{c.name}</button>
            ))}
          </div>
        </details>
      )}

      {reasons && Object.keys(reasons).length > 0 && (
        <details className="more">
          <summary>AI가 고른 이유</summary>
          <ul className="reasons">
            {courses.filter((c) => reasons[c.code]).map((c) => (
              <li key={c.code}><b>{c.name}</b> {reasons[c.code]}</li>
            ))}
          </ul>
        </details>
      )}

      <p className="muted small">과목을 누르면 지도에서 선수관계 선을 볼 수 있어요.</p>
      {onClear && <button className="link" onClick={onClear}>내 로드맵 지우기</button>}
    </aside>
  )
}
