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

"${compose[@]}" up -d api worker demo-ui

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

worker_attempts=0
until "${compose[@]}" ps --status running --services | rg -qx "worker"; do
  worker_attempts=$((worker_attempts + 1))
  if [[ "$worker_attempts" -ge 60 ]]; then
    echo "Timed out waiting for the ingestion worker" >&2
    "${compose[@]}" ps
    exit 1
  fi
  sleep 2
done

sample_pdf="${SMOKE_PDF:-bgts-bilgeadamstaj/04_Canli_Demo/Alperen_Manas_Staj_Programi_1_Hafta.pdf}"
if [[ -f "$sample_pdf" ]]; then
  receipt="$(curl --fail --silent \
    -H 'Idempotency-Key: compose-smoke-upload-001' \
    -H 'X-Tenant-ID: default' \
    -H 'X-ACL-Tags: public' \
    -F "file=@${sample_pdf};type=application/pdf" \
    "http://127.0.0.1:${api_host_port}/v1/documents")"
  job_id="$(printf '%s' "$receipt" | python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')"
  job_attempts=0
  while true; do
    job="$(curl --fail --silent "http://127.0.0.1:${api_host_port}/v1/jobs/${job_id}")"
    job_status="$(printf '%s' "$job" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
    if [[ "$job_status" == "succeeded" ]]; then
      break
    fi
    if [[ "$job_status" == "failed" ]]; then
      printf '%s\n' "$job" >&2
      exit 1
    fi
    job_attempts=$((job_attempts + 1))
    if [[ "$job_attempts" -ge 180 ]]; then
      echo "Timed out waiting for smoke ingestion job ${job_id}" >&2
      exit 1
    fi
    sleep 2
  done
else
  echo "Skipping sample PDF ingestion: ${sample_pdf} does not exist"
fi

# Readiness includes host Ollama. A 503 is a real environment failure, not a
# reason to pretend that the query path is ready.
wait_for "http://127.0.0.1:${api_host_port}/v1/health/ready"

collection_snapshot() {
  curl --fail --silent "http://127.0.0.1:${qdrant_host_port}/collections" \
    | python3 -c 'import json, sys; payload=json.load(sys.stdin); print(json.dumps(sorted(item["name"] for item in payload.get("result", {}).get("collections", []))))'
}

before="$(collection_snapshot)"
before_points="$(curl --fail --silent "http://127.0.0.1:${qdrant_host_port}/collections/document_chunks_v2_bm25" | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"].get("points_count", 0))')"
"${compose[@]}" restart qdrant >/dev/null
wait_for "http://127.0.0.1:${qdrant_host_port}/readyz"
after="$(collection_snapshot)"
after_points="$(curl --fail --silent "http://127.0.0.1:${qdrant_host_port}/collections/document_chunks_v2_bm25" | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"].get("points_count", 0))')"

if [[ "$before" != "$after" ]]; then
  echo "Qdrant collection snapshot changed after restart" >&2
  exit 1
fi

if [[ "$before_points" != "$after_points" ]]; then
  echo "Qdrant point count changed after restart: ${before_points} -> ${after_points}" >&2
  exit 1
fi

echo "Compose smoke passed: live, ready, worker, demo UI, sample ingestion and Qdrant restart persistence."
