"""상담 채팅과 로드맵 짜기. 백엔드는 chat()과 plan_roadmap()을 라우트로 감싸면 된다.
개인정보 규칙: LLM에는 과목 코드, 대화 내용만 보낸다. 이름·학번 같은 필드는 받지도 않는다.
"""
from pathlib import Path

from google.genai import types
from pydantic import BaseModel

from . import client
from . import context as ctx

PROMPTS = Path(__file__).resolve().parent / "prompts"
MAX_TOOL_ROUNDS = 5  # 한 턴 최악 대기 시간을 줄이려고 낮춤
MAX_MESSAGES = 40  # 대화 20턴(user+assistant)
MAX_CHARS = 2000  # 메시지 하나의 최대 글자 수
FIRST_PREREQ_MSG = "안 들은 선수과목마다 첫 판단을 알려 주세요."
PLAN_MSG = "지금까지의 대화를 바탕으로 목표 과목을 정해 주세요."


class Reason(BaseModel):
    """add/remove 한 과목 하나의 이유."""
    code: str
    reason: str


class RoadmapPlan(BaseModel):
    """plan_roadmap의 LLM 응답 스키마."""
    add: list[str]
    remove: list[str]
    reasons: list[Reason]


def _prompt(name, **kw):
    """prompts/<name>.md를 읽어 {변수}를 채운다."""
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8").format(**kw)


def _check_conversation(conversation):
    """[{role: user|assistant, text: str}] 형식과 길이 상한을 확인한다 (외부 입력, 무료 한도 보호)."""
    if not isinstance(conversation, list):
        raise ValueError("conversation은 목록이어야 합니다")
    if len(conversation) > MAX_MESSAGES:
        raise ValueError(f"대화가 너무 깁니다 (최대 {MAX_MESSAGES}개 메시지). 새 대화로 시작해 주세요")
    for m in conversation:
        if (not isinstance(m, dict) or m.get("role") not in ("user", "assistant")
                or not isinstance(m.get("text"), str)):
            raise ValueError("conversation 항목은 {role: user|assistant, text: str} 이어야 합니다")
        if len(m["text"]) > MAX_CHARS:
            raise ValueError(f"메시지가 너무 깁니다 (최대 {MAX_CHARS}자)")
    return [{"role": m["role"], "text": m["text"]} for m in conversation]


def _contents(conversation):
    """대화를 Gemini Content 목록으로 바꾼다."""
    return [
        types.Content(role="model" if m["role"] == "assistant" else "user",
                      parts=[types.Part.from_text(text=m["text"])])
        for m in conversation
    ]


def _reply(resp):
    """응답 텍스트. 비어 있으면(안전 차단 등) 오류로 처리해 빈 말풍선이 저장·표시되지 않게 한다."""
    if not (resp.text or "").strip():
        raise client.LLMError("Gemini가 빈 응답을 돌려줬습니다")
    return resp.text


def _known(codes):
    """subjects에 있는 코드만 남긴다. 코드가 아닌 문자열이 prompt로 새지 않게 한다."""
    return sorted({c for c in codes if c in ctx._db()["subjects"]})


def _run_tools(system, conversation, funcs):
    """tool 호출을 직접 처리하며 최종 답을 받는다. suggest_plan_roadmap 호출 여부도 돌려준다."""
    contents = _contents(conversation)
    suggest = False
    for _ in range(MAX_TOOL_ROUNDS):
        resp = client.generate(system, contents, tools=list(funcs.values()))
        calls = resp.function_calls or []
        if not calls:
            return {"reply": _reply(resp), "suggest_action": "plan_roadmap" if suggest else None}
        contents.append(resp.candidates[0].content)  # thought signature 보존
        parts = []
        for call in calls:
            suggest |= call.name == "suggest_plan_roadmap"
            try:
                result = funcs[call.name](**(call.args or {}))
            except (KeyError, TypeError):
                result = f"잘못된 tool 호출: {call.name}"
            parts.append(types.Part.from_function_response(name=call.name, response={"result": result}))
        contents.append(types.Content(role="user", parts=parts))
    raise client.LLMError("tool 호출이 너무 많습니다")


