import csv
import os
from pathlib import Path
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine
from models import Section, Subject, Syllabus, SyllabusBook, SyllabusWeek

DEFAULT_CSV_DIR = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "lecture_data"
    / "lecture_data_csv"
)


def _to_int(val: str | None) -> int | None:
    if val is None or str(val).strip() == "":
        return None
    try:
        return int(float(val))
    except ValueError:
        return None


def _to_bool(val: str | None) -> bool:
    if val is None:
        return False
    return str(val).strip().lower() in {"1", "true", "yes", "y"}


def load_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def seed_all(db: Session, csv_dir: Path) -> dict[str, int]:
    if db.query(Subject).first() is not None:
        return {"status": 0, "message": "already_seeded"}

    counts = {}

    subjects_rows = load_csv(csv_dir / "subjects.csv")
    db.bulk_save_objects([
        Subject(
            subject_code=r["subject_code"].strip(),
            subject_name=r["subject_name"].strip(),
            credit=_to_int(r.get("credit")),
            lecture_hours=_to_int(r.get("lecture_hours")),
            practice_hours=_to_int(r.get("practice_hours")),
            offered_terms=r.get("offered_terms"),
            section_count=_to_int(r.get("section_count")),
            prerequisites=r.get("prerequisites"),
            followups=r.get("followups"),
        )
        for r in subjects_rows
        if r.get("subject_code")
    ])
    counts["subjects"] = len(subjects_rows)

    sections_rows = load_csv(csv_dir / "sections.csv")
    db.bulk_save_objects([
        Section(
            term=r["term"].strip(),
            course_no=r["course_no"].strip(),
            subject_code=r["subject_code"].strip(),
            section=r.get("section"),
            professor=r.get("professor"),
            time_slots=r.get("time_slots"),
            time_real=r.get("time_real"),
            room=r.get("room"),
            language=r.get("language"),
            capacity=_to_int(r.get("capacity")),
            listed_in=r.get("listed_in"),
            source_url=r.get("source_url"),
            source_file=r.get("source_file"),
            has_syllabus=_to_bool(r.get("has_syllabus")),
        )
        for r in sections_rows
        if r.get("term") and r.get("course_no")
    ])
    counts["sections"] = len(sections_rows)

    syllabus_rows = load_csv(csv_dir / "syllabus.csv")
    db.bulk_save_objects([
        Syllabus(
            term=r["term"].strip(),
            course_no=r["course_no"].strip(),
            professor=r.get("professor"),
            credit_system=r.get("credit_system"),
            language=r.get("language"),
            summary=r.get("summary"),
            goals=r.get("goals"),
            textbooks_references=r.get("textbooks_references"),
            evaluation=r.get("evaluation"),
            notes=r.get("notes"),
            source_file=r.get("source_file"),
        )
        for r in syllabus_rows
        if r.get("term") and r.get("course_no")
    ])
    counts["syllabus"] = len(syllabus_rows)

    weeks_rows = load_csv(csv_dir / "syllabus_weeks.csv")
    db.bulk_save_objects([
        SyllabusWeek(
            term=r["term"].strip(),
            course_no=r["course_no"].strip(),
            week=_to_int(r.get("week")),
            content=r.get("content"),
            method=r.get("method"),
            source_file=r.get("source_file"),
        )
        for r in weeks_rows
        if r.get("term") and r.get("course_no")
    ])
    counts["syllabus_weeks"] = len(weeks_rows)

    books_rows = load_csv(csv_dir / "syllabus_books.csv")
    db.bulk_save_objects([
        SyllabusBook(
            term=r["term"].strip(),
            course_no=r["course_no"].strip(),
            book_no=_to_int(r.get("book_no")),
            title=r.get("title"),
            author=r.get("author"),
            publisher=r.get("publisher"),
            year=r.get("year"),
            isbn=r.get("isbn"),
            book_type_code=r.get("book_type_code"),
            source_file=r.get("source_file"),
        )
        for r in books_rows
        if r.get("term") and r.get("course_no")
    ])
    counts["syllabus_books"] = len(books_rows)

    db.commit()
    return counts


if __name__ == "__main__":
    csv_dir = Path(os.getenv("CSV_DIR", str(DEFAULT_CSV_DIR)))
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = seed_all(db, csv_dir)
        print("Seed result:", result)
    finally:
        db.close()
