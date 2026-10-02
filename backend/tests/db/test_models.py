import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from gatorway.db.models import Course, User, UserCourse


def vec(*head):
    return list(head) + [0.0] * (768 - len(head))


def test_vector_roundtrip_and_cosine_ordering(db):
    db.add_all([Course(code="A 1", embedding=vec(1.0)), Course(code="B 2", embedding=vec(0.0, 1.0)), Course(code="C 3")])
    db.commit()
    rows = db.scalars(select(Course).where(Course.embedding.is_not(None)).order_by(Course.embedding.cosine_distance(vec(1.0, 0.1))).limit(2)).all()
    assert [r.code for r in rows] == ["A 1", "B 2"]
    assert list(rows[0].embedding)[:2] == [1.0, 0.0]


def test_hnsw_index_exists(engine):
    with engine.connect() as c:
        defs = [r[0] for r in c.execute(text("select indexdef from pg_indexes where tablename = 'courses'"))]
    assert any("hnsw" in d and "vector_cosine_ops" in d for d in defs)


def test_jsonb_columns_hold_nested_lists(db):
    db.add(Course(code="X 1", prereq_groups=[["A 1", "B 2"], ["C 3"]], concurrent_ok=["A 1"]))
    db.commit()
    got = db.scalar(select(Course).where(Course.code == "X 1"))
    assert got.prereq_groups == [["A 1", "B 2"], ["C 3"]]


def test_course_code_and_user_email_are_unique(db):
    db.add(Course(code="DUP 1")); db.commit()
    db.add(Course(code="DUP 1"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(User(email="a@sfsu.edu", password_hash="x")); db.commit()
    db.add(User(email="a@sfsu.edu", password_hash="y"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_a_course_can_be_saved_once_per_user(db):
    u = User(email="b@sfsu.edu", password_hash="x"); db.add(u); db.commit()
    db.add(UserCourse(user_id=u.id, raw_code="CSC 101")); db.commit()
    db.add(UserCourse(user_id=u.id, raw_code="CSC 101"))
    with pytest.raises(IntegrityError):
        db.commit()
