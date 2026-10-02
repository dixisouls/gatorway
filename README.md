# GatorWay

Backend and API that turn an SFSU transcript plus a student's interest into a degree roadmap with interest-matched electives.
Design: `ARCHITECTURE.md`. Plan: `docs/superpowers/plans/`.

## Run it (everything on one laptop)

**Quick start:** `scripts/start.sh` starts Postgres, Redis, the MCP server, the extractor and the API (logs in `logs/`, Ctrl-C stops the Python servers). The steps below are what it does.

1. **Services** (Postgres + pgvector, Redis; data kept in named volumes):
   `docker compose up -d`
2. **Python env** (once): `venv/bin/pip install -e "backend[dev]"`; copy `.env.example` to `.env` and set `GOOGLE_CLOUD_PROJECT` (Gemini uses your gcloud ADC login, or set `GEMINI_API_KEY` instead) and a strong `JWT_SECRET`.
3. **Load the data** (once, and again after re-scraping):
   `cd backend && ../venv/bin/python -m gatorway.ingest --scrape-dir ../scraping/sfsu_output`
   (Embeddings run locally with sentence-transformers (`BAAI/bge-base-en-v1.5`, downloaded on first use; progress bar shown). Set `EMBED_PROVIDER` the same way for ingest and the MCP server; `--embeddings hashing` is an instant offline stand-in.)
4. **MCP server** (terminal 1): `cd backend && ../venv/bin/python -m gatorway.mcp_server`
5. **API** (terminal 2): `cd backend && ../venv/bin/uvicorn gatorway.api.main:create_app --factory --port 8000` - docs at http://127.0.0.1:8000/docs
6. **Extractor**: deployed on Cloud Run (see `extractor/`), or locally:
   `cd extractor && ../venv/bin/uvicorn app:create_app --factory --port 8080` and point `EXTRACTOR_URL` at it.

## Tests

`cd backend && ../venv/bin/pytest -q` (needs the Postgres container) and `cd extractor && ../venv/bin/pytest -q`.

## Manual end-to-end check (real Gemini)

`venv/bin/python scripts/smoke_e2e.py` with the API, MCP server and extractor running.
