"""LLM 상담·로드맵 생성 백엔드 라우터 (`data/llm/` 연동).

제공 엔드포인트:
- POST /api/chat            : general / prereq 상담 (요청·응답 캐싱 및 로그 저장)
- POST /api/roadmap/plan    : 대화 기반 목표 과목 추천 미리보기 (저장 안 함)
- GET  /api/roadmap/targets : 저장된 목표 과목 목록 조회
- PUT  /api/roadmap/targets : 사용자가 적용한 목표 과목 덮어쓰기 저장
- GET  /api/chat/history    : 사용자별 LLM 상담 기록 조회
"""
from contextlib import contextmanager
import hashlib
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from models import (
    Career,
    CareerSubject,
    CourseEdge,
    Curriculum,
    GraduationCredit,
    GraduationRule,
    LLMLog,
    Section,
    Subject,
    Syllabus,
    SyllabusWeek,
    UserCompletedCourse,
    UserRoadmap,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
if str(DATA_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_DIR))

try:
    from llm import api as llm_api, client as llm_client, context as llm_context
    _LLM_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - data/llm 머지 전 방어
    llm_api = None
    llm_client = None
    llm_context = None
    _LLM_IMPORT_ERROR = exc

router = APIRouter()

_DB_TABLE_MODELS = {
    "subjects": Subject,
    "sections": Section,
    "syllabus": Syllabus,
    "syllabus_weeks": SyllabusWeek,
    "curriculum": Curriculum,
    "course_edges": CourseEdge,
    "careers": Career,
    "career_subjects": CareerSubject,
    "graduation_credits": GraduationCredit,
    "graduation_rules": GraduationRule,
}


