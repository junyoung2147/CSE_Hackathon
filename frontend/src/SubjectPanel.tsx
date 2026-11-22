import { useEffect, useState } from 'react'
import { followupsOf, nameOf, relatedOf, SEMESTER_LABELS, splitPrereqs, subjectByCode, type Course } from './data'
import type { LocalSection } from './syllabus'
import { GRADES, type Scale } from './progress'
import AdviceBox from './AdviceBox'

type Props = {
  code: string
  course?: Course
  completed: Set<string>
  taking: Set<string>
  inMajor: (code: string) => boolean // 지금 고른 전공 교육과정에 있는 과목인지
  major: string
  grade: string | undefined // undefined = 미이수
  scale: Scale
  onToggle: (code: string) => void
  onGrade: (code: string, grade: string) => void
  onSelect: (code: string) => void
  pathCount: number // 거슬러 올라간 선수과목 전체 수
  showChain: boolean
  onToggleChain: () => void
}

function Chip({ code, done, onSelect }: { code: string; done: boolean; onSelect: (c: string) => void }) {
  return (
    <button className={`chip ${done ? 'done' : ''}`} onClick={() => onSelect(code)}>
      {nameOf(code)}
    </button>
  )
}

export default function SubjectPanel({ code, course, completed, taking, inMajor, major, grade, scale, onToggle, onGrade, onSelect, pathCount, showChain, onToggleChain }: Props) {
  // 계획서: 처음 열 때 syllabus.ts를 불러와서 이 과목 분반들을 찾는다
  const [sections, setSections] = useState<LocalSection[] | null>(null)
  const [secIdx, setSecIdx] = useState(0)
  const [asking, setAsking] = useState(false) // 선수과목 상담 열림
  useEffect(() => {
    setSections(null)
    setSecIdx(0)
    setAsking(false)
    let alive = true
    import('./syllabus').then((m) => alive && setSections(m.sectionsOf(code)))
    return () => {
      alive = false
    }
  }, [code])

  const s = subjectByCode.get(code)
  const { taken, missing } = splitPrereqs(code, completed, taking)
  const post = followupsOf(code)
  const rel = relatedOf(code)
  const isDone = grade !== undefined // 성적을 넣었으면(F 포함) 수강 기록이 있음
  const failed = grade === 'F'
  const sec = sections?.[secIdx]

  return (
    <aside className="panel">
      <div className="panel-head">
        <div>
          <h2>{nameOf(code)}</h2>
          <p className="meta">
            {code} · {s?.credit ?? course?.credit ?? '-'}학점
            {course ? (course.col < 8 ? ` · 권장 ${SEMESTER_LABELS[course.col]}학기` : ' · 이 전공 교육과정 밖 과목') : ''}
            {course?.required ? ' · 전공필수' : ''}
            {s?.offeredTerms.length ? ` · 2026 개설 ${s.offeredTerms.join(', ')}` : ' · 2026 미개설'}
          </p>
        </div>
        <button className={`toggle ${isDone ? (failed ? 'fail' : 'on') : ''}`} onClick={() => onToggle(code)}>
          {failed ? '재수강 필요' : isDone ? '✓ 이수함' : '이수 체크'}
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
        <h3>
          선수과목{' '}
          {pathCount > 0 && (
            <button className="link" style={{ marginTop: 0 }} onClick={onToggleChain}>
              {showChain ? '바로 앞 과목만 보기' : `지도에서 전체 경로 보기 (${pathCount}과목)`}
            </button>
          )}
        </h3>
        {taken.length + missing.length === 0 && <p className="muted">없음</p>}
        {taken.length > 0 && (
          <div className="chips" style={{ marginBottom: 8 }}>
            {taken.map((group) => (
              <span key={group.join('|')} className="chip-group">
                {group.map((c, i) => (
                  <span key={c} className="chip-group">
                    {i > 0 && <span className="or">또는</span>}
                    <Chip code={c} done={completed.has(c) || taking.has(c)} onSelect={onSelect} />
                  </span>
                ))}
              </span>
            ))}
          </div>
        )}
        {missing.length > 0 && (
          <>
            <p className="small muted" style={{ margin: '4px 0' }}>아직 안 들은 선수과목 (권장)</p>
            <ul className="missing">
              {missing.map((group) => {
                const other = !group.some(inMajor)
                return (
                  <li key={group.join('|')}>
                    <span className="chip-group">
                      {group.map((c, i) => (
                        <span key={c} className="chip-group">
                          {i > 0 && <span className="or">또는</span>}
                          <Chip code={c} done={false} onSelect={onSelect} />
                        </span>
                      ))}
                      {other && <span className="tag">타 전공</span>}
                    </span>
                  </li>
                )
              })}
            </ul>
            {!asking && (
              <button className="ask" style={{ marginTop: 6 }} onClick={() => setAsking(true)}>
                안 들었는데 들어도 될까요? AI에게 물어보기
              </button>
            )}
          </>
        )}
        {asking && (
          <AdviceBox
            code={code}
            major={major}
            missing={missing}
            completedCodes={[...completed]}
            takingCodes={[...taking]}
            notes={sections?.[0]?.notes ?? null}
            onClose={() => setAsking(false)}
          />
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
