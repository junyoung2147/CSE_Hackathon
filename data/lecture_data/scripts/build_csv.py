"""data/raw의 강의 목록·강의계획서 JSON을 사람이 읽는 CSV로 변환한다.

사용법: python data/lecture_data/scripts/build_csv.py [--overwrite]
출력(data/lecture_data/lecture_data_csv/): subjects, sections, syllabus, syllabus_weeks, syllabus_books
subjects에는 교육과정(data/curriculum_data)에만 있는 과목도 넣어 그래프 노드 테이블로 쓴다.
subjects.csv는 사람이 직접 고치는 파일이라 이미 있으면 --overwrite 없이는 덮어쓰지 않는다.
컬럼 설명은 data/lecture_data/lecture_data_csv/README.md 참고.
"""
import argparse
import csv
import html
import json
import re
from collections import defaultdict
from pathlib import Path

from crawl_lectures import EXCLUDED_SUBJECTS

DATA = Path(__file__).resolve().parents[1]
RAW, OUT = DATA / "raw", DATA / "lecture_data_csv"
CURRICULUM = DATA.parent / "curriculum_data" / "curriculum_data_csv" / "curriculum.csv"
SOURCE_URL = "https://knuin.knu.ac.kr/public/stddm/lectPlnInqr.knu"

# 원본 필드 → CSV 컬럼
SUBJECT_COLS = {"sbjetCd": "subject_code", "sbjetNm": "subject_name", "crdit": "credit",
                "thryTime": "lecture_hours", "prctsTime": "practice_hours"}
SECTION_COLS = {"crseNo": "course_no", "sbjetCd": "subject_code", "sbjetDvnno": "section",
                "totalPrfssNm": "professor", "lssnsTimeInfo": "time_slots", "lssnsRealTimeInfo": "time_real",
                "lctrmInfo": "room", "doPlan": "language", "attlcPrscpCnt": "capacity"}
SYLLABUS_COLS = {"crseNo": "course_no", "rprsnStfnoNm": "professor", "crditSyste": "credit_system",
                 "rprsnLctreLnggeSctnm": "language", "smmryPrpsCntns": "summary", "lctreGoalCntns": "goals",
                 "tchmtRefLtrtuCntns": "textbooks_references", "taskEvltnMethdCntns": "evaluation",
                 "attlcRefMtterCntns": "notes"}
PREREQ_COLS = {"rcmmdPlrSbjetInfo": "prerequisites", "rcmmdSbstsSbjetInfo": "followups"}
WEEK_COLS = {"weekSn": "week", "lssnsGoalLrnngCntns": "content", "lssnsMethdMediaCntns": "method"}
BOOK_COLS = {"booksSn": "book_no", "booksNm": "title", "athrNm": "author", "pbsffNm": "publisher",
             "pbsffYear": "year", "isbn": "isbn", "sllbsBooksSctcd": "book_type_code"}


def clean(v):
    """HTML 태그·엔티티를 정리하고 앞뒤 공백을 지운다. 내용은 바꾸지 않는다."""
    if v is None:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", str(v), flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", "", s)).replace("\r\n", "\n")
    return s.strip()


def pick(row, cols):
    """원본 dict에서 cols 필드만 골라 CSV 컬럼명으로 바꾼다."""
    return {new: clean(row.get(old)) for old, new in cols.items()}


def load(path):
    """JSON 파일의 data 부분을 읽는다."""
    return json.loads(path.read_text(encoding="utf-8"))["data"]


def rel(path):
    """data/ 기준 상대경로 (출처 표기용)."""
    return path.relative_to(DATA).as_posix()


