# GatorWay

**Your degree roadmap, tuned to what you love. Gemini picks the electives; rules check every prerequisite.**

GatorWay turns an SF State transcript and one sentence about what a student is into into a semester-by-semester degree roadmap. The official roadmap appears instantly, then Gemini's elective picks land on top of it, and a rules engine checks every prerequisite and unit so nothing the AI suggests can derail graduation.

Design: [`ARCHITECTURE.md`](ARCHITECTURE.md) · Build log: [`DEVLOG.md`](DEVLOG.md) · Plans: `docs/superpowers/plans/`

## What it does

1. **Sign in** with an SFSU email (Firebase Authentication).
2. **Upload a transcript**, or skip and just explore. The PDF text is redacted locally, then Gemini reads the courses.
3. **Pick a degree** and the official roadmap variant.
4. **Say what you're into**, e.g. "AI and machine learning" (optional).
5. **Watch the roadmap build**: the standard roadmap shows at once, then a shimmer as Gemini's picks (in gold, each with a reason) replace the baseline.

Then: open any course for its description and prerequisites; swap electives and GE rows from ranked options; choose between "Select One" alternatives; mark GE requirements completed; refresh the picks or try a new interest; reopen past roadmaps.

## How it works

- **Deterministic baseline first.** Passed courses are marked off the official roadmap by rules, not by an AI.
- **Gemini proposes, rules decide.** Gemini (Vertex AI) searches for courses through a tool server (FastMCP). A validator then checks each proposed swap: allowed course list, level, duplicates, units, and prerequisites for the whole pathway. Anything that fails is dropped.
- **Meaning-based course search.** About 5,000 scraped SFSU courses are embedded locally (`BAAI/bge-base-en-v1.5`) in Postgres with pgvector.
- **Privacy.** Transcript text is redacted on this machine with GLiNER (`nvidia/gliner-PII`) before it reaches Gemini. If redaction can't run, the upload is refused and nothing is sent.

**Built with:** Gemini on Vertex AI, Firebase Authentication · Next.js, React, TypeScript, Tailwind, Motion · FastAPI, FastMCP, SQLAlchemy, Postgres + pgvector, Redis · sentence-transformers, GLiNER, pdfplumber.

**Known limits:** transfer and GE credit on a transcript isn't matched to SFSU courses (you mark GE rows yourself); "Choose one" picks and completed GE rows are remembered in the browser only; redaction is a model, so best-effort.

## Run it (everything on one laptop)

**Quick start:** `scripts/start.sh` starts Postgres, Redis, the MCP server, the extractor, the API and the web app, then open <http://localhost:3000> (logs in `logs/`, Ctrl-C stops the servers it started). The steps below are what it does.

1. **Services** (Postgres + pgvector, Redis; data kept in named volumes): `docker compose up -d`
2. **Python env** (once): `python3 -m venv venv && venv/bin/pip install -e "backend[dev]"`. Copy `.env.example` to `.env` and set:
   - `GOOGLE_GENAI_USE_VERTEXAI=true` and `GOOGLE_CLOUD_PROJECT` (Gemini uses your gcloud login: `gcloud auth application-default login`), or `GEMINI_API_KEY` instead.
   - `GOOGLE_CLOUD_LOCATION=global` for the newest Gemini models.
   - The Firebase values (see **Sign-in** below) and `EXTRACTOR_API_KEY` (any long random string, also used by the extractor).
3. **Load the data** (once, and again after re-scraping): `venv/bin/python -m gatorway.ingest` from the repo root. Embeddings run locally and download on first use (progress bar shown); `--embeddings hashing` is an instant offline stand-in. Use the same `EMBED_PROVIDER` for ingest and the MCP server.
4. **MCP server:** `cd backend && ../venv/bin/python -m gatorway.mcp_server`
5. **API:** `cd backend && ../venv/bin/uvicorn gatorway.api.main:create_app --factory --port 8000` (docs at <http://127.0.0.1:8000/docs>). It loads the redaction model in the background at start (about 10 seconds, downloaded once from Hugging Face). `REDACTOR=stub` turns redaction off for tests and demos only.
6. **Extractor:** `cd extractor && ../venv/bin/uvicorn app:create_app --factory --port 8080`. It's a small stateless service, local by default and deployable to Cloud Run (see `extractor/`).
7. **Web app:** `cd frontend && npm install && npm run dev` (http://localhost:3000). It calls the API at `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`); the API allows the origins in `CORS_ORIGINS`.

## Sign-in (Firebase Authentication)

Accounts live in Firebase: the browser signs students in with the Firebase web SDK, and the API verifies the Firebase ID token on every request, then keeps a small local record (uid and email) so saved courses and pathways have an owner. Setup, once:

1. Firebase console, your project: **Build → Authentication → Get started → Sign-in method → Email/Password → Enable**.
2. **Project settings → General → Your apps → Add app → Web**; copy `apiKey`, `authDomain`, `projectId`, `appId` into `.env` as `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, `NEXT_PUBLIC_FIREBASE_APP_ID`, and set `FIREBASE_PROJECT_ID` to the same project id (the API needs only that; no key file).
3. Only `@sfsu.edu` (and subdomain) addresses are accepted, enforced in the browser and again in the API. `REQUIRE_EMAIL_VERIFIED=true` also demands a verified email.

## Tests

- Backend: `cd backend && ../venv/bin/pytest -q` (needs the Postgres container). `RUN_GLINER=1` also runs the real redaction model.
- Extractor: `cd extractor && ../venv/bin/pytest -q`
- Web app: `cd frontend && npm run typecheck && npm run lint && npm test && npm run build`

## Manual end-to-end check (real Gemini and Firebase)

With the stack running: `set -a; . ./.env; set +a; venv/bin/python scripts/smoke_e2e.py`
