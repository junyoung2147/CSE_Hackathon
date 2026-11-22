"""LLM 상담·로드맵 생성 백엔드 라우터 (`data/llm/` 연동).

제공 엔드포인트:
- POST /api/chat              : general / prereq 상담 (요청·응답 캐싱 및 로그 저장)
- POST /api/roadmap/plan      : 대화 기반 목표 과목 추천 미리보기 (저장 안 함)
- GET  /api/roadmap/targets   : 저장된 목표 과목 목록 조회
- PUT  /api/roadmap/targets   : 사용자가 적용한 목표 과목 덮어쓰기 저장
- GET  /api/chat/history      : 사용자별 LLM 상담 기록 조회
"""
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import inspect as sa_inspect
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


def _db_table_loader(table_name: str) -> list[dict]:
    """BACKEND.md 6절 규격: DB에서 PK 순으로 읽고, 비어 있으면 csv_loader로 폴백."""
    model = _DB_TABLE_MODELS.get(table_name)
    if model is None:
        return llm_context.csv_loader(table_name)

    db = SessionLocal()
    try:
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
    finally:
        db.close()


if llm_context is not None:
    llm_context.use_loader(_db_table_loader)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ChatRequest(BaseModel):
    user_id: str = Field(default="demo")
    mode: Literal["general", "prereq"]
    conversation: list[ChatMessage] = Field(default_factory=list)
    major: str | None = None
    subject: str | None = None
    targets: list[str] | None = None
    completed: list[str] | None = None


class RoadmapPlanRequest(BaseModel):
    user_id: str = Field(default="demo")
    major: str
    conversation: list[ChatMessage] = Field(default_factory=list)
    current_targets: list[str] | None = None
    completed: list[str] | None = None


class RoadmapTargetsRequest(BaseModel):
    user_id: str = Field(default="demo")
    targets: list[str] = Field(default_factory=list)
    source: Literal["preset", "llm"] = "llm"


def _ensure_llm_ready() -> None:
    if llm_api is None or llm_client is None:
        raise HTTPException(
            status_code=503,
            detail=f"LLM 모듈(data/llm)을 불러올 수 없습니다: {_LLM_IMPORT_ERROR}",
        )


def _parse_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in re.split(r"[;,]", raw) if item.strip()]


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


@router.post("/api/chat")
def post_chat(payload: ChatRequest, db: Session = Depends(get_db)):
    _ensure_llm_ready()

    completed = _resolve_completed(db, payload.user_id, payload.completed)
    targets = _resolve_targets(db, payload.user_id, payload.targets)
    conversation = [{"role": m.role, "text": m.text} for m in payload.conversation]

    unmet: list[str] = []
    if payload.mode == "prereq":
        if not payload.subject:
            raise HTTPException(status_code=400, detail="prereq 모드에는 subject가 필요합니다.")
        unmet = _compute_unmet_prereqs(db, payload.subject.strip(), set(completed))

    model_name = getattr(llm_client, "MODEL", "unknown")
    cache_input = {
        "kind": payload.mode,
        "model": model_name,
        "major": payload.major,
        "subject": payload.subject,
        "completed": sorted(set(completed)),
        "targets": sorted(set(targets)),
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
        return json.loads(cached.response)

    try:
        result = llm_api.chat(
            mode=payload.mode,
            conversation=conversation,
            completed=completed,
            major=payload.major,
            targets=targets,
            subject=payload.subject,
            unmet=unmet,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except llm_client.LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    db.add(
        LLMLog(
            user_id=payload.user_id,
            kind=payload.mode,
            subject_code=payload.subject if payload.mode == "prereq" else None,
            request_key=request_key,
            request=json.dumps(cache_input, ensure_ascii=False),
            response=json.dumps(result, ensure_ascii=False),
            model=model_name,
        )
    )
    db.commit()
    return result


@router.post("/api/roadmap/plan")
def post_roadmap_plan(payload: RoadmapPlanRequest, db: Session = Depends(get_db)):
    _ensure_llm_ready()

    completed = _resolve_completed(db, payload.user_id, payload.completed)
    current_targets = _resolve_targets(db, payload.user_id, payload.current_targets)
    conversation = [{"role": m.role, "text": m.text} for m in payload.conversation]

    model_name = getattr(llm_client, "MODEL", "unknown")
    cache_input = {
        "kind": "plan",
        "model": model_name,
        "major": payload.major,
        "subject": None,
        "completed": sorted(set(completed)),
        "targets": sorted(set(current_targets)),
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
        return json.loads(cached.response)

    try:
        result = llm_api.plan_roadmap(
            conversation=conversation,
            major=payload.major,
            current_targets=current_targets,
            completed=completed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except llm_client.LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    db.add(
        LLMLog(
            user_id=payload.user_id,
            kind="plan",
            subject_code=None,
            request_key=request_key,
            request=json.dumps(cache_input, ensure_ascii=False),
            response=json.dumps(result, ensure_ascii=False),
            model=model_name,
        )
    )
    db.commit()
    return result


@router.get("/api/roadmap/targets")
def get_roadmap_targets(
    user_id: str = Query(..., description="사용자 식별 ID"),
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
    unique_targets = list(dict.fromkeys(c.strip() for c in payload.targets if c and c.strip()))
    if unique_targets:
        valid_codes = {
            r[0]
            for r in db.query(Subject.subject_code)
            .filter(Subject.subject_code.in_(unique_targets))
            .all()
        }
        unique_targets = [c for c in unique_targets if c in valid_codes]

    db.query(UserRoadmap).filter(UserRoadmap.user_id == payload.user_id).delete()
    for code in unique_targets:
        db.add(
            UserRoadmap(
                user_id=payload.user_id,
                subject_code=code,
                source=payload.source,
            )
        )
    db.commit()
    return {
        "user_id": payload.user_id,
        "targets": unique_targets,
        "source": payload.source,
    }


@router.get("/api/chat/history")
def get_chat_history(
    user_id: str = Query(..., description="사용자 식별 ID"),
    kind: Literal["general", "prereq", "plan"] | None = Query(None),
    subject_code: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(LLMLog).filter(LLMLog.user_id == user_id)
    if kind:
        query = query.filter(LLMLog.kind == kind)
    if subject_code:
        query = query.filter(LLMLog.subject_code == subject_code)

    rows = query.order_by(LLMLog.id.desc()).limit(limit).all()
    return {
        "user_id": user_id,
        "total": len(rows),
        "logs": [
            {
                "id": r.id,
                "kind": r.kind,
                "subject_code": r.subject_code,
                "model": r.model,
                "request": json.loads(r.request),
                "response": json.loads(r.response),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
