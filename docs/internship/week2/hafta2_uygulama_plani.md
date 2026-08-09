# Hafta 2 Uygulama Planı — Kurumsal Doküman Bilgi Servisi

**Kaynak program:** Alperen Manas Yapay Zekâ Mühendisliği Gelişim Programı — 2. Hafta

**Sprint süresi:** 5 gün

**Çalışma biçimi:** Local-first, 32 GB RAM, CPU ağırlıklı, yeniden üretilebilir

**Haftanın ana hedefi:** Hafta 1'de kurulan RAG deneylerini dışarıdan PDF kabul eden, ölçülebilen, kaynak gösterebilen ve başka bir geliştiricinin kurabildiği küçük bir ürün çekirdeğine dönüştürmek.

## 1. Mentorun Asıl İsteği

Mentor bizden embedding, Qdrant, reranker ve no-answer parçalarını yeniden keşfetmemizi istemiyor. İstenen değişim şudur:

```text
Hafta 1: Ayrı deneyler ve teknik kanıtlar
                         ↓
Hafta 2: Tek API sözleşmesi altında çalışan ürün çekirdeği
```

Ürün şu zinciri görünür ve ölçülebilir biçimde çalıştırmalıdır:

```text
PDF upload
→ validation
→ content hash + ingestion version
→ parse/normalize/chunk
→ dense + sparse indeks
→ dense/BM25/hybrid retrieval
→ RRF fusion
→ bounded reranker
→ answerability policy
→ Gemma 3 4B veya no-answer
→ canonical source listesi + latency trace
```

Ana mühendislik sorusu her tasarım kararını yönetecektir:

> Sistem yanlış cevap verdiğinde problemin ingestion, retrieval, reranking, answerability, prompt veya model katmanında olduğunu hangi kanıtla ayırabiliyoruz?

## 2. Mevcut Temelden Yeniden Kullanılacaklar

| Hafta 1 çıktısı | Hafta 2'de kullanımı | Durum |
| --- | --- | --- |
| Multilingual MiniLM, 384 dense boyut | Dense retrieval adapter'ı | Uyarlanacak |
| Qdrant kalıcı indeks ve deterministik UUID | Versionlanmış document/chunk repository | Genişletilecek |
| PDF parse, chunk ve parent context | Generic, sayfa metadata'lı ingestion | Genişletilecek |
| Cross-encoder reranker | Bounded top-20 aday üzerinde reranking | Uyarlanacak |
| No-answer ve LLM-skip | Domain evidence policy + reason code | Genişletilecek |
| Gemma 3 4B / Ollama | Kaynaklı cevap üretimi | Yeniden kullanılacak |
| Prompt-injection deneyleri | Versionlanmış attack seti | Genişletilecek |
| Eval ve ham JSON sonuç disiplini | Golden JSONL + run manifest | Genişletilecek |
| Service unit/contract/integration testleri ve strict mypy | Ürün kalite kapısının temeli | Korunacak |

Doğrudan hazır sayılmayacak noktalar:

- Hafta 1'deki belirli başlıklara bağlı parser genel PDF servisi değildir.
- `0.45` evrensel eşik değildir; yeni validation split'inde yeniden seçilecektir.
- Basit hybrid örnekleri ürün seviyesinde Qdrant sparse/BM25 + RRF değildir.
- Dağınık eval vakaları mentorun istediği dengeli 40+ golden JSONL sözleşmesi değildir.
- Terminal demosu FastAPI, upload/job API, structured response ve demo UI yerine geçmez.

## 3. Kapsam Kararı

### Zorunlu MVP

- Katmanlı FastAPI servisi
- PDF upload, validation ve job durumu
- SHA-256 içerik kimliği ve pipeline fingerprint
- İdempotent, versionlanmış ve aktive edilen ingestion
- Qdrant dense + sparse şeması
- Dense-only, BM25-only ve hybrid RRF retrieval
- Bounded cross-encoder reranker
- No-answer reason code ve LLM-skip
- Evidence kayıtlarından üretilen canonical source listesi
- Request ID ve aşama bazlı latency
- 40+ golden JSONL ve attack seti
- Dense/BM25/hybrid/reranker benchmarkı
- API + Qdrant Compose; hedef topolojide aynı image'dan ayrı ingestion worker
- Upload/query/source akışını gösteren ayrı ve sade demo UI
- README, API örnekleri, ADR'ler, benchmark raporu ve 20 dakikalık demo

### Zaman Kalırsa

- OpenTelemetry exporter; zorunlu kapsamda önce span uyumlu internal timing bulunacak
- Prometheus endpoint'i
- Redis-backed dayanıklı queue; worker hedef topolojide kalır, Redis opsiyoneldir
- Gelişmiş document delete/retention seçenekleri
- Basit evidence warning'inin ötesinde gelişmiş output fact validation
- Security scan politikalarının release dışı ortamlara genişletilmesi

