from collections import defaultdict
from contextlib import asynccontextmanager
import os
import re

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import tuple_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from everytime_router import router as everytime_router
from llm_router import router as llm_router
from models import (
    Career,
    CareerSubject,
    CourseEdge,
    Curriculum,
    Section,
    Subject,
    Syllabus,
    SyllabusBook,
    SyllabusWeek,
    UserCompletedCourse,
    UserRoadmap,
    UserTimetable,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="KNU CSE Hackathon Backend",
    version="0.4.1",
    lifespan=lifespan,
)

# ALLOWED_ORIGINS 환경변수에 콤마 구분 도메인 지정 가능 (미지정 시 개발용 전체 허용 + credentials 비활성화)
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*").strip()
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()] or ["*"]
_allow_credentials = "*" not in _allowed_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(everytime_router)
app.include_router(llm_router)


class CompleteToggleRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    subject_code: str = Field(..., min_length=1, max_length=32)
    completed: bool
    term: str | None = None
    source: str = "manual"


class TimetableSaveRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    term: str = Field(..., min_length=1, max_length=32)
    course_nos: list[str] = Field(default_factory=list)


def _parse_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in re.split(r"[;,]", raw) if item.strip()]


def _is_edge_satisfied(edge: CourseEdge, completed_codes: set[str]) -> bool:
    if edge.from_code in completed_codes:
        return True
    if edge.or_with:
        alt_codes = _parse_list(edge.or_with)
        if any(code in completed_codes for code in alt_codes):
            return True
    return False


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/careers")
def get_careers(db: Session = Depends(get_db)):
    careers = db.query(Career).order_by(Career.career_id).all()
    career_subjects = db.query(CareerSubject).order_by(CareerSubject.id).all()

    targets_by_career: dict[str, list[str]] = defaultdict(list)
    seen_by_career: dict[str, set[str]] = defaultdict(set)
    for cs in career_subjects:
        code = cs.subject_code.strip() if cs.subject_code else ""
        if code and code not in seen_by_career[cs.career_id]:
            seen_by_career[cs.career_id].add(code)
            targets_by_career[cs.career_id].append(code)

    return [
        {
            "id": c.career_id,
            "name": c.name,
            "description": c.description or "",
            "targets": targets_by_career.get(c.career_id, []),
        }
        for c in careers
    ]
    
@app.get("/api/roadmap")
def get_roadmap(
    user_id: str = Query(..., min_length=1, max_length=64, description="사용자 식별 ID"),
    db: Session = Depends(get_db),
):
    subjects = db.query(Subject).order_by(Subject.subject_code).all()
    edges = db.query(CourseEdge).order_by(CourseEdge.id).all()
    completed_rows = (
        db.query(UserCompletedCourse)
        .filter(UserCompletedCourse.user_id == user_id)
        .all()
    )
    target_rows = (
        db.query(UserRoadmap)
        .filter(UserRoadmap.user_id == user_id)
        .order_by(UserRoadmap.id)
        .all()
    )
    completed_codes = {row.subject_code for row in completed_rows}
    target_codes = [row.subject_code for row in target_rows]

    prereq_edges_by_target: dict[str, list[CourseEdge]] = defaultdict(list)
    for e in edges:
        if e.type == "pre":
            prereq_edges_by_target[e.to_code].append(e)

    nodes = []
    for s in subjects:
        is_completed = s.subject_code in completed_codes
        target_edges = prereq_edges_by_target.get(s.subject_code, [])
        if is_completed:
            status = "completed"
        elif not target_edges or all(_is_edge_satisfied(e, completed_codes) for e in target_edges):
            status = "available"
        else:
            status = "locked"

        nodes.append({
            "subject_code": s.subject_code,
            "subject_name": s.subject_name,
            "credit": s.credit,
            "offered_terms": _parse_list(s.offered_terms),
            "prerequisites": _parse_list(s.prerequisites),
            "followups": _parse_list(s.followups),
            "is_completed": is_completed,
            "status": status,
            "light": "green" if is_completed else "default",
        })

    edge_list = [
        {
            "from_code": e.from_code,
            "from_name": e.from_name,
            "to_code": e.to_code,
            "to_name": e.to_name,
            "type": e.type,
            "or_with": _parse_list(e.or_with),
        }
        for e in edges
    ]

    return {
        "user_id": user_id,
        "total": len(nodes),
        "subjects": nodes,
        "edges": edge_list,
        "targets": target_codes,
    }