def chat(mode, conversation, completed, major=None, targets=(), subject=None, unmet=(), taking=()):
    """상담 채팅 한 턴. 반환: {reply, suggest_action: "plan_roadmap"|None}

    mode="general": major, targets 사용. 로드맵 요청이면 suggest_action이 채워진다.
    mode="prereq": subject(대상 과목), unmet(안 들은 선수과목) 사용. 대화가 비어 있으면 첫 판단을 만든다.
    taking: 이번 학기 수강 중인 과목 코드. 선수과목은 이수와 같게 충족으로 본다.
    """
    conversation = _check_conversation(conversation)
    completed, taking = _known(completed), _known(taking)

    if mode == "general":
        if not conversation:
            raise ValueError("general 모드는 학생 메시지가 하나 이상 있어야 합니다")

        def get_subject(code: str) -> str:
            """과목 코드로 선수과목(정리된 선수 관계), 이 학생 기준 안 들은 선수과목, 강의계획서 개요·목표·주차를 조회한다."""
            if code not in ctx._db()["subjects"]:
                return ctx.subject_detail(code)
            return f"이 학생 기준: {ctx.prereq_status(code, completed, taking)}\n" + ctx.subject_detail(code)

        def get_graduation() -> str:
            """학생 전공의 졸업 학점과 졸업 요건을 조회한다."""
            return ctx.graduation_text(major)

        def suggest_plan_roadmap() -> str:
            """학생이 로드맵(목표 과목 목록)을 새로 만들거나 고쳐 달라고 분명히 요청할 때만 호출한다. 다음 학기에 뭘 들을지 묻는 질문에는 호출하지 않는다. 화면에 로드맵 짜기 버튼이 뜬다."""
            return "버튼을 띄웠습니다. 학생에게 버튼을 누르라고 안내하세요."

        system = _prompt("general_chat", major=major, completed=ctx.codes_text(completed),
                         taking=ctx.codes_text(taking), targets=ctx.codes_text(_known(targets)),
                         careers=ctx.careers_text(completed, taking),  # 안 들은 선수과목은 코드가 계산해 넣는다
                         curriculum=ctx.curriculum_text(major, completed, taking))
        funcs = {f.__name__: f for f in (get_subject, get_graduation, suggest_plan_roadmap)}
        return _run_tools(system, conversation, funcs)

    if mode == "prereq":
        if subject not in ctx._db()["subjects"]:
            raise ValueError(f"알 수 없는 과목: {subject}")
        unmet = [c for c in _known(unmet) if c not in taking]  # 수강 중이면 충족
        if not unmet:
            raise ValueError("unmet(안 들은 선수과목)이 비어 있습니다")
        system = _prompt("prereq_chat", target=ctx.subject_detail(subject),
                         prereqs="\n\n".join(ctx.subject_detail(c) for c in unmet),
                         completed=ctx.codes_text(completed), taking=ctx.codes_text(taking))
        turns = conversation or [{"role": "user", "text": FIRST_PREREQ_MSG}]
        return {"reply": _reply(client.generate(system, _contents(turns), model=client.STRONG_MODEL)), "suggest_action": None}

    raise ValueError(f"알 수 없는 mode: {mode}")


def plan_roadmap(conversation, major, current_targets, completed, taking=()):
    """대화를 보고 목표 과목을 새로 짜거나 고친다. 진로는 LLM이 대화에서 판단한다.

    반환: {add, remove, reasons: {code: 이유}, outside_curriculum: add 중 전공 교육과정 밖 코드, dropped: 검증에서 버린 코드}
    """
    conversation = _check_conversation(conversation)
    allowed = ctx.major_codes(major)
    current, done, now = _known(current_targets), _known(completed), _known(taking)
    system = _prompt("plan_roadmap", major=major, targets=ctx.codes_text(current),
                     completed=ctx.codes_text(done), taking=ctx.codes_text(now), careers=ctx.careers_text(),
                     curriculum=ctx.curriculum_text(major), edges=ctx.edges_text(major))
    turns = conversation + [{"role": "user", "text": PLAN_MSG}]

    parsed = client.generate(system, _contents(turns), schema=RoadmapPlan).parsed
    if parsed is None:
        raise client.LLMError("로드맵 응답을 해석하지 못했습니다")
    return validate_plan(parsed.model_dump(), allowed, set(current), set(done) | set(now))  # 수강 중도 새로 추가하지 않음


def validate_plan(raw, allowed, current, done):
    """LLM 응답에서 실제 과목 코드만 남기고, 교육과정 밖 과목은 표시만 한다. 경로 계산은 이 결과로 기존 edges 로직이 한다."""
    known = ctx._db()["subjects"]
    add = list(dict.fromkeys(c for c in raw["add"] if c in known and c not in current and c not in done))
    remove = list(dict.fromkeys(c for c in raw["remove"] if c in current))
    kept = set(add) | set(remove)
    return {
        "add": add,
        "remove": remove,
        "reasons": {r["code"]: r["reason"] for r in raw["reasons"] if r["code"] in kept},
        "outside_curriculum": [c for c in add if c not in allowed],  # 화면에 "교육과정 밖 과목" 안내
        "dropped": sorted((set(raw["add"]) | set(raw["remove"])) - kept),
    }