### Bu Haftanın Kapsamı Dışında

- Kubernetes ve yüksek erişilebilirlik
- Redis zorunluluğu
- Gerçek multi-tenant authentication sistemi
- Cloud deployment
- Fine-tuning
- Tool calling/agent sistemi
- React gibi ayrı ve ağır frontend
- Tıbbi/klinik ürün entegrasyonu

## 4. Ürün Konumu ve Klasör Yapısı

Ürün, mevcut eğitim laboratuvarlarını bozmadan aşağıdaki bağımsız klasörde geliştirilecektir:

```text
projects/document_intelligence_service/
├── app/
│   ├── api/v1/
│   │   ├── health.py
│   │   ├── documents.py
│   │   ├── jobs.py
│   │   ├── queries.py
│   │   └── search.py
│   ├── application/
│   │   ├── ports.py
│   │   ├── ingestion_service.py
│   │   └── query_service.py
│   ├── domain/
│   │   ├── entities.py
│   │   ├── value_objects.py
│   │   ├── policies.py
│   │   └── errors.py
│   ├── infrastructure/
│   │   ├── qdrant/
│   │   ├── retrieval/
│   │   ├── parsing/
│   │   └── llm/
│   ├── observability/
│   ├── settings.py
│   ├── worker.py
│   └── main.py
├── demo_ui/
│   └── app.py
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   ├── security/
│   └── evaluation/
├── eval/
│   ├── golden.jsonl
│   ├── attacks.jsonl
│   ├── run_eval.py
│   └── results/
├── docs/
│   ├── architecture.md
│   ├── api_examples.md
│   ├── benchmark_report.md
│   └── adr/
├── docker/
├── scripts/
├── compose.yaml
├── Dockerfile
├── .env.example
├── pyproject.toml
└── README.md
```

Bağımlılık yönü:

```text
API → Application → Domain
       ↑
Infrastructure adapter'ları application port'larını uygular
```

Domain katmanı FastAPI, Pydantic, Qdrant, Ollama veya sentence-transformers bilmeyecektir.

## 5. Teknik Kararlar

### Çalışma ortamı

- Python 3.12
- FastAPI + Pydantic v2
- Uvicorn
- Qdrant `v1.18.3`, named volume
- Dense model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Reranker: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- Yerel LLM: Ollama üzerinde `gemma3:4b`
- Ollama host üzerinde kalacak; API container'ı `host.docker.internal` üzerinden erişecek
- Demo UI: mentor diyagramıyla uyumlu, ayrı nginx static `demo-ui` servisi (`:8501`)

### Job yaklaşımı

Upload `202 Accepted + job_id` döndürecek ve sorgu yolu senkron kalırken indeksleme asenkron yürütülecektir. Compose'ta API ile aynı image'i kullanan ayrı ingestion worker'ı ve restart-safe SQLite registry çalışır. Redis PDF'de opsiyonel olduğu için bu local MVP'ye zorunlu dependency yapılmamıştır. Evaluation ve idempotency bu sadeleştirme için azaltılmaz.

Hedef Compose veri akışı:

```text
demo-ui :8501 → api :8000 → worker (index jobs) → qdrant :6333
                         ↘ optional redis
api/worker → ollama host :11434
qdrant → named volume qdrant_data
```

### Hybrid yaklaşımı

Başlangıç adayı Qdrant named dense + sparse vektörler ve rank tabanlı RRF'dir. BM25 motorunun Qdrant native sparse mı yoksa ayrı adapter mı olacağı ADR-001'de resmi doküman ve küçük spike sonucuyla kesinleştirilecektir. Ham dense ve BM25 skorları doğrudan toplanmayacaktır.

### No-answer yaklaşımı

Tek bir magic cosine threshold kullanılmayacaktır. Politika en az şu sinyalleri alacaktır:

- Evidence boş mu?
- Kalibre edilen final/rerank skoru yeterli mi?
- Top-1 ile top-2 margin yeterli mi?
- Gerekli evidence coverage sağlanıyor mu?
- Request belge/ACL filtresinden geçti mi?

Minimum reason code'lar:

- `NO_EVIDENCE`
- `LOW_RELEVANCE`
- `INSUFFICIENT_COVERAGE`
- `DEPENDENCY_UNAVAILABLE`

No-answer response ayrıca hangi `document_ids` üzerinde arama yapıldığını ve eksik kalan kanıt türünü açıklayacaktır. Model cevabındaki sayı ve özel isimlerin evidence içinde bulunmaması durumunda structured warning üretilecek; canonical source listesi hiçbir zaman model metninden parse edilmeyecektir.

## 6. Beş Günlük Uygulama Sırası

### Gün 1 — Sözleşme, Mimari ve Çalışan API İskeleti

Amaç: Kodun geri kalanından önce dış sınırı ve hata davranışını sabitlemek.

