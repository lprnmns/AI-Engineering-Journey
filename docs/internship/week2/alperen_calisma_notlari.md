# Alperen'in Hafta 2 Çalışma Notları

Bu dosya, teknik sunum ve mentor görüşmesi öncesinde çalışılacak kısa anlatımları içerir. Kod ezberi yerine sistemin ne yaptığı, nasıl kurulduğu, neden bu şekilde tasarlandığı ve bilinen sınırları kaydedilir.

## 1. Katmanlı mimariyi neden kullanıyoruz?

### Mentora kısa anlatım

> Hafta 1'deki RAG parçalarını katmanlı bir servise dönüştürüyorum. API yalnız doğrulama ve HTTP sözleşmesini yönetiyor. Application katmanı ingestion ve query akışlarını orkestre ediyor. Domain katmanı no-answer ve evidence kararlarını frameworkten bağımsız tutuyor. Qdrant, embedding, reranker ve Ollama ise infrastructure adapter'larında bulunuyor. Böylece yanlış cevabın hangi katmandan kaynaklandığını test ve trace üzerinden ayırabiliyorum.

### Mantığı

- **API:** Dışarıdan gelen isteği doğrular ve HTTP response döndürür.
- **Application:** İşlerin hangi sırayla çalışacağını yönetir.
- **Domain:** No-answer ve evidence gibi iş kararlarını verir.
- **Infrastructure:** Qdrant, embedding modeli, reranker ve Ollama gibi gerçek araçlarla konuşur.

### Neden Qdrant kodunu doğrudan endpoint'e koymuyoruz?

Asıl problem yeni Qdrant sürümünün FastAPI ile teknik olarak uyumsuz olması değildir. Problem, endpoint'in belirli bir araca sıkı bağlanmasıdır.

Qdrant çağrısı doğrudan endpoint içinde olursa:

- Qdrant client veya API sürümü değiştiğinde HTTP katmanını da değiştirmek gerekir.
- Qdrant yerine başka bir vector database denemek zorlaşır.
- Gerçek Qdrant çalıştırmadan query akışını unit test etmek zorlaşır.
- Retrieval hatası ile HTTP/validation hatası birbirine karışır.
- Endpoint validation, retrieval, no-answer ve model çağrısını aynı yerde taşıyan büyük bir fonksiyona dönüşür.

Adapter ayrımı kullanıldığında application yalnız “aday kanıtları getir” sözleşmesini bilir. Qdrant'ın bunu hangi client metodu veya collection şemasıyla yaptığı infrastructure katmanında kalır.

### Kısa cevap

> Sorun doğrudan framework uyumsuzluğu değil, sıkı bağımlılık oluşturmasıdır. Qdrant kodunu endpoint'e koyarsam Qdrant değişikliği API kodunu da etkiler ve katmanları ayrı test edemem. Adapter kullanınca Qdrant değişse bile API ve no-answer kararları aynı kalabilir.

### Örnek

```text
Yanlış yaklaşım:
FastAPI endpoint → doğrudan Qdrant client → threshold → Ollama

Katmanlı yaklaşım:
FastAPI endpoint → QueryService → Retriever portu
                                      ↑
                              Qdrant adapter'ı
```

Qdrant adapter'ını testte sahte bir retriever ile değiştirebiliriz. Böylece Qdrant kapalıyken bile QueryService'in “kanıt yetersizse LLM'i çağırma” kararını test edebiliriz.

## 2. Qdrant nedir ve sistemde ne yapar?

### Mentora kısa anlatım

> Qdrant, RAG sistemindeki vektör veritabanıdır. PDF'ten oluşturduğum chunk metinlerini, bunların embedding vektörlerini ve sayfa/kaynak metadata'sını kalıcı olarak saklıyor. Kullanıcı soru sorduğunda soruyu da embedding'e dönüştürüp en yakın chunk adaylarını Qdrant'tan getiriyorum. Qdrant cevabı yazmıyor; yalnız cevap için kullanılabilecek kanıt adaylarını buluyor.

