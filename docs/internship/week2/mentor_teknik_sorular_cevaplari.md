# Hafta 2 Mentor Teknik Soruları — Kanıtlı Kısa Cevaplar

Bu not, cevapları ezber tanım olarak değil, mevcut repo davranışı ve ölçümleri
üzerinden savunmak için hazırlandı.

## 1. BM25 hangi query slice'ında dense'i geçti?

BM25 exact-term/code sorgularında beklenen avantajı verir; dense paraphrase ve
kavramsal sorularda daha güçlüdür. Mevcut 44-vaka benchmarkında genel sonuç
hybrid lehine: dense Recall@5 `0.901`, sparse/BM25 `0.840`, hybrid RRF `0.934`.
Bu yüzden “BM25 her zaman daha iyi” demiyorum; query category slice'ını ve raw
case listesini birlikte gösteriyorum.

Kanıt: `docs/benchmark_report.md`, `eval/results/*_baseline.json`.

## 2. Ham dense ve BM25 skorlarını neden toplamadın?

Cosine ve BM25 skorlarının ölçeği ve dağılımı aynı değil. Ham toplama, bir kolu
sorguya göre tesadüfen baskın yapabilir. Bu nedenle önce rank listeleri korunuyor,
RRF ile `1 / (k + rank)` katkıları birleşiyor; weighted tuning yalnız validation
split'inde yapılmalı.

Kanıt: `app/application/retrieval_service.py`, `docs/adr/ADR-002-rrf-tuning.md`.

## 3. Doğru chunk candidate set'e girmediyse hangi katmanı değiştirirsin?

Önce `candidate_recall@20` ve filtreleri kontrol ederim. Doğru kanıt havuza hiç
girmediyse reranker'ı değiştirmek çözüm değildir; chunking, embedding, BM25,
tenant/ACL/document filter veya candidate limit incelenir. Candidate havuzda
olup final sırada gerideyse reranker/fusion katmanı incelenir.

## 4. Reranker hangi sorguları bozdu?

Mevcut raporda reranker hybrid Recall@5'i `0.934`ten `0.912`ye, MRR@10'u
`0.883`ten `0.833`e düşürdü ve p95'i yaklaşık `28 ms`ten `1128 ms`e çıkardı.
`near_miss` vakaları ve çok kanıt gerektiren sıralamalar riskli örneklerdir.
Bu yüzden reranker varsayılan kapalıdır; yalnız kalite kazanımı ve latency
bütçesi birlikte sağlanırsa açılmalıdır.

Kanıt: `docs/benchmark_report.md`, `eval/results/ablation_summary.json`.

## 5. No-answer threshold hangi split'te seçildi?

Threshold validation split'inde seçilir; final test seçim sürecine dahil edilmez.
Temiz section-aware corpus snapshot'ında validation-only calibration önerisi
`0.330817965` (`0.331`) çıktı ve runtime default buna hizalandı. Bu küçük
validation alt kümesi güçlü genelleme kanıtı değildir; corpus, embedding veya
chunk ayarı değişince eşik yeniden seçilmelidir.

Kanıt: `app/domain/answerability.py`, `eval/results/hybrid_threshold_calibration.json`.

## 6. API source listesi modelden bağımsız nasıl garanti ediliyor?

Ollama yalnız answer text üretir. API `sources` alanını model metninden parse
etmez; `RetrievedChunk` evidence nesnelerinin canonical metadata'sından üretir.
Bu yüzden model uydurma bir source ID yazsa bile API'nin source listesine giremez.

Kanıt: `app/api/v1/queries.py`, `tests/contract/test_resource_contracts.py`.

## 7. Aynı PDF tekrar gelirse identity/version nasıl hesaplanıyor?

Byte içeriğinden SHA-256 `content_hash`, parser/normalizer/chunker/model/schema
ayarlarından `pipeline_fingerprint` üretiliyor. Tenant bu identity'ye dahil.
Aynı `(tenant, content_hash, pipeline_fingerprint)` mevcut receipt'i döndürür;
pipeline değişirse yeni version hazırlanır.

Kanıt: `app/domain/ingestion.py`, `app/infrastructure/storage/sqlite_registry.py`.

## 8. Active version geçişinde yarım indeks nasıl görünmüyor?

Yeni point'ler `is_active=false` olarak stage edilir. Worker expected/actual
point count ve payload metadata'sını doğrular; yalnız başarılı `verify` sonrası
new version active yapılır, önceki version görünmezleştirilir. Başarısız staged
version temizlenebilir; eski active version korunur.

Kanıt: `app/application/ingestion_worker.py`, `app/infrastructure/qdrant/chunk_store.py`, `ADR-003`.

## 9. Loglardan yanlış cevabın yolunu nasıl bulursun?

`request_id` ile query trace aranır. Trace karar, reason code, candidate sayıları,
answerability sinyalleri ve `embed/search/rerank/llm/total` sürelerini verir.
Ingestion tarafında aynı job timeline'ında stage status, duration, input/output
özeti ve decision bulunur. Böylece problem ingestion mı, retrieval mı, model mi
ayrıştırılır.

Kanıt: `app/observability/query_trace.py`, `/v1/jobs/{job_id}`, `/v1/metrics`.

## 10. Dokümanda “önceki talimatları yok say” yazarsa ne olur?

Doküman metni untrusted evidence kabul edilir. `EvidenceSafetyPolicy` yüksek
güvenli indirect injection parçalarını final evidence'tan çıkarır; tüm adaylar
çıkarılırsa LLM çağrılmadan `SECURITY_POLICY` no-answer döner. Structured prompt
DATA ile instruction sınırını ayrıca belirtir.

Kanıt: `app/domain/evidence_safety.py`, `app/infrastructure/ollama/answer_generator.py`.

## 11. Ollama kapalıyken readiness/query ne yapar?

`/v1/health/ready` dependency check ile `503 not_ready` döner. Query retrieval
çalışıp generation sırasında Ollama erişilemiyorsa bu “no-answer” değildir;
safe `503 DEPENDENCY_UNAVAILABLE` döner. Kanıt yetersizse Ollama'ya hiç gidilmez
ve `latency.llm_ms=0` olur.

## 12. Embedding modeli değişirse ne değişir?

Pipeline fingerprint ve run manifest değişir; dense boyutu/schema uyumu startup
ve Qdrant schema kontrolünden geçmelidir. Aynı golden set, aynı corpus snapshot
ve aynı query order ile benchmark tekrar koşulur. Eski version active kalabilir;
yeni version verify edilmeden yayınlanmaz.

Kanıt: `PipelineConfig`, `QdrantSchemaManager`, `eval/reporting.py`, ADR-003.