@contextmanager
def _short_db_session():
    """외부 LLM 호출 전후로 DB 커넥션 점유를 최소화하기 위한 단기 세션."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _db_table_loader(table_name: str) -> list[dict]:
    """BACKEND.md 6절 규격: DB에서 PK 순으로 읽고, 비어 있으면 csv_loader로 폴백."""
    model = _DB_TABLE_MODELS.get(table_name)
    if model is None:
        return llm_context.csv_loader(table_name)

    with _short_db_session() as db:
        mapper = sa_inspect(model)
        pk_cols = list(mapper.primary_key)
        rows = db.query(model).order_by(*pk_cols).all()
        if not rows:
            return llm_context.csv_loader(table_name)

        result = []
        for row in rows:
            item = {}
            for col in mapper.columns:
                attr_name = mapper.get_property_by_column(col).key
                item[col.name] = getattr(row, attr_name)
            result.append(item)
        return result


if llm_context is not None:
    llm_context.use_loader(_db_table_loader)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    user_id: str = Field(default="demo", min_length=1, max_length=64)
    mode: Literal["general", "prereq"]
    conversation: list[ChatMessage] = Field(default_factory=list, max_length=50)
    major: str | None = Field(default=None, max_length=100)
    subject: str | None = Field(default=None, max_length=32)
    targets: list[str] | None = None
    completed: list[str] | None = None
    taking: list[str] | None = None
    

class RoadmapPlanRequest(BaseModel):
    user_id: str = Field(default="demo", min_length=1, max_length=64)
    major: str = Field(..., min_length=1, max_length=100)
    conversation: list[ChatMessage] = Field(default_factory=list, max_length=50)
    current_targets: list[str] | None = None
    completed: list[str] | None = None
    taking: list[str] | None = None
    

class RoadmapTargetsRequest(BaseModel):
    user_id: str = Field(default="demo", min_length=1, max_length=64)
    targets: list[str] = Field(default_factory=list)
    source: Literal["preset", "llm"] = "llm"


def _ensure_llm_ready() -> None:
    if llm_api is None or llm_client is None:
        raise HTTPException(
            status_code=503,
            detail=f"LLM 모듈(data/llm)을 불러올 수 없습니다: {_LLM_IMPORT_ERROR}",
        )


def _safe_json_loads(raw: str | None) -> tuple[bool, Any]:
    if not raw:
        return False, None
    try:
        return True, json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return False, None


def _parse_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in re.split(r"[;,]", raw) if item.strip()]

def _normalize_codes(codes: list[str] | None) -> list[str]:
    if not codes:
        return []
    return list(dict.fromkeys(c.strip() for c in codes if c and c.strip()))
    
def _is_edge_satisfied(edge: CourseEdge, completed_codes: set[str]) -> bool:
    if edge.from_code in completed_codes:
        return True
    if edge.or_with:
        if any(code in completed_codes for code in _parse_list(edge.or_with)):
            return True
    return False


def _resolve_completed(
    db: Session,
    user_id: str,
    override: list[str] | None,
) -> list[str]:
    if override is not None:
        return [c.strip() for c in override if c and c.strip()]
    rows = (
        db.query(UserCompletedCourse.subject_code)
        .filter(UserCompletedCourse.user_id == user_id)
        .all()
    )
    return [r[0] for r in rows]


def _resolve_targets(
    db: Session,
    user_id: str,
    override: list[str] | None,
) -> list[str]:
    if override is not None:
        return [c.strip() for c in override if c and c.strip()]
    rows = (
        db.query(UserRoadmap.subject_code)
        .filter(UserRoadmap.user_id == user_id)
        .all()
    )
    return [r[0] for r in rows]


def _compute_unmet_prereqs(
    db: Session,
    subject_code: str,
    completed_codes: set[str],
) -> list[str]:
    edges = (
        db.query(CourseEdge)
        .filter(CourseEdge.to_code == subject_code, CourseEdge.type == "pre")
        .order_by(CourseEdge.id)
        .all()
    )
    unmet: list[str] = []
    seen: set[str] = set()
    for edge in edges:
        if not _is_edge_satisfied(edge, completed_codes) and edge.from_code not in seen:
            unmet.append(edge.from_code)
            seen.add(edge.from_code)
    return unmet


def _make_request_key(payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _save_llm_log(
    user_id: str,
    kind: str,
    subject_code: str | None,
    request_key: str,
    cache_input: dict,
    result: Any,
    model_name: str,
) -> None:
    try:
        with _short_db_session() as db:
            db.add(
                LLMLog(
                    user_id=user_id,
                    kind=kind,
                    subject_code=subject_code,
                    request_key=request_key,
                    request=json.dumps(cache_input, ensure_ascii=False),
                    response=json.dumps(result, ensure_ascii=False),
                    model=model_name,
                )
            )
            db.commit()
    except SQLAlchemyError:
        logger.exception("Failed to persist LLMLog (user_id=%s, kind=%s)", user_id, kind)


@router.post("/api/chat")
def post_chat(payload: ChatRequest):
    _ensure_llm_ready()

    user_id = payload.user_id.strip()
    subject_code = payload.subject.strip() if payload.subject else None
    conversation = [{"role": m.role, "text": m.text} for m in payload.conversation]

    if payload.mode == "prereq" and not subject_code:
        raise HTTPException(status_code=400, detail="prereq 모드에는 subject가 필요합니다.")

    model_name = getattr(llm_client, "MODEL", "unknown")

    # 1단계: 짧은 DB 세션으로 상태 조회 및 캐시 확인
    with _short_db_session() as db:
        completed = _resolve_completed(db, user_id, payload.completed)
        targets = _resolve_targets(db, user_id, payload.targets)
        taking = _normalize_codes(payload.taking)
        unmet = (
            _compute_unmet_prereqs(db, subject_code, set(completed) | set(taking))
            if payload.mode == "prereq" and subject_code
            else []
        )

        cache_input = {
            "kind": payload.mode,
            "model": model_name,
            "major": payload.major,
            "subject": subject_code,
            "completed": sorted(set(completed)),
            "targets": sorted(set(targets)),
            "taking": sorted(set(taking)),
            "unmet": sorted(set(unmet)),
            "conversation": conversation,
        }
        request_key = _make_request_key(cache_input)

        cached = (
            db.query(LLMLog)
            .filter(LLMLog.request_key == request_key)
            .order_by(LLMLog.id.desc())
            .first()
        )
        if cached is not None:
            ok, parsed = _safe_json_loads(cached.response)
            if ok:
                # 타 사용자의 캐시를 재사용한 경우에도 현재 사용자 이력에 남김
                if cached.user_id != user_id:
                    db.add(
                        LLMLog(
                            user_id=user_id,
                            kind=payload.mode,
                            subject_code=subject_code if payload.mode == "prereq" else None,
                            request_key=request_key,
                            request=json.dumps(cache_input, ensure_ascii=False),
                            response=cached.response,
                            model=model_name,
                        )
                    )
                    try:
                        db.commit()
                    except SQLAlchemyError:
                        db.rollback()
                        logger.exception("Failed to mirror cached LLMLog for user_id=%s", user_id)
                return parsed

    # 2단계: DB 세션을 점유하지 않은 상태로 외부 LLM 호출
    llm_error_cls = getattr(llm_client, "LLMError", RuntimeError)
    try:
        result = llm_api.chat(
            mode=payload.mode,
            conversation=conversation,
            completed=completed,
            major=payload.major,
            targets=targets,
            subject=subject_code,
            taking=taking,
            unmet=unmet,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except llm_error_cls as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("Unexpected error during llm_api.chat")
        raise HTTPException(status_code=502, detail="LLM 응답 생성 중 오류가 발생했습니다.")

    # 3단계: 결과 로그 저장
    _save_llm_log(
        user_id=user_id,
        kind=payload.mode,
        subject_code=subject_code if payload.mode == "prereq" else None,
        request_key=request_key,
        cache_input=cache_input,
        result=result,
        model_name=model_name,
    )
    return result


@router.post("/api/roadmap/plan")
def post_roadmap_plan(payload: RoadmapPlanRequest):
    _ensure_llm_ready()

    user_id = payload.user_id.strip()
    conversation = [{"role": m.role, "text": m.text} for m in payload.conversation]
    model_name = getattr(llm_client, "MODEL", "unknown")

    # 1단계: 짧은 DB 세션으로 상태 조회 및 캐시 확인
    with _short_db_session() as db:
        completed = _resolve_completed(db, user_id, payload.completed)
        current_targets = _resolve_targets(db, user_id, payload.current_targets)
        taking = _normalize_codes(payload.taking)
        
        cache_input = {
            "kind": "plan",
            "model": model_name,
            "major": payload.major,
            "subject": None,
            "completed": sorted(set(completed)),
            "targets": sorted(set(current_targets)),
            "taking": sorted(set(taking)),
            "unmet": [],
            "conversation": conversation,
        }
        request_key = _make_request_key(cache_input)

        cached = (
            db.query(LLMLog)
            .filter(LLMLog.request_key == request_key)
            .order_by(LLMLog.id.desc())
            .first()
        )
        if cached is not None:
            ok, parsed = _safe_json_loads(cached.response)
            if ok:
                if cached.user_id != user_id:
                    db.add(
                        LLMLog(
                            user_id=user_id,
                            kind="plan",
                            subject_code=None,
                            request_key=request_key,
                            request=json.dumps(cache_input, ensure_ascii=False),
                            response=cached.response,
                            model=model_name,
                        )
                    )
                    try:
                        db.commit()
                    except SQLAlchemyError:
                        db.rollback()
                        logger.exception("Failed to mirror cached plan LLMLog for user_id=%s", user_id)
                return parsed

    # 2단계: DB 세션을 점유하지 않은 상태로 외부 LLM 호출
    llm_error_cls = getattr(llm_client, "LLMError", RuntimeError)
    try:
        result = llm_api.plan_roadmap(
            conversation=conversation,
            major=payload.major,
            current_targets=current_targets,
            taking=taking,
            completed=completed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except llm_error_cls as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("Unexpected error during llm_api.plan_roadmap")
        raise HTTPException(status_code=502, detail="로드맵 추천 생성 중 오류가 발생했습니다.")

    # 3단계: 결과 로그 저장 (미리보기 엔드포인트이므로 UserRoadmap은 덮어쓰지 않음)
    _save_llm_log(
        user_id=user_id,
        kind="plan",
        subject_code=None,
        request_key=request_key,
        cache_input=cache_input,
        result=result,
        model_name=model_name,
    )
    return result


@router.get("/api/roadmap/targets")
def get_roadmap_targets(
    user_id: str = Query(..., min_length=1, max_length=64, description="사용자 식별 ID"),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(UserRoadmap)
        .filter(UserRoadmap.user_id == user_id)
        .order_by(UserRoadmap.id)
        .all()
    )
    return {
        "user_id": user_id,
        "targets": [r.subject_code for r in rows],
        "items": [{"subject_code": r.subject_code, "source": r.source} for r in rows],
    }


@router.put("/api/roadmap/targets")
def put_roadmap_targets(
    payload: RoadmapTargetsRequest,
    db: Session = Depends(get_db),
):
    user_id = payload.user_id.strip()
    unique_targets = list(dict.fromkeys(c.strip() for c in payload.targets if c and c.strip()))
    if unique_targets:
        valid_codes = {
            r[0]
            for r in db.query(Subject.subject_code)
            .filter(Subject.subject_code.in_(unique_targets))
            .all()
        }
        unique_targets = [c for c in unique_targets if c in valid_codes]

    try:
        db.query(UserRoadmap).filter(UserRoadmap.user_id == user_id).delete()
        for code in unique_targets:
            db.add(
                UserRoadmap(
                    user_id=user_id,
                    subject_code=code,
                    source=payload.source,
                )
            )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="목표 과목 저장 중 오류가 발생했습니다.")

    return {
        "user_id": user_id,
        "targets": unique_targets,
        "source": payload.source,
    }


@router.get("/api/chat/history")
def get_chat_history(
    user_id: str = Query(..., min_length=1, max_length=64, description="사용자 식별 ID"),
    kind: Literal["general", "prereq", "plan"] | None = Query(None),
    subject_code: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(LLMLog).filter(LLMLog.user_id == user_id)
    if kind:
        query = query.filter(LLMLog.kind == kind)
    if subject_code:
        query = query.filter(LLMLog.subject_code == subject_code.strip())

    rows = query.order_by(LLMLog.id.desc()).limit(limit).all()
    logs = []
    for r in rows:
        req_ok, req_data = _safe_json_loads(r.request)
        res_ok, res_data = _safe_json_loads(r.response)
        logs.append({
            "id": r.id,
            "kind": r.kind,
            "subject_code": r.subject_code,
            "model": r.model,
            "request": req_data if req_ok else None,
            "response": res_data if res_ok else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "user_id": user_id,
        "total": len(logs),
        "logs": logs,
    }