Öğrenilecek mantık:

- API, application, domain ve infrastructure neden ayrılır?
- Dependency injection neyi çözer?
- Liveness, readiness ve startup neden farklıdır?
- Neden ağır modeller request sırasında yüklenmez?

Uygulama adımları:

1. Ürün klasörü ve paket iskeleti oluşturulur.
2. Settings ve `.env.example` yazılır.
3. Domain entity, value object ve hata kodlarının ilk sürümü yazılır.
4. Query, source, retrieval, latency ve no-answer response sözleşmeleri yazılır.
5. FastAPI lifespan/container kurulumu yapılır.
6. `/v1/health/live`, `/ready`, `/startup` endpointleri eklenir.
7. Request ID middleware ve kararlı error envelope eklenir.
8. OpenAPI answer/no-answer örnekleri eklenir.
9. Tüm REST sözleşmesi koddan önce sabitlenir: document create/list/detail/delete, job detail, query, search ve opsiyonel evaluation run.
10. Liste endpointinde bounded pagination; production varsayılanında kapalı debug; indexing sürerken delete için `409 DOCUMENT_BUSY` tanımlanır.
11. `INVALID_REQUEST`, `UPLOAD_TOO_LARGE`, `UNSUPPORTED_MEDIA_TYPE`, `DOCUMENT_PARSE_FAILED`, `DOCUMENT_NOT_FOUND`, `INGESTION_CONFLICT` ve `DEPENDENCY_UNAVAILABLE` hata eşlemeleri yazılır.
12. Response'ta stack trace, host path, system prompt ve bağlantı bilgisinin sızmadığı test edilir.
13. Unit ve contract testleri yazılır.
14. Mimari ve sequence diagramı, PDF'deki servis sınırı ve ok yönleriyle yeniden çizilir.
15. İlk ADR taslakları kaydedilir.

Gün 1 kabul kapısı:

- API açılıyor ve OpenAPI görüntüleniyor.
- Liveness bağımlılık çağırmadan `200` dönüyor.
- Qdrant/Ollama kapalıyken readiness doğru hata durumunu gösteriyor.
- Endpoint içinde retrieval/business logic bulunmuyor.
- Contract testleri response alanlarını sabitliyor.
- Endpoint tablosu, status code'lar, pagination ve error envelope OpenAPI'de görünür.

Gün 1 kanıtları:

- OpenAPI JSON/screenshot
- Health curl çıktıları
- Architecture v1
- ADR taslakları
- Test çıktısı

### Gün 2 — Güvenli, İdempotent ve Versionlanmış PDF Ingestion

Amaç: Aynı girdinin kontrolsüz duplicate üretmediği, yarım indeksin görünmediği ingestion akışı.

Öğrenilecek mantık:

- Content hash ile document identity farkı
- Pipeline fingerprint neden gerekir?
- Stage → verify → activate yaklaşımı
- Deterministik point ID ve idempotency arasındaki ilişki
- Page metadata ve kaynak gösterimi

Uygulama adımları:

1. Upload boyutu, MIME, `%PDF` magic bytes ve sayfa limiti doğrulanır.
2. `POST /v1/documents` ve `GET /v1/jobs/{id}` yazılır.
3. SHA-256 `content_hash` hesaplanır.
4. Parser/chunker/model/schema bilgileriyle `pipeline_fingerprint` üretilir.
5. Generic page-aware parser ve normalizer yazılır.
6. Child chunk, parent context, sayfa ve title metadata üretilir.
7. Qdrant named vector/payload şeması oluşturulur ve doğrulanır.
8. Yeni version önce inactive/staged olarak yazılır.
9. Point count ve schema kontrolünden sonra active yapılır.
10. Aynı hash + fingerprint tekrar geldiğinde mevcut document/version döndürülür.
11. `Idempotency-Key` davranışı eklenir.
12. Retry politikası ve aynı job'ın güvenli yeniden çalıştırılma davranışı tanımlanır.
13. `tenant_id → acl_tags → document_id → active version` filtre sırası uygulanır.
14. Kullanıcıdan gelen filter alanları allowlist ile sınırlandırılır.
15. Kaynak döndürülürken request izin filtresi ikinci kez doğrulanır.
16. Qdrant payload'ı; `language`, `created_at`, `text_hash`, `token_count`, parser/chunker/model sürümleri ve warning alanlarını taşır.
17. Üç tekrar upload, retry ve restart/persistence testleri çalıştırılır.

Gün 2 kabul kapısı:

- Aynı PDF üç kez yüklenince point sayısı artmıyor.
- Aynı içerik ve aynı pipeline aynı version kimliğini döndürüyor.
- Pipeline ayarı değişince yeni version oluşuyor.
- Başarısız ingestion active version'ı bozmuyor.
- Response ve Qdrant payload'ında gerçek sayfa metadata'sı var.
- Yarım/başarısız indeks active görünmüyor ve retry duplicate üretmiyor.