def write(name, rows):
    """rows를 utf-8-sig CSV로 저장하고 건수를 출력한다(엑셀에서 한글 깨짐 방지)."""
    OUT.mkdir(exist_ok=True)
    with open(OUT / name, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{name}: {len(rows)}건")


def read_lists(kind):
    """list_{year}_{smstr}_{kind}_{code}.json을 (term, code, path, row)로 차례로 돌려준다."""
    for p in sorted((RAW / "lectures").glob(f"list_*_*_{kind}_*.json")):
        _, year, smstr, _, code = p.stem.split("_", 4)
        for r in load(p):
            yield f"{year}-{smstr}", code, p, r


def build_sections():
    """학과·교양 목록을 분반 단위로 합친다. 여러 목록에 나온 분반은 listed_in에 누적(교양 목록은 '교양')."""
    sections, subj_attrs = {}, {}
    rows = [(t, c, p, r) for t, c, p, r in read_lists("dept") if r["sbjetCd"] not in EXCLUDED_SUBJECTS]
    rows += [(t, "교양", p, r) for t, c, p, r in read_lists("subj") if r["sbjetCd"] == c]
    for term, code, p, r in rows:
        key = (term, r["crseNo"])
        if key in sections:
            sections[key]["listed_in"] += ";" + code
            continue
        sections[key] = {"term": term, **pick(r, SECTION_COLS), "listed_in": code,
                         "source_url": SOURCE_URL, "source_file": rel(p)}
        subj_attrs[key] = pick(r, SUBJECT_COLS)
    return sections, subj_attrs


def merge_texts(items):
    """(문구, 분반표기) 목록을 같은 문구끼리 묶어 '문구 (2026-1 003, …)' 줄들로 만든다."""
    groups = defaultdict(list)
    for text, src in items:
        norm = re.sub(r"\s+", " ", text).strip()
        if norm:
            groups[norm].append(src)
    return "\n".join(f"{t} ({', '.join(srcs)})" for t, srcs in groups.items())


def add_curriculum_subjects(subjects):
    """교육과정에만 있는 과목을 subjects에 추가한다(계획서 값은 비움). 겹치는 과목은 학점·시수가 같은지 확인."""
    with open(CURRICULUM, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    added = 0
    for r in rows:
        attrs = {"subject_code": r["course_code"], "subject_name": r["course_name_ko"], "credit": r["credits"],
                 "lecture_hours": r["theory_hours"], "practice_hours": r["lab_hours"]}
        s = subjects.get(r["course_code"])
        if s:
            # 학교현장실습처럼 교육과정 쪽 시수가 빈 값이면 비교하지 않는다
            assert not r["lab_hours"] or all(s[k] == attrs[k] for k in ("credit", "lecture_hours", "practice_hours")),                 f"시간표·교육과정 학점·시수 불일치: {r['course_code']}"
            continue
        # 전공마다 과목명 표기가 다르면 첫 값을 쓴다
        subjects[r["course_code"]] = {**attrs, "offered_terms": "", "section_count": 0,
                                      **{c: "" for c in PREREQ_COLS.values()}}
        added += 1
    print(f"교육과정에만 있는 과목 {added}개를 subjects에 추가")
    return {r["course_code"] for r in rows}


def main():
    """raw 전체를 읽어 CSV를 만들고 자체 점검 결과를 출력한다."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--overwrite", action="store_true", help="직접 고친 subjects.csv도 새로 쓴다")
    args = ap.parse_args()
    sections, subj_attrs = build_sections()
    syllabus, weeks, books, missing = [], [], [], []
    prereq_items = defaultdict(lambda: {c: [] for c in PREREQ_COLS.values()})
    for (term, no), sec in sections.items():
        d = RAW / "syllabus" / f"{term.replace('-', '_')}_{no}"
        sec["has_syllabus"] = "Y" if (d / "Pub.json").exists() else "N"
        if sec["has_syllabus"] == "N":
            missing.append(f"{term} {no}")
            continue
        pub = load(d / "Pub.json")
        syllabus.append({"term": term, **pick(pub, SYLLABUS_COLS), "source_file": rel(d / "Pub.json")})
        for col, text in pick(pub, PREREQ_COLS).items():
            prereq_items[sec["subject_code"]][col].append((text, f"{term} {sec['section']}"))
        for name, cols, out in [("WekCntns", WEEK_COLS, weeks), ("SrchBooks", BOOK_COLS, books)]:
            if (d / f"{name}.json").exists():
                for r in load(d / f"{name}.json"):
                    out.append({"term": term, "course_no": no, **pick(r, cols), "source_file": rel(d / f"{name}.json")})

    # 과목 단위로 묶기. 과목 속성이 분반마다 다르면 교육과정 개편 등이므로 멈춘다.
    subjects = {}
    for key, attrs in subj_attrs.items():
        code, term = attrs["subject_code"], key[0]
        if code not in subjects:
            subjects[code] = {**attrs, "offered_terms": [], "section_count": 0}
        s = subjects[code]
        assert all(s[k] == v for k, v in attrs.items()), f"과목 속성 불일치: {code} {s} {attrs}"
        if term not in s["offered_terms"]:
            s["offered_terms"].append(term)
        s["section_count"] += 1
    for code, s in subjects.items():
        s["offered_terms"] = ";".join(sorted(s["offered_terms"]))
        for col in PREREQ_COLS.values():
            s[col] = merge_texts(prereq_items[code][col])
    curriculum_codes = add_curriculum_subjects(subjects)

    if (OUT / "subjects.csv").exists() and not args.overwrite:
        print("subjects.csv: 이미 있어서 건너뜀 (직접 고친 내용 보호, 새로 쓰려면 --overwrite)")
    else:
        write("subjects.csv", sorted(subjects.values(), key=lambda s: s["subject_code"]))
    write("sections.csv", list(sections.values()))
    write("syllabus.csv", syllabus)
    write("syllabus_weeks.csv", weeks)
    write("syllabus_books.csv", books)

    # 자체 점검
    keys = {(s["term"], s["course_no"]) for s in sections.values()}
    assert len(keys) == len(sections)
    assert all(s["subject_code"] in subjects for s in sections.values())
    assert curriculum_codes <= subjects.keys()
    assert all((r["term"], r["course_no"]) in keys for r in syllabus + weeks + books)
    for col in ["summary", "goals"]:
        print(f"syllabus.{col} 빈 값: {sum(1 for r in syllabus if not r[col])}/{len(syllabus)}")
    for col in PREREQ_COLS.values():
        print(f"subjects.{col} 빈 값: {sum(1 for s in subjects.values() if not s[col])}/{len(subjects)}")
    # 교양은 과목·학기당 1개만 받으므로 계획서 없는 분반이 많다. 컴퓨터학부 분반만 목록으로 출력.
    cse_missing = [m for m in missing if "교양" not in sections[tuple(m.split(" "))]["listed_in"]]
    print(f"계획서 없는 분반: {len(missing)} (컴퓨터학부 목록 분반 {len(cse_missing)}건: {cse_missing})")


if __name__ == "__main__":
    main()