### Çalışma mantığı

Hafta 1'de mentor PDF'i için:

```text
PDF
→ 7 bölüm
→ 48 chunk
→ her chunk için 384 sayılık embedding
→ Qdrant point
```

Bir Qdrant point kabaca iki bölüm taşır:

```text
vector:
[0.12, -0.48, ..., 0.03]  # Anlamsal aramada kullanılan embedding

payload:
{
  "chunk_id": "local_model_chunk_006",
  "text": "...",
  "section_id": "local_model",
  "page_start": 4,
  "source": "mentor_programi.pdf"
}
```

Kullanıcı soru sorduğunda:

```text
Soru
→ aynı embedding modeliyle 384 sayılık query vector
→ Qdrant cosine benzerlik araması
→ en yakın top-k chunk adayları
```

### Qdrant ne yapmaz?

- Sorunun kesin olarak cevaplanabilir olduğuna karar vermez.
- Nihai cevabı yazmaz.
- Prompt güvenliğini tek başına sağlamaz.
- En yüksek cosine skorlu chunk'ın doğru kanıt olduğunu garanti etmez.

Bu nedenle Qdrant'tan sonra RRF, reranker, answerability policy ve LLM katmanları bulunur.

### Neden yalnız Python listesinde tutmuyoruz?

Python belleğindeki basit vector store öğrenme ve küçük deney için yeterlidir. Qdrant ise ürün tarafında şunları sağlar:

- Uygulama kapanıp açıldığında verilerin kalması
- Çok sayıda vektörde hızlı similarity search
- `document_id`, version, sayfa, tenant ve ACL gibi metadata filtreleri
- Deterministik ID ve idempotent upsert
- Aynı collection içinde dense ve sparse vektörler
- Point sayısı, şema ve payload indexlerinin kontrol edilebilmesi

### Kısa benzetme

> Embedding, her metin parçasının sayısal adresidir. Qdrant bu adresleri ve metin parçalarını saklayan, sorunun adresine yakın kanıtları bulan özel arama deposudur. Gemma ise Qdrant'ın bulduğu kanıtları okuyup cevabı yazan modeldir.

### Yeni haftada Qdrant nasıl genişleyecek?

Hafta 1'de Qdrant'ta temel olarak dense vector ve basit payload vardı. Hafta 2'de:

- Dense ve sparse/BM25 temsilleri birlikte tutulacak.
- Belge ve ingestion version bilgisi eklenecek.
- Yalnız `active` version sorgulanacak.
- Sayfa ve kaynak bilgileri API response'una taşınacak.
- Tenant/ACL/document filtreleri retrieval'dan önce uygulanacak.
- Aynı PDF tekrar yüklenirse duplicate point oluşması engellenecek.

### Tek cümlelik cevap

> Qdrant, RAG sisteminde belge chunklarının vektörlerini ve metadata'sını kalıcı saklayıp kullanıcı sorusuna en yakın kanıt adaylarını getiren vektör veritabanıdır; cevabı kendisi üretmez.

## 3. API sözleşmesini neden koddan önce belirliyoruz?

### Mentora kısa anlatım

> Önce endpoint, request, response ve hata sözleşmesini belirliyorum. Böylece retrieval veya model altyapısı değişse bile kullanıcıya sunduğum API kararlı kalıyor. Her response request ID, retrieval modu, gerçek kaynak listesi ve latency kırılımı taşıdığı için sistemin karar yolunu izleyebiliyorum.

### Request ne taşır?

```text
question         → kullanıcının sorusu
document_ids     → hangi belgelerde aranacağı
retrieval_mode   → dense, bm25 veya hybrid
top_k            → döndürülecek evidence sayısı
include_debug    → kontrollü ortamda skorların gösterimi
```

API katmanı sorunun boş olup olmadığını, retrieval modunun desteklenip desteklenmediğini ve limitlerin güvenli aralıkta olup olmadığını kontrol eder. Hangi chunk'ın doğru olduğuna API karar vermez.