Gün 2 kanıtları:

- Schema dump
- Üç upload response'u
- Önce/sonra point count
- Restart sonrası persistence çıktısı
- ADR-003 ingestion versioning

### Gün 3 — Dense, BM25, Hybrid RRF ve Reranker Ablation

Amaç: Varsayılan retrieval yöntemini tahminle değil aynı veri üzerinde ölçerek seçmek.

Öğrenilecek mantık:

- Dense ve lexical retrieval hangi sorgularda ayrışır?
- BM25 neden exact code/ürün adında güçlüdür?
- Ham skorları toplamak neden hatalıdır?
- RRF neyi normalize eder, neyi etmez?
- Candidate recall ile reranker precision farkı

Uygulama adımları:

1. Qdrant sparse/BM25 spike yapılır ve ADR-001 kararı kesinleştirilir.
2. Dense retriever adapter'ı ürün katmanına taşınır.
3. BM25/sparse adapter yazılır.
4. RRF fusion ve trace modeli yazılır.
5. `dense`, `bm25`, `hybrid` modları eklenir.
6. Filtreler retrieval öncesi normalize edilir.
7. Dense ve sparse prefetch ayrı ayrı top-30 ile bounded tutulur; RRF top-20 aday üretir ve reranker final top-5 seçer.
8. Cross-encoder reranker isteğe bağlı olarak eklenir.
9. `POST /v1/search` debug endpointi yazılır.
10. A/B/C/D ablation matrisi çalıştırılır:
    - Dense, reranker kapalı
    - Dense, reranker açık
    - Hybrid, reranker kapalı
    - Hybrid, reranker açık
11. Parent context expansion ve exact-term highlight evidence aşamasında korunur.
12. Recall@1/3/5, Candidate Recall@20, MRR@5/10, nDCG@5/10 ve latency hesaplayıcıları hazırlanır.
13. Kategori ve dil slice'ları ile macro ortalama ayrı raporlanır.
14. İlk 3–5 warm-up query ölçümden çıkarılır; koşu sırası randomize veya query bazında dönüşümlü yürütülür.
15. Timeout/dependency error sonuçları silinmez, `failure_rate` olarak raporlanır.
16. Retrieval p95 `<350 ms`, rerank p95 `<900 ms`; sürekli retrieval `>700 ms` ve baseline'a göre end-to-end `>%30` kötüleşme fail sinyalidir.
17. Mümkün olan metriklerde `%95` bootstrap güven aralığı üretilir; küçük veri nedeniyle sınırı raporda belirtilir.
18. Raw CSV/JSONL trace kaydedilir ve rapor grafikleri script ile yeniden üretilebilir olur.

Gün 3 kabul kapısı:

- Üç retrieval modu aynı corpus ve query sırasıyla çalışıyor.
- Her aday dense/sparse/fusion/rerank rank bilgisini taşıyor.
- Reranker yalnız bounded aday listesine uygulanıyor.
- En az bir exact-term ve bir paraphrase farkı açıklanabiliyor.
- İlk benchmark tekrar üretilebilir raw çıktı bırakıyor.
- Reranker yalnız MRR/nDCG kazanımı ve p95 bütçesi birlikte kabul edilebilirse varsayılan oluyor.

Gün 3 kanıtları:

- Ablation CSV/JSONL
- Recall/MRR/nDCG tablosu
- Latency p50/p95
- İlk flip-positive/flip-negative listesi
- ADR-001 ve ADR-002

### Gün 4 — Golden Dataset, Answerability, Güvenlik ve Observability

Amaç: Sistemin ne zaman cevap vereceğini validation verisiyle seçmek ve hata katmanını trace ile ayırmak.

Öğrenilecek mantık:

- Train/validation/test ayrımı ve data leakage
- Near-miss ile no-answer farkı
- Canonical source neden modelden üretilmez?
- Direct ve indirect prompt injection farkı
- Request ID ve stage latency ile hata teşhisi

Uygulama adımları:

