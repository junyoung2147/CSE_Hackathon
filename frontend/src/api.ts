// 백엔드가 있으면 API를, 없으면 브라우저 저장소를 쓴다.
const API = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || ''
const USER = (import.meta.env.VITE_USER_ID as string | undefined) || 'demo'

export const hasBackend = API !== ''

/** 백엔드에 저장된 이수 과목 (백엔드가 없으면 빈 집합 — 로컬 저장은 progress.ts가 맡는다) */
export async function loadCompleted(): Promise<Set<string>> {
  if (!hasBackend) return new Set()
  const res = await fetch(`${API}/api/roadmap?user_id=${encodeURIComponent(USER)}`)
  if (!res.ok) throw new Error(`roadmap ${res.status}`)
  const body = await res.json()
  return new Set(
    (body.subjects as { subject_code: string; is_completed: boolean }[])
      .filter((s) => s.is_completed)
      .map((s) => s.subject_code),
  )
}

export async function setCompleted(code: string, completed: boolean) {
  if (!hasBackend) return
  await fetch(`${API}/api/roadmap/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: USER, subject_code: code, completed }),
  })
}


export type EverytimeCourse = {
  course_no: string
  subject_code: string
  name: string
  professor: string
  credit: number | null
  times: { day: number; start: number; end: number; place: string }[]
}
export type EverytimeResult = {
  semesters: { year: number; semester: string; courses: EverytimeCourse[] }[]
  skipped: { year: number | null; semester: string | null; reason: string }[]
}

/** 에브리타임 공유 링크 → 학기별 시간표 (백엔드 /api/everytime 경유) */
export async function loadEverytime(link: string): Promise<EverytimeResult> {
  if (!hasBackend) throw new Error('백엔드 주소(VITE_API_URL)가 설정되지 않았어요')
  const res = await fetch(`${API}/api/everytime?link=${encodeURIComponent(link)}`)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`)
  return body
}

export type Advice = { answer: string; sources: string[] }

/**
 * 선수과목 상담 (LLM). 백엔드 POST /api/advise — 준영님 작업.
 * 요청: { subject_code, completed_codes, question } → 응답: { answer, sources }
 * 백엔드가 없거나 아직 엔드포인트가 없으면 null (화면에서 계획서 문구로 대신 보여줌)
 */
export async function askAdvice(subjectCode: string, completedCodes: string[], question: string): Promise<Advice | null> {
  if (!hasBackend) return null
  const res = await fetch(`${API}/api/advise`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: USER, subject_code: subjectCode, completed_codes: completedCodes, question }),
  })
  if (res.status === 404) return null
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`)
  return body
}
