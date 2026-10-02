"""SQLAlchemy models for ARCHITECTURE.md section 2."""
from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBED_DIM = 768


class Base(DeclarativeBase):
    pass


class Meta(Base):
    """Key/value row store; holds `data_version` (bumped by every ingest run)."""

    __tablename__ = "meta"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Course(Base):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    subject: Mapped[str | None] = mapped_column(String(16))
    number: Mapped[str | None] = mapped_column(String(16))
    number_int: Mapped[int | None] = mapped_column(Integer)  # leading digits of `number`; 700+ = graduate
    title: Mapped[str] = mapped_column(Text, default="")
    units_min: Mapped[float] = mapped_column(Float, default=0)
    units_max: Mapped[float] = mapped_column(Float, default=0)
    description: Mapped[str | None] = mapped_column(Text)
    prereq_text: Mapped[str | None] = mapped_column(Text)
    prereq_codes: Mapped[list] = mapped_column(JSONB, default=list)
    prereq_groups: Mapped[list] = mapped_column(JSONB, default=list)  # [[code, ...], ...] AND of ORs
    concurrent_ok: Mapped[list] = mapped_column(JSONB, default=list)
    prereq_warnings: Mapped[list] = mapped_column(JSONB, default=list)
    attributes: Mapped[list] = mapped_column(JSONB, default=list)
    text_hash: Mapped[str | None] = mapped_column(String(40))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))

    __table_args__ = (
        Index(
            "ix_courses_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class Program(Base):
    __tablename__ = "programs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_url: Mapped[str] = mapped_column(String(512), unique=True)
    slug: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(Text)
    college: Mapped[str | None] = mapped_column(String(255))
    college_slug: Mapped[str | None] = mapped_column(String(128))
    department: Mapped[str | None] = mapped_column(String(255))
    department_slug: Mapped[str | None] = mapped_column(String(128))
    degree_type: Mapped[str | None] = mapped_column(String(32))
    level: Mapped[str | None] = mapped_column(String(32))  # undergraduate | graduate | minor | certificate | credential
    concentration: Mapped[str | None] = mapped_column(Text)
    listed_units: Mapped[float | None] = mapped_column(Float)  # the "- 74 units" in the requirements heading (major units)

    sections: Mapped[list["RequirementSection"]] = relationship(back_populates="program", cascade="all, delete-orphan", order_by="RequirementSection.position")
    roadmaps: Mapped[list["Roadmap"]] = relationship(back_populates="program", cascade="all, delete-orphan", order_by="Roadmap.id")


class RequirementSection(Base):
    __tablename__ = "requirement_sections"
    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(Text)
    units_raw: Mapped[str | None] = mapped_column(String(64))
    units_min: Mapped[float | None] = mapped_column(Float)
    kind: Mapped[str] = mapped_column(String(16), default="other")  # core | elective | ge | other
    notes: Mapped[list] = mapped_column(JSONB, default=list)

    program: Mapped[Program] = relationship(back_populates="sections")
    items: Mapped[list["RequirementItem"]] = relationship(back_populates="section", cascade="all, delete-orphan", order_by="RequirementItem.position")


class RequirementItem(Base):
    __tablename__ = "requirement_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("requirement_sections.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"))
    raw_code: Mapped[str] = mapped_column(String(255))  # cross-listed entries ("CLAR 420/ANTH 424/...") are long
    or_with_previous: Mapped[bool] = mapped_column(Boolean, default=False)

    section: Mapped[RequirementSection] = relationship(back_populates="items")


class Roadmap(Base):
    __tablename__ = "roadmaps"
    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(512))
    total_units_required: Mapped[float | None] = mapped_column(Float)
    major_units: Mapped[float | None] = mapped_column(Float)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    program: Mapped[Program] = relationship(back_populates="roadmaps")
    terms: Mapped[list["RoadmapTerm"]] = relationship(back_populates="roadmap", cascade="all, delete-orphan", order_by="RoadmapTerm.position")


class RoadmapTerm(Base):
    __tablename__ = "roadmap_terms"
    id: Mapped[int] = mapped_column(primary_key=True)
    roadmap_id: Mapped[int] = mapped_column(ForeignKey("roadmaps.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(128))

    roadmap: Mapped[Roadmap] = relationship(back_populates="terms")
    slots: Mapped[list["RoadmapSlot"]] = relationship(back_populates="term", cascade="all, delete-orphan", order_by="RoadmapSlot.position")


class RoadmapSlot(Base):
    __tablename__ = "roadmap_slots"
    id: Mapped[int] = mapped_column(primary_key=True)
    term_id: Mapped[int] = mapped_column(ForeignKey("roadmap_terms.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    codes: Mapped[list] = mapped_column(JSONB, default=list)  # [] for generic slots (electives, GE)
    title: Mapped[str] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    footnotes: Mapped[list] = mapped_column(JSONB, default=list)
    units: Mapped[float] = mapped_column(Float, default=0)  # total for the row ("Take Three" = 9)
    seats: Mapped[int] = mapped_column(Integer, default=1)  # "Take Three" = 3
    slot_kind: Mapped[str] = mapped_column(String(24), default="fixed")  # fixed | major_elective | free_elective
    swappable: Mapped[bool] = mapped_column(Boolean, default=False)
    counts_toward_major: Mapped[bool] = mapped_column(Boolean, default=False)
    pool_section_id: Mapped[int | None] = mapped_column(ForeignKey("requirement_sections.id", ondelete="SET NULL"))

    term: Mapped[RoadmapTerm] = relationship(back_populates="slots")


class UserCourse(Base):
    __tablename__ = "user_courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    raw_code: Mapped[str] = mapped_column(String(32))
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"))
    grade: Mapped[str | None] = mapped_column(String(8))
    term: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(Text)  # as printed on the transcript, so lines we cannot match (transfer credit) can be recognised
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)  # code not found in `courses`

    __table_args__ = (UniqueConstraint("user_id", "raw_code", name="uq_user_course"),)


class SavedPathway(Base):
    """Snapshot of a result. roadmap_id is deliberately NOT a foreign key: re-ingesting recreates roadmaps."""

    __tablename__ = "pathways"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    program_id: Mapped[int] = mapped_column(Integer)
    roadmap_id: Mapped[int | None] = mapped_column(Integer)
    interest_raw: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[dict | None] = mapped_column(JSONB)
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
