import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from gatorway.db.models import Course
from gatorway.db.models import Meta
from gatorway.ingest.embeddings import HashingEmbedder, assert_embedding_matches, course_text, embed_courses
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


class OtherEmbedder(HashingEmbedder):
    identity = "other:model:768"


def test_switching_embedding_provider_re_embeds_everything_and_records_it(loaded):
    embed_courses(loaded, HashingEmbedder())
    assert loaded.get(Meta, "embedding_identity").value == "hashing:768"
    assert embed_courses(loaded, OtherEmbedder()) == 7
    loaded.expire_all()
    assert loaded.get(Meta, "embedding_identity").value == "other:model:768"


def test_the_search_server_refuses_to_start_on_vectors_made_by_another_embedder(loaded):
    with pytest.raises(RuntimeError, match="ingest"):
        assert_embedding_matches(loaded, HashingEmbedder())  # nothing embedded yet: identity unknown
    embed_courses(loaded, HashingEmbedder())
    assert_embedding_matches(loaded, HashingEmbedder())  # same embedder: fine
    with pytest.raises(RuntimeError, match="other:model:768"):
        assert_embedding_matches(loaded, OtherEmbedder())


class _StubST:
    """Stands in for a sentence-transformers model: records what it was asked to encode."""

    def __init__(self):
        self.calls = []

    def encode(self, texts, **kw):
        self.calls.append((list(texts), kw))
        return [[3.0, 4.0] + [0.0] * 766 for _ in texts]


def test_local_embedder_prefixes_queries_not_documents_and_records_identity():
    from gatorway.ingest.embeddings import LocalEmbedder

    stub = _StubST()
    e = LocalEmbedder("BAAI/bge-base-en-v1.5", model=stub)
    assert e.identity == "local:BAAI/bge-base-en-v1.5:768"
    docs = e.embed_documents(["intro to ai"])
    q = e.embed_query("machine learning")
    assert stub.calls[0][0] == ["intro to ai"]
    assert stub.calls[1][0][0].startswith("Represent this sentence for searching relevant passages:")
    assert stub.calls[1][0][0].endswith("machine learning")
    assert len(docs[0]) == 768 and abs(sum(x * x for x in q) - 1.0) < 1e-6


def test_embed_courses_shows_progress_when_asked(db, capsys):
    from gatorway.db.models import Course
    from gatorway.ingest.embeddings import HashingEmbedder, embed_courses

    db.add(Course(code="CSC 1", subject="CSC", number="1", title="A", description="alpha beta", units_min=3, units_max=3))
    db.commit()
    embed_courses(db, HashingEmbedder(), progress=True)
    assert "Embedding courses" in capsys.readouterr().err
