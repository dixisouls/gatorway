# Setup

How to run GatorWay locally (for developers).

## Run it

Needs Docker, Python 3.12, Node, and a Google Cloud login (`gcloud auth application-default login`).

```bash
cp .env.example .env        # set GOOGLE_CLOUD_PROJECT, the Firebase values, EXTRACTOR_API_KEY
docker compose up -d        # Postgres + pgvector, Redis
python3 -m venv venv && venv/bin/pip install -e "backend[dev]"
venv/bin/python -m gatorway.ingest   # load the catalog + local embeddings (first run downloads the model)
scripts/start.sh            # starts the MCP server, extractor, API and web app; open http://localhost:3000
```

**Firebase setup (once):** Console → *Authentication → Get started → Email/Password → Enable*, then *Project settings → Your apps → Web* and copy `apiKey`, `authDomain`, `projectId`, `appId` into `.env` as `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, `NEXT_PUBLIC_FIREBASE_APP_ID`, plus `FIREBASE_PROJECT_ID` (same project id; the API needs no key file).

**Tests:** `cd backend && ../venv/bin/pytest -q` · `cd frontend && npm run typecheck && npm run lint && npm test && npm run build`