### Response neden yalnız answer alanından oluşmuyor?

Response ayrıca şunları taşır:

- `request_id`: Aynı isteği log ve trace boyunca bulmak için
- `decision`: `answered` veya `no_answer`
- `no_answer.reason_code`: Neden cevap verilmediğini açıklamak için
- `sources`: Gerçek evidence kayıtlarını göstermek için
- `retrieval`: Hangi modun ve kaç adayın kullanıldığını göstermek için
- `model`: Hangi modelin çağrıldığını göstermek için
- `latency_ms`: Embed, search, rerank, LLM ve total sürelerini ayırmak için

Bu sayede “sistem yavaş” veya “yanlış cevap verdi” demek yerine hangi katmanda problem olduğunu araştırabiliriz.

## 4. `model: null` ve `llm latency: 0` neyi kanıtlar?

### Alperen'in açıklaması

> LLM'e hiç uğramadan no-answer döndürdüğünü gösterir. Böylece sistemin kanıt yetersiz olduğunda modeli çağırmama davranışının istediğimiz gibi çalıştığını anlarız.

### Mühendislik ayrımı

Bu değerler **LLM-skip mekanizmasının çalıştığını** kanıtlar. Tek başına bütün kararın doğru olduğunu kanıtlamaz.

İki olasılık vardır:

1. Soru gerçekten kaynak dışıdır: doğru no-answer, yani true negative.
2. Cevap belgede vardır fakat sistem reddetmiştir: yanlış ret, yani false negative.

Bu ayrımı golden evaluation setindeki `answerable` etiketi ve kabul edilebilir evidence kayıtlarıyla ölçeriz.

### Mentora kısa cevap

> `model: null` ve LLM süresinin sıfır olması, answerability kapısının model çağrısından önce çalıştığını ve no-answer durumunda maliyetli üretim adımının atlandığını kanıtlar. Kararın gerçekten doğru ret olup olmadığını ise etiketli evaluation setiyle ayrıca doğrularım.

## 5. Liveness, readiness ve startup health endpointleri

### Üç endpointin görevi

- `GET /v1/health/live`: FastAPI sürecinin cevap verebildiğini gösterir. Dış bağımlılık çağırmaz ve bu yüzden Qdrant kapalı olsa bile süreç hayattaysa `200` döner.
- `GET /v1/health/ready`: Sorgu trafiği için gerekli bağımlılıkları kontrol eder. Qdrant veya Ollama gibi zorunlu bir bileşen kullanılamıyorsa `503` döner.
- `GET /v1/health/startup`: Uygulamanın composition root/lifespan başlangıç işlemlerini tamamlayıp tamamlamadığını gösterir. Başlangıç tamamlanmadıysa `503` döner.

### Neden liveness bağımlılık kontrolü yapmıyor?

Qdrant geçici olarak kapandığında yalnız Qdrant'ı düzeltmek gerekir; FastAPI sürecini yeniden başlatmak problemi çözmez. Liveness'ın Qdrant'ı da kontrol etmesi, geçici bir veritabanı arızasında çalışan API'nin gereksiz yere yeniden başlatılmasına yol açabilir.

### `503` ile `no-answer` ayrımı

Qdrant kapalıysa arama yapılamamıştır. Bu durumda `no-answer` döndürmek yanıltıcı olur; çünkü kanıt aranmış fakat bulunamamış değildir. Doğru sınıflandırma `DEPENDENCY_UNAVAILABLE` ve HTTP `503`'tür.

```text
FastAPI canlı, Qdrant kapalı:
/v1/health/live     → 200
/v1/health/startup  → 200 (başlangıç tamamlandıysa)
/v1/health/ready    → 503
query               → dependency unavailable; no-answer değil
```

### İlk çalışan dikey dilim

Health akışında bağımlılık yönü korunmuştur:

