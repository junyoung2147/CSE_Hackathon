import type { Edge as FlowEdge } from '@xyflow/react'
import type { Edge, MajorGraph } from './data'

export const NODE_W = 168
export const NODE_H = 46
export const COL_GAP = 84 // 학기 열 사이 간격
export const ROW_GAP = 14
export const TOP = 64 // 학기 제목 아래부터 과목 시작
export const COL_W = NODE_W + COL_GAP

export const colX = (col: number) => col * COL_W

/**
 * x = 권장 학기 열(1-1 ~ 4-2), y = 열 안의 순서.
 * 열 안의 순서는 '바리센터' 방식으로 정한다:
 * 각 과목을 이어진 과목들의 평균 높이 쪽으로 정렬하는 걸 몇 번 반복하면 선이 덜 꼬인다.
 */
export function layoutBySemester(g: MajorGraph) {
  const columns: string[][] = Array.from({ length: 9 }, () => [])
  for (const c of g.courses) columns[Math.min(Math.max(c.col, 0), 8)].push(c.code)

  // 처음엔 전공필수 → 이름순
  for (const col of columns) {
    col.sort((a, b) => {
      const ca = g.courseByCode.get(a)!
      const cb = g.courseByCode.get(b)!
      return Number(cb.required) - Number(ca.required) || ca.name.localeCompare(cb.name, 'ko')
    })
  }

  const neighbors = new Map<string, string[]>()
  for (const e of g.edges) {
    neighbors.set(e.to, [...(neighbors.get(e.to) ?? []), e.from])
    neighbors.set(e.from, [...(neighbors.get(e.from) ?? []), e.to])
  }

  const rowOf = () => {
    const m = new Map<string, number>()
    columns.forEach((col) => col.forEach((code, i) => m.set(code, i)))
    return m
  }

  for (let iter = 0; iter < 6; iter++) {
    const row = rowOf()
    for (const col of columns) {
      const score = new Map<string, number>()
      for (const code of col) {
        const ns = (neighbors.get(code) ?? []).map((n) => row.get(n)!).filter((v) => v !== undefined)
        score.set(code, ns.length ? ns.reduce((a, b) => a + b, 0) / ns.length : row.get(code)!)
      }
      col.sort((a, b) => score.get(a)! - score.get(b)!)
    }
  }

  const positions = new Map<string, { x: number; y: number }>()
  columns.forEach((col, ci) =>
    col.forEach((code, ri) => positions.set(code, { x: colX(ci), y: TOP + ri * (NODE_H + ROW_GAP) })),
  )
  const height = TOP + Math.max(...columns.map((c) => c.length)) * (NODE_H + ROW_GAP)
  return { positions, height, hasOutside: columns[8].length > 0 }
}

/**
 * 선을 언제 그리나
 * - 진로나 과목을 골랐을 때(active): 그 경로 선만 진하게, 나머지는 숨김
 * - 기본 화면: 내가 들었거나 듣고 있는 과목(start)에서 나가는 선만 그린다
 *   (아무것도 안 들었으면 1학년 과목에서 나가는 선만 옅게)
 */
export function toFlowEdges(
  es: Edge[],
  isPathEdge: (e: Edge) => boolean,
  active: boolean,
  start: Set<string>,
  firstYear: Set<string>,
  selected: string | null = null,
  positions?: Map<string, { x: number; y: number }>,
): FlowEdge[] {
  const fresh = start.size === 0
  return es.flatMap((e, i) => {
    const onPath = active && e.type === 'pre' && isPathEdge(e)
    // 고른 과목에서 나가는 선(다음 과목)은 옅은 파랑, 들어오는 선(선수과목)은 보라
    const outgoing = onPath && selected !== null && e.from === selected
    const isRel = e.type === 'rel'
    const fromMine = start.has(e.from)
    // 기본 화면: 들은(수강 중) 과목에서 아직 안 들은 과목으로 가는 선수 선만 그린다 (들은 과목끼리 선은 생략)
    const show = active ? onPath : fresh ? firstYear.has(e.from) && !isRel : fromMine && !isRel && !start.has(e.to)
    if (!show) return []
    // 같은 열(x가 같음)이면 위·아래 핸들로 잇는다
    const a = positions?.get(e.from)
    const b = positions?.get(e.to)
    const sameCol = a && b && a.x === b.x
    const handles = sameCol
      ? b!.y > a!.y
        ? { sourceHandle: 's-bottom', targetHandle: 't-top' }
        : { sourceHandle: 's-top', targetHandle: 't-bottom' }
      : { sourceHandle: 's-right', targetHandle: 't-left' }
    return [{
      id: `e${i}-${e.from}-${e.to}`,
      source: e.from,
      target: e.to,
      ...handles,
      type: 'default',
      animated: false,
      style: {
        stroke: outgoing ? '#f2c48a' : onPath ? '#e08a1e' : '#c9d0d9',
        strokeWidth: onPath ? 2 : 1.2,
        strokeDasharray: isRel || outgoing ? '6 4' : undefined,
        opacity: fresh ? 0.6 : 0.9,
      },
      zIndex: onPath ? 1 : 0,
    }]
  })
}
