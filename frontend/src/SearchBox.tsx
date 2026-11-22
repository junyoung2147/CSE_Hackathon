import { useMemo, useState } from 'react'
import type { Course } from './data'

type Props = { courses: Course[]; onPick: (code: string) => void }

/** 과목 이름(초성 아님, 부분 일치)이나 코드로 찾아서 지도에서 바로 열기 */
export default function SearchBox({ courses, onPick }: Props) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const hits = useMemo(() => {
    const k = q.replace(/\s/g, '').toLowerCase()
    if (!k) return []
    return courses
      .filter((c) => c.name.replace(/\s/g, '').toLowerCase().includes(k) || c.code.toLowerCase().includes(k))
      .slice(0, 8)
  }, [q, courses])

  const pick = (code: string) => {
    onPick(code)
    setQ('')
    setOpen(false)
  }

  return (
    <div className="search">
      <input
        value={q}
        placeholder="과목 검색"
        onChange={(e) => { setQ(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => e.key === 'Enter' && hits[0] && pick(hits[0].code)}
      />
      {open && hits.length > 0 && (
        <ul>
          {hits.map((c) => (
            <li key={c.code} onMouseDown={() => pick(c.code)}>
              {c.name} <span className="muted">{c.col < 8 ? `${Math.floor(c.col / 2) + 1}-${(c.col % 2) + 1}` : '교육과정 밖'}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