1. En az 40 vakalık `golden.jsonl` tamamlanır.
2. Direct, paraphrase, exact-term, near-miss, no-answer, multi-evidence ve injection sınıfları dengelenir.
3. Her vaka için acceptable/forbidden evidence doğrulanır.
4. Çelişkili/belirsiz vakalar `adjudication` listesine alınır; mentorun kör incelemesi için en az `%20` örnek ayrı manifestte hazırlanır.
5. Train/validation/test split dondurulur.
6. Threshold yalnız validation üzerinde seçilir.
7. No-answer policy ve reason code'lar API'ye bağlanır.
8. `test_no_answer_skips_llm_call_when_evidence_is_low` yazılır.
9. Source listesi seçilen evidence nesnelerinden üretilir.
10. Evidence coverage, retriever agreement ve score margin sinyalleri trace'e eklenir.
11. Structured promptta instruction/data ayrımı uygulanır.
12. Direct injection, PDF içi indirect injection, system-prompt extraction, cross-document leakage, HTML/Markdown exfiltration, RAG poisoning ve DoS upload vakaları çalıştırılır.
13. Source allowlist/provenance, ACL pre-filter/source recheck ve URL/image sanitization kontrolleri eklenir.
14. Tool calling kapalı tutulur; output HTML olarak doğrudan render edilmez.
15. Evidence dışı sayı/özel isim için output-validation warning'i üretilir.
16. Structured JSON log, request ID, stage latency, metric ve audit olayları eklenir.
17. Kullanıcı sorusu varsayılan log alanı olmaz; hash/redaction, sampling, retention ve debug config ile yönetilir.
18. Run manifest; git SHA, corpus snapshot, point count, tüm model/config sürümleri, seed, warm-up ve donanım bilgisini kaydeder.
19. Evaluation koşularında `corpus_snapshot_id` sabitlenir.
20. Final test yalnız bir kez rapor amacıyla çalıştırılır.

Gün 4 kabul kapısı:

- 40+ versionlanmış vaka schema validation'dan geçiyor.
- Threshold final test görülmeden validation üzerinde seçilmiş.
- No-answer durumunda Ollama mock'u çağrılmıyor.
- API source listesi model textinden bağımsız.
- Injection vakaları kayıtlı ve sonuçları raporlanmış.
- Bir request embed/search/rerank/LLM süreleriyle izlenebiliyor.
- `rag_query_duration_ms`, `rag_query_total`, candidate count, no-answer reason, dependency error ve ingestion duration sinyalleri üretilebiliyor.
- Document/version/action/result audit izi bulunuyor.

Gün 4 kanıtları:

- Golden ve attack JSONL
- Split manifest
- Threshold calibration CSV/JSONL
- Attack sonuçları
- Structured log örneği
- ADR-004

### Gün 5 — Compose, Demo UI, CI, Dokümantasyon ve Savunma

Amaç: Başka bir geliştiricinin kurabildiği ve mentor karşısında ölçümlerle savunulabilen teslim.

Öğrenilecek mantık:

- Container healthcheck ile process health farkı
- Named volume ve persistence
- Clean setup testinin gerçek anlamı
- Demo sırasında teori yerine kanıt zinciri gösterme

Uygulama adımları:

1. API Dockerfile hazırlanır.
2. Demo UI `:8501`, API `:8000`, worker ve Qdrant `:6333` hedef topolojisi kurulur; Redis yalnız gerçekten gerekli bulunursa eklenir.
3. API ve worker aynı image digest'ini kullanır.
4. Qdrant healthcheck ve API `depends_on: condition: service_healthy` bağı eklenir.
5. Qdrant named volume, CPU/RAM limiti, log rotation ve graceful shutdown eklenir.
6. Host Ollama `:11434` bağlantısı ve `host.docker.internal` Linux ayarı belgelenir.
7. Upload, document seçme, query mode, cevap ve source gösteren sade UI tamamlanır.
8. README clean setup, troubleshooting ve known limitations ile yazılır.
9. Curl answer/no-answer/upload/list/delete örnekleri eklenir.
10. Ruff, mypy, unit, contract, integration, security scan ve 10-query eval-smoke CI akışı eklenir.
11. Dependency, secret ve container scan eklenir.
12. Image build, SBOM ve git-SHA tabanlı immutable tag release kanıtı hazırlanır.
13. PR şablonuna model/prompt/chunk config değişimi ve evaluation etkisi zorunlu alan olarak eklenir.
14. Benchmark raporu ve en az 5 kazanım/5 kayıp qualitative error analysis tamamlanır.
15. Beş ADR tamamlanır.
16. Compose restart + volume persistence testi yapılır.
17. Temiz kurulum benzeri ayrı ortam testi yapılır.
18. Mentorun 12 teknik görüşme sorusu kod, ölçüm, alternatif ve sınırla cevaplanır.
19. 20 dakikalık demo akışı prova edilir.
20. Repo, raw sonuçlar, rapor ve demo aynı git SHA ile etiketlenir.

Gün 5 kabul kapısı:

- `docker compose up --build -d` ile servis açılıyor.
- Readiness geçmeden demo başlamıyor.
- Restart sonrası dokümanlar kaybolmuyor.
- UI'dan upload → job → query → source akışı çalışıyor.
- README adımları boş/temiz ortam benzeri koşulda doğrulanmış.
- Tüm zorunlu testler ve eval smoke geçiyor.

Gün 5 kanıtları:

- Compose çıktısı ve health curl
- UI ekran görüntüleri
- CI sonucu
- Final benchmark raporu
- 20 dakikalık demo senaryosu
- Known limitations
- Teslim manifesti

