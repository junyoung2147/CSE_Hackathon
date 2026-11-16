// 백엔드가 있으면 API를, 없으면 브라우저 저장소를 쓴다.
const API = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || ''
const USER = (import.meta.env.VITE_USER_ID as string | undefined) || 'demo'
const LS_KEY = 'cse-map-completed'

export const hasBackend = API !== ''

function readLocal(): string[] {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) || '[]')
  } catch {
    return []
  }
}
function writeLocal(codes: string[]) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(codes))
  } catch {
    /* 저장소를 못 써도 화면 상태는 유지된다 */
  }
}

export async function loadCompleted(): Promise<Set<string>> {
  if (!hasBackend) return new Set(readLocal())
  const res = await fetch(`${API}/api/roadmap?user_id=${encodeURIComponent(USER)}`)
  if (!res.ok) throw new Error(`roadmap ${res.status}`)
  const body = await res.json()
  return new Set(
    (body.subjects as { subject_code: string; is_completed: boolean }[])
      .filter((s) => s.is_completed)
      .map((s) => s.subject_code),
  )
}

export async function setCompleted(code: string, completed: boolean, all: Set<string>) {
  if (!hasBackend) {
    writeLocal([...all])
    return
  }
  await fetch(`${API}/api/roadmap/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: USER, subject_code: code, completed }),
  })
}

export type SubjectDetail = {
  subject_code: string
  subject_name: string
  sections: {
    term: string
    course_no: string
    professor: string | null
    time_real: string | null
    room: string | null
    syllabus: { summary: string | null; goals: string | null; evaluation: string | null } | null
    weeks: { week: number | null; content: string | null }[]
  }[]
}

export async function loadDetail(code: string): Promise<SubjectDetail | null> {
  if (!hasBackend) return null
  const res = await fetch(`${API}/api/subjects/${encodeURIComponent(code)}`)
  if (!res.ok) return null
  return res.json()
}
