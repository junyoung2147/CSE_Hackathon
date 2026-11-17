"""에브리타임 공유 시간표 링크에서 학기별 수강 과목을 가져온다.

공유 페이지는 빈 HTML이고, 브라우저가 아래 API를 호출해 XML로 시간표를 받는다(로그인 불필요).
비공식 API라 에브리타임이 구조를 바꾸면 깨질 수 있다.
응답 XML은 저장하지 않으며, 응답에 담긴 실명(<user name>)은 읽지 않는다.

실행: python data/timetable/everytime.py https://everytime.kr/@<식별자>
"""
import json
import re
import sys
import time
import xml.etree.ElementTree as ET

import requests

API_URL = "https://api.everytime.kr/find/timetable/table/friend"
HEADERS = {"User-Agent": "Mozilla/5.0", "Origin": "https://everytime.kr", "Referer": "https://everytime.kr/"}
LINK_RE = re.compile(r"(?:https?://)?(?:www\.)?everytime\.kr/@([A-Za-z0-9]+)/?|@?([A-Za-z0-9]+)")
STATUS_REASON = {"-1": "시간표 없음", "-2": "비공개"}


def parse_identifier(link):
    """공유 URL 또는 식별자에서 식별자만 꺼낸다. 형식이 다르면 ValueError."""
    m = LINK_RE.fullmatch(link.strip())
    if not m:
        raise ValueError(f"에브리타임 시간표 링크 형식이 아닙니다: {link!r}")
    return m.group(1) or m.group(2)


def fetch_xml(session, identifier, friend_info):
    """시간표 API를 한 번 호출해 XML 루트를 돌려준다. friend_info=True면 학기 목록이 함께 온다."""
    res = session.post(API_URL, data={"identifier": identifier, "friendInfo": str(friend_info).lower()},
                       headers=HEADERS, timeout=15)
    res.raise_for_status()
    root = ET.fromstring(res.text)
    if root.find("table") is None:
        # 없는 식별자면 <response>-1</response>
        raise ValueError(f"존재하지 않는 시간표입니다: {identifier}")
    return root


def _value(subject, tag):
    """<tag value="..."/>의 value를 꺼낸다. 없으면 빈 문자열."""
    el = subject.find(tag)
    return (el.get("value") or "").strip() if el is not None else ""


def parse_table(root):
    """XML 루트에서 (year, semester, status, courses)를 꺼낸다."""
    table = root.find("table")
    courses = []
    for s in table.findall("subject"):
        course_no = _value(s, "internal")
        credit = _value(s, "credit")
        courses.append({
            "course_no": course_no,
            "name": _value(s, "name"),
            "professor": _value(s, "professor"),
            "credit": int(credit) if credit.isdigit() else None,
        })
    return int(table.get("year")), table.get("semester"), table.get("status"), courses


def parse_primary_tables(root):
    """학기 목록(<primaryTables>)을 [(year, semester, identifier)]로 꺼낸다."""
    return [(int(t.get("year")), t.get("semester"), t.get("identifier"))
            for t in root.iter("primaryTable")]


def fetch_all_timetables(link, delay=1.0, session=None):
    """공유 링크 하나로 그 사용자의 모든 학기 시간표를 가져온다."""
    session = session or requests.Session()
    identifier = parse_identifier(link)
    first = fetch_xml(session, identifier, True)
    tables = parse_primary_tables(first)
    if not any(tid == identifier for _, _, tid in tables):
        tables.insert(0, (None, None, identifier))  # 대표 시간표가 아닌 링크도 포함

    semesters, skipped = [], []
    for _, _, tid in tables:
        if tid == identifier:
            root = first
        else:
            time.sleep(delay)
            root = fetch_xml(session, tid, False)
        year, semester, status, courses = parse_table(root)
        if status in STATUS_REASON:
            skipped.append({"year": year, "semester": semester, "reason": STATUS_REASON[status]})
        elif not courses:
            skipped.append({"year": year, "semester": semester, "reason": "과목 없음"})
        else:
            semesters.append({"year": year, "semester": semester, "courses": courses})
    return {"semesters": semesters, "skipped": skipped}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("사용법: python everytime.py <에브리타임 시간표 링크>")
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(fetch_all_timetables(sys.argv[1]), ensure_ascii=False, indent=2))
