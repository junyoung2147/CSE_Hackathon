from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import (
    Section,
    Subject,
    Syllabus,
    SyllabusBook,
    SyllabusWeek,
    UserCompletedCourse,
    UserTimetable,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="KNU CSE Hackathon Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    return [item.strip() for item in raw.split(",") if item.strip()]


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/roadmap")
def get_roadmap(
    user_id: str = Query(..., description="사용자 식별 ID"),
    db: Session = Depends(get_db),
):
    subjects = db.query(Subject).order_by(Subject.subject_code).all()
    completed_rows = (
        db.query(UserCompletedCourse)
        .filter(UserCompletedCourse.user_id == user_id)
        .all()
    )
    completed_codes = {row.subject_code for row in completed_rows}

    nodes = []
    for s in subjects:
        is_completed = s.subject_code in completed_codes
        prereqs = _parse_list(s.prerequisites)
        followups = _parse_list(s.followups)
        nodes.append({
            "subject_code": s.subject_code,
            "subject_name": s.subject_name,
            "credit": s.credit,
            "offered_terms": _parse_list(s.offered_terms),
            "prerequisites": prereqs,
            "followups": followups,
            "is_completed": is_completed,
            "light": "green" if is_completed else "default",
        })

    return {"user_id": user_id, "total": len(nodes), "subjects": nodes}


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