## 7. Evaluation Veri Planı

Minimum 40 yerine hata analizi için **44 vaka** hedeflenecektir:

| Sınıf | Hedef |
| --- | ---: |
| Direct fact | 8 |
| Paraphrase | 6 |
| Exact term/code | 6 |
| Near-miss | 6 |
| No-answer | 6 |
| Multi-evidence | 4 |
| Prompt injection | 4 |
| Leakage/ACL hazırlık vakası | 4 |
| **Toplam** | **44** |

Primary eval corpus olarak Hafta 1 ve Hafta 2 mentor PDF'leri birlikte kullanılabilir. Bu seçim:

- tek ve çoklu doküman sorgularını,
- exact code/status değerlerini,
- iki haftanın benzer başlıklarından doğan near-miss riskini,
- cross-document filtreleme davranışını

ölçmeye imkân verir. Klinik Akış verisi bu haftanın benchmarkına karıştırılmayacaktır.

Split ilkesi:

- Geliştirme/train: yaklaşık %50
- Validation: yaklaşık %25; threshold ve tuning yalnız burada
- Test: yaklaşık %25; final rapora kadar dokunulmaz

44 vakada confidence interval zayıf yorumlanacağı için sonuçlar iddialı genellenmeyecek; raw vakalar ve hata örnekleri ana kanıt olacaktır.

## 8. Test Stratejisi

### Unit

- Hash/fingerprint determinismi
- RRF sıralaması
- No-answer policies
- Domain errors
- Filter normalization
- Source construction

### Contract

- OpenAPI snapshot
- Answer/no-answer response modelleri
- Status code ve error envelope
- Pagination ve bounded limitler
- Query response'ta `request_id`, `retrieval_mode`, `sources`, `model` ve stage latency kırılımı
- Source evidence'ta document/version/chunk, sayfa aralığı, excerpt ve dense/sparse/rerank skorları

### Integration

- Ephemeral/local Qdrant collection
- PDF upload → active version
- Duplicate upload
- Qdrant restart/persistence
- Ollama unavailable readiness/query davranışı

### Evaluation

- Dense/BM25/hybrid aynı query sırası
- Reranker on/off ablation
- LLM-skip
- Attack regression
- Slice ve latency raporu

Her anlamlı değişiklikte mevcut repo standardı korunacaktır:

```bash
.venv/bin/pytest -q
.venv/bin/mypy src examples tests labs projects
```

Ruff ürün klasörü oluşturulduğunda kalite kapısına eklenecektir.

Kod standardı:

- Public fonksiyonlar type hint ve kısa docstring taşır.
- Fonksiyonlar tek karar düzeyinde tutulur; endpoint içinde business logic bulunmaz.
- Threshold, model ve candidate limitleri kod içine magic constant olarak gömülmez; settings üzerinden doğrulanır.
- Domain hataları exception sınıflarıyla temsil edilir ve tek API handler ile eşlenir.
- Async yalnız I/O sınırında kullanılır; embedding, reranking ve PDF parse gibi CPU-bound işler thread pool/worker'a offload edilir.
- Test adları davranışı açıkça anlatır.

## 9. ADR Listesi

1. `ADR-001`: Qdrant native sparse/BM25 mi, ayrı BM25 adapter'ı mı?
2. `ADR-002`: RRF parametresi ve tuning politikası
3. `ADR-003`: Ingestion version activation ve retention
4. `ADR-004`: No-answer sinyalleri ve threshold kalibrasyonu
5. `ADR-005`: Ollama host/container sınırı
6. `ADR-006`: Durable SQLite ingestion registry ve worker sınırı
7. `ADR-007`: Privacy-safe metrics, trace ve document audit sınırı

Her ADR şu yapıyı kullanacaktır:

```text
Bağlam → Alternatifler → Karar → Ölçüm/kanıt → Sonuçlar → Bilinen sınır
```

## 10. 20 Dakikalık Demo Planı

| Süre | Gösterim | Ana mesaj |
| --- | --- | --- |
| 0–3 dk | Compose startup + health | Sistem bağımlılıklarını açıkça kontrol ediyor |
| 3–6 dk | PDF upload + job/version | Ingestion izlenebilir ve duplicate-safe |
| 6–10 dk | Exact-code, direct ve paraphrase | Retrieval yöntemi sorgu tipine göre değişiyor |
| 10–13 dk | No-answer + LLM skip | Zayıf kanıtta model çağrılmıyor |
| 13–16 dk | PDF içi injection | Doküman talimat değil, güvenilmeyen veri |
| 16–19 dk | Benchmark + reranker flip | Kararlar ölçümle savunuluyor |
| 19–20 dk | Sınırlar ve sonraki adım | Sonuçlar kapsamından fazla genellenmiyor |

