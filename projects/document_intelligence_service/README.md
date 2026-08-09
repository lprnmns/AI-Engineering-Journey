# Document Intelligence Service

Hafta 1'deki RAG çekirdeğini, PDF kabul eden ve kanıt yolunu görünür kılan
local-first bir servis haline getirir.

## Çalışan topoloji

```text
demo-ui :8501 → api :8000 → SQLite job registry
                    │
                    ├── POST /v1/queries → dense/BM25/RRF → gate → Ollama
                    └── POST /v1/documents → worker → Qdrant :6333

worker ve api aynı image'i kullanır; Ollama API image'ının dışında tek model
runtime olarak `ai-journey-ollama` container'ında çalışır. Qdrant named volume
ile kalıcıdır.
```

Host portları çakışmayı önlemek için varsayılan olarak API `8010`, UI `8501`,
Qdrant `6335`'tir. Container içindeki portlar API `8000`, Qdrant `6333` olarak
kalır.

## Başlatma

Repo kökünden:

```bash
docker compose up --build -d
docker compose ps
curl -i http://127.0.0.1:8010/v1/health/live
curl -i http://127.0.0.1:8010/v1/health/ready
open http://127.0.0.1:8501
```

Readiness `503` ise bu bir “cevap vermeyi dene” durumu değildir. Response içindeki
Qdrant/Ollama check'lerini oku. Varsayılan Compose kurulumu mevcut
`ai-journey-ollama` container'ının aynı ağa bağlı olmasını bekler. Host üzerinde
çalışan Ollama kullanacaksan:

```bash
DIS_OLLAMA_URL=http://host.docker.internal:11434 docker compose up --build -d
```

Smoke script API, worker ve UI'yi açar; örnek PDF'i upload eder, job'ın
`validate → inspect → extract_and_chunk → embed_dense → embed_sparse →
stage_qdrant → verify → activate → complete` timeline'ını bekler ve Qdrant
restart sonrası point count'ın korunduğunu kontrol eder.

32 GB RAM için:

- Ollama ayrı model container'ı olarak çoğaltılmaz.
- Compose API/worker CPU ve RAM limitleriyle çalışır.
- Reranker varsayılan kapalıdır; açılırsa en fazla 20 aday üzerinde çalışır.
- LLM yalnız answerability geçerse çağrılır ve `max_output_tokens` bounded'dır.
- Host portu doluysa `API_HOST_PORT` veya `QDRANT_HOST_PORT` değiştirilebilir.

## API akışı

1. `POST /v1/documents` PDF'i boyut/MIME/magic-byte/sayfa kontrolünden geçirir ve
   `202 + job_id` döndürür.
2. SQLite registry content hash + pipeline fingerprint ile idempotent identity
   tutar. Aynı upload tekrarında aynı document/version receipt'i döner.
3. Worker parent/child chunk üretir, named dense/sparse Qdrant point'lerini
   inactive stage'e yazar, count/metadata doğrular ve sonra active eder.
4. `POST /v1/queries` tenant/ACL/document filtrelerini normalize eder; dense,
   BM25 veya hybrid RRF ile bounded candidate listesi üretir.
5. Reranker açıksa RRF sonrası en fazla 20 aday üzerinde çalışır ve final top-5
   evidence döner.
6. No-answer veya security policy kararında Ollama çağrılmaz. `sources` her
   zaman retrieval'dan gelen canonical evidence nesnelerinden üretilir.

Query için `POST /v1/queries` kullanılır; eski `POST /v1/query` uyumluluk alias'ı
olarak korunur. `POST /v1/search` yalnız retrieval yapar ve `llm_ms=0` döner.

## Sözleşme ve gözlemleme

- Health: `/v1/health/live`, `/v1/health/startup`, `/v1/health/ready`
- Catalog: `/v1/documents`, `/v1/documents/{id}`
- Job: `/v1/jobs/{id}`
- Query/search: `/v1/queries`, `/v1/query`, `/v1/search`
- Metrics: `/v1/metrics`
- Evaluation: `/v1/evaluations/runs`

