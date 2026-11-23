import { useEffect, useRef, useState } from 'react'
import { chat, NotReadyError, planRoadmap, type ChatMessage, type RoadmapPlan } from './api'
import { nameOf } from './data'
import Markdown from './Markdown'

type Props = {
  major: string
  messages: ChatMessage[]
  setMessages: (m: ChatMessage[]) => void
  currentTargets: string[] // 지금 목표 과목 (내 로드맵 또는 고른 진로)
  completed: string[]
  taking: string[] // 이번 학기 수강 중
  onApply: (targets: string[], reasons: Record<string, string>) => void
}

const EXAMPLES = [
  'GPU나 AI 추론 최적화 쪽으로 가고 싶은데 뭘 들어야 해?',
  '졸업까지 전공 학점이 얼마나 남았어?',
  '웹 개발자가 되려면 3학년 때 뭘 들으면 좋아?',
]

/**
 * AI 상담 (POST /api/chat, mode=general) + 로드맵 짜기 (POST /api/roadmap/plan).
 * AI가 "로드맵을 짜 드릴까요?"(suggest_action)라고 하면 버튼이 뜨고,
 * 누르면 추가·삭제 미리보기를 보여준 뒤 '적용'하면 지도에 '내 로드맵'으로 표시된다.
 */
export default function ChatView({ major, messages, setMessages, currentTargets, completed, taking, onApply }: Props) {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [suggest, setSuggest] = useState(false)
  const [plan, setPlan] = useState<RoadmapPlan | null>(null)
  const [planning, setPlanning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => { endRef.current?.scrollIntoView({ block: 'nearest' }) }, [messages, loading])

  const fail = (e: unknown) =>
    setError(e instanceof NotReadyError ? `${e.message}. 백엔드 /api/chat 이 올라오면 바로 쓸 수 있어요.` : (e as Error).message)

  const send = async (text: string) => {
    const q = text.trim()
    if (!q || loading) return
    setInput('')
    setError(null)
    const next = [...messages, { role: 'user' as const, text: q }]
    setMessages(next)
    setLoading(true)
    try {
      const r = await chat('general', next, { major, targets: currentTargets, completed, taking })
      setMessages([...next, { role: 'assistant', text: r.reply }])
      setSuggest(r.suggest_action === 'plan_roadmap')
    } catch (e) {
      fail(e)
      setMessages(messages) // 실패한 질문은 되돌려서 다시 보낼 수 있게
      setInput(q)
    } finally {
      setLoading(false)
    }
  }

  const makePlan = async () => {
    setPlanning(true)
    setError(null)
    try {
      setPlan(await planRoadmap(messages, major, currentTargets, completed, taking))
    } catch (e) {
      fail(e)
    } finally {
      setPlanning(false)
    }
  }

  const apply = () => {
    if (!plan) return
    const remove = new Set(plan.remove)
    const targets = [...currentTargets.filter((c) => !remove.has(c)), ...plan.add.filter((c) => !currentTargets.includes(c))]
    onApply(targets, plan.reasons)
    setPlan(null)
    setSuggest(false)
  }

  return (
    <div className="chat">
      <div className="chat-main">
        <div className="chat-msgs">
          {messages.length === 0 && (
            <div className="chat-empty">
              <h2>AI 상담</h2>
              <p className="muted">진로, 들을 과목, 졸업요건을 물어보세요. {major} 교육과정과 강의계획서를 근거로 답해요.</p>
              <div className="chips">
                {EXAMPLES.map((q) => (
                  <button key={q} className="chip" onClick={() => send(q)}>{q}</button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>{m.role === 'assistant' ? <Markdown text={m.text} /> : m.text}</div>
          ))}
          {loading && <div className="msg assistant muted">생각 중…</div>}
          {error && <p className="error">{error}</p>}
          {(suggest || messages.length >= 2) && !plan && (
            <div className="plan-cta">
              {suggest && <span>대화 내용으로 로드맵을 짜 드릴까요?</span>}
              <button className="primary" disabled={planning || loading} onClick={makePlan}>
                {planning ? '로드맵 짜는 중…' : '이 대화로 로드맵 짜기'}
              </button>
            </div>
          )}
          <div ref={endRef} />
        </div>
        <div className="chat-input">
          <textarea
            value={input}
            placeholder="예) 보안 쪽에 관심 있는데 2학년 2학기에 뭘 들으면 좋을까?"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), send(input))}
            rows={2}
          />
          <button className="primary" disabled={loading || !input.trim()} onClick={() => send(input)}>보내기</button>
        </div>
        <div className="chat-foot">
          <p className="muted small">참고용 답변이에요. 수강 계획은 학과 공지와 지도교수님 상담으로 꼭 확인하세요.</p>
          {messages.length > 0 && (
            <button className="link" onClick={() => { setMessages([]); setPlan(null); setSuggest(false); setError(null) }}>새 대화</button>
          )}
        </div>
      </div>

      {plan && (
        <aside className="plan">
          <h3>로드맵 미리보기</h3>
          {plan.add.length === 0 && plan.remove.length === 0 && <p className="muted">바꿀 과목이 없대요.</p>}
          {plan.add.length > 0 && (
            <>
              <h4>추가할 과목</h4>
              <ul>
                {plan.add.map((c) => (
                  <li key={c}>
                    <b>+ {nameOf(c)}</b>
                    {plan.outside_curriculum.includes(c) && <span className="tag">교육과정 밖</span>}
                    {plan.reasons[c] && <p className="small">{plan.reasons[c]}</p>}
                  </li>
                ))}
              </ul>
            </>
          )}
          {plan.remove.length > 0 && (
            <>
              <h4>뺄 과목</h4>
              <ul>
                {plan.remove.map((c) => (
                  <li key={c}>
                    <b>− {nameOf(c)}</b>
                    {plan.reasons[c] && <p className="small">{plan.reasons[c]}</p>}
                  </li>
                ))}
              </ul>
            </>
          )}
          <div className="plan-actions">
            <button className="primary" onClick={apply}>적용하고 지도에서 보기</button>
            <button onClick={() => setPlan(null)}>취소</button>
          </div>
        </aside>
      )}
    </div>
  )
}
