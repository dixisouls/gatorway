#!/usr/bin/env bash
# Starts everything locally: Postgres + Redis (docker), MCP server, extractor, API. Ctrl-C stops the three Python servers.
# Usage: scripts/start.sh        Logs: logs/{mcp,extractor,api}.log
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/venv/bin/python"
UVICORN="$ROOT/venv/bin/uvicorn"
[ -x "$PY" ] || { echo "venv missing: run  python3 -m venv venv && venv/bin/pip install -e 'backend[dev]'"; exit 1; }
[ -f .env ] || { echo ".env missing: copy .env.example to .env and fill it in"; exit 1; }

# export .env so the extractor (which does not read .env itself) sees the Vertex settings and its API key
set -a; . ./.env; set +a

mkdir -p logs
PIDS=()
cleanup() {
  echo; echo "Stopping servers..."
  for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null || true; done
  wait 2>/dev/null || true
  echo "Stopped. (Postgres and Redis are left running: docker compose stop to stop them.)"
}
trap cleanup INT TERM EXIT

wait_http() {  # name url seconds
  for _ in $(seq 1 "$3"); do
    curl -s -o /dev/null "$2" && return 0
    sleep 1
  done
  echo "$1 did not come up in $3s, see logs/"; exit 1
}

echo "Starting Postgres + Redis..."
docker compose up -d --wait

echo "Starting MCP server (:8001)..."
(cd backend && exec "$PY" -m gatorway.mcp_server) >logs/mcp.log 2>&1 &
PIDS+=($!)

echo "Starting extractor (:8080)..."
(cd extractor && exec "$UVICORN" app:create_app --factory --port 8080) >logs/extractor.log 2>&1 &
PIDS+=($!)
wait_http extractor http://127.0.0.1:8080/docs 30

# the MCP server loads the local embedding model before it listens, so give it longer
for _ in $(seq 1 90); do
  grep -q "Traceback\|RuntimeError" logs/mcp.log 2>/dev/null && { echo "MCP server failed:"; tail -n 8 logs/mcp.log; exit 1; }
  curl -s -o /dev/null http://127.0.0.1:8001/mcp && break
  sleep 1
done

echo "Starting API (:8000)..."
(cd backend && exec "$UVICORN" gatorway.api.main:create_app --factory --port 8000) >logs/api.log 2>&1 &
PIDS+=($!)
wait_http API http://127.0.0.1:8000/health 30

echo
echo "All up:  API http://127.0.0.1:8000/docs   MCP :8001   extractor :8080"
echo "Logs:    tail -f logs/api.log logs/mcp.log logs/extractor.log"
echo "Ctrl-C to stop."
wait
