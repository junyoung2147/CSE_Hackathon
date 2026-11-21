"""data/ 아래 CSV를 읽어 prompt에 넣을 텍스트를 만든다."""
import csv
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]
LECTURE = DATA / "lecture_data/lecture_data_csv"
CURR = DATA / "curriculum_data"
WEEK_CHARS = 120  # 주차 내용이 길어서 자름


def _read(path):
    """CSV를 dict 목록으로 읽는다 (BOM 허용)."""
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


@lru_cache
def _db():
    """모든 CSV를 한 번만 읽어 둔다."""
    subjects = {r["subject_code"]: r for r in _read(LECTURE / "subjects.csv")}
    sec_code = {(r["term"], r["course_no"]): r["subject_code"] for r in _read(LECTURE / "sections.csv")}
    syllabus = {}  # subject_code -> 개요가 있는 첫 계획서
    for r in _read(LECTURE / "syllabus.csv"):
        code = sec_code.get((r["term"], r["course_no"]))
        if code and r["summary"] and code not in syllabus:
            syllabus[code] = r
    weeks = {}
    for r in _read(LECTURE / "syllabus_weeks.csv"):
        weeks.setdefault((r["term"], r["course_no"]), []).append(r)
    curriculum = {}
    for r in _read(CURR / "curriculum.csv"):
        curriculum.setdefault(r["major_name"], []).append(r)
    return {
        "subjects": subjects,
        "syllabus": syllabus,
        "weeks": weeks,
        "curriculum": curriculum,
        "edges": _read(DATA / "graph_data/edges.csv"),
        "careers": _read(DATA / "career_data/careers.csv"),
        "career_subjects": _read(DATA / "career_data/career_subjects.csv"),
        "credits": _read(CURR / "out/graduation_credits.csv"),
        "rules": _read(CURR / "out/graduation_rules.csv"),
    }


def name(code):
    """과목 코드 → 과목명 (없으면 코드 그대로)."""
    s = _db()["subjects"].get(code)
    return s["subject_name"] if s else code


def major_codes(major):
    """전공 교육과정에 있는 과목 코드 집합. 모르는 전공이면 ValueError."""
    rows = _db()["curriculum"].get(major)
    if not rows:
        raise ValueError(f"알 수 없는 전공: {major}")
    return {r["course_code"] for r in rows}


def codes_text(codes):
    """코드 목록을 '코드 과목명' 줄로."""
    return "\n".join(f"- {c} {name(c)}" for c in codes) or "(없음)"


def curriculum_text(major):
    """전공 교육과정 과목 목록."""
    major_codes(major)
    return "\n".join(
        f"- {r['course_code']} {r['course_name_ko']} | {r['grade']}학년 {r['semester']} | "
        f"{r['category']} | {'필수' if r['is_required'] == 'Y' else '선택'} | {r['credits']}학점"
        for r in _db()["curriculum"][major]
    )


def careers_text():
    """진로별 목표 과목 (참고 데이터)."""
    out = []
    for c in _db()["careers"]:
        codes = [r["subject_code"] for r in _db()["career_subjects"] if r["career_id"] == c["career_id"]]
        out.append(f"[{c['career_id']}] {c['name']}: {c['description']}\n" + codes_text(codes))
    return "\n\n".join(out)


def edges_text(major):
    """전공 과목끼리의 선수 관계. or_with가 있으면 대체 가능 과목."""
    codes = major_codes(major)
    lines = []
    for e in _db()["edges"]:
        if e["from_code"] in codes and e["to_code"] in codes:
            alt = f" (또는 {e['or_with']})" if e["or_with"] else ""
            lines.append(f"- {e['from_code']}{alt} → {e['to_code']} [{e['type']}]")
    return "\n".join(lines)


def subject_detail(code):
    """과목 하나의 계획서 개요·목표·주차와 선수과목 원문. 계획서가 없으면 그렇게 적는다."""
    db = _db()
    s = db["subjects"].get(code)
    if not s:
        return f"{code}: 과목 데이터 없음"
    out = [f"## {code} {s['subject_name']} ({s['credit']}학점)", f"선수과목 원문: {s['prerequisites'] or '없음'}"]
    syl = db["syllabus"].get(code)
    if not syl:
        out.append("강의계획서 없음")
        return "\n".join(out)
    out += [f"개요: {syl['summary']}", f"목표: {syl['goals'] or '없음'}", "주차:"]
    for w in db["weeks"].get((syl["term"], syl["course_no"]), []):
        out.append(f"  {w['week']}주: {' '.join(w['content'].split())[:WEEK_CHARS]}")
    return "\n".join(out)


def graduation_text(major):
    """전공의 졸업 학점과 학점 외 요건."""
    db = _db()
    rows = [f"- [{r['from']}~{r['to']}학번 {r['track']}] {r['category']}: {r['credits_min']}~{r['credits_max']}학점"
            for r in db["credits"] if r["major_name"] == major]
    rows += [f"- [{r['from']}~{r['to']}학번 {r['track']}] {r['item']}: {r['requirement']}"
             for r in db["rules"] if r["major_name"] == major]
    return "\n".join(rows) or "졸업요건 데이터 없음"
