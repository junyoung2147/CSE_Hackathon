import { useMemo, useState } from 'react'
import { hasBackend, loadEverytime, type EverytimeResult } from './api'
import sample from './sampleTimetable.json'

type Props = {
  onApply: (done: string[], taking: string[]) => void
}

const DAYS = ['월', '화', '수', '목', '금', '토', '일']
const PX_PER_MIN = 0.9
const COLORS = ['#dbeafe', '#dcfce7', '#fef3c7', '#fce7f3', '#ede9fe', '#cffafe', '#fee2e2', '#e0e7ff']
const hhmm = (m: number) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`

/** 에브리타임 공유 링크로 학기별 시간표를 불러와 격자로 보여주고, 로드맵에 반영한다 */
export default function TimetableView({ onApply }: Props) {
  const [link, setLink] = useState('')
  const [data, setData] = useState<EverytimeResult | null>(null)
  const [idx, setIdx] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [applied, setApplied] = useState<string | null>(null)

  const load = async (fromSample = false) => {
    setError(null)
    setApplied(null)
    if (fromSample) {
      setData(sample as EverytimeResult)
      setIdx((sample as EverytimeResult).semesters.length - 1)
      return
    }
    setLoading(true)
    try {
      const r = await loadEverytime(link)
      if (!r.semesters.length) throw new Error('공개된 시간표가 없어요')
      setData(r)
      setIdx(r.semesters.length - 1)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const sem = data?.semesters[idx]
  const grid = useMemo(() => {
    if (!sem) return null
    const slots = sem.courses.flatMap((c) => c.times)
    const start = Math.min(9 * 60, ...slots.map((t) => t.start))
    const end = Math.max(18 * 60, ...slots.map((t) => t.end))
    const days = Math.max(5, ...slots.map((t) => t.day + 1))
    return { start: Math.floor(start / 60) * 60, end: Math.ceil(end / 60) * 60, days }
  }, [sem])

  const apply = () => {
    if (!data) return
    const last = data.semesters.length - 1
    const done = data.semesters.slice(0, last).flatMap((s) => s.courses.map((c) => c.subject_code))
    const taking = data.semesters[last].courses.map((c) => c.subject_code)
    onApply(done, taking)
    setApplied(`이전 학기 ${done.length}과목은 이수로, 이번 학기 ${taking.length}과목은 수강 중으로 반영했어요. 성적은 로드맵에서 과목을 눌러 입력해 주세요.`)
  }

  return (
    <div className="tt">
      <div className="tt-input">
        <input
          placeholder="에브리타임 시간표 공유 링크 (https://everytime.kr/@...)"
          value={link}
          onChange={(e) => setLink(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && link && load()}
        />
        <button className="primary" disabled={!link || loading || !hasBackend} onClick={() => load()}>
          {loading ? '불러오는 중…' : '불러오기'}
        </button>
        <button onClick={() => load(true)}>샘플로 보기</button>
      </div>
      {!hasBackend && (
        <p className="muted small">링크로 불러오려면 백엔드가 필요해요(.env.local의 VITE_API_URL). 지금은 샘플만 볼 수 있어요.</p>
      )}
      <p className="muted small">에브리타임 앱 → 시간표 → 설정 → URL로 공유하기에서 링크를 복사하세요. 시간표가 '전체 공개'여야 불러올 수 있어요.</p>
      {error && <div className="error">{error}</div>}

      {data && sem && grid && (
        <>
          <div className="tt-tabs">
            {data.semesters.map((s, i) => (
              <button key={`${s.year}-${s.semester}`} className={`chip ${i === idx ? 'on' : ''}`} onClick={() => setIdx(i)}>
                {s.year}년 {s.semester}{/^\d$/.test(s.semester) ? '학기' : ''}
              </button>
            ))}
            {data.skipped.length > 0 && (
              <span className="muted small">
                (건너뜀: {data.skipped.map((s) => `${s.year ?? ''} ${s.semester ?? ''} ${s.reason}`).join(', ')})
              </span>
            )}
          </div>

          <div className="tt-body">
            <div className="tt-grid" style={{ gridTemplateColumns: `48px repeat(${grid.days}, 1fr)` }}>
              <div />
              {DAYS.slice(0, grid.days).map((d) => <div key={d} className="tt-day">{d}</div>)}
              <div className="tt-hours" style={{ height: (grid.end - grid.start) * PX_PER_MIN }}>
                {Array.from({ length: (grid.end - grid.start) / 60 }, (_, i) => (
                  <span key={i} style={{ top: i * 60 * PX_PER_MIN }}>{hhmm(grid.start + i * 60)}</span>
                ))}
              </div>
              {DAYS.slice(0, grid.days).map((d, day) => (
                <div key={d} className="tt-col" style={{ height: (grid.end - grid.start) * PX_PER_MIN }}>
                  {sem.courses.flatMap((c, ci) =>
                    c.times
                      .filter((t) => t.day === day)
                      .map((t, ti) => (
                        <div
                          key={`${c.course_no}-${ti}`}
                          className="tt-block"
                          style={{
                            top: (t.start - grid.start) * PX_PER_MIN,
                            height: (t.end - t.start) * PX_PER_MIN - 2,
                            background: COLORS[ci % COLORS.length],
                          }}
                          title={`${c.name} · ${c.professor} · ${hhmm(t.start)}~${hhmm(t.end)} · ${t.place}`}
                        >
                          <b>{c.name}</b>
                          <span>{t.place.replace(/^산격동 캠퍼스\s*/, '')}</span>
                        </div>
                      )),
                  )}
                </div>
              ))}
            </div>

            <aside className="tt-list">
              <h3>{sem.year}년 {sem.semester}학기 · {sem.courses.reduce((s, c) => s + (c.credit ?? 0), 0)}학점</h3>
              <ul>
                {sem.courses.map((c) => (
                  <li key={c.course_no}>
                    <b>{c.name}</b> <span className="muted">{c.course_no} · {c.professor} · {c.credit ?? '-'}학점</span>
                  </li>
                ))}
              </ul>
              <button className="primary" onClick={apply}>로드맵에 반영</button>
              <p className="muted small">마지막 학기는 '수강 중', 그 이전 학기는 '이수'로 표시돼요.</p>
              {applied && <p className="ok small">{applied}</p>}
            </aside>
          </div>
        </>
      )}
    </div>
  )
}
