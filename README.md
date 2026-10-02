# GatorWay

Backend, API and web app that turn an SFSU transcript plus a student's interest into a degree roadmap with interest-matched electives.
Design: `ARCHITECTURE.md`. Plan: `docs/superpowers/plans/`.

## Run it (everything on one laptop)

**Quick start:** `scripts/start.sh` starts Postgres, Redis, the MCP server, the extractor, the API and the web app, then open http://localhost:3000 (logs in `logs/`, Ctrl-C stops the servers it started). The steps below are what it does.

1. **Services** (Postgres + pgvector, Redis; data kept in named volumes):
   `docker compose up -d`
2. **Python env** (once): `venv/bin/pip install -e "backend[dev]"`; copy `.env.example` to `.env` and set `GOOGLE_CLOUD_PROJECT` (Gemini uses your gcloud ADC login, or set `GEMINI_API_KEY` instead) and the Firebase values (see **Sign-in** below).
3. **Load the data** (once, and again after re-scraping):
   `cd backend && ../venv/bin/python -m gatorway.ingest --scrape-dir ../scraping/sfsu_output`
   (Embeddings run locally with sentence-transformers (`BAAI/bge-base-en-v1.5`, downloaded on first use; progress bar shown). Set `EMBED_PROVIDER` the same way for ingest and the MCP server; `--embeddings hashing` is an instant offline stand-in.)
4. **MCP server** (terminal 1): `cd backend && ../venv/bin/python -m gatorway.mcp_server`
5. **API** (terminal 2): `cd backend && ../venv/bin/uvicorn gatorway.api.main:create_app --factory --port 8000` - docs at http://127.0.0.1:8000/docs
6. **Extractor**: deployed on Cloud Run (see `extractor/`), or locally:
   `cd extractor && ../venv/bin/uvicorn app:create_app --factory --port 8080` and point `EXTRACTOR_URL` at it.

7. **Web app**: `cd frontend && npm install && npm run dev` (http://localhost:3000). It calls the API at `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`); the API allows the origins in `CORS_ORIGINS`.

## Sign-in (Firebase Authentication)
Accounts live in Firebase (a Google service): the browser signs students in with the Firebase web SDK, and the API checks the Firebase ID token on every request, then keeps a small local record (uid and email) so saved courses and pathways have an owner. Setup, once:
1. Firebase console, your project: **Build → Authentication → Get started → Sign-in method → Email/Password → Enable**.
2. **Project settings → General → Your apps → Add app → Web**; copy `apiKey`, `authDomain`, `projectId`, `appId` into `.env` as `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, `NEXT_PUBLIC_FIREBASE_APP_ID`, and set `FIREBASE_PROJECT_ID` to the same project id (the API needs only that; no key file).
3. Only `@sfsu.edu` (and subdomain) addresses are accepted, enforced in the browser and again in the API. `REQUIRE_EMAIL_VERIFIED=true` also demands a verified email.

## Tests

`cd backend && ../venv/bin/pytest -q` (needs the Postgres container), `cd extractor && ../venv/bin/pytest -q`, and for the web app `cd frontend && npm run typecheck && npm run lint && npm test && npm run build`.

## Manual end-to-end check (real Gemini)

`venv/bin/python scripts/smoke_e2e.py` with the API, MCP server and extractor running.
