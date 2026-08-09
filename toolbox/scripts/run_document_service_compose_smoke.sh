#!/usr/bin/env bash

set -euo pipefail

compose=(docker compose -f compose.yaml)
qdrant_host_port="${QDRANT_HOST_PORT:-6335}"
api_host_port="${API_HOST_PORT:-8010}"
compose_network="ai-engineering-journey_default"
legacy_ollama="ai-journey-ollama"
ollama_network_connected=false

"${compose[@]}" config --quiet
"${compose[@]}" up --build -d qdrant

cleanup() {
  if [[ "$ollama_network_connected" == "true" ]]; then
    docker network disconnect "$compose_network" "$legacy_ollama" >/dev/null 2>&1 || true
  fi
  "${compose[@]}" down --remove-orphans >/dev/null
}
trap cleanup EXIT

if docker inspect "$legacy_ollama" >/dev/null 2>&1; then
  if ! docker network inspect "$compose_network" \
    --format '{{range .Containers}}{{.Name}}{{"\n"}}{{end}}' \
    | rg -qx "$legacy_ollama"; then
    docker network connect "$compose_network" "$legacy_ollama"
    ollama_network_connected=true
  fi
  export DIS_OLLAMA_URL="http://${legacy_ollama}:11434"
fi

"${compose[@]}" up -d api demo-ui

wait_for() {
  local url="$1"
  local attempts=0
  until curl --fail --silent "$url" >/dev/null; do
    attempts=$((attempts + 1))
    if [[ "$attempts" -ge 60 ]]; then
      echo "Timed out waiting for $url" >&2
      "${compose[@]}" ps
      exit 1
    fi
    sleep 2
  done
}

wait_for "http://127.0.0.1:${api_host_port}/v1/health/live"
wait_for "http://127.0.0.1:8501/"
wait_for "http://127.0.0.1:${qdrant_host_port}/readyz"

# Readiness includes host Ollama. A 503 is a real environment failure, not a
# reason to pretend that the query path is ready.
wait_for "http://127.0.0.1:${api_host_port}/v1/health/ready"

collection_snapshot() {
  curl --fail --silent "http://127.0.0.1:${qdrant_host_port}/collections" \
    | python3 -c 'import json, sys; payload=json.load(sys.stdin); print(json.dumps(sorted(item["name"] for item in payload.get("result", {}).get("collections", []))))'
}

before="$(collection_snapshot)"
"${compose[@]}" restart qdrant >/dev/null
wait_for "http://127.0.0.1:${qdrant_host_port}/readyz"
after="$(collection_snapshot)"

if [[ "$before" != "$after" ]]; then
  echo "Qdrant collection snapshot changed after restart" >&2
  exit 1
fi

echo "Compose smoke passed: live, ready, demo UI and Qdrant restart persistence."