## 11. Öncelik ve Kesme Kuralları

Zaman daralırsa şu sırayla kapsam azaltılır:

1. Ayrı worker ve Redis çıkarılır.
2. OpenTelemetry exporter yerine structured timing/log bırakılır.
3. Gelişmiş UI yerine tek sayfalık işlevsel demo korunur.
4. Opsiyonel evaluation-run API çıkarılır; CLI eval korunur.
5. Gelişmiş delete/retention seçenekleri daraltılır.

Şunlar hiçbir koşulda azaltılmaz:

- Idempotent/versionlanmış ingestion
- Dense/BM25/hybrid karşılaştırması
- 40+ eval ve train/validation/test ayrımı
- No-answer ve LLM-skip
- Canonical sources
- Raw sonuçlar
- Clean setup ve persistence testi

## 12. Riskler ve Önlemler

| Risk | Etki | Önlem |
| --- | --- | --- |
| Qdrant native BM25 sürüm/API uyumsuzluğu | Gün 3 gecikmesi | Gün 1 sonunda küçük spike; adapter fallback ADR'de hazır |
| Model yükleme CPU/RAM baskısı | API readiness/gecikme | Lifespan preload, tek instance, bounded concurrency |
| 44 vakanın etiket kalitesi | Yanlış benchmark | Evidence/page doğrulama ve adjudication listesi |
| Threshold leakage | Geçersiz sonuç | Split manifesti erken dondurulur |
| Container içinden host Ollama erişimi | Demo blokajı | ADR-005 ve erken smoke test |
| PDF parser tabloları bozabilir | Retrieval hatası | Page metadata, warning ve known limitation |
| Beş güne fazla kapsam | Teslim dağılması | Kesme kuralları ve her gün çalışan dikey dilim |

## 13. Çalışma ve Öğrenme Biçimimiz

Her aşamada şu döngü izlenecektir:

1. İlgili resmi kaynağı ve mentor PDF'indeki gereksinimi birlikte kontrol etme
2. Önce kavramı eski sistem üzerinden açıklama
3. Yeni ihtiyacın nedenini örnekle gösterme
4. Küçük tasarım kararı, alternatifi ve beklenen hata senaryosu
5. Kodlama
6. Unit/integration testi
7. Gerçek komut ve ölçüm
8. Sonucu kullanıcının kendi cümlesiyle açıklaması
9. Teknik nota ve AI Engineer terimler PDF'ine ekleme
10. Conventional Commit ve `origin/main` push

Günlük çalışma ritmi mentor takvimine göre tutulacaktır:

- `09:30`: Gün planı ve gate tanımı
- `16:30`: Ölçüm, test ve gün sonu kanıtı
- `17:00`: Teknik not, hata analizi ve ilerleme kaydı

Her gün sonunda kullanıcıya şu dört bilgi verilecektir:

- Bugün ne öğrendik?
- Sistem önce nasıldı, şimdi nasıl?
- Hangi ölçüm/kanıt oluştu?
- Günün ve Hafta 2'nin yüzde kaçı tamamlandı?

## 14. İlerleme Tanımı

Plan hazırlanırken başlangıç konumu:

- Hafta 1'den yeniden kullanılabilir RAG çekirdeği: yaklaşık `%25–30`
- Hafta 2 ürün uygulaması: `%0`

Yüzde dağılımı:

| Bölüm | Ağırlık |
| --- | ---: |
| Gün 1 — Mimari/API | %15 |
| Gün 2 — Ingestion/versioning | %20 |
| Gün 3 — Retrieval/benchmark | %25 |
| Gün 4 — Eval/security/observability | %25 |
| Gün 5 — Ops/UI/docs/demo | %15 |

Bir gün, yalnız kod yazıldığı için tamamlanmış sayılmaz; gün sonu kabul kapısı ve kanıtları oluştuğunda `%100` olur.

## 15. Sayfa 1–28 Uyum Denetimi

Bu tablo PDF'in metni ve tam sayfa görselleri tek tek incelendikten sonra hazırlanmıştır.

