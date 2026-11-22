from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from database import Base


class Subject(Base):
    __tablename__ = "subjects"

    subject_code = Column(String(32), primary_key=True, index=True)
    subject_name = Column(String(200), nullable=False)
    credit = Column(Integer, nullable=True)
    lecture_hours = Column(Integer, nullable=True)
    practice_hours = Column(Integer, nullable=True)
    offered_terms = Column(String(100), nullable=True)
    section_count = Column(Integer, nullable=True)
    prerequisites = Column(Text, nullable=True)
    followups = Column(Text, nullable=True)


class CourseEdge(Base):
    __tablename__ = "course_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_code = Column(String(32), nullable=False, index=True)
    from_name = Column(String(200), nullable=True)
    to_code = Column(String(32), nullable=False, index=True)
    to_name = Column(String(200), nullable=True)
    type = Column(String(32), nullable=False, default="pre")
    or_with = Column(String(100), nullable=True)


class Curriculum(Base):
    __tablename__ = "curriculum"

    id = Column(Integer, primary_key=True, autoincrement=True)
    major_name = Column(String(100), nullable=False, index=True)
    basis_year = Column(Integer, nullable=True)
    grade = Column(Integer, nullable=True, index=True)
    semester = Column(String(20), nullable=True, index=True)
    category = Column(String(50), nullable=True)
    course_code = Column(String(32), nullable=False, index=True)
    course_name_ko = Column(String(200), nullable=True)
    credits = Column(Integer, nullable=True)
    theory_hours = Column(Integer, nullable=True)
    lab_hours = Column(Integer, nullable=True)
    is_required = Column(Boolean, default=False)
    note = Column(Text, nullable=True)


class Career(Base):
    __tablename__ = "careers"

    career_id = Column(String(64), primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    source = Column(String(200), nullable=True)


class CareerSubject(Base):
    __tablename__ = "career_subjects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    career_id = Column(String(64), ForeignKey("careers.career_id"), nullable=False, index=True)
    subject_code = Column(String(32), nullable=False, index=True)
    source = Column(String(200), nullable=True)


class GraduationCredit(Base):
    __tablename__ = "graduation_credits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    major_name = Column(String(100), nullable=False, index=True)
    track = Column(String(100), nullable=True)
    from_year = Column("from", String(20), nullable=True)
    to_year = Column("to", String(20), nullable=True)
    category = Column(String(100), nullable=True)
    credits_min = Column(Integer, nullable=True)
    credits_max = Column(Integer, nullable=True)
    note = Column(Text, nullable=True)


class GraduationRule(Base):
    __tablename__ = "graduation_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    major_name = Column(String(100), nullable=False, index=True)
    track = Column(String(100), nullable=True)
    from_year = Column("from", String(20), nullable=True)
    to_year = Column("to", String(20), nullable=True)
    item = Column(String(200), nullable=True)
    requirement = Column(Text, nullable=True)
    footnotes = Column(Text, nullable=True)


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("term", "course_no", name="uq_section_term_course"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    term = Column(String(20), nullable=False, index=True)
    course_no = Column(String(64), nullable=False, index=True)
    subject_code = Column(String(32), ForeignKey("subjects.subject_code"), index=True)
    section = Column(String(20), nullable=True)
    professor = Column(String(100), nullable=True)
    time_slots = Column(Text, nullable=True)
    time_real = Column(Text, nullable=True)
    room = Column(String(200), nullable=True)
    language = Column(String(50), nullable=True)
    capacity = Column(Integer, nullable=True)
    listed_in = Column(String(100), nullable=True)
    source_url = Column(Text, nullable=True)
    source_file = Column(Text, nullable=True)
    has_syllabus = Column(Boolean, default=False)


class Syllabus(Base):
    __tablename__ = "syllabus"
    __table_args__ = (
        UniqueConstraint("term", "course_no", name="uq_syllabus_term_course"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    term = Column(String(20), nullable=False, index=True)
    course_no = Column(String(64), nullable=False, index=True)
    professor = Column(String(100), nullable=True)
    credit_system = Column(String(50), nullable=True)
    language = Column(String(50), nullable=True)
    summary = Column(Text, nullable=True)
    goals = Column(Text, nullable=True)
    textbooks_references = Column(Text, nullable=True)
    evaluation = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    source_file = Column(Text, nullable=True)


class SyllabusWeek(Base):
    __tablename__ = "syllabus_weeks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    term = Column(String(20), nullable=False, index=True)
    course_no = Column(String(64), nullable=False, index=True)
    week = Column(Integer, nullable=True)
    content = Column(Text, nullable=True)
    method = Column(String(200), nullable=True)
    source_file = Column(Text, nullable=True)


class SyllabusBook(Base):
    __tablename__ = "syllabus_books"

    id = Column(Integer, primary_key=True, autoincrement=True)
    term = Column(String(20), nullable=False, index=True)
    course_no = Column(String(64), nullable=False, index=True)
    book_no = Column(Integer, nullable=True)
    title = Column(Text, nullable=True)
    author = Column(String(200), nullable=True)
    publisher = Column(String(200), nullable=True)
    year = Column(String(20), nullable=True)
    isbn = Column(String(50), nullable=True)
    book_type_code = Column(String(50), nullable=True)
    source_file = Column(Text, nullable=True)


class UserCompletedCourse(Base):
    __tablename__ = "user_completed_courses"
    __table_args__ = (
        UniqueConstraint("user_id", "subject_code", name="uq_user_completed_subject"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True)
    subject_code = Column(String(32), ForeignKey("subjects.subject_code"), nullable=False)
    term = Column(String(20), nullable=True)
    source = Column(String(20), default="manual")


class UserRoadmap(Base):
    __tablename__ = "user_roadmaps"
    __table_args__ = (
        UniqueConstraint("user_id", "subject_code", name="uq_user_roadmap_subject"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True)
    subject_code = Column(String(32), ForeignKey("subjects.subject_code"), nullable=False)
    source = Column(String(20), default="llm")


class LLMLog(Base):
    __tablename__ = "llm_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True)
    kind = Column(String(20), nullable=False, index=True)
    subject_code = Column(String(32), nullable=True, index=True)
    request_key = Column(String(64), nullable=False, index=True)
    request = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    model = Column(String(100), nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class UserTimetable(Base):
    __tablename__ = "user_timetables"
    __table_args__ = (
        UniqueConstraint("user_id", "term", "course_no", name="uq_user_timetable"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True)
    term = Column(String(20), nullable=False, index=True)
    course_no = Column(String(64), nullable=False)
