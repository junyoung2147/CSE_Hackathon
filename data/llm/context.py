"""data/ 아래 데이터를 읽어 prompt에 넣을 텍스트를 만든다.

데이터 출처는 load_table 하나로만 바뀐다. 기본은 CSV, 백엔드는 use_loader()로 DB 함수를 꽂는다.
테이블 이름은 backend/models.py의 __tablename__, 컬럼 이름은 CSV 헤더와 같다.
loader 규칙: 행을 id 순서(= CSV 순서)로 돌려준다. 순서가 바뀌면 같은 데이터라도 prompt 텍스트가 달라진다.
"""
import csv
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]
LECTURE = DATA / "lecture_data/lecture_data_csv"
CURR = DATA / "curriculum_data"
WEEK_CHARS = 120  # 주차 내용이 길어서 자름

# 테이블 이름 → CSV 경로. 뒤의 4개는 아직 백엔드 테이블이 없음 (README 제안 참고)
TABLES = {
    "subjects": LECTURE / "subjects.csv",
    "sections": LECTURE / "sections.csv",
    "syllabus": LECTURE / "syllabus.csv",
    "syllabus_weeks": LECTURE / "syllabus_weeks.csv",
    "curriculum": CURR / "curriculum.csv",
    "course_edges": DATA / "graph_data/edges.csv",
    "careers": DATA / "career_data/careers.csv",
    "career_subjects": DATA / "career_data/career_subjects.csv",
    "graduation_credits": CURR / "out/graduation_credits.csv",
    "graduation_rules": CURR / "out/graduation_rules.csv",
}


