import csv
import os
from pathlib import Path
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine
from models import (
    CourseEdge,
    Curriculum,
    Section,
    Subject,
    Syllabus,
    SyllabusBook,
    SyllabusWeek,
)

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_CSV_DIR = DEFAULT_DATA_DIR / "lecture_data" / "lecture_data_csv"
DEFAULT_EDGES_CSV = DEFAULT_DATA_DIR / "graph_data" / "edges.csv"
DEFAULT_CURRICULUM_CSV = DEFAULT_DATA_DIR / "curriculum_data" / "curriculum.csv"


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


def seed_all(
    db: Session,
    csv_dir: Path,
    edges_csv: Path,
    curriculum_csv: Path,
) -> dict[str, int | str]:
    counts: dict[str, int | str] = {}

    if db.query(Subject).first() is None:
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

    if db.query(CourseEdge).first() is None and edges_csv.exists():
        edge_rows = load_csv(edges_csv)
        db.bulk_save_objects([
            CourseEdge(
                from_code=r["from_code"].strip(),
                from_name=r.get("from_name"),
                to_code=r["to_code"].strip(),
                to_name=r.get("to_name"),
                type=(r.get("type") or "pre").strip(),
                or_with=(r.get("or_with") or "").strip() or None,
            )
            for r in edge_rows
            if r.get("from_code") and r.get("to_code")
        ])
        counts["course_edges"] = len(edge_rows)

    if db.query(Curriculum).first() is None and curriculum_csv.exists():
        curriculum_rows = load_csv(curriculum_csv)
        db.bulk_save_objects([
            Curriculum(
                major_name=r["major_name"].strip(),
                basis_year=_to_int(r.get("basis_year")),
                grade=_to_int(r.get("grade")),
                semester=(r.get("semester") or "").strip() or None,
                category=(r.get("category") or "").strip() or None,
                course_code=r["course_code"].strip(),
                course_name_ko=(r.get("course_name_ko") or "").strip() or None,
                credits=_to_int(r.get("credits")),
                theory_hours=_to_int(r.get("theory_hours")),
                lab_hours=_to_int(r.get("lab_hours")),
                is_required=_to_bool(r.get("is_required")),
                note=(r.get("note") or "").strip() or None,
            )
            for r in curriculum_rows
            if r.get("major_name") and r.get("course_code")
        ])
        counts["curriculum"] = len(curriculum_rows)

    db.commit()
    return counts or {"message": "already_seeded"}


if __name__ == "__main__":
    csv_dir = Path(os.getenv("CSV_DIR", str(DEFAULT_CSV_DIR)))
    edges_csv = Path(os.getenv("EDGES_CSV", str(DEFAULT_EDGES_CSV)))
    curriculum_csv = Path(os.getenv("CURRICULUM_CSV", str(DEFAULT_CURRICULUM_CSV)))
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = seed_all(db, csv_dir, edges_csv, curriculum_csv)
        print("Seed result:", result)
    finally:
        db.close()