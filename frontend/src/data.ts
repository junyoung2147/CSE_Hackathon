import Papa from 'papaparse'
import edgesCsv from '../../data/graph_data/edges.csv?raw'
import subjectsCsv from '../../data/lecture_data/lecture_data_csv/subjects.csv?raw'

export type Subject = {
  code: string
  name: string
  credit: number | null
  offeredTerms: string[]
}

export type Edge = {
  from: string
  to: string
  type: 'pre' | 'rel'
  orWith: string[]
}

function parse<T>(text: string): T[] {
  // BOM 제거 후 파싱. 계획서 텍스트에 줄바꿈이 있어도 papaparse가 처리한다.
  const res = Papa.parse<T>(text.replace(/^﻿/, ''), { header: true, skipEmptyLines: true })
  return res.data
}

type SubjectRow = { subject_code: string; subject_name: string; credit: string; offered_terms: string }
type EdgeRow = { from_code: string; to_code: string; type: string; or_with: string }

export const subjects: Subject[] = parse<SubjectRow>(subjectsCsv)
  .filter((r) => r.subject_code)
  .map((r) => ({
    code: r.subject_code.trim(),
    name: r.subject_name.trim(),
    credit: r.credit ? Number(r.credit) : null,
    offeredTerms: (r.offered_terms || '').split(',').map((s) => s.trim()).filter(Boolean),
  }))

export const edges: Edge[] = parse<EdgeRow>(edgesCsv)
  .filter((r) => r.from_code && r.to_code)
  .map((r) => ({
    from: r.from_code.trim(),
    to: r.to_code.trim(),
    type: r.type === 'rel' ? 'rel' : 'pre',
    orWith: (r.or_with || '').split(';').map((s) => s.trim()).filter(Boolean),
  }))

export const subjectByCode = new Map(subjects.map((s) => [s.code, s]))

/** 선수 관계(pre)만 따라 거슬러 올라간 모든 조상 과목 */
export function ancestorsOf(code: string): Set<string> {
  const parents = new Map<string, string[]>()
  for (const e of edges) {
    if (e.type !== 'pre') continue
    parents.set(e.to, [...(parents.get(e.to) ?? []), e.from])
  }
  const seen = new Set<string>()
  const stack = [code]
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

export function prereqsOf(code: string): Edge[] {
  return edges.filter((e) => e.type === 'pre' && e.to === code)
}

/** 선수과목을 '이 중 하나만 들으면 되는 묶음'으로 정리 (A 또는 B 가 두 번 나오지 않게) */
export function prereqGroupsOf(code: string): string[][] {
  const seen = new Set<string>()
  const groups: string[][] = []
  for (const e of prereqsOf(code)) {
    const group = [e.from, ...e.orWith]
    const key = [...group].sort().join('|')
    if (seen.has(key)) continue
    seen.add(key)
    groups.push(group)
  }
  return groups
}

export function followupsOf(code: string): Edge[] {
  return edges.filter((e) => e.type === 'pre' && e.from === code)
}

export function relatedOf(code: string): string[] {
  return edges
    .filter((e) => e.type === 'rel' && (e.from === code || e.to === code))
    .map((e) => (e.from === code ? e.to : e.from))
}
