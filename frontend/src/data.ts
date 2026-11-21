import Papa from 'papaparse'
import edgesCsv from '../../data/graph_data/edges.csv?raw'
import subjectsCsv from '../../data/lecture_data/lecture_data_csv/subjects.csv?raw'
import curriculumCsv from '../../data/curriculum_data/curriculum.csv?raw'

// ---------- 원본 CSV 읽기 ----------

export type Subject = {
  code: string
  name: string
  credit: number | null
  offeredTerms: string[]
  prereqText: string // 계획서에 교수님이 적은 선수과목 문구 (분반별로 한 줄씩)
}

export type Edge = {
  from: string
  to: string
  type: 'pre' | 'rel'
  orWith: string[] // 이 중 하나만 들어도 되는 대안 과목
}

/** 교육과정표 한 줄 = 전공 × 과목 */
export type CurriculumRow = {
  major: string
  code: string
  name: string
  grade: number // 권장 학년
  semester: number // 권장 학기 (1 또는 2)
  category: string // 전공 / 교양 / 교직 ...
  credit: number | null
  required: boolean // 전공필수
}

function parse<T>(text: string): T[] {
  // BOM 제거 후 파싱. 계획서 텍스트 안의 줄바꿈도 papaparse가 처리한다.
  return Papa.parse<T>(text.replace(/^﻿/, ''), { header: true, skipEmptyLines: true }).data
}

type SubjectRow = { subject_code: string; subject_name: string; credit: string; offered_terms: string; prerequisites: string }
type EdgeRow = { from_code: string; to_code: string; type: string; or_with: string }
type CurRow = {
  major_name: string
  grade: string
  semester: string
  category: string
  course_code: string
  course_name_ko: string
  credits: string
  is_required: string
}

export const subjects: Subject[] = parse<SubjectRow>(subjectsCsv)
  .filter((r) => r.subject_code)
  .map((r) => ({
    code: r.subject_code.trim(),
    name: r.subject_name.trim(),
    credit: r.credit ? Number(r.credit) : null,
    offeredTerms: (r.offered_terms || '').split(/[,;]/).map((s) => s.trim()).filter(Boolean),
    prereqText: (r.prerequisites || '').trim(),
  }))

export const subjectByCode = new Map(subjects.map((s) => [s.code, s]))

export const edges: Edge[] = parse<EdgeRow>(edgesCsv)
  .filter((r) => r.from_code && r.to_code)
  .map((r) => ({
    from: r.from_code.trim(),
    to: r.to_code.trim(),
    type: r.type === 'rel' ? 'rel' : 'pre',
    orWith: (r.or_with || '').split(';').map((s) => s.trim()).filter(Boolean),
  }))

export const curriculum: CurriculumRow[] = parse<CurRow>(curriculumCsv)
  .filter((r) => r.course_code && r.major_name)
  .map((r) => ({
    major: r.major_name.trim(),
    code: r.course_code.trim(),
    // 이름은 시간표(subjects.csv) 쪽을 우선한다 (교육과정표는 띄어쓰기가 다를 수 있음)
    name: subjectByCode.get(r.course_code.trim())?.name ?? r.course_name_ko.trim(),
    grade: Number(r.grade),
    semester: r.semester.startsWith('2') ? 2 : 1,
    category: r.category,
    credit: r.credits ? Number(r.credits) : null,
    required: r.is_required === 'Y',
  }))

/** 전공 목록 (교육과정표 순서 유지) */
export const majors: string[] = [...new Set(curriculum.map((r) => r.major))]

export function nameOf(code: string): string {
  return subjectByCode.get(code)?.name ?? curriculum.find((r) => r.code === code)?.name ?? code
}

// ---------- 전공별 그래프 ----------

export type Course = CurriculumRow & { col: number } // col: 0 = 1-1학기, 7 = 4-2학기

export type MajorGraph = {
  major: string
  courses: Course[]
  courseByCode: Map<string, Course>
  edges: Edge[] // 이 전공 과목끼리만 남긴 간선
}

/**
 * 한 전공의 교육과정 과목만 노드로 쓰고, 간선도 그 안에서만 잇는다.
 * 선수과목이 다른 전공 과목이면(예: 프로그래밍기초) or_with 대안 중
 * 이 전공에 있는 과목(예: 기초프로그래밍)으로 바꿔서 잇는다.
 */
