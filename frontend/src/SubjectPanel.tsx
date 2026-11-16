import { useEffect, useState } from 'react'
import { followupsOf, prereqGroupsOf, relatedOf, subjectByCode } from './data'
import { hasBackend, loadDetail, type SubjectDetail } from './api'

type Props = {
  code: string | null
  completed: Set<string>
  onToggle: (code: string) => void
  onSelect: (code: string) => void
  pathCount: number
}

function Chip({ code, done, onSelect }: { code: string; done: boolean; onSelect: (c: string) => void }) {
  const s = subjectByCode.get(code)
  return (
    <button className={`chip ${done ? 'done' : ''}`} onClick={() => onSelect(code)}>
      {s?.name ?? code}
    </button>
  )
}

export default function SubjectPanel({ code, completed, onToggle, onSelect, pathCount }: Props) {
  const [detail, setDetail] = useState<SubjectDetail | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setDetail(null)
    if (!code || !hasBackend) return
    setLoading(true)
    loadDetail(code)
      .then(setDetail)
      .finally(() => setLoading(false))
  }, [code])

  if (!code) {
    return (
      <aside className="panel empty">
        <p>과목을 클릭하면 상세 정보와<br />그 과목까지 가는 선수과목 경로가 보여요.</p>
      </aside>
    )
  }

  const s = subjectByCode.get(code)
  const pre = prereqGroupsOf(code)
  const post = [...new Map(followupsOf(code).map((e) => [e.to, e])).values()]
  const rel = relatedOf(code)
  const isDone = completed.has(code)
  const sec = detail?.sections.find((x) => x.syllabus) ?? detail?.sections[0]

  return (
    <aside className="panel">
      <div className="panel-head">
        <div>
          <h2>{s?.name ?? code}</h2>
          <p className="meta">
            {code} · {s?.credit ?? '-'}학점 {s?.offeredTerms.length ? `· 개설 ${s.offeredTerms.join(', ')}` : ''}
          </p>
        </div>
        <button className={`toggle ${isDone ? 'on' : ''}`} onClick={() => onToggle(code)}>
          {isDone ? '✓ 이수함' : '이수 체크'}
        </button>
      </div>

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
            {post.map((e) => (
              <Chip key={e.to} code={e.to} done={completed.has(e.to)} onSelect={onSelect} />
            ))}
          </div>
        )}
      </section>

      {rel.length > 0 && (
        <section>
          <h3>관련 과목</h3>
          <div className="chips">
            {rel.map((c) => (
              <Chip key={c} code={c} done={completed.has(c)} onSelect={onSelect} />
            ))}
          </div>
        </section>
      )}

      {!hasBackend && (
        <p className="muted small">백엔드를 연결하면(.env.local의 VITE_API_URL) 강의계획서와 주차별 내용이 여기에 표시돼요.</p>
      )}
      {loading && <p className="muted">계획서 불러오는 중…</p>}
      {sec && (
        <>
          <section>
            <h3>강의 정보 <small>{sec.term} · {sec.course_no}</small></h3>
            <p className="small">{[sec.professor, sec.time_real, sec.room].filter(Boolean).join(' · ')}</p>
          </section>
          {sec.syllabus?.summary && (
            <section>
              <h3>개요</h3>
              <p className="pre">{sec.syllabus.summary}</p>
            </section>
          )}
          {sec.syllabus?.goals && (
            <section>
              <h3>강의 목표</h3>
              <p className="pre">{sec.syllabus.goals}</p>
            </section>
          )}
          {sec.weeks.length > 0 && (
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
