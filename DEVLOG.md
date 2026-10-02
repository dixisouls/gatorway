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

## Task 6 — Embeddings and `python -m gatorway.ingest`
- Added embedders (`HashingEmbedder` offline stand-in, `GeminiEmbedder`), `embed_courses` (skips unchanged text), and the ingest CLI.
- TDD: 5 embedding tests failed then passed.
- **Real data run found two bugs the small fixtures could not**, each fixed test-first:
  1. cross-listed requirement codes (e.g. `CLAR 420/ANTH 424/ARTH 401/M S 420`) overflowed `raw_code varchar(32)` → widened to 255;
  2. 16 roadmap rows had a course code but a null title → fall back to the codes.
- Test fixtures now rebuild the test schema each session. I dropped and recreated the (empty, verified) dev schema once.
- **Real ingest result (matches the spec's "done means"):** 4,995 courses, 378 programs, 1,828 requirement sections, 364 roadmaps, 12,757 slots (10,963 fixed / 1,664 free-elective / 130 major-elective), 4,986 courses embedded. Second run embedded 0 and changed nothing. 249 programs have no elective list (their major-elective slots stay fixed, as designed). Embeddings are the offline hashing stand-in; re-run with `--embeddings gemini` (needs `GEMINI_API_KEY`) for real semantic search.

## Task 7 — Repository and shared queries
- Added `engine/repository.py` (catalog cached per `data_version`, roadmap choice, per-seat skeleton, `build_baseline_for`, `user_passed_codes`) and `catalog_queries.py` (program/roadmap/requirement reads shared by the API and MCP tools).
- TDD: tests failed (module missing), then 7/7 passed.
- Real-data check: Computer Science B.S. baseline = 8 terms, 37 slots, 7 swappable (5 major-elective seats = the 15 elective units, plus 2 free electives); passed courses are marked.

## Task 8 — Redis cache, sessions, locks, rate limiter
- Added `cache/store.py` (intent/embedding/pathway caches with the spec's TTLs, single-flight lock, pathway sessions, fixed-window rate limiter; Redis outage = no cache / fail-open limiter, sessions raise `CacheUnavailable`).
- TDD: tests failed (module missing), then 8/8 passed with fakeredis.
- Also smoke-tested against the **real Redis container** (I started it): session TTL 1800s, lock exclusivity, intent TTL 7 days, rate limiter blocks after the limit, AOF persistence on. Test keys were removed afterwards.

## Task 9 — MCP server and tools
- Added the FastMCP server with auto-registered tool modules: `list_programs`, `get_program`, `get_roadmaps`, `get_requirements`, `build_baseline` + `open_session` (orchestrator-only), `get_baseline`, `validate_edits`, `search_courses`. Tools return `{"error": ...}` instead of raising, so Gemini can recover. `python -m gatorway.mcp_server` serves HTTP on 127.0.0.1:8001/mcp (needs `GEMINI_API_KEY` for query embeddings).
- TDD: tests failed (module missing), then 11/11 passed (pool restriction, passed/planned exclusion, prerequisite feasibility filter, undergraduate level filter, no-embedding courses never returned, empty results, dry-run validation, cached query embeddings).
- Real-data check (CS B.S. with core passed): 7 open swappable slots; major-elective search returns only courses from the program's own elective list, free-elective search returns undergraduate courses of any subject.
- **Open item:** semantic quality needs real Gemini embeddings — set `GEMINI_API_KEY` in `.env` and run `python -m gatorway.ingest --embeddings gemini` (only changed courses are re-embedded). Right now the DB holds the offline word-overlap stand-in.

## Task 10 — Gemini adapter and pathway orchestrator
- Added `llm/ports.py` (Intent, LlmPort), `llm/gemini.py` (intent parsing with structured output; tool-calling loop over the MCP client with an allowlist; tolerant JSON edit parsing; student text treated as data) and `llm/orchestrator.py` (`PathwayService`: baseline → intent → cache → single-flight lock → Gemini edits → authoritative validation with up to 2 retries → graceful fallbacks).
- TDD: tests failed (module missing), then 18/18 passed — no network used. Covers: no interest, no specialization, no swappable slots (Gemini never called), valid edit + cache hit, injection attempt on a core slot dropped, retry with validator feedback, give-up after max retries, Gemini/intent failure and Redis-session failure degrade to the baseline with a note (and are not cached), concurrent identical requests run Gemini once.
- Confirmed the installed `google-genai` still exposes `parameters_json_schema` and `function_calls`.
- Not yet exercised with the **real Gemini** (no `GEMINI_API_KEY` in this environment) — done in the final smoke test.

## Task 11 — Transcript adapters
- Added local PDF→text (`pdf.py`; scans/corrupt files rejected, no OCR), transcript normalisation (`extraction.py`: codes like `csc215` → `CSC 215`, only passing grades, retake after an F counts), the redaction port with a pass-through `StubRedactor` (logs a warning once that nothing is redacted), and `HttpExtractor` (API key header, every failure mode → `ExtractorError`).
- TDD: tests failed (module missing), then 13/13 passed (HTTP tested with a mocked transport).

## Task 12 — API foundation, auth, health
- Added argon2 password hashing + JWT helpers + the `sfsu.edu`/subdomain email check; the app state/builder; a uniform error envelope (`{"error": {code, message, details}}`); auth deps and per-IP / per-user rate limiting; `/auth/signup`, `/auth/login`, `/auth/me`; `/health` (Postgres + Redis, 503 if either is down).
- TDD: tests failed (package missing), then 27/27 passed (email tricks like `evilsfsu.edu` / `sfsu.edu.evil.com`, duplicate emails, identical login failures for wrong password vs unknown user, expired tokens, login rate limit, login still works with Redis down).
- **Real boot check:** started `uvicorn` against the real Postgres and Redis — `/health` → ok/ok/ok; a real signup returned a token; an `@evilsfsu.edu` signup was rejected with `invalid_email`. The throwaway test user was deleted.

## Task 13 — Transcript upload and saved-courses routes
- Added `POST /transcripts` (PDF only, ≤10 MB; local text extraction → redaction → extractor → SFSU check → save), `GET /me/courses`, `DELETE /me/courses`.
- TDD: 10 tests failed (routes missing). After adding the routes, 5 still failed — a bug in the plan's code (`dict(db.execute(...))` treats a SQLAlchemy result as a mapping); fixed with `.all()`, then 10/10 passed. I also corrected the same line in the plan document.
- Covers: unknown codes flagged but kept, the extractor only ever sees redacted text, re-upload replaces the list, a non-SFSU transcript is rejected without touching the saved list, unreadable/oversized files, extractor outage → 502 with nothing changed, an empty transcript is fine, login + rate limit (5 uploads/hour).