export function buildMajorGraph(major: string): MajorGraph {
  const courses: Course[] = []
  const seen = new Set<string>()
  for (const r of curriculum) {
    if (r.major !== major || seen.has(r.code)) continue
    seen.add(r.code)
    courses.push({ ...r, col: (r.grade - 1) * 2 + (r.semester - 1) })
  }
  const courseByCode = new Map(courses.map((c) => [c.code, c]))

  const out: Edge[] = []
  const key = new Set<string>()
  for (const e of edges) {
    const from = [e.from, ...e.orWith].find((c) => courseByCode.has(c))
    if (!from || !courseByCode.has(e.to) || from === e.to) continue
    const k = `${e.type}|${from}|${e.to}`
    if (key.has(k)) continue
    key.add(k)
    out.push({ ...e, from, orWith: e.orWith.filter((c) => c !== from && courseByCode.has(c)) })
  }
  return { major, courses, courseByCode, edges: out }
}

// ---------- 그래프 탐색 ----------

/** 선수(pre) 간선만 따라 거슬러 올라간 모든 조상 과목 */
export function ancestorsOf(codes: string[], es: Edge[]): Set<string> {
  const parents = new Map<string, string[]>()
  for (const e of es) {
    if (e.type !== 'pre') continue
    parents.set(e.to, [...(parents.get(e.to) ?? []), e.from])
  }
  const seen = new Set<string>()
  const stack = [...codes]
  while (stack.length) {
    const cur = stack.pop()!
    for (const p of parents.get(cur) ?? []) {
      if (!seen.has(p)) {
        seen.add(p)
        stack.push(p)
      }
    }
  }
  return seen
}

/** 선수과목을 '이 중 하나만 들으면 되는 묶음'으로 정리 (전체 데이터 기준) */
export function prereqGroupsOf(code: string): string[][] {
  const seen = new Set<string>()
  const groups: string[][] = []
  for (const e of edges) {
    if (e.type !== 'pre' || e.to !== code) continue
    const group = [e.from, ...e.orWith]
    const k = [...group].sort().join('|')
    if (seen.has(k)) continue
    seen.add(k)
    groups.push(group)
  }
  return groups
}

export function followupsOf(code: string): string[] {
  // 전공마다 코드가 다른 같은 이름 과목(예: 데이터베이스)은 한 번만
  const byName = new Map<string, string>()
  for (const e of edges) {
    if (e.type === 'pre' && e.from === code && !byName.has(nameOf(e.to))) byName.set(nameOf(e.to), e.to)
  }
  return [...byName.values()]
}

export function relatedOf(code: string): string[] {
  return edges
    .filter((e) => e.type === 'rel' && (e.from === code || e.to === code))
    .map((e) => (e.from === code ? e.to : e.from))
}

/**
 * 이수 / 수강 중 / 다음 후보 / 기본
 * 선수과목은 대부분 '권장'이라서 "다 들어야 들을 수 있다"로 막지 않는다.
 * 선수과목을 하나라도 들었으면(또는 수강 중이면) '다음 후보'로 보여준다.
 */
export type Status = 'done' | 'taking' | 'next' | 'none'

export function statusOf(code: string, completed: Set<string>, taking: Set<string> = new Set()): Status {
  if (completed.has(code)) return 'done'
  if (taking.has(code)) return 'taking'
  const had = (c: string) => completed.has(c) || taking.has(c)
  const anyPre = edges.some((e) => e.type === 'pre' && e.to === code && (had(e.from) || e.orWith.some(had)))
  return anyPre ? 'next' : 'none'
}

/** 선수과목 묶음을 들은 것 / 안 들은 것으로 나눈다 */
export function splitPrereqs(code: string, completed: Set<string>, taking: Set<string>) {
  const had = (c: string) => completed.has(c) || taking.has(c)
  const groups = prereqGroupsOf(code)
  return {
    taken: groups.filter((g) => g.some(had)),
    missing: groups.filter((g) => !g.some(had)),
  }
}

export const SEMESTER_LABELS = ['1-1', '1-2', '2-1', '2-2', '3-1', '3-2', '4-1', '4-2']
