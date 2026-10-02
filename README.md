# GatorWay

Backend and API that turn an SFSU transcript plus a student's interest into a degree roadmap with interest-matched electives.
Design: `ARCHITECTURE.md`. Plan: `docs/superpowers/plans/`.

## Run it (everything on one laptop)

1. **Services** (Postgres + pgvector, Redis; data kept in named volumes):
   `docker compose up -d`
2. **Python env** (once): `venv/bin/pip install -e "backend[dev]"`; copy `.env.example` to `.env` and fill in `GEMINI_API_KEY`, `JWT_SECRET`.
3. **Load the data** (once, and again after re-scraping):
   `cd backend && ../venv/bin/python -m gatorway.ingest --scrape-dir ../scraping/sfsu_output`
   (`--embeddings hashing` runs offline without a Gemini key; the default `gemini` gives real semantic search. If you ingest with `hashing`, also set `EMBED_PROVIDER=hashing` in `.env` so the MCP server embeds search queries the same way.)
4. **MCP server** (terminal 1): `cd backend && ../venv/bin/python -m gatorway.mcp_server`
5. **API** (terminal 2): `cd backend && ../venv/bin/uvicorn gatorway.api.main:create_app --factory --port 8000` - docs at http://127.0.0.1:8000/docs
6. **Extractor**: deployed on Cloud Run (see `extractor/`), or locally:
   `cd extractor && ../venv/bin/uvicorn app:create_app --factory --port 8080` and point `EXTRACTOR_URL` at it.

## Tests

`cd backend && ../venv/bin/pytest -q` (needs the Postgres container) and `cd extractor && ../venv/bin/pytest -q`.

## Manual end-to-end check (real Gemini)

`venv/bin/python scripts/smoke_e2e.py` with the API, MCP server and extractor running.
