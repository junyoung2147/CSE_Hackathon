"""가짜 client로 돌리는 오프라인 테스트. 실행: python -m llm.test_api (data/ 에서)"""
from types import SimpleNamespace as NS

from . import api, client
from . import context as ctx

MAJOR = "심화컴퓨팅전공"
REAL_GENERATE = client.generate  # fake()가 바꾸기 전 원본


def fake(responses):
    """client.generate를 정해진 응답을 차례로 돌려주는 함수로 바꾼다. 호출 기록을 돌려준다."""
    calls = []

    def gen(system, contents, schema=None, tools=None, model=None):
        calls.append({"system": system, "contents": contents, "schema": schema, "model": model})
        return responses.pop(0)

    client.generate = gen
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
    assert calls[0]["model"] == client.STRONG_MODEL  # 선수과목 상담은 판단 품질이 좋은 모델
    calls = fake([NS(function_calls=None, text="ok")])
    api.chat("general", [{"role": "user", "text": "안녕"}], [], major=MAJOR)
    assert calls[0]["model"] is None  # 일반 상담은 기본 모델(tool 호출이 많아 빠른 쪽)


def test_taking_reaches_prompt_and_counts_as_met():
    """수강 중 과목은 prompt에 들어가고, 선수과목 충족·add 제외로 처리된다 (코드가 아닌 값은 버림)."""
    edge = next(e for e in ctx._db()["edges"] if e["type"] == "pre")
    codes = sorted(ctx.major_codes(MAJOR))
    calls = fake([NS(function_calls=None, text="ok")])
    api.chat("general", [{"role": "user", "text": "안녕"}], [], major=MAJOR, taking=[codes[0], "홍길동"])
    assert ctx.codes_text([codes[0]]) in calls[0]["system"] and "홍길동" not in calls[0]["system"]
    try:  # 유일한 unmet이 수강 중이면 판단할 게 없다
        api.chat("prereq", [], [], subject=edge["to_code"], unmet=[edge["from_code"]], taking=[edge["from_code"]])
        raise AssertionError("ValueError가 나야 함")
    except ValueError:
        pass
    plan = api.RoadmapPlan(add=[codes[1], codes[2]], remove=[], reasons=[])
    fake([NS(parsed=plan)])
    out = api.plan_roadmap([{"role": "user", "text": "x"}], MAJOR, [], [], taking=[codes[1]])
    assert out["add"] == [codes[2]], out


def test_bad_input():
    """외부 입력 검증: 형식·길이·빈 general 대화·모르는 전공·과목은 ValueError."""
    user = {"role": "user", "text": "x"}
    for bad in (lambda: api.chat("general", [{"role": "system", "text": "x"}], [], major=MAJOR),
                lambda: api.chat("general", ["문자열"], [], major=MAJOR),
                lambda: api.chat("general", [], [], major=MAJOR),
                lambda: api.chat("general", [user] * (api.MAX_MESSAGES + 1), [], major=MAJOR),
                lambda: api.chat("general", [{"role": "user", "text": "가" * (api.MAX_CHARS + 1)}], [], major=MAJOR),
                lambda: api.plan_roadmap([], "없는전공", [], []),
                lambda: api.chat("prereq", [], [], subject="NOPE", unmet=["COMP0218"])):
        try:
            bad()
            raise AssertionError("ValueError가 나야 함")
        except ValueError:
            pass


def test_empty_reply_is_error():
    """빈 응답(안전 차단 등)은 정상 응답이 아니라 LLMError."""
    fake([NS(function_calls=None, text=None)])
    try:
        api.chat("general", [{"role": "user", "text": "안녕"}], [], major=MAJOR)
        raise AssertionError("LLMError가 나야 함")
    except client.LLMError:
        pass


def real_client(outcomes):
    """진짜 client.generate를 가짜 SDK에 연결한다. outcomes: 호출마다 예외(던짐) 또는 응답(돌려줌). 쓴 모델 이름 목록을 돌려준다."""
    names, slept = [], []

    def gen(model, **kw):
        names.append(model)
        out = outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out

    client.generate, client._client = REAL_GENERATE, NS(models=NS(generate_content=gen))
    client.time.sleep = slept.append
    return names, slept


def test_client_wraps_all_errors():
    """timeout 같은 SDK 밖 예외도 다른 모델로 한 번 넘어간 뒤 실패하면 LLMError로 바뀐다."""
    saved = (client.generate, client._client, client.time.sleep)
    names, _ = real_client([TimeoutError("가짜 timeout"), TimeoutError("가짜 timeout")])
    try:
        client.generate("sys", [])
        raise AssertionError("LLMError가 나야 함")
    except client.LLMError as e:
        assert "TimeoutError" in str(e) and names == [client.MODEL, client.STRONG_MODEL], (e, names)
    finally:
        client.generate, client._client, client.time.sleep = saved