```text
HTTP endpoint → HealthService → HealthProbe portu → HTTP adapter → Qdrant/Ollama
```

Domain katmanı FastAPI veya HTTPX bilmez. `HealthService` yalnız probe sözleşmesini bilir; gerçek Qdrant/Ollama adreslerini infrastructure adapter'ı kontrol eder. Testlerde fake probe verilerek liveness'ın hiç probe çağırmadığı ve readiness arızasında `503` döndüğü kanıtlanmıştır.

### Mentora kısa anlatım

> Liveness sürecin hayatta olduğunu, readiness bağımlılıklarla birlikte trafik kabul edebildiğini, startup ise uygulama başlangıcının tamamlandığını gösterir. Qdrant erişilemiyorsa bunu no-answer olarak gizlemem; çünkü o durumda retrieval hiç çalışmamıştır. Bu nedenle bağımlılık hatasını `503 DEPENDENCY_UNAVAILABLE` olarak ayrı raporlarım.

## 6. Request ID ve ortak hata sözleşmesi

### Request ID neyi çözer?

Her HTTP isteğine `X-Request-ID` atanır. İstemci güvenli biçimde bir ID gönderirse korunur; geçersiz veya aşırı uzun bir değer gelirse sistem yeni bir `req_...` ID üretir. ID response header'da ve hata gövdesinde aynı kalır.

```text
İstek → RequestIdMiddleware → API → Application → Infrastructure
          │
          └── X-Request-ID: req_... → log/trace/audit korelasyonu
```

Bu, “Qdrant yavaş” gibi genel bir iddia yerine aynı isteğin API, retrieval ve model aşamalarını birlikte incelemeyi sağlar.

### Hata envelope'u neden standarttır?

Her endpoint farklı hata biçimi döndürürse istemci ve UI her endpoint için ayrı parser yazmak zorunda kalır. Ortak format şöyledir:

```json
{
  "error": {
    "code": "DEPENDENCY_UNAVAILABLE",
    "message": "Required service is temporarily unavailable",
    "request_id": "error-7"
  }
}
```

`code` makine tarafından işlenebilir, `message` kullanıcıya güvenli açıklamadır, `request_id` ise operasyonel iz sürme içindir. Stack trace, host yolu, bağlantı URL'si ve system prompt response'a sızdırılmaz.

### Hata kodu ile HTTP status aynı şey değildir

- `INVALID_REQUEST` → `400`: İstemci sözleşmeye uymayan veri gönderdi.
- `DOCUMENT_NOT_FOUND` → `404`: İstenen kaynak yok.
- `DOCUMENT_BUSY` / `INGESTION_CONFLICT` → `409`: Kaynak mevcut işlemle çakışıyor.
- `DEPENDENCY_UNAVAILABLE` → `503`: Sistem isteği işlemek için gerekli altyapıya erişemiyor.

HTTP status genel ağ protokolü anlamını, error code ise ürünün daha ayrıntılı iş kararını anlatır.

### Mentora kısa anlatım

> Request ID'yi middleware katmanında üretip response header'a koyuyorum; böylece aynı isteği tüm katmanlarda izleyebiliyorum. Hataları ortak envelope ve kararlı error code'larla döndürüyorum. Validation, conflict ve dependency arızasını birbirine karıştırmıyor; stack trace ve altyapı ayrıntılarını kullanıcıya sızdırmıyorum.

## 7. REST sözleşmesini implementation'dan önce sabitlemek

### İlk endpoint sınırı

```text
POST   /v1/documents              PDF upload → 202 + job_id
GET    /v1/documents              bounded cursor pagination
GET    /v1/documents/{id}         document/version detail
DELETE /v1/documents/{id}         delete veya indexing sırasında 409
GET    /v1/jobs/{job_id}          asynchronous ingestion status
POST   /v1/query                  answer veya structured no-answer
POST   /v1/search                 LLM'siz evidence/debug retrieval
```

### Neden önce sözleşme?

