"""에브리타임 공유 시간표 링크 → 학기별 수강 과목 + 수업 시간.

브라우저에서 에브리타임 API를 직접 부르면 CORS에 막혀서, 백엔드가 대신 호출한다.
실제 호출·파싱은 data/timetable/everytime.py(준영님 코드)를 그대로 쓰고,
여기서는 시간표 격자를 그리기 위한 수업 시간(<time><data .../>)만 추가로 꺼낸다.

GET /api/everytime?link=https://everytime.kr/@xxxx
"""
import sys
import time
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException, Query

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data" / "timetable"))
import everytime as et  # noqa: E402

router = APIRouter()


def _times(root):
    """course_no → [{day(0=월), start, end(분 단위, 0시 기준), place}]"""
    out = {}
    for s in root.find("table").findall("subject"):
        course_no = et._value(s, "internal")
        slots = []
        for d in s.iter("data"):
            # 에브리타임은 5분 단위 칸 번호를 쓴다 (108 → 540분 = 09:00)
            slots.append({
                "day": int(d.get("day")),
                "start": int(d.get("starttime")) * 5,
                "end": int(d.get("endtime")) * 5,
                "place": d.get("place") or "",
            })
        out[course_no] = slots
    return out


def fetch_with_times(link, delay=1.0, session=None):
    session = session or requests.Session()
    identifier = et.parse_identifier(link)
    first = et.fetch_xml(session, identifier, True)
    tables = et.parse_primary_tables(first)
    if not any(tid == identifier for _, _, tid in tables):
        tables.insert(0, (None, None, identifier))

    semesters, skipped = [], []
    for _, _, tid in tables:
        if tid == identifier:
            root = first
        else:
            time.sleep(delay)
            root = et.fetch_xml(session, tid, False)
        year, semester, status, courses = et.parse_table(root)
        if status in et.STATUS_REASON:
            skipped.append({"year": year, "semester": semester, "reason": et.STATUS_REASON[status]})
            continue
        if not courses:
            skipped.append({"year": year, "semester": semester, "reason": "과목 없음"})
            continue
        times = _times(root)
        for c in courses:
            c["times"] = times.get(c["course_no"], [])
            c["subject_code"] = c["course_no"].split("-")[0] if c["course_no"] else ""
        semesters.append({"year": year, "semester": semester, "courses": courses})

    def order(s):
        sem = str(s["semester"])
        return (s["year"] or 0, {"1": 1, "여름": 2, "2": 3, "겨울": 4}.get(sem, 0))

    semesters.sort(key=order)
    return {"semesters": semesters, "skipped": skipped}


@router.get("/api/everytime")
def get_everytime(link: str = Query(..., description="에브리타임 시간표 공유 링크")):
    try:
        return fetch_with_times(link)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"에브리타임 응답 실패: {e}")