def test_client_falls_back_to_other_model():
    """503이면 다른 모델로 넘어가 성공하고, used_model()이 실제로 응답한 모델을 알려 준다. 400은 넘어가지 않는다."""
    from google.genai import errors
    saved = (client.generate, client._client, client.time.sleep, client.STRONG_MODEL)
    try:
        client.STRONG_MODEL = "strong-test"
        names, slept = real_client([errors.ServerError(503, {"error": {"message": "x"}}), "응답"])
        assert client.generate("sys", []) == "응답"
        assert names == [client.MODEL, "strong-test"] and client.used_model() == "strong-test" and not slept, (names, slept)
        names, _ = real_client([errors.ServerError(503, {}), "응답"])  # 선수과목 상담은 strong이 기본이라 lite로 내려간다
        client.generate("sys", [], model="strong-test")
        assert names == ["strong-test", client.MODEL] and client.used_model() == client.MODEL, names
        names, _ = real_client([errors.ClientError(400, {"error": {"message": "잘못된 요청"}}), "응답"])
        try:
            client.generate("sys", [])
            raise AssertionError("LLMError가 나야 함")
        except client.LLMError as e:
            assert "400" in str(e) and len(names) == 1, (e, names)
        client.STRONG_MODEL = client.MODEL  # 같은 모델이면 넘어갈 곳이 없으니 5초 기다렸다가 같은 모델로 재시도
        names, slept = real_client([errors.ServerError(503, {}), "응답"])
        assert client.generate("sys", []) == "응답" and names == [client.MODEL] * 2 and slept == [5], (names, slept)
    finally:
        client.generate, client._client, client.time.sleep, client.STRONG_MODEL = saved


def test_context_builds():
    """모든 전공의 prompt 데이터가 만들어지고 졸업요건이 비어 있지 않다."""
    for major in ctx._db()["curriculum"]:
        assert ctx.curriculum_text(major) and ctx.edges_text(major) is not None
        assert ctx.graduation_text(major) != "졸업요건 데이터 없음", major
    assert ctx.careers_text().count("[") == len(ctx._db()["careers"])


def test_subject_detail_prereq_from_edges():
    """선수과목은 edges에서 만든다. or_with는 한 줄로 묶고, 간선이 없는 과목은 없다고 적는다."""
    text = ctx.subject_detail("COME0331")
    assert "선수과목 원문" not in text
    assert "프로그래밍기초(COMP0204) 또는 기초프로그래밍(COMP0206)" in text
    assert text.count("COMP0206") == 1  # 서로 대체 가능한 쌍이 두 번 적히지 않는다
    assert "등록된 선수 관계 없음" in ctx.subject_detail("EECS0442")


def test_prereq_status_per_group():
    """안 들은 선수과목은 줄마다 따로 계산한다. 다른 줄을 이수해도 안 들은 줄은 남고, 수강 중은 충족."""
    s = ctx.prereq_status("ITEC0418", ["COME0331", "COMP0206"], ["COMP0411"])
    for c in ("COMP0312", "COMP0319", "GLSO0216", "STAT0452"):
        assert c in s, s
    for c in ("COME0331", "COMP0204", "COMP0206", "COMP0411"):
        assert c not in s, s
    assert ctx.prereq_status("ITEC0418", ["ITEC0418"]) == "이수함"
    assert ctx.prereq_status("EECS0442", []) == "선수 관계 데이터 없음"
    call = NS(name="get_subject", args={"code": "ITEC0418"})
    calls = fake([NS(function_calls=[call], candidates=[NS(content=api._contents([{"role": "assistant", "text": "x"}])[0])]),
                  NS(function_calls=None, text="ok")])
    api.chat("general", [{"role": "user", "text": "뭐 들을까"}], ["COME0331"], major=MAJOR)
    result = calls[1]["contents"][-1].parts[0].function_response.response["result"]
    assert result.startswith("이 학생 기준: 안 들은 선수과목: ") and "COME0331" not in result.splitlines()[0], result
    lines = calls[0]["system"].splitlines()
    assert any("(COME0331) |" in l and l.endswith("| 이수함") for l in lines)
    assert any("| 안 들은 선수과목: " in l for l in lines)


def fake_db_loader(table):
    """backend seed처럼 타입을 바꾼 행을 돌려준다: 빈 값 None, 숫자 int, Y/N bool, id 추가 (id 순서 = CSV 순서)."""
    ints = {"credit", "lecture_hours", "practice_hours", "section_count", "capacity", "week",
            "basis_year", "grade", "credits", "theory_hours", "lab_hours"}
    bools = {"is_required", "has_syllabus"}
    out = []
    for i, r in enumerate(ctx.csv_loader(table)):
        row = {"id": i}
        for k, v in r.items():
            if k in bools:
                row[k] = ctx._yes(v)
            elif v == "":
                row[k] = None
            elif k in ints:
                row[k] = int(float(v))
            else:
                row[k] = v
        out.append(row)
    return out


def test_db_loader_same_output():
    """DB에서 읽어도 CSV와 prompt 텍스트가 한 글자도 다르지 않아야 한다."""
    def snapshot():
        majors = list(ctx._db()["curriculum"])
        return ([ctx.curriculum_text(m) + ctx.edges_text(m) + ctx.graduation_text(m) for m in sorted(majors)]
                + [ctx.subject_detail(c) for c in sorted(ctx._db()["subjects"])] + [ctx.careers_text()])
    ctx.use_loader(ctx.csv_loader)
    from_csv = snapshot()
    ctx.use_loader(fake_db_loader)
    try:
        from_db = snapshot()
    finally:
        ctx.use_loader(ctx.csv_loader)
    diff = [(a, b) for a, b in zip(from_csv, from_db) if a != b]
    assert not diff, (diff[0][0][:300], diff[0][1][:300])


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
