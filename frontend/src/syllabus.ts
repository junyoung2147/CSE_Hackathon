// 강의계획서 CSV는 크기가 커서(약 0.8MB) 과목을 처음 열 때만 불러온다 (동적 import).
import Papa from 'papaparse'
import sectionsCsv from '../../data/lecture_data/lecture_data_csv/sections.csv?raw'
import syllabusCsv from '../../data/lecture_data/lecture_data_csv/syllabus.csv?raw'
import weeksCsv from '../../data/lecture_data/lecture_data_csv/syllabus_weeks.csv?raw'

function parse<T>(text: string): T[] {
  return Papa.parse<T>(text.replace(/^﻿/, ''), { header: true, skipEmptyLines: true }).data
}

type SectionRow = {
  term: string
  course_no: string
  subject_code: string
  professor: string
  time_real: string
  room: string
  language: string
  has_syllabus: string
}
type SyllabusRow = { term: string; course_no: string; summary: string; goals: string; evaluation: string; textbooks_references: string }
type WeekRow = { term: string; course_no: string; week: string; content: string }

const sections = parse<SectionRow>(sectionsCsv)
const syllabusByKey = new Map(parse<SyllabusRow>(syllabusCsv).map((r) => [`${r.term}|${r.course_no}`, r]))
const weeksByKey = new Map<string, { week: number; content: string }[]>()
for (const w of parse<WeekRow>(weeksCsv)) {
  const k = `${w.term}|${w.course_no}`
  weeksByKey.set(k, [...(weeksByKey.get(k) ?? []), { week: Number(w.week), content: w.content }])
}

export type LocalSection = {
  term: string
  courseNo: string
  professor: string
  time: string
  room: string
  language: string
  summary: string | null
  goals: string | null
  evaluation: string | null
  textbooks: string | null
  weeks: { week: number; content: string }[]
}

/** 과목의 모든 분반. 계획서가 있는 최신 학기 분반이 맨 앞에 온다. */
export function sectionsOf(code: string): LocalSection[] {
  return sections
    .filter((s) => s.subject_code === code)
    .map((s) => {
      const k = `${s.term}|${s.course_no}`
      const syl = syllabusByKey.get(k)
      return {
        term: s.term,
        courseNo: s.course_no,
        professor: s.professor,
        time: s.time_real,
        room: s.room?.replace(/\s+/g, ' '),
        language: s.language,
        summary: syl?.summary || null,
        goals: syl?.goals || null,
        evaluation: syl?.evaluation || null,
        textbooks: syl?.textbooks_references || null,
        weeks: (weeksByKey.get(k) ?? []).sort((a, b) => a.week - b.week),
      }
    })
    .sort((a, b) => Number(!!b.summary) - Number(!!a.summary) || b.term.localeCompare(a.term))
}
