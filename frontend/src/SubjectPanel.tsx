import { useEffect, useState } from 'react'
import { followupsOf, nameOf, prereqGroupsOf, relatedOf, SEMESTER_LABELS, subjectByCode, type Course } from './data'
import type { LocalSection } from './syllabus'
import { GRADES, type Scale } from './progress'

type Props = {
  code: string
  course?: Course
  completed: Set<string>
  grade: string | undefined // undefined = 미이수
  scale: Scale
  onToggle: (code: string) => void
  onGrade: (code: string, grade: string) => void
  onSelect: (code: string) => void
  pathCount: number
}

function Chip({ code, done, onSelect }: { code: string; done: boolean; onSelect: (c: string) => void }) {
  return (
    <button className={`chip ${done ? 'done' : ''}`} onClick={() => onSelect(code)}>
      {nameOf(code)}
    </button>
  )
}

export default function SubjectPanel({ code, course, completed, grade, scale, onToggle, onGrade, onSelect, pathCount }: Props) {
  // 계획서: 처음 열 때 syllabus.ts를 불러와서 이 과목 분반들을 찾는다
  const [sections, setSections] = useState<LocalSection[] | null>(null)
  const [secIdx, setSecIdx] = useState(0)
  useEffect(() => {
    setSections(null)
    setSecIdx(0)
    let alive = true
    import('./syllabus').then((m) => alive && setSections(m.sectionsOf(code)))
    return () => {
      alive = false
    }
  }, [code])

  const s = subjectByCode.get(code)
  const pre = prereqGroupsOf(code)
  const post = followupsOf(code)
  const rel = relatedOf(code)
  const isDone = completed.has(code)
  const sec = sections?.[secIdx]

  return (
    <aside className="panel">
      <div className="panel-head">
        <div>
          <h2>{nameOf(code)}</h2>
          <p className="meta">
            {code} · {s?.credit ?? course?.credit ?? '-'}학점
            {course ? ` · 권장 ${SEMESTER_LABELS[course.col]}학기` : ''}
            {course?.required ? ' · 전공필수' : ''}
            {s?.offeredTerms.length ? ` · 2026 개설 ${s.offeredTerms.join(', ')}` : ' · 2026 미개설'}
          </p>
        </div>
        <button className={`toggle ${isDone ? 'on' : ''}`} onClick={() => onToggle(code)}>
          {isDone ? '✓ 이수함' : '이수 체크'}
        </button>
      </div>

      {/* 이수했으면 성적 고르기 → 평점·졸업요건에 반영 */}
      {isDone && (
        <div className="grade-picker">
          <span>성적</span>
          {[...GRADES[scale].map(([g]) => g), 'P'].map((g) => (
            <button key={g} className={`g ${grade === g ? 'on' : ''}`} onClick={() => onGrade(code, grade === g ? '' : g)}>
              {g}
            </button>
          ))}
        </div>
      )}

      {/* 과목 설명: 계획서의 개요 */}
      <section>
        <h3>과목 설명</h3>
        {sections === null ? (
          <p className="muted">불러오는 중…</p>
        ) : sec?.summary ? (
          <p className="pre">{sec.summary}</p>
        ) : (
          <p className="muted">2026년 강의계획서가 없어요{s?.offeredTerms.length ? '' : ' (올해 미개설)'}.</p>
        )}
      </section>

      <section>
        <h3>선수과목 {pathCount > 0 && <small>(거슬러 올라가면 {pathCount}과목)</small>}</h3>
        {pre.length === 0 ? (
          <p className="muted">없음</p>
        ) : (
          <div className="chips">
            {pre.map((group) => (
              <span key={group.join('|')} className="chip-group">
                {group.map((c, i) => (
                  <span key={c} className="chip-group">
                    {i > 0 && <span className="or">또는</span>}
                    <Chip code={c} done={completed.has(c)} onSelect={onSelect} />
                  </span>
                ))}
              </span>
            ))}
          </div>
        )}
      </section>

      <section>
        <h3>이 과목 다음에</h3>
        {post.length === 0 ? (
          <p className="muted">없음</p>
        ) : (
          <div className="chips">
            {post.map((c) => <Chip key={c} code={c} done={completed.has(c)} onSelect={onSelect} />)}
          </div>
        )}
      </section>

      {rel.length > 0 && (
        <section>
          <h3>관련 과목</h3>
          <div className="chips">
            {rel.map((c) => <Chip key={c} code={c} done={completed.has(c)} onSelect={onSelect} />)}
          </div>
        </section>
      )}

      {sections && sections.length > 0 && (
        <>
          <section>
            <h3>개설 분반</h3>
            <div className="chips">
              {sections.map((x, i) => (
                <button key={x.term + x.courseNo} className={`chip ${i === secIdx ? 'on' : ''}`} onClick={() => setSecIdx(i)}>
                  {x.term} {x.courseNo.split('-')[1]} · {x.professor || '미정'}
                </button>
              ))}
            </div>
            {sec && <p className="small" style={{ marginTop: 6 }}>{[sec.time, sec.room].filter(Boolean).join(' · ')}</p>}
          </section>
          {sec?.goals && (
            <section>
              <h3>강의 목표</h3>
              <p className="pre">{sec.goals}</p>
            </section>
          )}
          {sec?.evaluation && (
            <section>
              <details>
                <summary>평가 방법</summary>
                <p className="pre">{sec.evaluation}</p>
              </details>
            </section>
          )}
          {sec && sec.weeks.length > 0 && (
            <section>
              <details>
                <summary>주차별 내용 ({sec.weeks.length}주)</summary>
                <ol className="weeks">
                  {sec.weeks.map((w, i) => (
                    <li key={i}>
                      <b>{w.week}주</b> <span className="pre">{w.content}</span>
                    </li>
                  ))}
                </ol>
              </details>
            </section>
          )}
        </>
      )}
    </aside>
  )
}