@app.get("/api/curriculum")
def get_curriculum(
    major_name: str | None = Query(None, description="전공명 (예: 심화컴퓨팅전공)"),
    grade: int | None = Query(None, description="학년"),
    semester: str | None = Query(None, description="학기 (예: 1학기)"),
    db: Session = Depends(get_db),
):
    query = db.query(Curriculum)
    if major_name:
        query = query.filter(Curriculum.major_name == major_name)
    if grade is not None:
        query = query.filter(Curriculum.grade == grade)
    if semester:
        query = query.filter(Curriculum.semester == semester)

    rows = query.order_by(
        Curriculum.major_name,
        Curriculum.grade,
        Curriculum.semester,
        Curriculum.course_code,
    ).all()
    return {
        "total": len(rows),
        "items": [
            {
                "major_name": r.major_name,
                "basis_year": r.basis_year,
                "grade": r.grade,
                "semester": r.semester,
                "category": r.category,
                "course_code": r.course_code,
                "course_name_ko": r.course_name_ko,
                "credits": r.credits,
                "theory_hours": r.theory_hours,
                "lab_hours": r.lab_hours,
                "is_required": r.is_required,
                "note": r.note,
            }
            for r in rows
        ],
    }


@app.post("/api/roadmap/complete")
def toggle_completed_subject(
    payload: CompleteToggleRequest,
    db: Session = Depends(get_db),
):
    user_id = payload.user_id.strip()
    subject_code = payload.subject_code.strip()
    if not user_id or not subject_code:
        raise HTTPException(status_code=400, detail="user_id and subject_code are required")

    subject = (
        db.query(Subject)
        .filter(Subject.subject_code == subject_code)
        .first()
    )
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    existing = (
        db.query(UserCompletedCourse)
        .filter(
            UserCompletedCourse.user_id == user_id,
            UserCompletedCourse.subject_code == subject_code,
        )
        .first()
    )

    try:
        if payload.completed:
            if not existing:
                db.add(
                    UserCompletedCourse(
                        user_id=user_id,
                        subject_code=subject_code,
                        term=payload.term,
                        source=payload.source,
                    )
                )
                db.commit()
        else:
            if existing:
                db.delete(existing)
                db.commit()
    except IntegrityError:
        # 동시 요청으로 이미 삽입된 경우 멱등하게 처리
        db.rollback()
        if not payload.completed:
            raise HTTPException(status_code=409, detail="Database conflict while updating completion")
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update completed subject")

    return {
        "user_id": user_id,
        "subject_code": subject_code,
        "completed": payload.completed,
    }


