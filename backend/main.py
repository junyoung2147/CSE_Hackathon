import re
from collections import defaultdict
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import (
    CourseEdge,
    Curriculum,
    Section,
    Subject,
    Syllabus,
    SyllabusBook,
    SyllabusWeek,
    UserCompletedCourse,
    UserTimetable,
)

from everytime_router import router as everytime_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="KNU CSE Hackathon Backend", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(everytime_router)


class CompleteToggleRequest(BaseModel):
    user_id: str
    subject_code: str
    completed: bool
    term: str | None = None
    source: str = "manual"


class TimetableSaveRequest(BaseModel):
    user_id: str
    term: str
    course_nos: list[str]


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


@app.get("/api/roadmap")
def get_roadmap(
    user_id: str = Query(..., description="사용자 식별 ID"),
    db: Session = Depends(get_db),
):
    subjects = db.query(Subject).order_by(Subject.subject_code).all()
    edges = db.query(CourseEdge).order_by(CourseEdge.id).all()
    completed_rows = (
        db.query(UserCompletedCourse)
        .filter(UserCompletedCourse.user_id == user_id)
        .all()
    )
    completed_codes = {row.subject_code for row in completed_rows}

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

    rows = query.order_by(Curriculum.major_name, Curriculum.grade, Curriculum.semester, Curriculum.course_code).all()
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
    subject = (
        db.query(Subject)
        .filter(Subject.subject_code == payload.subject_code)
        .first()
    )
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    existing = (
        db.query(UserCompletedCourse)
        .filter(
            UserCompletedCourse.user_id == payload.user_id,
            UserCompletedCourse.subject_code == payload.subject_code,
        )
        .first()
    )

    if payload.completed:
        if not existing:
            db.add(
                UserCompletedCourse(
                    user_id=payload.user_id,
                    subject_code=payload.subject_code,
                    term=payload.term,
                    source=payload.source,
                )
            )
            db.commit()
    else:
        if existing:
            db.delete(existing)
            db.commit()

    return {
        "user_id": payload.user_id,
        "subject_code": payload.subject_code,
        "completed": payload.completed,
    }


@app.get("/api/subjects/{subject_code}")
def get_subject_detail(subject_code: str, db: Session = Depends(get_db)):
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

    section_details = []
    for sec in sections:
        syl = (
            db.query(Syllabus)
            .filter(Syllabus.term == sec.term, Syllabus.course_no == sec.course_no)
            .first()
        )
        weeks = (
            db.query(SyllabusWeek)
            .filter(
                SyllabusWeek.term == sec.term,
                SyllabusWeek.course_no == sec.course_no,
            )
            .order_by(SyllabusWeek.week)
            .all()
        )
        books = (
            db.query(SyllabusBook)
            .filter(
                SyllabusBook.term == sec.term,
                SyllabusBook.course_no == sec.course_no,
            )
            .order_by(SyllabusBook.book_no)
            .all()
        )
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
                "summary": syl.summary if syl else None,
                "goals": syl.goals if syl else None,
                "evaluation": syl.evaluation if syl else None,
                "textbooks_references": syl.textbooks_references if syl else None,
                "notes": syl.notes if syl else None,
            } if syl else None,
            "weeks": [
                {"week": w.week, "content": w.content, "method": w.method}
                for w in weeks
            ],
            "books": [
                {
                    "title": b.title,
                    "author": b.author,
                    "publisher": b.publisher,
                    "year": b.year,
                    "isbn": b.isbn,
                }
                for b in books
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
    user_id: str = Query(...),
    term: str = Query("2026-1"),
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
    db.query(UserTimetable).filter(
        UserTimetable.user_id == payload.user_id,
        UserTimetable.term == payload.term,
    ).delete()

    for course_no in payload.course_nos:
        db.add(
            UserTimetable(
                user_id=payload.user_id,
                term=payload.term,
                course_no=course_no.strip(),
            )
        )
    db.commit()
    return {
        "user_id": payload.user_id,
        "term": payload.term,
        "saved_count": len(payload.course_nos),
    }