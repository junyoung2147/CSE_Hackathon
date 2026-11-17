"""everytime.py 오프라인 테스트 (네트워크 호출 없음). 실행: python data/timetable/test_everytime.py"""
from pathlib import Path

import everytime as et

FIXTURE = (Path(__file__).parent / "fixtures" / "friend_2026_2.xml").read_text(encoding="utf-8")
OTHER = {
    "FakeId2026s1": '<response><table year="2026" semester="1" status="-2" identifier="FakeId2026s1"/></response>',
    "FakeId2025w": '<response><table year="2025" semester="겨울" status="1" identifier="FakeId2025w"/></response>',
}


class FakeSession:
    """식별자별로 저장된 XML을 돌려주는 가짜 세션."""

    def __init__(self):
        self.calls = []

    def post(self, url, data, headers, timeout):
        """요청을 기록하고 fixture 응답을 돌려준다."""
        self.calls.append(data)
        text = FIXTURE if data["identifier"] == "FakeId2026s2" else OTHER.get(data["identifier"], "<response>-1</response>")
        return type("Res", (), {"text": text, "raise_for_status": lambda self: None})()


def test_parse_identifier():
    """URL·식별자 입력은 받고, 다른 형식은 거부한다."""
    assert et.parse_identifier("https://everytime.kr/@Cw55NsbaXQOdl2DKx31N") == "Cw55NsbaXQOdl2DKx31N"
    assert et.parse_identifier(" everytime.kr/@abc123/ ") == "abc123"
    assert et.parse_identifier("abc123") == "abc123"
    for bad in ["https://evil.com/@abc", "abc/../x", "", "https://everytime.kr/@ab-c"]:
        try:
            et.parse_identifier(bad)
            raise AssertionError(bad)
        except ValueError:
            pass


def test_fetch_all():
    """첫 응답의 학기 목록을 따라 모든 학기를 모으고, 비공개·빈 학기는 skipped로 뺀다."""
    s = FakeSession()
    out = et.fetch_all_timetables("https://everytime.kr/@FakeId2026s2", delay=0, session=s)
    assert [c["friendInfo"] for c in s.calls] == ["true", "false", "false"]
    assert len(out["semesters"]) == 1
    sem = out["semesters"][0]
    assert (sem["year"], sem["semester"], len(sem["courses"])) == (2026, "2", 7)
    assert sem["courses"][2] == {"course_no": "COMP0324-004", "subject_code": "COMP0324",
                                 "name": "인공지능", "professor": "정든솔", "credit": 3}
    assert out["skipped"] == [{"year": 2026, "semester": "1", "reason": "비공개"},
                              {"year": 2025, "semester": "겨울", "reason": "과목 없음"}]


def test_missing_table():
    """없는 식별자는 ValueError."""
    try:
        et.fetch_all_timetables("nope", delay=0, session=FakeSession())
        raise AssertionError
    except ValueError:
        pass


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
