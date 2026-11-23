import type { ReactNode } from 'react'

/** 줄 안의 **굵게**와 `코드`만 처리한다. */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4 ? <b key={i}>{part.slice(2, -2)}</b>
      : part.startsWith('`') && part.endsWith('`') && part.length > 2 ? <code key={i}>{part.slice(1, -1)}</code>
        : part,
  )
}

/**
 * AI 답변용 작은 마크다운 렌더러. 제목(#), 목록(-, *, 1.), 굵게, 코드만 지원한다.
 * HTML을 직접 넣지 않고 React 요소로만 만들어 XSS가 생기지 않는다.
 * shortcut: 표·링크·중첩 목록 구조는 지원하지 않음, 필요해지면 react-markdown으로 바꾼다.
 */
export default function Markdown({ text }: { text: string }) {
  const out: ReactNode[] = []
  let list: { ordered: boolean; items: ReactNode[] } | null = null
  const flush = () => {
    if (!list) return
    const Tag = list.ordered ? 'ol' : 'ul'
    out.push(<Tag key={out.length}>{list.items.map((it, i) => <li key={i}>{it}</li>)}</Tag>)
    list = null
  }
  for (const raw of text.split('\n')) {
    const line = raw.trimEnd()
    const bullet = line.match(/^\s*[-*]\s+(.*)$/)
    const num = line.match(/^\s*\d+[.)]\s+(.*)$/)
    const head = line.match(/^#{1,6}\s+(.*)$/)
    if (bullet || num) {
      const ordered = !bullet
      if (list && list.ordered !== ordered) flush()
      list ??= { ordered, items: [] }
      // 들여쓴 하위 항목은 한 단계 들여서 보여 준다
      const indent = /^\s{2,}/.test(line)
      list.items.push(<span className={indent ? 'md-sub' : undefined}>{inline((bullet ?? num)![1])}</span>)
      continue
    }
    flush()
    if (head) out.push(<p key={out.length} className="md-head">{inline(head[1])}</p>)
    else if (line.trim()) out.push(<p key={out.length}>{inline(line)}</p>)
  }
  flush()
  return <div className="md">{out}</div>
}
