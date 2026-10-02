#!/usr/bin/env bash
# Starts everything locally: Postgres + Redis (docker), MCP server, extractor, API. Ctrl-C stops the three Python servers.
# Usage: scripts/start.sh        Logs: streamed here with a coloured tag per service, and kept in logs/{mcp,extractor,api}.log
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

# coloured log streaming: [DB] blue, [REDIS] red, [MCP] magenta, [EXTRACTOR] yellow, [API] green, [WEB] cyan (plain tags if not a terminal)
if [ -t 1 ]; then C_DB=$'\033[34m'; C_REDIS=$'\033[31m'; C_MCP=$'\033[35m'; C_EXT=$'\033[33m'; C_API=$'\033[32m'; C_WEB=$'\033[36m'; C_OFF=$'\033[0m'
else C_DB=; C_REDIS=; C_MCP=; C_EXT=; C_API=; C_WEB=; C_OFF=; fi
tag() {  # tag COLOR NAME : prefix every line read from stdin
  local color="$1" name="$2" line
  while IFS= read -r line; do printf '%s[%s]%s %s\n' "$color" "$name" "$C_OFF" "$line"; done
}
: > logs/mcp.log; : > logs/extractor.log; : > logs/api.log; : > logs/web.log
tail -n 0 -F logs/mcp.log       > >(tag "$C_MCP" MCP) 2>&1 & PIDS+=($!)
tail -n 0 -F logs/extractor.log > >(tag "$C_EXT" EXTRACTOR) 2>&1 & PIDS+=($!)
tail -n 0 -F logs/api.log       > >(tag "$C_API" API) 2>&1 & PIDS+=($!)
tail -n 0 -F logs/web.log       > >(tag "$C_WEB" WEB) 2>&1 & PIDS+=($!)
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
docker compose logs -f --no-log-prefix --tail 0 db    > >(tag "$C_DB" DB) 2>&1 & PIDS+=($!)
docker compose logs -f --no-log-prefix --tail 0 redis > >(tag "$C_REDIS" REDIS) 2>&1 & PIDS+=($!)

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

if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend dependencies (first run)..."
  (cd frontend && npm install --no-audit --no-fund) >logs/web-install.log 2>&1 || { echo "npm install failed, see logs/web-install.log"; exit 1; }
fi
echo "Starting frontend (:3000)..."
(cd frontend && exec node_modules/.bin/next dev --port 3000) >logs/web.log 2>&1 &
PIDS+=($!)
wait_http frontend http://127.0.0.1:3000 90

echo
echo "All up:  open http://localhost:3000   (API http://127.0.0.1:8000/docs   MCP :8001   extractor :8080)"
echo "Logs are streaming below (also saved in logs/)."
echo "Ctrl-C to stop."
wait
