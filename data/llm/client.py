"""Gemini 호출과 재시도를 맡는 얇은 래퍼. 응답 저장은 하지 않는다 (백엔드 몫)."""
import os
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
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")  # 3.6/3.8-flash는 11/21 테스트 때 503(수요 과다)

_client = None


class LLMError(RuntimeError):
    """LLM 호출 실패(한도 초과, timeout, 빈 응답 등). 백엔드에서 503으로 바꿔 응답하면 된다."""


def get_client():
    """genai.Client를 한 번만 만든다. 키는 GOOGLE_API_KEY(또는 GEMINI_API_KEY) 환경변수에서 SDK가 읽는다."""
    global _client
    if _client is None:
        if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
            raise LLMError("GOOGLE_API_KEY 또는 GEMINI_API_KEY가 없습니다")
        _client = genai.Client(http_options=types.HttpOptions(timeout=60_000))  # ms, 무한 대기 방지
    return _client


def generate(system, contents, schema=None, tools=None):
    """generate_content를 한 번 호출한다. 429·503·timeout·연결 오류면 5초 뒤 한 번만 다시 시도."""
    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=tools,
        # tool 실행은 api.py에서 직접 해서 신호(suggest_plan_roadmap)를 잡는다
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        response_mime_type="application/json" if schema else None,
        response_schema=schema,
    )
    client = get_client()
    for attempt in range(2):
        try:
            return client.models.generate_content(model=MODEL, contents=contents, config=config)
        except errors.APIError as e:
            err, reason, retry = e, getattr(e, "code", "?"), getattr(e, "code", None) in (429, 503)
        except Exception as e:  # timeout·연결 오류는 SDK가 APIError로 감싸지 않음 (httpx2 예외)
            err, reason, retry = e, type(e).__name__, True
        if not retry or attempt == 1:
            raise LLMError(f"Gemini 호출 실패 ({reason})") from err
        time.sleep(5)