@app.get("/api/subjects/{subject_code}")
def get_subject_detail(subject_code: str, db: Session = Depends(get_db)):
    subject_code = subject_code.strip()
    subject = (
        db.query(Subject)
        .filter(Subject.subject_code == subject_code)
        .first()
    )
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    sections = (
        db.query(Section)
        .filter(Section.subject_code == subject_code)
        .order_by(Section.term.desc(), Section.course_no)
        .all()
    )

    # N+1 방지: 분반 키 목록으로 Syllabus / SyllabusWeek / SyllabusBook 일괄 조회
    section_keys = [(sec.term, sec.course_no) for sec in sections]
    syllabus_map: dict[tuple[str, str], Syllabus] = {}
    weeks_map: dict[tuple[str, str], list[SyllabusWeek]] = defaultdict(list)
    books_map: dict[tuple[str, str], list[SyllabusBook]] = defaultdict(list)

    if section_keys:
        syllabi = (
            db.query(Syllabus)
            .filter(tuple_(Syllabus.term, Syllabus.course_no).in_(section_keys))
            .all()
        )
        for syl in syllabi:
            syllabus_map[(syl.term, syl.course_no)] = syl

        weeks = (
            db.query(SyllabusWeek)
            .filter(tuple_(SyllabusWeek.term, SyllabusWeek.course_no).in_(section_keys))
            .order_by(SyllabusWeek.week)
            .all()
        )
        for w in weeks:
            weeks_map[(w.term, w.course_no)].append(w)

        books = (
            db.query(SyllabusBook)
            .filter(tuple_(SyllabusBook.term, SyllabusBook.course_no).in_(section_keys))
            .order_by(SyllabusBook.book_no)
            .all()
        )
        for b in books:
            books_map[(b.term, b.course_no)].append(b)

    section_details = []
    for sec in sections:
        key = (sec.term, sec.course_no)
        syl = syllabus_map.get(key)
        sec_weeks = weeks_map.get(key, [])
        sec_books = books_map.get(key, [])

        section_details.append({
            "term": sec.term,
            "course_no": sec.course_no,
            "section": sec.section,
            "professor": sec.professor,
            "time_slots": sec.time_slots,
            "time_real": sec.time_real,
            "room": sec.room,
            "language": sec.language,
            "capacity": sec.capacity,
            "syllabus": {
                "summary": syl.summary,
                "goals": syl.goals,
                "evaluation": syl.evaluation,
                "textbooks_references": syl.textbooks_references,
                "notes": syl.notes,
            } if syl else None,
            "weeks": [
                {"week": w.week, "content": w.content, "method": w.method}
                for w in sec_weeks
            ],
            "books": [
                {
                    "title": b.title,
                    "author": b.author,
                    "publisher": b.publisher,
                    "year": b.year,
                    "isbn": b.isbn,
                }
                for b in sec_books
            ],
        })

    return {
        "subject_code": subject.subject_code,
        "subject_name": subject.subject_name,
        "credit": subject.credit,
        "lecture_hours": subject.lecture_hours,
        "practice_hours": subject.practice_hours,
        "offered_terms": _parse_list(subject.offered_terms),
        "prerequisites": _parse_list(subject.prerequisites),
        "followups": _parse_list(subject.followups),
        "sections": section_details,
    }


@app.get("/api/timetable")
def get_timetable(
    user_id: str = Query(..., min_length=1, max_length=64),
    term: str = Query("2026-1", min_length=1, max_length=32),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(UserTimetable, Section, Subject)
        .join(
            Section,
            (UserTimetable.term == Section.term)
            & (UserTimetable.course_no == Section.course_no),
        )
        .join(Subject, Section.subject_code == Subject.subject_code)
        .filter(UserTimetable.user_id == user_id, UserTimetable.term == term)
        .all()
    )

    items = [
        {
            "term": sec.term,
            "course_no": sec.course_no,
            "subject_code": sec.subject_code,
            "subject_name": subj.subject_name,
            "professor": sec.professor,
            "time_slots": sec.time_slots,
            "time_real": sec.time_real,
            "room": sec.room,
        }
        for _, sec, subj in rows
    ]
    return {"user_id": user_id, "term": term, "courses": items}


@app.put("/api/timetable")
def save_timetable(
    payload: TimetableSaveRequest,
    db: Session = Depends(get_db),
):
    user_id = payload.user_id.strip()
    term = payload.term.strip()
    if not user_id or not term:
        raise HTTPException(status_code=400, detail="user_id and term are required")

    # 공백 제거 및 순서 유지 중복 제거
    unique_course_nos = list(
        dict.fromkeys(c.strip() for c in payload.course_nos if c and c.strip())
    )

    # 실제 해당 학기에 개설된 분반인지 검증
    if unique_course_nos:
        valid_course_nos = {
            row[0]
            for row in db.query(Section.course_no)
            .filter(
                Section.term == term,
                Section.course_no.in_(unique_course_nos),
            )
            .all()
        }
        invalid_course_nos = [c for c in unique_course_nos if c not in valid_course_nos]
        if invalid_course_nos:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid course_no for term {term}: {', '.join(invalid_course_nos)}",
            )

    try:
        db.query(UserTimetable).filter(
            UserTimetable.user_id == user_id,
            UserTimetable.term == term,
        ).delete()

        for course_no in unique_course_nos:
            db.add(
                UserTimetable(
                    user_id=user_id,
                    term=term,
                    course_no=course_no,
                )
            )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save timetable")

    return {
        "user_id": user_id,
        "term": term,
        "saved_count": len(unique_course_nos),
        "course_nos": unique_course_nos,
    }
