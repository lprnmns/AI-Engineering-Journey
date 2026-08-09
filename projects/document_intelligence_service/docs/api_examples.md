# API v1 Examples

Base URL: `http://127.0.0.1:8000`

## Health

```bash
curl -i http://127.0.0.1:8000/v1/health/live
curl -i http://127.0.0.1:8000/v1/health/startup
curl -i http://127.0.0.1:8000/v1/health/ready
```

`live` yalnızca API sürecini kontrol eder. `ready` Qdrant ve Ollama gibi zorunlu bağımlılıkları da kontrol eder.

Local durable worker composition'ını açmak için:

```bash
export DIS_INGESTION_REGISTRY_BACKEND=sqlite
export DIS_INGESTION_DATABASE_PATH=data/ingestions.sqlite3
# Generic PDFs: none; mentor PDF family: mentor_program_v1.
export DIS_SECTION_MARKER_PROFILE=mentor_program_v1
# Baseline için false; ölçümlü reranker deneyi için true.
export DIS_RERANKER_ENABLED=false
export DIS_LLM_MODEL=gemma3:4b
export DIS_LLM_MAX_OUTPUT_TOKENS=256
```

## Document upload

```bash
curl -i \
  -H 'Idempotency-Key: upload-demo-001' \
  -F 'file=@sample.pdf;type=application/pdf' \
  http://127.0.0.1:8000/v1/documents
```

Beklenen çalışan akış:

```json
{
  "document_id": "doc_...",
  "version_id": "ver_...",
  "job_id": "job_...",
  "status": "indexing",
  "request_id": "req_..."
}
```

Status: `202 Accepted`. Varsayılan demo/test composition'ı in-memory registry kullanır. SQLite backend seçilirse upload sonrası aynı process'teki bounded background worker stage → verify → activate akışını başlatır; ayrı process queue/recovery politikası sonraki production dilimidir.

## Job status

```bash
curl -i http://127.0.0.1:8000/v1/jobs/job_...
```

## Query

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: mentor-query-001' \
  -d '{
    "question": "Yerel model karşılaştırmasında hangi değerler ölçülmelidir?",
    "retrieval_mode": "hybrid",
    "top_k": 5,
    "include_debug": false
  }' \
  http://127.0.0.1:8000/v1/query
```

## Evidence search

`/v1/search` yalnız retrieval kanıtlarını döndürür; LLM çağırmaz. Local SQLite composition açıkken:

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: search-demo-001' \
  -d '{
    "question": "Yerel model karşılaştırmasında hangi değerler ölçülmelidir?",
    "retrieval_mode": "hybrid",
    "top_k": 5
  }' \
  http://127.0.0.1:8000/v1/search
```

Response'taki `sources` canonical Qdrant payload'ından, `retrieval` ise dense/sparse/RRF trace'inden gelir. `llm_ms` bu endpointte her zaman `0` olmalıdır.

`DIS_RERANKER_ENABLED=true` seçilirse RRF sonrası bounded cross-encoder devreye girer; en fazla 20 adayı skorlayıp en fazla 5 final kaynak döndürür. CPU cold-start ve inference latency'si baseline ile ayrı ölçülmelidir.

Query önce answerability gate'ten geçer. `NO_EVIDENCE` veya `LOW_RELEVANCE` kararında Ollama çağrılmaz ve `llm_ms=0` kalır. Kanıt yeterliyse `gemma3:4b` yalnız bounded evidence prompt'u ile çağrılır. Qdrant/embedding çalıştığı halde Ollama üretimi başarısızsa bu no-answer değildir; güvenli `503 DEPENDENCY_UNAVAILABLE` döner.

Answered response'ta `warnings` alanı, model çıktısının final evidence ile
karşılaştırılmasından doğan structured output/evidence uyarılarını taşır.
İlk sürüm `UNSUPPORTED_NUMBER` koduyla evidence'ta bulunmayan sayıları bildirir.
Bu warning cevabı otomatik olarak reddetmez; `sources` ise her zaman retrieval
payload'ından canonical olarak üretilir.

## No-answer response

```json
{
  "decision": "no_answer",
  "answer": null,
  "no_answer_reason": "LOW_RELEVANCE",
  "sources": [],
  "retrieval": {
    "mode": "hybrid",
    "dense_candidates": 30,
    "sparse_candidates": 30,
    "rrf_candidates": 20,
    "reranked_candidates": 5
  },
  "model": {"provider": null, "model": null},
  "warnings": [],
  "latency": {
    "embedding_ms": 12.4,
    "search_ms": 18.1,
    "rerank_ms": 38.2,
    "llm_ms": 0,
    "total_ms": 70.1
  },
  "request_id": "mentor-query-001"
}
```