Job response'unda `attempt_count`, `max_attempts`, `current_stage`, her stage'in
`duration_ms`, input/output özeti, decision ve hata alanları bulunur. Query
trace; request ID, question hash, retrieval adayları, answerability kararı ve
embed/search/rerank/LLM sürelerini JSON log olarak taşır. Audit event'leri
`document.audit` adıyla kabul/activate/fail/delete işlemlerini raw PDF veya raw
soru yazmadan kaydeder.

`/v1/metrics` process-local JSON registry'dir; Prometheus sunucusu değildir.
Worker metrikleri worker logları ve job timeline üzerinden izlenir. Bu local MVP
sınırı bilinçli olarak belgelenmiştir.

## Geliştirme kontrolleri

```bash
.venv/bin/pytest -q projects/document_intelligence_service/tests
.venv/bin/ruff check projects/document_intelligence_service/app projects/document_intelligence_service/eval projects/document_intelligence_service/tests
.venv/bin/mypy projects/document_intelligence_service/app projects/document_intelligence_service/eval projects/document_intelligence_service/tests
docker compose config --quiet
```

## Benchmarkı yeniden üretme

Dedicated Week 2 Qdrant `6335` portunda açık ve benchmark PDF'i section-aware
profil ile indekslenmiş olmalıdır. Worker volume'ündeki `/data/bm25_state.json`
dosyası hostta erişilebilir bir kopyaya alınır; sparse query vocabulary'si ile
ingestion state'i aynı kalmalıdır.

```bash
export DIS_QDRANT_URL=http://127.0.0.1:6335
export DIS_QDRANT_COLLECTION=document_chunks_v2_bm25
export DIS_BM25_STATE_PATH=/tmp/week2-benchmark/bm25_state.json
export DIS_SECTION_MARKER_PROFILE=mentor_program_v1

.venv/bin/python -m projects.document_intelligence_service.eval.run_benchmark \
  --mode hybrid --top-k 5 --point-count 26 \
  --output projects/document_intelligence_service/eval/results/hybrid_baseline.json \
  --raw-output-dir projects/document_intelligence_service/eval/results

.venv/bin/python -m projects.document_intelligence_service.eval.run_evidence_coverage \
  --benchmark projects/document_intelligence_service/eval/results/hybrid_baseline.json \
  --output projects/document_intelligence_service/eval/results/hybrid_evidence_coverage.json
```

Dense/BM25 ve reranker varyantları aynı komutun `--mode`/`--reranker`
seçenekleriyle çalıştırılır. Full A/B/C/D özeti
`eval/results/week2_report_v2/` altında oluşur; bu koşu Ollama çağırmaz.

Ephemeral Qdrant entegrasyon testi yalnız URL verilirse çalışır:

```bash
QDRANT_INTEGRATION_URL=http://127.0.0.1:6333 \
  pytest -q projects/document_intelligence_service/tests/integration
```

## Sınırlar

Bu servis production authentication/authorization, object storage, rate limit,
çoklu worker koordinasyonu, Kubernetes, tıbbi karar ve tool calling iddiasında
bulunmaz. `tenant_id` ve `acl_tags` local ACL-ready filtre sınırıdır; gerçek
request principal/policy store bir sonraki güvenlik kapsamıdır. 44-vakalık golden
set ve mevcut benchmark sonuçları aynı corpus/config için geçerlidir; model,
chunk veya collection değişince yeniden çalıştırılmalıdır.

Detaylı karar kayıtları `docs/adr/`, API örnekleri `docs/api_examples.md`,
benchmark `docs/benchmark_report.md`, security matrisi
`docs/security_attack_matrix_v1.md`, 28 sayfalık kabul matrisi
`docs/acceptance/week2_pdf_acceptance_matrix.md` ve sayfa sayfa görsel inceleme
`docs/acceptance/week2_pdf_visual_review.md` altındadır.