def csv_loader(table):
    """CSV를 dict 목록으로 읽는다 (BOM 허용)."""
    with open(TABLES[table], encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


load_table = csv_loader


def use_loader(fn):
    """데이터 출처를 바꾼다. fn(table_name) -> [dict]. 읽어 둔 데이터도 비운다."""
    global load_table
    load_table = fn
    _db.cache_clear()


def _yes(v):
    """CSV 'Y'/'N'과 DB True/False를 똑같이 판정한다 (backend seed의 _to_bool과 같은 기준)."""
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


def _rows(table):
    """load_table 결과에서 None을 ''로 바꾼다. DB의 빈 값(None)이 'None'으로 찍히지 않게."""
    return [{k: "" if v is None else v for k, v in r.items()} for r in load_table(table)]


@lru_cache
def _db():
    """모든 테이블을 한 번만 읽어 둔다."""
    subjects = {r["subject_code"]: r for r in _rows("subjects")}
    sec_code = {(r["term"], r["course_no"]): r["subject_code"] for r in _rows("sections")}
    syllabus = {}  # subject_code -> 계획서 하나 (개요 있는 것 우선, 없으면 목표만 있는 것)
    for r in sorted(_rows("syllabus"), key=lambda r: (r["term"], r["course_no"])):  # DB는 순서 보장 안 됨
        code = sec_code.get((r["term"], r["course_no"]))
        if not code or not (r["summary"] or r["goals"]):
            continue
        cur = syllabus.get(code)
        if cur is None or (not cur["summary"] and r["summary"]):
            syllabus[code] = r
    weeks = {}
    for r in sorted(_rows("syllabus_weeks"), key=lambda r: int(r["week"] or 0)):
        weeks.setdefault((r["term"], r["course_no"]), []).append(r)
    curriculum = {}
    for r in _rows("curriculum"):
        curriculum.setdefault(r["major_name"], []).append(r)
    return {
        "subjects": subjects,
        "syllabus": syllabus,
        "weeks": weeks,
        "curriculum": curriculum,
        "edges": _rows("course_edges"),
        "careers": _rows("careers"),
        "career_subjects": _rows("career_subjects"),
        "credits": _rows("graduation_credits"),
        "rules": _rows("graduation_rules"),
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
    """코드 목록을 '과목명(코드)' 줄로. 모델이 이 형식을 따라 쓰므로 프롬프트 규칙과 맞춘다."""
    return "\n".join(f"- {name(c)}({c})" for c in codes) or "(없음)"


def curriculum_text(major, completed=None, taking=()):
    """전공 교육과정 과목 목록. completed를 주면 줄 끝에 이수 상태·안 들은 선수과목을 붙인다."""
    major_codes(major)
    return "\n".join(
        f"- {r['course_name_ko']}({r['course_code']}) | {r['grade']}학년 {r['semester']} | "
        f"{r['category']} | {'필수' if _yes(r['is_required']) else '선택'} | {r['credits']}학점"
        + ("" if completed is None else f" | {prereq_status(r['course_code'], completed, taking)}")
        for r in _db()["curriculum"][major]
    )


def careers_text(completed=None, taking=()):
    """진로별 목표 과목 (참고 데이터). completed를 주면 과목마다 이수 상태·안 들은 선수과목을 붙인다."""
    out = []
    for c in _db()["careers"]:
        codes = [r["subject_code"] for r in _db()["career_subjects"] if r["career_id"] == c["career_id"]]
        lines = (codes_text(codes) if completed is None else
                 "\n".join(f"- {name(x)}({x}) | {prereq_status(x, completed, taking)}" for x in codes))
        out.append(f"[{c['career_id']}] {c['name']}: {c['description']}\n" + lines)
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


def prereq_groups(code):
    """edges.csv의 pre 간선을 줄(서로 대체 가능한 과목 묶음) 목록으로. 줄마다 하나씩 필요하다."""
    groups = {}  # 서로 대체 가능한 과목 묶음은 한 번만 (A or B, B or A가 따로 적힌 경우)
    for e in _db()["edges"]:
        if e["to_code"] == code and e["type"] == "pre":
            alts = [e["from_code"], *[c for c in (e["or_with"] or "").split(";") if c]]
            groups.setdefault(frozenset(alts), alts)
    return list(groups.values())


def prereq_text(code):
    """선수과목 줄. or_with는 '또는'으로 묶는다. 간선이 없으면 없다고 적는다."""
    lines = ["- " + " 또는 ".join(f"{name(c)}({c})" for c in alts) for alts in prereq_groups(code)]
    return "\n".join(lines) or "- 등록된 선수 관계 없음"


def prereq_status(code, completed, taking=()):
    """이수 상태와 안 들은 선수과목을 코드가 계산한다 (작은 모델이 줄 단위 판단을 틀려서). 수강 중은 이수로 본다."""
    if code in completed:
        return "이수함"
    if code in taking:
        return "수강 중"
    groups = prereq_groups(code)
    if not groups:
        return "선수 관계 데이터 없음"
    met = set(completed) | set(taking)
    unmet = [alts for alts in groups if not met & set(alts)]
    if not unmet:
        return "선수과목 모두 들음"
    return "안 들은 선수과목: " + ", ".join(" 또는 ".join(f"{name(c)}({c})" for c in alts) for alts in unmet)


def subject_detail(code):
    """과목 하나의 선수과목(edges 기준)과 계획서 개요·목표·주차. 계획서가 없으면 그렇게 적는다."""
    db = _db()
    s = db["subjects"].get(code)
    if not s:
        return f"{code}: 과목 데이터 없음"
    syl = db["syllabus"].get(code)
    out = [f"## {s['subject_name']}({code}) · {s['credit']}학점", "선수과목 (줄마다 하나씩 필요함. 한 줄 안의 '또는'은 그중 하나만 들으면 그 줄이 충족됨):", prereq_text(code)]
    if not syl:
        out.append("강의계획서 없음")
        return "\n".join(out)
    out += [f"개요: {syl['summary'] or '없음'}", f"목표: {syl['goals'] or '없음'}", "회차:"]
    for w in db["weeks"].get((syl["term"], syl["course_no"]), []):
        out.append(f"  {w['week']}주: {' '.join(w['content'].split())[:WEEK_CHARS]}")
    return "\n".join(out)


def _scope(r):
    """졸업요건 행의 적용 범위 '[2018~2022학번 다중전공 트랙] '. 빈 값은 생략."""
    parts = [f"{r['from']}~{r['to']}학번"] if r["from"] or r["to"] else []
    parts += [str(r["track"])] if r["track"] else []
    return f"[{' '.join(parts)}] " if parts else ""


def graduation_text(major):
    """전공의 졸업 학점과 학점 외 요건."""
    db = _db()
    rows = [f"- {_scope(r)}{r['category']}: {r['credits_min']}~{r['credits_max']}학점"
            for r in db["credits"] if r["major_name"] == major]
    rows += [f"- {_scope(r)}{r['item']}: {r['requirement']}"
             for r in db["rules"] if r["major_name"] == major]
    return "\n".join(rows) or "졸업요건 데이터 없음"
