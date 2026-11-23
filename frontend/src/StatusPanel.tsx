import { useState } from 'react'
import { nameOf } from './data'
import { gpaOf, graduationOf, requiredCourses, type Grades, type Overrides, type Scale } from './progress'

type Props = {
  major: string
  doneCount: number
  takingCount: number
  totalCount: number
  grades: Grades
  scale: Scale
  overrides: Overrides
  onOverrides: (o: Overrides) => void
  onSelect: (code: string) => void
  onOpenTimetable: () => void
  onReset: () => void
}

/** 아무것도 안 골랐을 때 오른쪽 패널: 내 평점 + 졸업요건 */
export default function StatusPanel({ major, doneCount, takingCount, totalCount, grades, scale, overrides, onOverrides, onSelect, onOpenTimetable, onReset }: Props) {
  const [confirming, setConfirming] = useState(false)
  const { gpa, credits, gpaCredits } = gpaOf(grades, scale)
  const reqs = graduationOf(major, grades, overrides)
  const totalCredits = reqs.find((r) => r.category === '전체')?.have ?? credits
  const required = requiredCourses(major)
  const missingGrades = Object.values(grades).filter((g) => g === '').length
  const set = (k: string, n: number) => onOverrides({ ...overrides, [k]: Math.max(0, n) })
  const reset = (k: string) => { const { [k as keyof Overrides]: _, ...rest } = overrides; onOverrides(rest) }

  return (
    <aside className="panel status">
      <h2>이수 현황</h2>
      <p className="meta">{major} 기준</p>

      <div className="stats">
        <div><b>{doneCount}</b><span>이수</span></div>
        <div><b>{takingCount}</b><span>수강 중</span></div>
        <div><b>{Math.max(0, totalCount - doneCount - takingCount)}</b><span>남은 과목</span></div>
      </div>

      <section>
        {reqs.length === 0 && <p className="muted">이 전공의 졸업요건 데이터가 없어요.</p>}
        {reqs.map((r) => {
          const pct = r.have === null ? 0 : Math.min(100, (r.have / r.need) * 100)
          return (
            <div key={r.category} className="req">
              <div className="req-head">
                <span>{r.category}</span>
                {r.base !== undefined && r.have !== null ? (
                  <span className="stepper">
                    <span className="stepbox">
                      <button aria-label={`${r.category} 학점 줄이기`} onClick={() => set(r.category, r.have! - 1)}>−</button>
                      <input type="number" min={0} value={r.have} onChange={(e) => set(r.category, Number(e.target.value) || 0)} />
                      <button aria-label={`${r.category} 학점 늘리기`} onClick={() => set(r.category, r.have! + 1)}>+</button>
                    </span>
                    / {r.need}학점                  </span>
                ) : (
                  <span>{r.have === null ? '직접 확인' : `${r.have} / ${r.need}학점`}</span>
                )}
              </div>
              {r.have !== null && <div className="bar"><i style={{ width: `${pct}%` }} className={pct >= 100 ? 'full' : ''} /></div>}
              {r.base !== undefined && (
                <div className="req-reset">
                  {r.category in overrides && <button className="link" onClick={() => reset(r.category)}>되돌리기</button>}
                </div>
              )}
            </div>
          )
        })}
      </section>

      {required.length > 0 && (
        <details className="more">
          <summary>전공필수</summary>
          <div className="chips">
            {required.map((r) => (
              <button key={r.code} className={`chip ${r.code in grades && grades[r.code] !== 'F' ? 'done' : ''}`} onClick={() => onSelect(r.code)}>
                {r.code in grades && grades[r.code] !== 'F' ? '✓ ' : ''}{nameOf(r.code)}
              </button>
            ))}
          </div>
        </details>
      )}

      <details className="more">
        <summary>평점 · 입력 안내</summary>
        <p className="small">평점 <b>{gpa === null ? '-' : gpa.toFixed(2)}</b> / {scale} · 이수 학점 {totalCredits}</p>
        <p className="muted small">
          평점은 성적을 입력한 {gpaCredits}학점 기준이에요(경북대 4.3 만점){missingGrades ? `. 성적 미입력 ${missingGrades}과목` : ''}.
        </p>
        <p className="small">지도에서 과목을 눌러 <b>이수 체크</b>하고 성적을 고르거나, 아래 버튼으로 시간표를 불러오세요.</p>
      </details>

      <section className="push">
        <button className="primary" onClick={onOpenTimetable}>시간표 가져오기</button>
        {confirming ? (
          <p className="small">
            이수·성적·수강 중·내 로드맵을 모두 지울까요?{' '}
            <button className="link danger" onClick={() => { onReset(); setConfirming(false) }}>지우기</button>{' '}
            <button className="link" onClick={() => setConfirming(false)}>취소</button>
          </p>
        ) : (
          <button className="link" onClick={() => setConfirming(true)}>기록 초기화</button>
        )}
      </section>
    </aside>
  )
}
