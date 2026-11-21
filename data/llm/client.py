"""Gemini 호출, 응답 캐시, 429 재시도를 맡는 얇은 래퍼."""
import hashlib
import json
import os
import time
from pathlib import Path

from google import genai
from google.genai import errors, types

HERE = Path(__file__).resolve().parent
CACHE_DIR = HERE / "cache"
ENV_FILE = HERE.parent / ".env"  # data/.env
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")  # 3.6/3.8-flash는 11/21 테스트 때 503(수요 과다)

_client = None


class LLMError(RuntimeError):
    """LLM 호출 실패(한도 초과 등). 백엔드에서 503으로 바꿔 응답하면 된다."""


def _load_env():
    """data/.env의 KEY=VALUE를 읽는다. 이미 설정된 환경변수가 우선."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))


def get_client():
    """genai.Client를 한 번만 만든다. 키는 GOOGLE_API_KEY(또는 GEMINI_API_KEY) 환경변수에서 SDK가 읽는다."""
    global _client
    if _client is None:
        _load_env()
        if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
            raise LLMError("GOOGLE_API_KEY 또는 GEMINI_API_KEY가 없습니다")
        _client = genai.Client(http_options=types.HttpOptions(timeout=60_000))  # ms, 무한 대기 방지
    return _client


def generate(system, contents, schema=None, tools=None):
    """generate_content를 한 번 호출한다. 429·503이면 5초 뒤 한 번만 다시 시도."""
    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=tools,
        # tool 실행은 api.py에서 직접 해서 신호(suggest_plan_roadmap)를 잡는다
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        response_mime_type="application/json" if schema else None,
        response_schema=schema,
    )
    for attempt in range(2):
        try:
            return get_client().models.generate_content(model=MODEL, contents=contents, config=config)
        except errors.APIError as e:
            if getattr(e, "code", None) in (429, 503) and attempt == 0:
                time.sleep(5)
                continue
            raise LLMError(f"Gemini 호출 실패 ({getattr(e, 'code', '?')})") from e


def cached(key_obj, fn):
    """key_obj(JSON 직렬화 가능)의 해시로 결과를 캐시한다. 같은 입력이면 다시 호출하지 않는다."""
    raw = json.dumps([MODEL, key_obj], ensure_ascii=False, sort_keys=True)
    path = CACHE_DIR / f"{hashlib.sha256(raw.encode()).hexdigest()}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    result = fn()
    CACHE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result
