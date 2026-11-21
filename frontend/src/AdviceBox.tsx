import { useEffect, useState } from 'react'
import { askAdvice, type Advice } from './api'
import { nameOf, subjectByCode } from './data'

type Props = {
  code: string // 들으려는 과목
  missing: string[] // 안 들은 선수과목 묶음 (이 중 하나)
  completedCodes: string[]
  notes: string | null // 계획서 수강 참고사항
  onClose: () => void
}

/**
 * "이 선수과목 꼭 들어야 하나요?" 상담.
 * 백엔드 LLM(/api/advise)이 있으면 답을 받고, 없으면 계획서에 적힌 문구를 그대로 보여준다.
 * 답은 참고용 — 최종 판단은 교수님·학과에 확인.
 */
export default function AdviceBox({ code, missing, completedCodes, notes, onClose }: Props) {
  const preset = `${missing.map(nameOf).join(' 또는 ')}을(를) 안 들었는데 ${nameOf(code)}을(를) 들어도 될까요? 미리 뭘 공부하면 좋을까요?`
  const [question, setQuestion] = useState(preset)
  const [loading, setLoading] = useState(false)
  const [advice, setAdvice] = useState<Advice | null>(null)
  const [noBackend, setNoBackend] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const ask = async (q: string) => {
    setLoading(true)
    setError(null)
    try {
      const a = await askAdvice(code, completedCodes, q)
      if (a) setAdvice(a)
      else setNoBackend(true)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setAdvice(null)
    setNoBackend(false)
    setQuestion(preset)
    ask(preset)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, missing.join('|')])

  const prereqText = subjectByCode.get(code)?.prereqText

  return (
    <div className="advice">
      <div className="advice-head">
        <b>선수과목 상담</b>
        <button className="x" onClick={onClose}>닫기</button>
      </div>

      {loading && <p className="muted small">답변 준비 중…</p>}
      {error && <p className="error">{error}</p>}
      {advice && (
        <>
          <p className="pre">{advice.answer}</p>
          {advice.sources?.length > 0 && (
            <p className="muted small">근거: {advice.sources.join(' · ')}</p>
          )}
        </>
      )}

      {/* LLM이 없을 때도 판단할 수 있게 계획서 원문을 항상 같이 보여준다 */}
      {(noBackend || advice) && (
        <div className="advice-src">
          {noBackend && <p className="muted small">AI 상담은 아직 연결 전이에요. 대신 계획서에 적힌 내용을 보여드려요.</p>}
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
        </div>
      )}

      <div className="advice-ask">
        <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={2} />
        <button className="primary" disabled={loading || !question.trim()} onClick={() => ask(question)}>물어보기</button>
      </div>
      <p className="muted small">참고용 답변이에요. 최종 판단은 교수님이나 학과에 확인하세요.</p>
    </div>
  )
}
