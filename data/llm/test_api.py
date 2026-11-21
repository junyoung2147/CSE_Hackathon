"""가짜 client로 돌리는 오프라인 테스트. 실행: python -m llm.test_api (data/ 에서)"""
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

from . import api, client
from . import context as ctx

MAJOR = "심화컴퓨팅전공"


def fake(responses):
    """client.generate를 정해진 응답을 차례로 돌려주는 함수로 바꾼다. 호출 기록을 돌려준다."""
    calls = []

    def gen(system, contents, schema=None, tools=None):
        calls.append({"system": system, "contents": contents, "schema": schema})
        return responses.pop(0)

    client.generate = gen
    client.CACHE_DIR = Path(tempfile.mkdtemp())
    return calls


def test_plan_filters_codes():
    """지어낸 코드·이수 과목·현재 목표에 없는 remove는 버리고, 교육과정 밖 과목은 남기되 표시한다."""
    codes = sorted(ctx.major_codes(MAJOR))
    outside = next(c for c in ctx._db()["subjects"] if c not in ctx.major_codes(MAJOR))
    good, done, cur = codes[0], codes[1], codes[2]
    plan = api.RoadmapPlan(add=[good, "FAKE0000", outside, done, good], remove=[cur, "COMP9999"],
                           reasons=[api.Reason(code=good, reason="a"), api.Reason(code="FAKE0000", reason="b")])
    fake([NS(parsed=plan)])
    out = api.plan_roadmap([{"role": "user", "text": "AI 하고 싶어요"}], MAJOR, [cur], [done])
    assert out["add"] == [good, outside], out
    assert out["outside_curriculum"] == [outside], out
    assert out["remove"] == [cur], out
    assert out["reasons"] == {good: "a"}, out
    assert set(out["dropped"]) == {"FAKE0000", done, "COMP9999"}, out


def test_cache_hit():
    """같은 입력이면 두 번째는 호출하지 않는다."""
    calls = fake([NS(function_calls=None, text="안녕하세요")])
    conv = [{"role": "user", "text": "졸업하려면?"}]
    a = api.chat("general", conv, [], major=MAJOR)
    b = api.chat("general", conv, [], major=MAJOR)
    assert a == b == {"reply": "안녕하세요", "suggest_action": None}
    assert len(calls) == 1


def test_suggest_tool_sets_action():
    """suggest_plan_roadmap tool을 부르면 suggest_action이 채워진다."""
    call = NS(name="suggest_plan_roadmap", args={})
    calls = fake([NS(function_calls=[call], candidates=[NS(content=api._contents([{"role": "assistant", "text": "x"}])[0])]),
                  NS(function_calls=None, text="버튼을 눌러 주세요")])
    out = api.chat("general", [{"role": "user", "text": "로드맵 짜줘"}], [], major=MAJOR)
    assert out == {"reply": "버튼을 눌러 주세요", "suggest_action": "plan_roadmap"}, out
    assert len(calls) == 2


def test_prereq_first_message_and_privacy():
    """prereq 모드는 빈 대화에 첫 질문을 넣고, 코드가 아닌 completed 값은 prompt에 넣지 않는다."""
    edge = next(e for e in ctx._db()["edges"] if e["type"] == "pre")
    calls = fake([NS(text="판단: 권장")])
    out = api.chat("prereq", [], ["홍길동", "2021123456"], subject=edge["to_code"], unmet=[edge["from_code"]])
    assert out["reply"] == "판단: 권장"
    assert calls[0]["contents"][0].parts[0].text == api.FIRST_PREREQ_MSG
    assert "홍길동" not in calls[0]["system"] and "2021123456" not in calls[0]["system"]


def test_bad_input():
    """외부 입력 검증: 잘못된 role, 모르는 전공·과목은 ValueError."""
    for bad in (lambda: api.chat("general", [{"role": "system", "text": "x"}], [], major=MAJOR),
                lambda: api.plan_roadmap([], "없는전공", [], []),
                lambda: api.chat("prereq", [], [], subject="NOPE", unmet=["COMP0218"])):
        try:
            bad()
            raise AssertionError("ValueError가 나야 함")
        except ValueError:
            pass


def test_context_builds():
    """모든 전공의 prompt 데이터가 만들어지고 졸업요건이 비어 있지 않다."""
    for major in ctx._db()["curriculum"]:
        assert ctx.curriculum_text(major) and ctx.edges_text(major) is not None
        assert ctx.graduation_text(major) != "졸업요건 데이터 없음", major
    assert ctx.careers_text().count("[") == len(ctx._db()["careers"])


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