| Sayfa | İstenen konu | Plandaki kesin karşılığı |
| ---: | --- | --- |
| 1 | Ürünleştirme, ölçüm, kaynak ve yeniden üretilebilirlik | Ana hedef, zorunlu MVP ve clean setup |
| 2 | Hafta 1 parçalarını tek uygulamada birleştirme; hata katmanını ayırma | Mevcut temel matrisi, katmanlı ürün akışı ve trace |
| 3 | Kanıt/sözleşme/ölçüm/güvenli varsayılan/local-first | Teknik kararlar, API-first, eval ve güvenlik kapıları |
| 4 | Senkron sorgu, asenkron ingestion; Gateway, Ingestion, Query Orchestrator, Qdrant, Answerability, Ollama | Hedef Compose/veri akışı, application servisleri ve ayrı worker hedefi |
| 5 | Query sequence: validate → dense+sparse → RRF top-20 → rerank top-5 → gate → LLM/no-answer | Gün 3–4 sorgu zinciri, bounded aday ve LLM-skip test sınırları |
| 6 | Önerilen klasör ağacı ve bağımlılık yönü | Bağımsız ürün klasörü ve `API → Application → Domain` kuralı |
| 7 | FastAPI lifespan, DI, CPU offload, üç health endpointi, `202 + job_id` | Gün 1 health/lifespan; Gün 2 async job; worker/executor kararı |
| 8 | Tüm REST endpointleri, pagination, idempotency, debug ve delete conflict | Gün 1 tam REST sözleşmesi; Gün 2 Idempotency-Key |
| 9 | Versionlanabilir response ve hata taksonomisi; bilgi sızdırmama | Gün 1 Pydantic contract, hata kodları ve leakage testleri |
| 10 | 8 aşamalı ingestion, pipeline fingerprint, stage/activate ve üç upload testi | Gün 2 ingestion akışı ve acceptance gate |
| 11 | Named dense/sparse, deterministik point ID, payload indexleri ve boyut kontrolü | Gün 2 schema, metadata, startup validation |
| 12 | Metadata sınıfları, ACL/filter sırası, source recheck, corpus snapshot, log gizliliği | Gün 2 filtre/ACL; Gün 4 snapshot ve privacy logging |
| 13 | Dense top-30 + sparse top-30 → RRF top-20 → rerank top-5 → parent evidence | Gün 3 tam hybrid akışı ve debug trace |
| 14 | Query-type/language slice; Recall/MRR/nDCG; p50/p95; 5 kazanım/5 kayıp | Gün 3 benchmark ve Gün 5 error analysis |
| 15 | A/B/C/D reranker ablation, flip positive/negative ve p95 kabul kapısı | Gün 3 ablation matrisi ve reranker varsayılanlık gate'i |
| 16 | Run manifest, warm-up, randomizasyon, bootstrap, failure rate ve bütçeler | Gün 3 benchmark protokolü; Gün 4 run manifest |
| 17 | 40+ dengeli golden set, evidence etiketleri, adjudication ve split/leakage | Evaluation veri planı ve Gün 4 kalite süreci |
| 18 | Çok sinyalli answerability, canonical source ve output warning | No-answer teknik kararı ve Gün 4 output validation |
| 19 | Yedi tehdit sınıfı, structured prompt, tool-off ve defense-in-depth | Gün 4 tam attack matrisi ve güvenli output |
| 20 | JSON log, metric, trace, audit ve PII politikası | Gün 4 observability ve exact metric/audit sinyalleri |
| 21 | `demo-ui:8501`, `api:8000`, worker, Qdrant, optional Redis, host Ollama, volume | Hedef Compose topolojisi ve Gün 5 operasyon adımları |
| 22 | Ruff/type, unit, contract, integration, security, eval, image/SBOM; kod standardı ve PR alanları | Gün 5 CI, scan, SBOM, immutable tag ve PR template |
| 23 | Beş günlük gate takvimi ve 09:30/16:30/17:00 ritmi | Beş günlük sıra, kabul kapıları ve günlük ritim |
| 24 | 10 teslim kalemi ve 6 zorunlu acceptance kriteri | Zorunlu MVP, gün kanıtları ve final teslim manifesti |
| 25 | Teknik review checklist ve 20 dakikalık çalışan demo | Test stratejisi, Gün 5 review ve demo planı |
| 26 | 100 puan rubrik, kritik fail: duplicate/source/leakage/clean setup | Ağırlıklı ilerleme, azaltılamaz kapsam ve kritik testler |
| 27 | 12 teknik görüşme sorusunu ölçüm ve kodla savunma | Gün 5 savunma maddesi ve ADR/benchmark kanıtları |
| 28 | `.env.example`, 5 ADR, resmi kaynaklar ve aynı Git SHA | Settings planı, ADR listesi, resmi kaynak kontrolü ve final tag |

Denetim sonucu: Plan, PDF'in bütün zorunlu teslim ve acceptance kriterlerini kapsar. PDF'in “opsiyonel” dediği `POST /v1/evaluations/runs`, Redis ve ayrı worker için fallback tanımlıdır; ancak hedef mimari görseline uyum için demo UI ve worker topolojisi planın birincil yönü olarak korunmuştur.

## 16. İlk Uygulama Adımı

Gün 1 şu soruyla başlayacaktır:

> Terminalde çalışan mevcut RAG kodunu neden doğrudan FastAPI endpointinin içine koymuyoruz?

Bu soru üzerinden katmanların görevini, request lifecycle'ı, dependency injection'ı ve ilk response sözleşmesini kuracağız. İlk commit, çalışan health endpointleri ve framework bilmeyen domain modellerini içerecektir.
