import { useEffect, useRef, useState } from 'react'
import { chat, FIRST_PREREQ_MSG, NotReadyError, type ChatMessage } from './api'
import { nameOf, subjectByCode } from './data'
import Markdown from './Markdown'

type Props = {
  code: string // 들으려는 과목
  major: string
  missing: string[][] // 안 들은 선수과목 묶음들 (화면 안내용, 실제 판단은 백엔드가 간선으로 계산)
  completedCodes: string[]
  takingCodes: string[]
  notes: string | null // 계획서 수강 참고사항
  onClose: () => void
}

/**
 * 선수과목 상담 (POST /api/chat, mode=prereq).
 * 처음엔 빈 대화로 불러서 '첫 판단'을 받고, 이후 질문은
 * [FIRST_PREREQ_MSG, 첫 판단, 질문, 답, ...] 순서로 대화 전체를 보낸다.
 * 서버가 없으면 계획서에 적힌 선수과목 문구를 대신 보여준다. 답은 참고용.
 */
export default function AdviceBox({ code, major, missing, completedCodes, takingCodes, notes, onClose }: Props) {
  const [msgs, setMsgs] = useState<ChatMessage[]>([]) // 첫 user 메시지(FIRST_PREREQ_MSG)는 화면에 안 보임
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [notReady, setNotReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  const send = async (conversation: ChatMessage[]) => {
    setLoading(true)
    setError(null)
    try {
      const r = await chat('prereq', conversation.length ? conversation : [], {
        major,
        subject: code,
        completed: completedCodes,
        taking: takingCodes,
      })
      const base = conversation.length ? conversation : [{ role: 'user' as const, text: FIRST_PREREQ_MSG }]
      setMsgs([...base, { role: 'assistant', text: r.reply }])
    } catch (e) {
      if (e instanceof NotReadyError) setNotReady(true)
      else setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setMsgs([])
    setNotReady(false)
    send([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code])

  useEffect(() => { endRef.current?.scrollIntoView({ block: 'nearest' }) }, [msgs, loading])

  const ask = () => {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    const next = [...msgs, { role: 'user' as const, text: q }]
    setMsgs(next)
    send(next)
  }

  const prereqText = subjectByCode.get(code)?.prereqText

  return (
    <div className="advice">
      <div className="advice-head">
        <b>선수과목 상담 · {nameOf(code)}</b>
        <button className="x" onClick={onClose}>닫기</button>
      </div>
      <p className="muted small" style={{ margin: '0 0 6px' }}>
        안 들은 선수과목: {missing.map((g) => g.map(nameOf).join(' 또는 ')).join(', ')}
      </p>

      <div className="msgs">
        {msgs.slice(1).map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>{m.role === 'assistant' ? <Markdown text={m.text} /> : m.text}</div>
        ))}
        {loading && <div className="msg assistant muted">생각 중…</div>}
        <div ref={endRef} />
      </div>
      {error && <p className="error">{error}</p>}

      {/* 서버가 없을 때 + 답과 함께 근거로: 계획서 원문 */}
      <details className="advice-src" open={notReady}>
        <summary>{notReady ? 'AI 상담 서버가 아직 준비되지 않아서, 계획서 내용을 보여드려요' : '계획서 원문 보기'}</summary>
        {prereqText && (
          <>
            <h4>계획서에 적힌 선수과목</h4>
            <p className="pre small">{prereqText}</p>
          </>
        )}
        {notes && (
          <>
            <h4>수강 참고사항</h4>
            <p className="pre small">{notes}</p>
          </>
        )}
        {!prereqText && !notes && <p className="muted small">계획서에 적힌 내용이 없어요.</p>}
      </details>

      {!notReady && msgs.length > 0 && (
        <div className="advice-ask">
          <textarea
            value={input}
            placeholder="더 궁금한 걸 물어보세요 (예: 방학에 뭘 공부하면 될까요?)"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), ask())}
            rows={2}
          />
          <button className="primary" disabled={loading || !input.trim()} onClick={ask}>보내기</button>
        </div>
      )}
      <p className="muted small">참고용 답변이에요. 최종 판단은 교수님이나 학과에 확인하세요.</p>
    </div>
  )
}
