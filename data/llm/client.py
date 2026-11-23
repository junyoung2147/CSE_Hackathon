"""Gemini 호출과 재시도를 맡는 얇은 래퍼. 응답 저장은 하지 않는다 (백엔드 몫)."""
import os
import threading
import time
from pathlib import Path

from google import genai
from google.genai import errors, types

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE.parent / ".env"  # data/.env


def _load_env():
    """data/.env의 KEY=VALUE를 읽는다. 이미 설정된 환경변수가 우선."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))


_load_env()  # MODEL보다 먼저 읽어야 .env의 GEMINI_MODEL이 적용됨
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")  # 기본: 일반 상담·로드맵 (11/21 테스트 때 일반 상담 38~74초)
# 판단 품질이 중요한 선수과목 상담용. 3.6-flash는 11/21 테스트 때 503이었고, 실패하면 MODEL로 넘어간다
STRONG_MODEL = os.environ.get("GEMINI_STRONG_MODEL", "gemini-3.6-flash")
TIMEOUT_MS = 40_000  # 모델 한 번당. 실패하면 다른 모델로 넘어가므로 무한 대기만 막으면 된다
RETRY_CODES = (429, 503, 504)  # 서비스 쪽 사정(한도·수요 과다·시간 초과). 400 같은 요청 오류는 모델을 바꿔도 같다

_client = None
_last = threading.local()  # 스레드마다 마지막으로 응답한 모델 (백엔드가 로그에 쓰려는 용도)


class LLMError(RuntimeError):
    """LLM 호출 실패(한도 초과, timeout, 빈 응답 등). 백엔드에서 503으로 바꿔 응답하면 된다."""


def get_client():
    """genai.Client를 한 번만 만든다. 키는 GOOGLE_API_KEY(또는 GEMINI_API_KEY) 환경변수에서 SDK가 읽는다."""
    global _client
    if _client is None:
        if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
            raise LLMError("GOOGLE_API_KEY 또는 GEMINI_API_KEY가 없습니다")
        _client = genai.Client(http_options=types.HttpOptions(timeout=TIMEOUT_MS))  # 무한 대기 방지
    return _client


def used_model():
    """이 스레드에서 마지막으로 응답한 모델 이름 (아직 없으면 None). 예비 모델로 넘어갔는지 로그에 남길 때 쓴다."""
    return getattr(_last, "model", None)


def generate(system, contents, schema=None, tools=None, model=None):
    """generate_content를 호출한다. model을 안 주면 MODEL.

    429·503·504·timeout·연결 오류면 다른 모델(MODEL ↔ STRONG_MODEL)로 한 번 넘어간다.
    두 모델이 같게 설정돼 있으면 5초 뒤 같은 모델로 한 번 다시 시도한다. 400 같은 요청 오류는 바로 실패.
    """
    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=tools,
        # tool 실행은 api.py에서 직접 해서 신호(suggest_plan_roadmap)를 잡는다
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        response_mime_type="application/json" if schema else None,
        response_schema=schema,
    )
    client = get_client()
    primary = model or MODEL
    other = STRONG_MODEL if primary == MODEL else MODEL
    order = [primary, other] if other != primary else [primary, primary]
    for attempt, name in enumerate(order):
        try:
            resp = client.models.generate_content(model=name, contents=contents, config=config)
            _last.model = name
            return resp
        except errors.APIError as e:
            err, reason, retry = e, getattr(e, "code", "?"), getattr(e, "code", None) in RETRY_CODES
        except Exception as e:  # timeout·연결 오류는 SDK가 APIError로 감싸지 않음 (httpx2 예외)
            err, reason, retry = e, type(e).__name__, True
        if not retry or attempt == 1:
            raise LLMError(f"Gemini 호출 실패 ({reason})") from err
        if other == primary:
            time.sleep(5)  # 넘어갈 다른 모델이 없을 때만 잠깐 기다린다
