# GatorWay development log

Running record of what was done on `feat/backend`, newest last. Plan: `docs/superpowers/plans/2026-10-02-backend.md`. Spec: `ARCHITECTURE.md`.

## 2026-10-02 — Setup
- Pushed `docs` (spec + plan) to origin.
- Created branch `feat/backend` from `docs` (spec and plan travel with the code).
- Executing the plan inline, task by task; each task = test first (watched failing), implementation, passing run, commit.
- Added `.superpowers/` (execution ledger) to `.gitignore`.

## Task 1 — Scaffold, Docker, settings, fixtures
- Wrote `docker-compose.yml` (pgvector/pgvector:pg18 + redis:8-alpine, named volumes), `.env.example`, `backend/pyproject.toml`, `config.py`, `tests/conftest.py`, `tests/test_config.py`.
- TDD: settings test failed (`No module named gatorway.config`), then passed (3/3).
- Installed the package into `venv/` (`pip install -e "backend[dev]"`).
- **Docker (run by me, as authorised):** `docker compose up -d` → `gw-db` and `gw-redis` both healthy. `CREATE EXTENSION vector` + `SELECT '[1,2,3]'::vector` works. Volumes created: `gatorway_gw_pgdata`, `gatorway_gw_redisdata` (compose prefixes the project name).

## Task 2 — Database models and session helpers
- Added all SQLAlchemy models (`courses` with `Vector(768)` + HNSW cosine index, programs, requirement sections/items, roadmaps/terms/slots, users, user_courses, saved pathways, meta) and `db/session.py` (`init_db` creates the `vector` extension + tables).
- TDD: tests failed (no `gatorway.db.models`), then 5/5 passed against the real Postgres container. The test database `gatorway_test` is created automatically by the fixtures.

## Task 3 — Ingestion rules (pure logic)
- Added prerequisite grouping (AND-of-ORs, `*` = concurrent OK, non-course conditions), slot classification (major/free elective vs fixed), "Take N" seat parsing, default-roadmap choice, section kinds, and the grade-passing rule.
- TDD: tests failed (module missing), then 8/8 passed. Against the real scraped data the rules find **1,794 swappable roadmap rows**.

## Task 4 — Pathway engine (pure)
- Added the database-free engine: `models` (Pathway/Slot/Edit/Catalog…), `baseline` (marks passed courses, fills open major-elective seats from the pool, splits "Take N" rows), `validator` (prerequisites incl. later courses, pool/duplicate/units rules, only newly introduced violations block an edit).
- TDD: tests failed (module missing), then 17/17 passed.

## Task 5 — Ingestion loader
- Added `ingest/loader.py` (courses upsert, requirement sections/items, roadmaps → terms → slots with slot classification, default roadmap, data_version stamp) and a small hand-built fixture set (`tests/fixtures/mini_*.json`) that mirrors the scraper output.
- TDD: tests failed (module missing), then 7/7 passed against Postgres — including re-running ingest twice (no duplicates, stable program ids, changed data applied) and a program with no elective list (elective slots stay fixed).