Frontend, test ve ilerideki worker; Qdrant veya embedding adapter'ının iç sınıflarını değil bu HTTP alanlarını kullanır. Bu yüzden önce request alanlarını, status kodlarını, pagination sınırlarını ve response modellerini sabitliyorum. Gün 1'de workflow implementation'ı henüz bağlı olmadığı için geçerli çağrıya sahte başarı dönmüyor; endpoint `FEATURE_NOT_READY` ve `501` ile açıkça scaffold durumunu bildiriyor.

### Query response'ta neden bu kadar alan var?

- `decision`: `answered` veya `no_answer`
- `answer`: Cevap üretildiyse metin; no-answer'da `null`
- `no_answer_reason`: Reddedilme nedeni; answer'da `null`
- `sources`: Cevabın dayandığı gerçek kanıtlar
- `retrieval`: dense/BM25/hybrid ve aday sayıları
- `model`: Çağrılan model; LLM atlandıysa `null`
- `latency`: embedding, search, rerank, LLM ve toplam süre
- `request_id`: Uçtan uca izleme kimliği

Bu alanlar cevabın yalnız metnini değil, sistemin hangi kararı hangi kanıt ve maliyetle verdiğini de açıklamayı sağlar.

### Mentora kısa anlatım

> REST sınırını implementation'dan önce sabitledim. Upload asenkron `202 + job_id`, query senkron, search ise LLM'siz evidence endpointi. Query response'ta answer, source, retrieval, model ve stage latency alanlarını birlikte taşıyorum; böylece yalnız doğru görünen bir metin değil, savunulabilir bir karar izi üretiyorum.

## 8. Gün 1 mimari kanıtları ve ADR yaklaşımı

### Mimari diyagramı nasıl okuyorum?

```text
demo-ui → API → application → domain policy
              ↘ infrastructure adapters → Qdrant/Ollama
```

Ok yönü bağımlılık yönünü anlatır. API, Qdrant'a doğrudan bağlanmaz; application port üzerinden adapter kullanır. Query akışı senkron, ingestion akışı `202 + job_id` ile asenkron tasarlanmıştır.

### Sequence diagramın ana kararı

```text
validate → dense top-30 + sparse top-30 → RRF top-20
         → rerank top-5 → answerability gate
         → LLM answer veya LLM'siz no-answer
```

Bu sıralama önemlidir: LLM kanıt seçmeden çağrılmaz; no-answer kararı üretim modelinin keyfi cevabına bırakılmaz.

### ADR ne işe yarar?

ADR (Architecture Decision Record), yalnız sonucu değil kararın bağlamını, alternatiflerini, ölçümünü ve sınırlarını kaydeder. Örneğin “hybrid retrieval kullandım” demek yerine native Qdrant sparse ile ayrı BM25 adapter'ını hangi Recall/MRR/p95 ölçümleriyle karşılaştıracağımı yazarım.

İlk ADR konuları:

- Qdrant native sparse/BM25 veya ayrı adapter
- RRF parametresi ve tuning politikası
- Ingestion version activation ve retention
- Multi-signal no-answer kalibrasyonu
- Ollama'nın host/container sınırı

### Mentora kısa anlatım

> Mimari diyagramda API, application, domain ve infrastructure sınırlarını ayırdım. Query sequence'te dense+sparse adayları RRF ve reranker'dan geçtikten sonra answerability gate'e giriyor; kanıt yetersizse LLM çağrılmıyor. Her kritik teknoloji kararını alternatif, ölçüm ve bilinen sınırlarıyla ADR olarak kaydediyorum.

## 9. Gün 2 — Content hash ve pipeline fingerprint

### İki kimlik neden ayrı?

`content_hash`, PDF byte'larının SHA-256 özetidir. Aynı byte dizisi aynı hash'i üretir; tek bir byte değişince hash değişir. Bu, “yüklenen içerik gerçekten aynı mı?” sorusunu cevaplar.

