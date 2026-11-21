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

// ---------- LLM 상담 (data/llm, 준영님 모듈 / 백엔드 엔드포인트는 재웅님) ----------

export type ChatMessage = { role: 'user' | 'assistant'; text: string }
export type ChatReply = { reply: string; suggest_action: 'plan_roadmap' | null }
export type RoadmapPlan = {
  add: string[]
  remove: string[]
  reasons: Record<string, string>
  outside_curriculum: string[]
  dropped: string[]
}

/** prereq 모드에서 후속 질문을 보낼 때 맨 앞에 넣는 첫 메시지 (data/llm/api.py의 FIRST_PREREQ_MSG와 같아야 함) */
export const FIRST_PREREQ_MSG = '안 들은 선수과목마다 첫 판단을 알려 주세요.'

export class NotReadyError extends Error {}

async function post<T>(path: string, body: unknown): Promise<T> {
  if (!hasBackend) throw new NotReadyError('백엔드가 연결되지 않았어요')
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (res.status === 404 || res.status === 405) throw new NotReadyError('AI 상담 서버가 아직 준비되지 않았어요')
  const data = await res.json().catch(() => ({}))
  if (res.status === 503) throw new Error('AI가 지금 바빠요. 잠시 후 다시 시도해 주세요')
  if (!res.ok) throw new Error((data as { detail?: string }).detail || `HTTP ${res.status}`)
  return data as T
}

/**
 * POST /api/chat
 * - general: 진로·과목·졸업요건 상담 (major, targets)
 * - prereq: subject를 듣기 전 안 들은 선수과목을 건너뛰어도 되는지 (빈 대화면 첫 판단)
 * completed·targets는 백엔드가 DB에서 읽는 게 원칙이지만, 로컬 모드 사용자도 있어서 같이 보낸다.
 */
export function chat(
  mode: 'general' | 'prereq',
  conversation: ChatMessage[],
  opts: { major: string; subject?: string; targets?: string[]; completed: string[] },
) {
  return post<ChatReply>('/api/chat', { user_id: USER, mode, conversation, ...opts })
}

/** POST /api/roadmap/plan — 대화를 보고 목표 과목 추가·삭제안 (미리보기, 저장 안 함) */
export function planRoadmap(conversation: ChatMessage[], major: string, currentTargets: string[], completed: string[]) {
  return post<RoadmapPlan>('/api/roadmap/plan', {
    user_id: USER,
    major,
    conversation,
    current_targets: currentTargets,
    completed,
  })
}
