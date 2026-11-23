/**
 * 내 학업 현황: 과목별 성적, 평점, 졸업요건, 수강 중 과목.
 * 모두 브라우저(localStorage)에 저장한다. 이수 여부만 백엔드에도 보낸다(api.ts).
 */
import Papa from 'papaparse'
import gradCsv from '../../data/curriculum_data/out/graduation_credits.csv?raw'
import { curriculum, subjectByCode } from './data'

// ---------- 성적 ----------

export type Scale = '4.5' | '4.3'
export const GRADES: Record<Scale, [string, number][]> = {
  '4.5': [['A+', 4.5], ['A0', 4.0], ['B+', 3.5], ['B0', 3.0], ['C+', 2.5], ['C0', 2.0], ['D+', 1.5], ['D0', 1.0], ['F', 0]],
  '4.3': [['A+', 4.3], ['A0', 4.0], ['A-', 3.7], ['B+', 3.3], ['B0', 3.0], ['B-', 2.7], ['C+', 2.3], ['C0', 2.0], ['C-', 1.7], ['D+', 1.3], ['D0', 1.0], ['D-', 0.7], ['F', 0]],
}
/** P(통과)와 ''(성적 미입력)는 평점 계산에서 뺀다 */
export const NON_GPA = ['P', '']

/** 과목코드 → 성적 ('' = 이수했지만 성적 미입력) */
export type Grades = Record<string, string>

/** 교양·그 외 학점을 사용자가 직접 고친 값 (없으면 지도 계산값) */
export type Overrides = { 교양?: number; '그 외'?: number }
export const EDITABLE = ['교양', '그 외'] as const

const KEY = { grades: 'cse-map-grades', taking: 'cse-map-taking', overrides: 'cse-map-credit-override', scale: 'cse-map-scale', mine: 'cse-map-my-roadmap' }

function read<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key)
    return v === null ? fallback : (JSON.parse(v) as T)
  } catch {
    return fallback
  }
}
function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* 저장소를 못 써도 화면 상태는 유지 */
  }
}

export const store = {
  loadGrades: (): Grades => {
    const g = read<Grades | null>(KEY.grades, null)
    if (g) return g
    // 예전 버전(이수 목록만 저장)에서 옮겨오기
    const old = read<string[]>('cse-map-completed', [])
    return Object.fromEntries(old.map((c) => [c, '']))
  },
  saveGrades: (g: Grades) => write(KEY.grades, g),
  loadTaking: (): string[] => read(KEY.taking, []),
  saveTaking: (t: string[]) => write(KEY.taking, t),
  /** AI 상담으로 만든 내 로드맵 (목표 과목 + 이유) */
  loadMine: (): { targets: string[]; reasons: Record<string, string> } => read(KEY.mine, { targets: [], reasons: {} }),
  saveMine: (m: { targets: string[]; reasons: Record<string, string> }) => write(KEY.mine, m),
  loadOverrides: (): Overrides => read(KEY.overrides, {}),
  saveOverrides: (o: Overrides) => write(KEY.overrides, o),
  // 경북대는 4.3 만점. 다른 학교로 넓힐 때 대비해서 4.5 표도 남겨 둔다
  loadScale: (): Scale => '4.3',
  saveScale: (s: Scale) => write(KEY.scale, s),
}

export function creditOf(code: string): number {
  return subjectByCode.get(code)?.credit ?? curriculum.find((r) => r.code === code)?.credit ?? 3
}

export function gpaOf(grades: Grades, scale: Scale) {
  const table = new Map(GRADES[scale])
  let points = 0
  let gpaCredits = 0
  let credits = 0
  for (const [code, g] of Object.entries(grades)) {
    const cr = creditOf(code)
    if (g !== 'F') credits += cr
    if (NON_GPA.includes(g) || !table.has(g)) continue
    points += table.get(g)! * cr
    gpaCredits += cr
  }
  return { gpa: gpaCredits ? points / gpaCredits : null, credits, gpaCredits }
}

// ---------- 졸업요건 ----------

type GradRow = { major_name: string; from: string; to: string; category: string; credits_min: string; note: string }
const gradRows = Papa.parse<GradRow>(gradCsv.replace(/^﻿/, ''), { header: true, skipEmptyLines: true }).data

/** 졸업요건 항목 → 교육과정표 교과구분 중 어떤 걸 세는지. 없는 항목은 '직접 확인'으로 표시 */
const COUNTS: Record<string, string[] | 'all'> = {
  전체: 'all',
  전공: ['전공', '공학전공', '전공기반'],
  교양: ['교양', '기본소양'],
  'ABEEK 공학전공': ['공학전공'],
  'ABEEK 전공기반': ['전공기반'],
  'ABEEK 기본소양': ['기본소양'],
  'ABEEK 이수학점': ['공학전공', '전공기반', '기본소양'],
}

export type Requirement = {
  category: string
  need: number
  have: number | null // null = 자동으로 셀 수 없음
  base?: number // 교양·그 외: 지도에서 센 학점 (사용자가 고치기 전 값)
  note: string
}

/** 가장 최근 기준(종료 연도가 비어 있는 것)의 졸업요건으로 계산 */
export function graduationOf(major: string, grades: Grades, overrides: Overrides): Requirement[] {
  const rows = gradRows.filter((r) => r.major_name === major && !r.to)
  const latest = new Map<string, GradRow>()
  for (const r of rows) {
    const prev = latest.get(r.category)
    if (!prev || Number(r.from || 0) > Number(prev.from || 0)) latest.set(r.category, r)
  }
  const passed = Object.entries(grades).filter(([, g]) => g !== 'F').map(([c]) => c)
  const catOf = new Map(curriculum.filter((r) => r.major === major).map((r) => [r.code, r.category]))

  const sum = (f: (cat: string) => boolean) =>
    passed.filter((c) => f(catOf.get(c) ?? '')).reduce((s, c) => s + creditOf(c), 0)
  // 그 외 = 전공·교양 규칙에 안 들어가는 지도 과목
  const base: Record<string, number> = {
    교양: sum((c) => (COUNTS.교양 as string[]).includes(c)),
    '그 외': sum((c) => !(COUNTS.전공 as string[]).includes(c) && !(COUNTS.교양 as string[]).includes(c)),
  }
  // 요건이 있는 항목만, 사용자가 고친 만큼의 차이를 전체에 더한다
  const delta = EDITABLE.filter((k) => latest.has(k) && overrides[k] !== undefined)
    .reduce((s, k) => s + overrides[k]! - base[k], 0)

  return [...latest.values()].map((r) => {
    const rule = COUNTS[r.category]
    let have: number | null = null
    const editable = (EDITABLE as readonly string[]).includes(r.category)
    if (rule === 'all') have = passed.reduce((s, c) => s + creditOf(c), 0) + delta
    else if (editable) have = overrides[r.category as keyof Overrides] ?? base[r.category]
    else if (rule) have = sum((c) => rule.includes(c))
    return { category: r.category, need: Number(r.credits_min), have, base: editable ? base[r.category] : undefined, note: r.note || '' }
  })
}

export function requiredCourses(major: string) {
  return curriculum.filter((r) => r.major === major && r.required)
}