`pipeline_fingerprint` ise parser, normalizer, chunker, embedding modeli, reranker ve vector schema gibi üretim ayarlarının canonical JSON üzerinden SHA-256 özetidir. PDF aynı kalsa bile chunker veya embedding modeli değişirse fingerprint değişir.

```text
document identity = content_hash
version identity  = content_hash + pipeline_fingerprint
```

Bu ayrım olmadan model değişikliğinde eski ve yeni vektörleri aynı version sanabilir, sorgularda karışık embedding uzayları kullanabilirdik.

### Upload doğrulama sırası

```text
size limit → MIME allowlist → %PDF magic bytes
          → filename normalization → SHA-256
          → page-aware PDF inspection
```

Ucuz ve güvenlik açısından temel kontroller parser/embedding gibi pahalı işlemlerden önce yapılır. MIME header'a tek başına güvenilmez; `%PDF` magic bytes da kontrol edilir. Dosya adı path traversal izlerini taşısa bile yalnız güvenli basename saklanır.

### Gün 2 ilk teknik dilim

Henüz Qdrant'a yazmadan şu metadata hazırlanıyor:

- güvenli dosya adı
- içerik türü ve byte boyutu
- `content_hash`
- PDF sayfa sayısı
- `pipeline_fingerprint`

Geçersiz dosya `DOCUMENT_PARSE_FAILED`, yanlış MIME `UNSUPPORTED_MEDIA_TYPE`, fazla büyük dosya `UPLOAD_TOO_LARGE` olarak ayrılır.

### Mentora kısa anlatım

> Content hash dosyanın byte kimliğini, pipeline fingerprint ise o dosyadan vektör üretme reçetesini temsil ediyor. Aynı PDF aynı pipeline ile tekrar gelirse idempotent davranabilirim; pipeline değişirse yeni version üretirim. Önce boyut, MIME ve magic bytes kontrolü yapıp sonra page-aware parse'a geçiyorum.

## 10. `202 Accepted`, job ve idempotency akışı

### Upload neden hemen `200` dönmüyor?

PDF'nin parse edilmesi, chunk'lanması, embedding üretilmesi ve Qdrant'a yazılması request süresinden uzun sürebilir. Bu nedenle upload kabulü ile indeksleme tamamlanmasını ayırıyorum:

```text
POST /v1/documents
  → validate + identity + registry
  → 202 Accepted + document_id + version_id + job_id

GET /v1/jobs/{job_id}
  → queued / running / succeeded / failed
```

`202`, isteğin kabul edildiğini; işlemin tamamlandığını değil, anlatır. `200` dönmek burada yanlış bir tamamlandı izlenimi oluştururdu.

### Idempotency nasıl çalışıyor?

Registry iki anahtarı birlikte değerlendiriyor:

- `(content_hash, pipeline_fingerprint)`: Aynı dosya ve aynı üretim reçetesi tekrar gelirse aynı document/version/job receipt döner.
- `Idempotency-Key`: Aynı client request tekrar gönderilirse aynı sonucu döndürür. Aynı key farklı içerikle kullanılırsa `409 INGESTION_CONFLICT` döner.

```text
aynı PDF + aynı pipeline → duplicate job yok
aynı Idempotency-Key + farklı PDF → 409 conflict
```

### Geliştirme adapter'ının sınırı

Şu an registry ve staged PDF byte'ları RAM'de tutuluyor. Bu, akışı test etmek için yeterlidir fakat process restart sonrası job ve içerik kaybolur. Production'a geçmeden önce durable staging/persistence ve ayrı worker eklenmelidir; bu sınırlılık gizlenmemiştir.

### Mentora kısa anlatım

> Upload ile indexing completion'ı ayırdım: `202 + job_id` yalnız kabul anlamına geliyor. Content hash ve pipeline fingerprint duplicate version'ları engelliyor; Idempotency-Key retry güvenliği sağlıyor. Şu an in-memory adapter geliştirme sınırı olarak kullanılıyor, restart-safe durable staging ve worker sonraki adım.
