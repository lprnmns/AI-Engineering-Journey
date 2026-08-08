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
| 322 test ve strict mypy | Ürün kalite kapısının temeli | Korunacak |

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
- API + Qdrant Compose
- Sade upload/query/source demo UI
- README, API örnekleri, ADR'ler, benchmark raporu ve 20 dakikalık demo

### Zaman Kalırsa

- OpenTelemetry exporter; zorunlu kapsamda önce span uyumlu internal timing bulunacak
- Prometheus endpoint'i
- Ayrı worker container
- Gelişmiş document delete/retention seçenekleri
- Daha güçlü output fact validation
- SBOM ve container security scan genişletmesi

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
│   ├── web/
│   ├── settings.py
│   └── main.py
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
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
- Qdrant `v1.15.4`, named volume
- Dense model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Reranker: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- Yerel LLM: Ollama üzerinde `gemma3:4b`
- Ollama host üzerinde kalacak; API container'ı `host.docker.internal` üzerinden erişecek
- Demo UI: FastAPI'nin sunduğu sade HTML/CSS/JavaScript; ayrı frontend runtime yok

### Job yaklaşımı

İlk MVP'de upload `202 Accepted + job_id` döndürecek. İş, kontrollü ve bounded bir application executor üzerinden yürütülecek. Ayrı worker/Redis sonraki aşamaya bırakılacak. Bu seçimin tek-process sınırlılığı açıkça belgelenecektir.

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
9. Unit ve contract testleri yazılır.
10. Mimari diyagram ve ilk ADR taslakları kaydedilir.

Gün 1 kabul kapısı:

- API açılıyor ve OpenAPI görüntüleniyor.
- Liveness bağımlılık çağırmadan `200` dönüyor.
- Qdrant/Ollama kapalıyken readiness doğru hata durumunu gösteriyor.
- Endpoint içinde retrieval/business logic bulunmuyor.
- Contract testleri response alanlarını sabitliyor.

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
12. Üç tekrar upload ve restart/persistence testleri çalıştırılır.

Gün 2 kabul kapısı:

- Aynı PDF üç kez yüklenince point sayısı artmıyor.
- Aynı içerik ve aynı pipeline aynı version kimliğini döndürüyor.
- Pipeline ayarı değişince yeni version oluşuyor.
- Başarısız ingestion active version'ı bozmuyor.
- Response ve Qdrant payload'ında gerçek sayfa metadata'sı var.

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
7. Candidate listesi bounded tutulur.
8. Cross-encoder reranker isteğe bağlı olarak eklenir.
9. `POST /v1/search` debug endpointi yazılır.
10. A/B/C/D ablation matrisi çalıştırılır:
    - Dense, reranker kapalı
    - Dense, reranker açık
    - Hybrid, reranker kapalı
    - Hybrid, reranker açık
11. Recall, MRR, nDCG ve latency hesaplayıcıları hazırlanır.
12. Raw CSV/JSONL trace kaydedilir.

Gün 3 kabul kapısı:

- Üç retrieval modu aynı corpus ve query sırasıyla çalışıyor.
- Her aday dense/sparse/fusion/rerank rank bilgisini taşıyor.
- Reranker yalnız bounded aday listesine uygulanıyor.
- En az bir exact-term ve bir paraphrase farkı açıklanabiliyor.
- İlk benchmark tekrar üretilebilir raw çıktı bırakıyor.

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
4. Train/validation/test split dondurulur.
5. Threshold yalnız validation üzerinde seçilir.
6. No-answer policy ve reason code'lar API'ye bağlanır.
7. `test_no_answer_skips_llm_call_when_evidence_is_low` yazılır.
8. Source listesi seçilen evidence nesnelerinden üretilir.
9. Structured promptta instruction/data ayrımı uygulanır.
10. Direct ve PDF içi indirect injection vakaları çalıştırılır.
11. Output HTML olarak doğrudan render edilmez.
12. Structured JSON log, request ID ve latency breakdown eklenir.
13. Run manifest; git SHA, model, dataset, config ve donanım bilgisini kaydeder.
14. Final test yalnız bir kez rapor amacıyla çalıştırılır.

Gün 4 kabul kapısı:

- 40+ versionlanmış vaka schema validation'dan geçiyor.
- Threshold final test görülmeden validation üzerinde seçilmiş.
- No-answer durumunda Ollama mock'u çağrılmıyor.
- API source listesi model textinden bağımsız.
- Injection vakaları kayıtlı ve sonuçları raporlanmış.
- Bir request embed/search/rerank/LLM süreleriyle izlenebiliyor.

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
2. API + Qdrant Compose yazılır.
3. Qdrant healthcheck ve API dependency koşulu eklenir.
4. CPU/RAM limiti ve log rotation eklenir.
5. Host Ollama bağlantısı ve Linux ayarı belgelenir.
6. Upload, document seçme, query mode, cevap ve source gösteren sade web UI tamamlanır.
7. README clean setup ve troubleshooting ile yazılır.
8. Curl answer/no-answer/upload örnekleri eklenir.
9. Ruff, mypy, unit, contract, integration ve eval-smoke CI akışı eklenir.
10. Benchmark raporu ve qualitative error analysis tamamlanır.
11. Beş ADR tamamlanır.
12. Compose restart + volume persistence testi yapılır.
13. Temiz kurulum benzeri ayrı ortam testi yapılır.
14. 20 dakikalık demo akışı prova edilir.
15. Repo, raw sonuçlar, rapor ve demo aynı git SHA ile etiketlenir.

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

## 9. ADR Listesi

1. `ADR-001`: Qdrant native sparse/BM25 mi, ayrı BM25 adapter'ı mı?
2. `ADR-002`: RRF parametresi ve tuning politikası
3. `ADR-003`: Ingestion version activation ve retention
4. `ADR-004`: No-answer sinyalleri ve threshold kalibrasyonu
5. `ADR-005`: Ollama host/container sınırı

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

1. Önce kavramı eski sistem üzerinden açıklama
2. Yeni ihtiyacın nedenini örnekle gösterme
3. Küçük tasarım kararı ve beklenen hata senaryosu
4. Kodlama
5. Unit/integration testi
6. Gerçek komut ve ölçüm
7. Sonucu kullanıcının kendi cümlesiyle açıklaması
8. Teknik nota ve AI Engineer terimler PDF'ine ekleme
9. Conventional Commit ve `origin/main` push

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

## 15. İlk Uygulama Adımı

Gün 1 şu soruyla başlayacaktır:

> Terminalde çalışan mevcut RAG kodunu neden doğrudan FastAPI endpointinin içine koymuyoruz?

Bu soru üzerinden katmanların görevini, request lifecycle'ı, dependency injection'ı ve ilk response sözleşmesini kuracağız. İlk commit, çalışan health endpointleri ve framework bilmeyen domain modellerini içerecektir.
