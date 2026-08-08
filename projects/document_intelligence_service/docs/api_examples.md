# API v1 Examples

Base URL: `http://127.0.0.1:8000`

## Health

```bash
curl -i http://127.0.0.1:8000/v1/health/live
curl -i http://127.0.0.1:8000/v1/health/startup
curl -i http://127.0.0.1:8000/v1/health/ready
```

`live` yalnızca API sürecini kontrol eder. `ready` Qdrant ve Ollama gibi zorunlu bağımlılıkları da kontrol eder.

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

Status: `202 Accepted`. Gün 2'nin ilk diliminde kimlik doğrulama ve in-memory job registry çalışır; Qdrant staging ve gerçek worker bir sonraki dilimde bağlanacaktır.

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

## No-answer response

```json
{
  "decision": "no_answer",
  "answer": null,
  "no_answer_reason": "NO_EVIDENCE",
  "sources": [],
  "retrieval": {
    "mode": "hybrid",
    "dense_candidates": 30,
    "sparse_candidates": 30,
    "rrf_candidates": 20,
    "reranked_candidates": 5
  },
  "model": {"provider": null, "model": null},
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
