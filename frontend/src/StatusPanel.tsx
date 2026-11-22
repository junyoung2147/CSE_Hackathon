import { useState } from 'react'
import { nameOf } from './data'
import { gpaOf, graduationOf, requiredCourses, type Grades, type Scale } from './progress'

type Props = {
  major: string
  grades: Grades
  scale: Scale
  extra: number
  onExtra: (n: number) => void
  onSelect: (code: string) => void
  onOpenTimetable: () => void
  onReset: () => void
}

/** 아무것도 안 골랐을 때 오른쪽 패널: 내 평점 + 졸업요건 */
export default function StatusPanel({ major, grades, scale, extra, onExtra, onSelect, onOpenTimetable, onReset }: Props) {
  const [confirming, setConfirming] = useState(false)
  const { gpa, credits, gpaCredits } = gpaOf(grades, scale)
  const reqs = graduationOf(major, grades, extra)
  const required = requiredCourses(major)
  const missingGrades = Object.values(grades).filter((g) => g === '').length

  return (
    <aside className="panel">
      <h2>내 현황</h2>
      <p className="meta">{major} 기준</p>

      <div className="stats">
        <div><b>{gpa === null ? '-' : gpa.toFixed(2)}</b><span>평점 / {scale}</span></div>
        <div><b>{credits + extra}</b><span>이수 학점</span></div>
        <div><b>{Object.values(grades).filter((g) => g !== 'F').length}</b><span>이수 과목</span></div>
      </div>
      <p className="muted small">
        평점은 성적을 입력한 {gpaCredits}학점 기준이에요(경북대 4.3 만점){missingGrades ? `. 성적 미입력 ${missingGrades}과목` : ''}.
      </p>

      <section>
        <h3>졸업요건</h3>
        {reqs.length === 0 && <p className="muted">이 전공의 졸업요건 데이터가 없어요.</p>}
        {reqs.map((r) => {
          const pct = r.have === null ? 0 : Math.min(100, (r.have / r.need) * 100)
          return (
            <div key={r.category} className="req">
              <div className="req-head">
                <span>{r.category}</span>
                <span>{r.have === null ? '직접 확인' : `${r.have} / ${r.need}학점`}</span>
              </div>
              {r.have !== null && <div className="bar"><i style={{ width: `${pct}%` }} className={pct >= 100 ? 'full' : ''} /></div>}
            </div>
          )
        })}
        <label className="extra">
          목록에 없는 교양·기타 이수 학점
          <input type="number" min={0} value={extra} onChange={(e) => onExtra(Math.max(0, Number(e.target.value) || 0))} />
        </label>
        <p className="muted small">지도에 있는 과목만 자동으로 세요. 교양은 대부분 지도에 없어서 위 칸에 직접 더해 주세요.</p>
      </section>

      {required.length > 0 && (
        <section>
          <h3>전공필수</h3>
          <div className="chips">
            {required.map((r) => (
              <button key={r.code} className={`chip ${r.code in grades && grades[r.code] !== 'F' ? 'done' : ''}`} onClick={() => onSelect(r.code)}>
                {r.code in grades && grades[r.code] !== 'F' ? '✓ ' : ''}{nameOf(r.code)}
              </button>
            ))}
          </div>
        </section>
      )}

      <section>
        <h3>이수 과목 입력</h3>
        <p className="small">지도에서 과목을 눌러 <b>이수 체크</b>하고 성적을 고르거나,</p>
        <button className="primary" onClick={onOpenTimetable}>에브리타임 시간표로 한 번에 불러오기</button>
      </section>

      <section>
        {confirming ? (
          <p className="small">
            이수·성적·수강 중·내 로드맵을 모두 지울까요?{' '}
            <button className="link danger" onClick={() => { onReset(); setConfirming(false) }}>지우기</button>{' '}
            <button className="link" onClick={() => setConfirming(false)}>취소</button>
          </p>
        ) : (
          <button className="link" onClick={() => setConfirming(true)}>내 기록 초기화</button>
        )}
      </section>
    </aside>
  )
}
