import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from gatorway.db.models import Course
from gatorway.ingest.embeddings import HashingEmbedder, course_text, embed_courses
from gatorway.ingest.loader import ingest_all

FIX = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def loaded(db):
    ingest_all(db, json.loads((FIX / "mini_courses.json").read_text()), json.loads((FIX / "mini_programs.json").read_text()))
    db.commit()
    return db


def test_hashing_embedder_ranks_related_text_closer():
    e = HashingEmbedder()
    q = e.embed_query("web development javascript react")
    docs = e.embed_documents(["Build web applications with JavaScript and React", "Drawing fundamentals and sketching"])
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    assert dot(q, docs[0]) > dot(q, docs[1]) and len(q) == e.dim == 768


def test_only_courses_with_a_description_are_embedded(loaded):
    n = embed_courses(loaded, HashingEmbedder())
    assert n == 7  # CSC 999 has no description
    assert loaded.scalar(select(func.count()).select_from(Course).where(Course.embedding.is_not(None))) == 7
    assert loaded.scalar(select(Course.embedding).where(Course.code == "CSC 999")) is None


def test_unchanged_text_is_not_reembedded_but_changed_text_is(loaded):
    embed_courses(loaded, HashingEmbedder())
    assert embed_courses(loaded, HashingEmbedder()) == 0
    loaded.execute(Course.__table__.update().where(Course.code == "ART 101").values(description="Oil painting and color theory."))
    loaded.commit()
    assert embed_courses(loaded, HashingEmbedder()) == 1


def test_semantic_search_finds_the_web_course_first(loaded):
    e = HashingEmbedder()
    embed_courses(loaded, e)
    top = loaded.scalars(select(Course).where(Course.embedding.is_not(None)).order_by(Course.embedding.cosine_distance(e.embed_query("next.js react web apps"))).limit(1)).one()
    assert top.code == "CSC 600"


def test_course_text_combines_code_title_and_description():
    assert course_text("CSC 600", "Web", "Build sites.") == "CSC 600 Web. Build sites."
