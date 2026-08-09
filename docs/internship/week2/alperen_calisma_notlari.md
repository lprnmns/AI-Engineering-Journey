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

## 11. Page-aware parent/child chunking

### Eski ve yeni chunk yaklaşımı

Hafta 1'de chunk temel olarak `doc_id + title + text + chunk_index` taşıyordu. Bu, benzerlik araması için yeterliydi fakat production kaynak gösterimi için eksikti.

Hafta 2'de iki seviyeli yapı kullanıyorum:

```text
ParentSection
  ├── section title
  ├── full parent context
  ├── page_start / page_end
  └── ChildChunk 1..n
        ├── retrieval text
        ├── deterministic chunk_id
        ├── parent_id
        ├── page metadata
        └── text_hash
```

Retriever child chunk üzerinde hızlı arama yapar. Cevap üretirken child'ın `parent_id`, title ve sayfa bilgisiyle daha geniş bağlam ve gerçek kaynak döndürülebilir.

### Overlap neden var?

İki cümlelik pencere ve bir cümle overlap örneği:

```text
1–2
  2–3
    3–4
```

Bir bilginin cümle sınırında bölünüp iki chunk'a da anlam kaybettirmesini azaltır. Overlap büyüdükçe recall artabilir fakat duplicate text, embedding maliyeti ve index boyutu da artar; bu yüzden pipeline fingerprint'e chunk size/overlap değerlerini dahil ettim.

### Neden heading tahmin etmiyoruz?

Her PDF aynı tipografik yapıya sahip değildir. İlk sürümde bilinen doküman ailesi için explicit `SectionMarker` kullanıyor, marker yoksa tek document-level parent oluşturuyorum. Her başlığı körlemesine tahmin etmek yerine bu kuralı evaluation ile genişletmek daha savunulabilir.

### Mentora kısa anlatım

> PDF sayfa sınırlarını koruyarak parent section ve child retrieval chunk üretiyorum. Child üzerinde arama yapıp parent context ve page metadata ile kaynak göstereceğim. Sentence overlap bağlam kopmasını azaltıyor; chunk ayarları pipeline fingerprint'e girdiği için ayar değişikliği yeni version oluşturuyor.

## 12. Qdrant named-vector schema ve persistence adapter'ı

### Bu aşamada ne yaptım?

Child chunk'ları yalnız düz bir dense vektör olarak saklamak yerine Qdrant collection sözleşmesini açıkça tanımladım:

```text
ChildChunk
  → dense embedding (384 boyut, cosine)
  → sparse embedding (IDF destekli)
  → named vectors ile Qdrant point
  → kaynak ve version metadata'sı
```

Collection içinde iki ayrı vektör adı bulunuyor:

- `dense`: Embedding modelinin anlamsal yakınlık vektörü.
- `sparse`: Kelime/term tabanlı arama için sparse temsil; BM25/hybrid retrieval'a geçiş noktası.

Qdrant client API'sinde sparse vector, `vectors_config` içine konulmuyor. Dense named vector `vectors_config`, sparse named vector ise `sparse_vectors_config` altında tanımlanıyor. Bu ayrımı küçük bir local probe ve unit test ile doğruladım.

### Payload neden önemli?

Vektör yalnızca benzerlik hesabında kullanılır. Cevabı kaynaklandırmak, aktif belge sürümünü seçmek ve ileride tenant/ACL filtresi uygulamak için point payload'ında şu bilgiler tutuluyor:

```json
{
  "document_id": "doc-1",
  "version_id": "ver-1",
  "parent_id": "doc-1:ver-1:parent:000",
  "source": "guide.pdf",
  "page_start": 2,
  "page_end": 2,
  "is_active": false,
  "pipeline_fingerprint": "..."
}
```

`document_id`, `version_id`, `parent_id`, `source`, sayfa alanları ve `is_active` için payload indexleri planlandı. Böylece retrieval yalnız cosine skoruna bırakılmıyor; belge, sürüm ve erişim kapsamı filtreleriyle sınırlandırılabiliyor.

### Deterministic point ID ve duplicate davranışı

Point ID'yi rastgele üretmek yerine `version_id + chunk_id` üzerinden UUID5 ile deterministik üretiyorum:

```text
aynı version + aynı chunk → aynı Qdrant point ID
retry/upsert → yeni duplicate point yok
farklı version → farklı point ID
```

Bu, ingestion retry'larında aynı chunk'ın çoğalmasını engeller. `pipeline_fingerprint` ise chunk boyutu, overlap ve embedding reçetesi değiştiğinde yeni bir version üretmek için kullanılır.

### Adapter neyi doğruluyor?

- Chunk, dense vector ve sparse vector batch uzunlukları eşleşiyor mu?
- Dense vektör 384 boyutlu mu?
- Sparse index ve value listeleri aynı uzunlukta mı?
- Sparse index değerleri negatif mi?
- Mevcut collection beklenen named-vector schema ile uyumlu mu?

Şema uyuşmazlığında sessizce yanlış veri yazmak yerine startup/ingestion öncesi `QdrantSchemaError` üretiliyor. Bu, “sistem çalışıyor” görünürken yanlış boyutlu veya eksik sparse veriyle retrieval kalitesinin bozulmasını önler.

### Bilinen sınır ve gözlem

Qdrant'ın `:memory:` local client'ında payload indexleri işlevsiz olduğuna dair uyarı görülebilir; bu test ortamının sınırlılığıdır. Gerçek Docker Qdrant üzerinde named dense/sparse collection oluşturma probe'u başarılı oldu. Bu yüzden local unit testte uyarıyı filtreliyor, gerçek servis davranışını ayrıca Docker probe ile kontrol ediyorum.

### Mentora kısa anlatım

> Qdrant'a bağlanmayı endpoint içine gömmek yerine named dense/sparse schema ve chunk store adapter'ı oluşturdum. Dense vektör anlamsal arama, sparse vektör lexical/hybrid arama için ayrılıyor. Point ID'yi version ve chunk'tan deterministik üreterek retry'larda duplicate oluşmasını engelliyorum; payload indexleriyle sayfa, kaynak ve aktif version filtrelenebilir hale geliyor. Schema veya vektör boyutu uyuşmazlığını veri yazmadan önce yakalıyorum.

## 13. Stage → verify → activate worker akışı

### Neden upload endpoint'inden ayırıyoruz?

PDF parse, chunking ve özellikle embedding CPU/RAM tüketir. Bunları HTTP request'in içinde çalıştırmak response süresini ve API'nin kararlılığını bozar. Upload yalnız işi kabul eder; worker aynı `job_id` üzerinden ağır işlemi yürütür.

```text
POST /documents
  → validate + identity + staged bytes
  → 202 + job_id

worker(job_id)
  → page-aware parse/chunk
  → dense + sparse embedding
  → Qdrant inactive points (stage)
  → point count + schema + metadata (verify)
  → önceki version pasif, yeni version active (activate)
  → job succeeded
```

### Stage neden inactive?

Yeni version'ın tüm chunk'ları yazılmadan sorgu trafiğine açılırsa kullanıcı yarım belge üzerinden cevap alabilir. `is_active=false` ile yazılan point'ler doğrulama tamamlanana kadar retrieval kapsamına girmez.

### Verify hangi kanıtları kontrol ediyor?

- Beklenen child chunk sayısı ile Qdrant point sayısı aynı mı?
- Version'a ait bütün point'ler hâlâ inactive mi?
- Dense/sparse collection schema beklenen boyut ve isimlere sahip mi?
- Kaynak, sayfa, text hash, pipeline fingerprint ve active metadata'sı mevcut mu?

Bu kontrolden sonra `VersionVerification.is_valid` true ise activation yapılır. Başarısız parse, embedding veya doğrulama eski active version'ı değiştirmez.

### Worker ile model sınırı

Dense adapter `SentenceTransformerEmbedder` modelini import sırasında değil ilk batch'te lazy yükler. Böylece API process'i açılırken ağır model yüklenmez. Sparse adapter ilk spike için Türkçe Unicode tokenlarını deterministik feature ID'lerine ve term-frequency değerlerine çevirir; Qdrant'ın IDF modifier'ı collection düzeyindeki lexical ağırlığı sağlar.

### Şu anki bilinçli sınır

Worker orchestration'ı gerçek Qdrant adapter'ıyla in-memory registry üzerinde test edildi; API upload'ı henüz ayrı durable worker process'ine otomatik bağlanmadı. Çünkü mevcut registry RAM'de ve process restart sonrası API ile worker aynı job bilgisini paylaşamaz. Bir sonraki adım SQLite/durable staging veya ölçülmüş queue adapter'ı eklemek, sonra worker trigger'ını bağlamaktır.

### Mentora kısa anlatım

> Upload'ı ağır embedding işinden ayırdım. Worker chunk'ları dense ve sparse vektörlerle önce inactive stage ediyor; point count, schema ve kaynak metadata'sını doğrulamadan active etmiyor. Böylece yarım indeks sorguya görünmüyor, retry aynı deterministic point ID'leri güncelliyor ve eski active version başarısız işte korunuyor. Şu an worker gerçek Qdrant adapter'ıyla testli, API-worker arasındaki RAM sınırı için durable persistence bir sonraki adım.

## 14. Restart-safe staging ve job persistence

### RAM registry neden yeterli değildi?

API process'i PDF'yi RAM'de kabul edip ayrı worker process'i başlatırsa worker aynı Python dictionary'lerini göremez. Process restart olduğunda job, idempotency key ve staged PDF de kaybolur. Bu durumda `202` verilmiş bir işin durumunu veya tekrar çalıştırılacak içeriği bulamayız.

Bu nedenle aynı `IngestionRegistry` portuna SQLite adapter'ı ekledim:

```text
API process ─┐
             ├── SQLite file: identity + idempotency + job + PDF bytes
worker ──────┘
```

İki ayrı registry instance'ı aynı database dosyasını açtığında job status, progress, content hash, pipeline fingerprint ve staged PDF tekrar okunabiliyor. `BEGIN IMMEDIATE` ile identity ve idempotency kontrolü tek transaction içinde yapılıyor.

### İki status neden ayrı?

Job'ın `running/succeeded/failed` durumu ile document version'ın `indexing/active/failed` durumu aynı kavram değildir. Worker progress güncellerken upload receipt'in document status'ını yanlışlıkla `running` yapmamak için SQLite tablosunda ikisini ayrı tutuyorum.

### Bilinen sınır

SQLite adapter local single-node dayanıklılık ve worker/API paylaşımı için MVP çözümüdür. PDF byte'larını BLOB olarak tutmak küçük/orta dosyalarda pratiktir; yüksek hacimde object storage, metadata için PostgreSQL ve queue için Redis/başka broker ayrıca ölçülmelidir. Demo composition'ı hâlâ in-memory registry kullanıyor; durable adapter'ın uygulama factory'sine seçilebilir biçimde bağlanması sıradaki adımdır.

### Mentora kısa anlatım

> RAM registry'nin process sınırında çalışmadığını gösterdim ve aynı port için SQLite adapter yazdım. Content/pipeline identity, idempotency key, job progress ve staged PDF aynı transaction-backed dosyada tutuluyor; yeni registry instance'ı restart sonrası aynı job'ı ve içeriği okuyabiliyor. Bu local MVP dayanıklılığıdır; yüksek hacimli production storage/queue kararı ayrıca ölçülecek.

## 15. Registry ve worker composition'ı

### Adapter seçimi nasıl yapılıyor?

API/Application kodu registry'nin hangi teknoloji olduğunu bilmiyor. Composition root ayarı seçiyor:

```text
DIS_INGESTION_REGISTRY_BACKEND=memory
  → InMemoryIngestionRegistry (test/demo)

DIS_INGESTION_REGISTRY_BACKEND=sqlite
  → SqliteIngestionRegistry (local durable)
  → aynı registry ile IngestionWorker
  → upload sonrası bounded background task
```

Bu seçim sayesinde domain ve application akışı değişmeden local demo ile restart-safe çalışma arasında geçiş yapılabiliyor. Qdrant client ve SentenceTransformer modeli yalnız SQLite worker composition'ı oluşturulduğunda bağlanıyor; dense model ise ilk gerçek embedding batch'inde lazy yükleniyor.

### Background task neyi çözüyor, neyi çözmüyor?

Upload request'i bekletilmeden `202` döner ve worker işi aynı process içinde arka planda başlatır. Bu, local geliştirmede gerçek uçtan uca akışı göstermek için yeterlidir. Fakat process kapanırsa çalışan Python task'ı yeniden kuyruğa alınmaz; SQLite job `running` durumda kalabilir. Production için worker polling/recovery, lease/timeout ve retry/backoff politikası eklenmelidir.

### Mentora kısa anlatım

> Registry seçimini composition root'a taşıdım. Testte memory, local dayanıklı çalışmada SQLite kullanılabiliyor; SQLite seçilince API ve bounded worker aynı durable job kaydını paylaşıyor. Upload yine `202` dönüyor, worker arka planda parse, embedding, stage, verify ve activate yapıyor. Bu process içi fallback; process restart recovery ve gerçek queue sonraki üretim adımı.

## 16. Gerçek local ingestion smoke sonucu

Kod testine ek olarak mevcut makinedeki servislerle gerçek bir uçtan uca smoke çalıştırıldı:

```text
PDF: Alperen_Manas_Staj_Programi_1_Hafta 1.pdf
Qdrant: Docker v1.18.3, 127.0.0.1:6333, ready
Embedding: paraphrase-multilingual-MiniLM-L12-v2, cache'ten yüklendi
Registry: temporary SQLite
LLM: çağrılmadı
```

Sonuç:

```text
POST /v1/documents → 202
job status          → succeeded
job progress        → 100
job error           → None
Qdrant total points → 27
Qdrant active       → 27
```

Bu smoke, yalnız unit test fake'lerini değil; gerçek PDF extraction, gerçek 384 boyutlu dense embedding, gerçek sparse encoding, Qdrant named dense/sparse upsert, verify ve activate zincirini doğruluyor. `gemma3:4b` hazır olsa da bu aşamada LLM'e gitmemek bilinçli; ingestion'ın retrieval indexini doğru kurduğunu üretim adımından bağımsız ölçmek istiyoruz.

### Smoke sırasında yakalanan ve düzeltilen hata

İlk gerçek denemede SQLite satırına `document_status=indexing` değeri yanlışlıkla `job_status` alanına da yazılmıştı. Worker `JobStatus('indexing')` okuyamayınca hata verdi. `document_status` ve `job_status` insert değerleri ayrıştırıldı; regression testi ilk kabulden sonra job'ın `queued`, worker sonrasında `succeeded` olduğunu kontrol ediyor. Bu, gerçek ortam testinin unit testlerin yakalayamadığı bir wiring hatasını bulduğunu gösteriyor.

### Mentora kısa anlatım

> Fake testlerin üstüne gerçek PDF ile smoke yaptım. API `202` döndü, SQLite job yüzde yüz tamamlandı ve Qdrant named dense/sparse collection'ına 27 point yazılıp 27'si active oldu. LLM'i bu ölçümde çağırmadım; önce ingestion/indexing zincirini izole doğruladım. İlk smoke'ta job/document status alanlarının karıştığını bulup düzelttim ve regression testi ekledim.

## 17. Dense, sparse ve hybrid RRF retrieval

### Search katmanında ne değişti?

Ingestion ile Qdrant'a yazılan active child chunk'lar artık soru üzerinden aranabiliyor:

```text
soru
 ├── dense embedding → Qdrant named dense → semantic adaylar
 ├── sparse encoding → Qdrant named sparse/IDF → lexical adaylar
 └── iki rank listesi → RRF fusion → top-k evidence
```

Dense ve sparse skorlarını doğrudan toplamadım. Çünkü cosine skoru ile sparse lexical skor aynı ölçekte değildir. Her listenin rank'ına göre:

```text
RRF katkısı = 1 / (k + rank)
```

şeklinde puan veriliyor. Aynı chunk iki listede de üst sıralardaysa fusion avantajı kazanıyor. `source_id`, dense rank, sparse rank ve fused score trace içinde korunuyor.

### Güvenlik ve filtre davranışı

Qdrant retriever yalnız `is_active=true` point'leri arıyor. `document_ids` verilirse arama öncesinde Qdrant payload filtresine ekleniyor. `tenant_id` ve `acl_tags` henüz payload/authorization katmanına bağlanmadığı için sessizce yok sayılmıyor; endpoint açıkça `FEATURE_NOT_READY` döndürüyor.

### `/v1/search` neden ayrı?

Search, LLM'e gitmeden retrieval kalitesini ölçmek için evidence-only endpoint. Böylece “cevap kötü” demeden önce dense, sparse ve RRF'nin hangi chunk'ı seçtiği görülebiliyor. `llm_ms=0`; latency embedding ve Qdrant search aşamalarına ayrılıyor.

### Gerçek local search smoke sonucu

Mevcut Qdrant collection'ındaki 27 active point üzerinde şu soru çalıştırıldı:

```text
Soru: Yerel model karşılaştırmasında hangi değerler ölçülmelidir?
Mode: hybrid, top_k: 5
HTTP: 200
dense_candidates: 27
sparse_candidates: 15
rrf_candidates: 27
sources: 5
llm_ms: 0
```

İlk source sayfa `1`, belge adı ve chunk snippet'i ile döndü. Bu sonuç retrieval zincirinin gerçek model/cache, gerçek Qdrant ve canonical payload üzerinden çalıştığını gösteriyor. Baseline smoke'ta reranker varsayılan kapalı olduğu için `reranked_candidates=0` beklenen durum; reranker açık smoke'u sonraki bölümde ayrıca kaydedildi.

### Mentora kısa anlatım

> `/v1/search` ile LLM'siz evidence araması ekledim. Soru aynı anda 384 boyutlu dense embedding ve deterministic sparse representation'a gidiyor; Qdrant yalnız active version point'lerini getiriyor. Dense ve sparse ham skorlarını toplamak yerine rank tabanlı RRF ile birleştiriyorum. Gerçek smoke'ta 27 dense, 15 sparse adaydan 27 birleşik aday üretip 5 kaynak döndürdüm; LLM süresi sıfır.

## 18. Bounded cross-encoder reranker

### Reranker neden Qdrant'ın yerine geçmiyor?

Qdrant hızlı aday üretir; dense/sparse arama top-30 civarında recall'ı korumaya çalışır. Cross-encoder ise soru ve chunk metnini birlikte okuyarak daha pahalı ama daha hassas bir relevance skoru üretir. Qdrant'a hiç girmemiş bir chunk'ı bulamaz; bu nedenle yalnız bounded candidate window üzerinde çalışır.

```text
dense top-30 + sparse top-30
  → RRF top-20 window
  → cross-encoder rerank
  → final top-5 evidence
```

`CrossEncoderReranker` modeli import/startup sırasında yüklenmiyor. İlk rerank batch'inde lazy yükleniyor; böylece API'nin health açılışı ağır model yüzünden beklemiyor. `rerank_score` ham dense/sparse/fusion skorundan ayrı tutuluyor.

### Neden varsayılan kapalı?

Reranker kaliteyi artırabilir fakat CPU latency ve model belleği maliyeti getirir. Bu yüzden `DIS_RERANKER_ENABLED=false` baseline'ı koruyor; `true` ile aynı corpus/query üzerinde ablation yapılabiliyor. “Reranker daha iyi” kararı ancak Recall/MRR/nDCG kazanımı ile p50/p95 latency birlikte ölçülürse verilecek.

### Gerçek local reranker smoke sonucu

Mevcut 27 active Qdrant point üzerinde aynı hybrid soru reranker açıkken çalıştırıldı:

```text
dense_candidates: 27
sparse_candidates: 15
rrf_candidates: 27
reranked_candidates: 5
sources: 5
llm_ms: 0
first source score: -3.6436679363250732
```

İlk score'un negatif olması hata değildir; cross-encoder çıktısı cosine similarity gibi [0,1] aralığında olmak zorunda değildir. Bu skor yalnız aynı reranker modeli ve aynı çalışma koşulları içindeki sıralama için anlamlıdır. Cold CPU çalışması baseline search'ten belirgin biçimde pahalı olduğu için reranker'ı varsayılan yapmadan benchmarklamak gerekiyor.

### Mentora kısa anlatım

> Qdrant'tan gelen adayları doğrudan LLM'e vermek yerine RRF sonrası en fazla 20 chunk'ı cross-encoder ile yeniden sıralıyorum ve finalde en fazla 5 kaynak bırakıyorum. Model lazy yükleniyor. Reranker skorunun negatif olabileceğini, mutlak cosine gibi yorumlanmaması gerektiğini biliyorum. CPU maliyeti nedeniyle baseline kapalı; aynı golden set üzerinde kalite ve p95 latency ölçülmeden varsayılan seçmeyeceğim.

## 19. Query akışı: answerability gate ve LLM-skip

### Search ile query farkı

`/v1/search` yalnızca retrieval kanıtını ölçer; `/v1/query` ise bunun üstüne karar ve üretim katmanı ekler:

```text
POST /v1/query
  → request validation
  → dense + sparse retrieval
  → RRF top-20 / opsiyonel rerank top-5
  → answerability gate
      ├─ zayıf/boş evidence → no_answer, Ollama çağrısı yok
      └─ yeterli evidence → bounded prompt → Ollama/Gemma → answered
```

No-answer kararını LLM'e sormuyorum. Çünkü modelden “bu soruya cevap verebilir misin?” diye istemek hem gereksiz latency üretir hem de modelin zayıf kanıtı güvenilir sanmasına izin verebilir. Gate, önce Qdrant'tan gelen kanıt sayısını ve ham skor türünü inceliyor; hybrid akışında RRF skorunu cosine gibi yorumlamamak için dense ham skorunu ayrı taşıyor.

### Çoklu sinyalin mevcut sınırı

Domain policy şu sinyalleri üretiyor:

- evidence sayısı ve boşluk durumu,
- dense/sparse/rerank skor türü ve top score,
- top-1/top-2 margin,
- soru terimleri ile evidence arasındaki lexical coverage,
- filter'ların gerçekten uygulanıp uygulanmadığı.

İlk provisional gate'te local corpus üzerinde dense alt sınırı `0.45`, sparse alt sınırı `0.1`, reranker alt sınırı `-5.0`. Margin ve coverage trace'e yazılıyor fakat yeterli golden validation set oluşmadan agresif rejection eşiği yapılmıyor. Bu ayrım “kodda threshold var” ile “threshold kalibre edildi” arasındaki farkı koruyor.

### Gerçek no-answer smoke

```text
Soru: Stajyer maaşı ne kadar?
HTTP: 200
Karar: no_answer
Neden: LOW_RELEVANCE
dense_candidates: 27
sparse_candidates: 9
rrf_candidates: 27
sources: []
model: null
llm_ms: 0
```

Bu sonuçta Qdrant ve embedding çalıştı; soru corpus tarafından desteklenmediği için Gemma'ya hiç gidilmedi. Bu nedenle `no_answer`, dependency failure değildir.

### Gerçek answered smoke

```text
Soru: Yerel model karşılaştırmasında hangi değerler ölçülmelidir?
HTTP: 200
Karar: answered
Model: ollama / gemma3:4b
Kaynak: 2 canonical source
embedding_ms: 23345.7
llm_ms: 62921.0
total_ms: 86324.8
```

Model yalnız gate'i geçen evidence ile bounded prompt üzerinden çağrıldı ve kaynak listesi retrieval payload'ından üretildi; model metninden source parse edilmedi. Bu smoke HTTP/orkestrasyon kanıtıdır, cevap doğruluğu kabulü değildir: Gemma'nın döndürdüğü cümle beklenen “ilk cevap süresi/toplam süre/bellek/doğruluk...” listesini tam karşılamadı. Bu, `answered` kararının yalnızca evidence eşiğinin geçildiğini gösterdiğini; answer quality için ayrıca golden expected-phrase/evidence değerlendirmesi gerektiğini gösteriyor. CPU local çalışmada yaklaşık 63 saniyelik generation latency gözlendi. `DIS_LLM_MAX_OUTPUT_TOKENS=256` ve 8.000 karakter evidence bütçesi RAM/context kontrolü için ayarlanabilir; cold embedding ile warm embedding ayrı benchmarklanmalıdır.

### Mentora kısa anlatım

> `/v1/search` retrieval debug endpointi, `/v1/query` ise karar + üretim endpointi. Query'de önce dense/sparse/RRF evidence'i alıp domain answerability gate'ten geçiriyorum. “Stajyer maaşı” gibi corpus dışı soruda karar `LOW_RELEVANCE`, kaynak listesi boş ve `llm_ms=0`; yani model gereksiz yere çağrılmıyor. Desteklenen soruda gate geçiyor, bounded evidence prompt'u ile host'taki `gemma3:4b` çağrılıyor ve canonical source'lar retrieval'dan dönüyor. İlk local ölçümde LLM yaklaşık 63 saniye sürdü; bu yüzden token/context bütçesi ve cold/warm benchmarkı sonraki acceptance gate.

## 20. Section-aware ingestion düzeltmesi

### Önceki durum

İlk gerçek ingestion smoke'unda mentor PDF'i tek bir document-level parent altında işlendi. Bu parent'ın altına 27 child chunk yazıldı. Sistem teknik olarak çalışıyordu; fakat retrieval bir section sınırını aşan veya farklı konuların aynı parent içinde birleştiği bağlamları seçebiliyordu. Bu nedenle PDF'in bilinen yapısını ingestion aşamasında kaybetmemek gerekiyordu.

### Yeni yaklaşım

Section marker davranışını kodun içine sabit gömmek yerine açık bir profil yaptım:

```text
section_marker_profile=none
  → bilinmeyen/genel PDF'ler
  → güvenli document-level parent davranışı

section_marker_profile=mentor_program_v1
  → mentor PDF ailesinin bilinen başlıkları
  → purpose, model_fundamentals, embedding, rag,
    local_model, corporate_problem, deliverables
  → section-level parent'lar
```

Profil `PipelineConfig` fingerprint'inin parçası. Aynı PDF byte'ı markersız ve section-aware işlense bile iki index aynı pipeline version kabul edilmiyor. Böylece eski, daha zayıf index'in yeni section-aware index'in yerine yanlışlıkla active kalması engelleniyor.

### Gerçek smoke sonucu

Mentor PDF'i `mentor_program_v1` profiliyle yeniden işlendi:

```text
job_status: succeeded
progress: 100
parent_count: 7
active_points: 26
active_version: ver_fd69f03d0a6c65a686e6b8c9f210487489cb12772e5a79d8771e835849796c
sections: purpose, model_fundamentals, embedding, rag,
          local_model, corporate_problem, deliverables
```

Reranker açık retrieval smoke'unda 26 dense aday, 13 sparse aday ve 26 RRF adayı oluştu; final bounded sonuçta `local_model` section'ı en üst kaynağa çıktı. Bu, section bilgisinin yalnızca metadata olarak saklanmadığını, retrieval kararını etkileyebildiğini gösteriyor.

### Context bütçesi ile candidate window ayrımı

Retrieval tarafında recall kaybetmemek için daha geniş bir aday penceresi tutulabilir; fakat LLM'e gönderilen evidence daha küçük ve kontrollü olmalıdır:

```text
dense/sparse adayları
  → RRF candidate window
  → opsiyonel reranker
  → final evidence top-2/top-5
  → bounded LLM context
```

Gerçek CPU smoke'unda top-5 evidence ile Ollama generation timeout'a girdi; top-2 evidence ile doğru cevap üretilebildi. Bu yüzden “retrieval'da daha çok aday” ile “LLM prompt'una daha çok metin” aynı karar değildir. Birincisi recall için, ikincisi cevap üretim maliyeti ve dikkat bütçesi için yönetilir.

### Sınırlama ve sonraki ölçüm

Section marker profili bu mentor PDF'i için bilinçli ve güvenilir bir adapter'dır; her PDF'e uygulanacak genel başlık çıkarma çözümü değildir. Yeni doküman ailelerinde marker profili doğrulanmadan kullanılmamalıdır. Sıradaki evaluation benchmark'ta section-aware ve document-level ingestion aynı golden sorular üzerinde Recall@k, MRR, nDCG, no-answer hata oranları ve p50/p95 latency ile karşılaştırılacaktır.

### Mentora kısa anlatım

> İlk ingestion'da mentor PDF'i tek parent ve 27 child point olarak indeksleniyordu. Bilinen başlıkları `mentor_program_v1` marker profiline taşıdım; şimdi 7 section parent ve 26 active point oluşuyor. Profil pipeline fingerprint'e girdiği için eski markersız index ile yeni index karışmıyor. Reranker `local_model` section'ını seçebiliyor. Ayrıca retrieval candidate window ile LLM context window'u ayırdım; top-5 CPU'da timeout olurken top-2 bounded context ile smoke tamamlandı. Bundan sonra bu iyileştirmeyi golden benchmark ile sayısal olarak doğrulayacağım.

## 21. Evaluation benchmark sözleşmesi ve ilk ölçüm altyapısı

### Önceki durum

Şimdiye kadar retrieval kalitesi birkaç seçilmiş demo sorusu ve ham smoke çıktısıyla kontrol ediliyordu. Bu, sistemin çalıştığını gösterir; fakat “kaç soruda doğru section ilk 5'e girdi?”, “reranker aday havuzunda doğru kanıtı korudu mu?” ve “no-answer hangi yönde hata yaptı?” sorularını cevaplamaz. Ayrıca reranker açıkken top-20 aday penceresi ile final top-5 evidence aynı nesne gibi izleniyordu.

### Golden vaka sözleşmesi

`data/evaluations/mentor_program_pdf_rag_golden_v1.jsonl` içinde 44 versionlanabilir vaka tanımladım:

```text
direct_fact       8
paraphrase        6
exact_term        6
near_miss         6
no_answer         6
multi_evidence    4
prompt_injection  4
leakage_acl       4
```

Her vaka en az şu bilgileri taşır:

```text
id, split, category, question, expected_answerable,
relevant_sections veya relevant_document_ids,
expected_phrases, forbidden_phrases
```

Çocuk chunk ID'si yerine section adı (`rag`, `local_model` gibi) gold hedefi olarak kullanılabiliyor. Çünkü pipeline version değişince generated point ID değişebilir; fakat mentor PDF'inin bilgi section'ı aynı kalır. `multi_evidence` vakalarında birden fazla section bekleniyor. `prompt_injection` ve `leakage_acl` vakaları cevap üretme yetkisi olmayan istekleri temsil ediyor; ACL özelliği henüz bağlı olmadığı için bunlar hazırlık/regression vakasıdır.

### Ölçülen metrikler

```text
Recall@1/3/5
Candidate Recall@20     → reranker öncesi aday havuzunun kapsaması
MRR@5/10                → ilk doğru kanıtın sırası
nDCG@5/10               → birden fazla kanıt ve graded relevance
p50/p95 latency         → toplam, embedding, search, rerank
```

Bir section'a ait birden fazla child chunk aynı hedef olarak sayılıyor; aksi halde overlap nedeniyle recall yapay biçimde yüksek görünürdü. `no_answer_false_positive`, answerable soruyu gereksiz reddetmeyi; `no_answer_false_negative`, corpus dışı soruya cevap vermeyi ifade ediyor. Bu iki yönü özellikle ayrı raporluyorum.

### Benchmark akışı

```text
golden JSONL
  → schema/balance validation
  → warm-up soruları (kalite hesabı dışında)
  → dense / bm25 / hybrid aynı soru sırası
  → candidate window raw trace
  → final evidence raw trace
  → Recall/MRR/nDCG + p50/p95
  → JSONL/CSV error analysis
```

Runner, warm-up sorgularını ölçümden çıkarıyor; her vaka için final adayları, reranker öncesi candidate window'u ve embedding/search/rerank/toplam süreleri saklıyor. Böylece yalnız özet skor değil, hangi sorunun neden kaybedildiği de incelenebilecek.

### Bu aşamadaki kanıt ve sınır

Bu aşamada golden dataset sözleşmesi, metrik hesaplayıcıları, runner ve retrieval domain trace'i unit testlerle doğrulandı. `44` vaka şema ve kategori dengesi kontrolünden geçiyor; ilgili testler ve mypy temiz. O sırada gerçek Qdrant ablation sayıları henüz yoktu; sonraki koşuda aynı active snapshot üzerinde ölçülerek aşağıdaki karar üretildi.

### Mentora kısa anlatım

> Demo sorularını 44 vakalık versionlanmış golden JSONL sözleşmesine dönüştürdüm. Direct, paraphrase, exact-term, near-miss, no-answer, multi-evidence ve injection/ACL hazırlık sınıfları var; development/validation/test split'i ayrılıyor. Retrieval için Recall@k, candidate Recall@20, MRR, nDCG; sistem davranışı için no-answer hata yönleri ve p50/p95 latency ölçtüm. Reranker öncesi aday penceresini final evidence'tan ayrı trace ediyorum. Altyapı contract testlerinden sonra gerçek Qdrant ablation ile hybrid'in bu snapshot'ta en iyi kalite/latency dengesini verdiğini gösterdim.

## 22. Gerçek retrieval ablation ve gate sonucu

### Aynı deney koşulu

44 golden vaka aynı sırayla çalıştırıldı; ilk 3 warm-up soru kalite hesabına alınmadı. Active Qdrant snapshot'ında 26 active point vardı, eski 27 point inactive durumdaydı. Dört retrieval koşusu ve bir no-answer gate koşusu aynı `git_sha=928e608` ile raw JSON olarak kaydedildi. Ollama hiç çağrılmadı.

### Sonuç tablosu

```text
Strategy              Recall@5  MRR@10  nDCG@10  Candidate@20  p95
Dense                 0.901     0.875   0.930    0.993          25.2 ms
Sparse/IDF            0.840     0.778   0.860    0.987           3.5 ms
Hybrid RRF            0.934     0.883   0.963    0.993          28.1 ms
Dense + reranker      0.912     0.836   0.933    0.993        1224.6 ms
Hybrid + reranker     0.912     0.833   0.933    0.993        1128.5 ms
```

Bu tablo “büyük model veya ekstra katman mutlaka daha iyi” varsayımını kırıyor. Hybrid en iyi kalite/latency dengesini verdi. Reranker doğru section'ı aday havuzundan silmiyor; Candidate Recall@20 aynı kalıyor. Fakat final top-5 sıralamasında bazı kanıtları aşağı itiyor ve CPU maliyeti yaklaşık 40 kat büyüyor. Bu yüzden varsayılan kapalı kaldı.

### Gate sonucu

Hybrid + validation'dan seçilen dense threshold ile, LLM'siz gate smoke'u:

```text
answerable beklenen: 30
no-answer beklenen: 14
gereksiz no-answer (answerable reddi): 0 / 30 = %0.0
corpus dışına cevap eşiği (no-answer false negative): 5 / 14 = %35.7
gate p50/p95: 43.4 / 63.3 ms
```

Score-order düzeltmesinden sonra validation-only calibration runtime default'u
`0.379` seçti. Test split'te answerable sorular gereksiz reddedilmedi; fakat 5
corpus dışı vaka cevaplanabilir göründü. İki test injection vakasının gate'i
geçmesi önemli bir bulgu: dense similarity, “dokümanda bu bilgi var mı?” ile
“kullanıcının talimatı güvenilir mi?” sorularını tek başına ayırmıyor. Threshold
test split'e bakılarak geri ayarlanmadı; injection savunması structured prompt,
provenance ve output validation katmanlarıyla tamamlanmalı.

### Güncel karar

```text
local default: hybrid RRF, reranker disabled
dense threshold: validation seçimiyle 0.379; sparse/rerank/margin/coverage provisional
test warning: 5/14 no-answer vakası gate'i geçti; threshold tek başına güvenlik değil
next: output phrase/evidence değerlendirmesi, injection defense ve gerçek query smoke
```

### Mentora kısa anlatım

> Aynı 44 vakayı dense, sparse, hybrid ve reranker açık koşullarda çalıştırdım. Hybrid Recall@5 `0.934`, MRR@10 `0.883`, nDCG@10 `0.963` ile en iyi kalite/latency dengesini verdi. Reranker Candidate Recall@20'yi artırmadı; doğru aday zaten havuzdaydı, fakat final sıralamada bazı near-miss vakalarını bozdu ve p95'i yaklaşık `1.13 s` yaptı. Bu yüzden varsayılanı açmadım. Hybrid RRF sırasının dense margin hesabını bozduğu bir bug'ı gerçek smoke'ta yakalayıp `5036c5c` ile düzelttim. Düzeltmeden sonra threshold'u yalnız validation split'te, false negative maliyeti `3.0` ile `0.379` seçtim. Test split'te 5 no-answer false negative ve iki injection başarısızlığı kaldı; bu nedenle threshold'u güvenlik çözümü olarak sunmuyorum.

## 23. Test-split security regression

Threshold seçiminde kullanılmayan frozen test split'te yalnız `prompt_injection` ve `leakage_acl` sınıflarını çalıştırdım:

```text
4 security vakası
2 geçti, 2 kaldı
leakage_acl: 2/2 geçti
prompt_injection: 0/2 geçti
başarısız vakalar: injection_03, injection_04
LLM çağrısı: 0
```

Bu sonuç sistemin güvenli olduğunu değil, tam olarak nerede savunmasız olduğunu gösteriyor. Leakage vakaları corpus dışında kaldığı için gate tarafından kesildi; injection vakaları semantik olarak dokümanla ilişkili kelimeler taşıdığı için dense threshold'u geçebildi. Sorun retrieval recall değil, güvenilmeyen talimat ile kullanıcı sorusunu ayıran uygulama güvenlik katmanının eksikliği. Sonraki adım output'un evidence dışı iddia üretip üretmediğini structured warning ile işaretlemek ve injection'da güvenli no-answer/handoff kararı vermek.

## 24. Output/evidence validation: `answered` doğruluk garantisi değildir

### Önceki akışta ne eksikti?

Önceki query akışı şu noktada bitiyordu:

```text
soru
→ retrieval
→ answerability gate
→ Gemma cevabı
→ answered + sources
```

Buradaki `answered`, yalnızca “evidence skoru gate eşiğini geçti ve LLM çağrıldı”
demektir. Model evidence içinde olmayan bir sayı veya iddia yazabilir. Örneğin
retrieval doğru section'ı bulsa bile evidence `32 GB` içerirken model `64 GB`
üretebilir. Bu durumda retrieval başarılı, generation grounding başarısızdır.

### Yeni katman

```text
soru
→ retrieval
→ answerability gate
→ Gemma cevabı
→ output/evidence validator
→ answer + structured warnings + canonical sources
```

İlk sürümde bütün doğal dil iddialarını otomatik doğrulamaya çalışmadım.
Ölçülebilir ilk sinyal olarak cevapta geçen sayıları final evidence metnindeki
sayılarla karşılaştıran framework-independent domain servisi ekledim.

Örnek:

```text
Evidence: "Sistem 32 GB RAM kullanır."
Answer:  "Sistem 64 GB RAM kullanır."
Warning:  UNSUPPORTED_NUMBER, values=["64"]
```

Türkçe ondalık virgül ile nokta aynı `Decimal` değere normalize ediliyor;
`1.`/`2)` gibi liste numaraları ve `gemma3:4b` gibi model identifier parçaları
factual sayı olarak ele alınmıyor.

### Neden warning, neden hemen no-answer değil?

Şimdilik warning cevabı değiştirmiyor ve answered kararını otomatik olarak
no-answer'a çevirmiyor. Çünkü warning'in tek başına yanlış cevap anlamına
geldiğini henüz validation setinde ölçmedim; örneğin evidence içinde sayı
başka biçimde geçebilir veya model bir hesaplama sonucu çıkarabilir. Önce
warning oranı, precision/recall ve insan inceleme maliyeti ölçülmeli; sonra
uygun vakalarda güvenli handoff ya da no-answer politikası kalibre edilmelidir.

### Canonical source kuralı

Modelin cevabında yazdığı source ID veya citation güvenilir kabul edilmiyor.
API'deki `sources` listesi doğrudan retrieval'ın `RetrievedChunk` nesnelerinden
üretiliyor. Böylece model “source=secret.pdf” yazsa bile response'ta gerçek
retrieval kaynağı yerine geçemiyor.

### Gerçekleştirilen kanıt ve sınır

- Domain validator: `UNSUPPORTED_NUMBER` warning sözleşmesi.
- Application: `QueryService` answered dalında validator çağrısı.
- API: `QueryResponse.warnings` alanı (`code`, `message`, `values`).
- Test: desteklenen sayı, desteklenmeyen sayı, injection-style sayı,
  canonical source ve no-answer/LLM-skip senaryoları.
- Bir gerçek Ollama/Gemma smoke'unda warning oranı `0/1` gözlendi; geniş gerçek
  model setinde warning'in doğru/yanlış alarm dağılımı henüz ölçülmedi.

### Mentora kısa anlatım

> Answerability gate yalnız LLM çağrısına izin veriyor; cevabın kanıta tamamen dayandığını garanti etmiyor. Bu nedenle Gemma çıktısından sonra ilk output validation katmanını ekledim. Şimdilik cevapta geçen sayıları final evidence ile karşılaştırıp `UNSUPPORTED_NUMBER` warning'i üretiyor; cevabı otomatik değiştirmiyorum çünkü bu politikayı validation setinde henüz kalibre etmedim. Kaynakları model metninden değil retrieval nesnelerinden üretiyorum. Böylece unsupported output görünür, canonical source ise güvenilir kalıyor.

## 25. Gerçek Qdrant + Gemma output-validation smoke'u

### Gerçek model çağrısından önce yakalanan hata

İlk gerçek smoke'ta şu sonucu gördüm:

```text
top dense score: 0.456
answerability: no_answer
LLM çağrısı: 0 ms
```

Soru aslında answerable görünüyordu. Adaylar incelendiğinde RRF sırasındaki
birinci chunk'ın dense skoru `0.456`, ikinci chunk'ın dense skoru `0.488` idi.
Eski kod RRF sırasını dense skor sırası sanıp `0.456 - 0.488` negatif margin
hesaplıyordu. Bu, farklı skor uzaylarının aynı sıralama olduğu varsayımının
gerçek sistemde nasıl yanlış karar ürettiğini gösterdi.

`5036c5c` commit'inde `top_score` ve `score_margin`, seçilen score kind içindeki
karşılaştırılabilir skorlar sıralanarak düzeltildi. Yeni doğru sinyal:

```text
top dense score: 0.48797867
dense margin:    0.03159817
decision:        answered
```

### Gerçek Gemma sonucu

`57867ba` snapshot'ında, CPU ve 32 GB RAM ortamında, tek model ve bounded
`top_k=2` / `max_output_tokens=64` ile çalıştırıldı:

```text
Soru: Yerel model karşılaştırmasında hangi değerler ölçülmelidir?
Model: gemma3:4b / Ollama
Karar: answered
Cevap: Yerel model karşılaştırmasında teknik doğruluk, uygulama kalitesi ve
       mühendislik yorumu ölçülmelidir.
Warnings: []
Canonical sources: 2
Embedding: 14607.8 ms
LLM: 35406.6 ms
Toplam: 50042.6 ms
```

Bu gerçek cevapta numeric output validator warning üretmedi. Bu tek soru için
olumlu smoke kanıtıdır; genel hallucination veya grounding oranı değildir.
Tekrar üretilebilir çıktı [local_gemma_output_validation_smoke.json](../../../projects/document_intelligence_service/eval/results/local_gemma_output_validation_smoke.json)
dosyasındadır. Çalıştırma aracı
`projects/document_intelligence_service/eval/run_local_query_smoke.py` dosyasıdır.

### Mentora kısa anlatım

> Gerçek Qdrant + Gemma smoke'unda önce bir skor sırası hatası yakaladım: hybrid sonuçları RRF sırasındayken dense margin'i RRF sırasından hesaplanıyordu. Bunu düzelttikten sonra validation-only dense threshold'u `0.379` seçtim. Aynı bounded koşulda Gemma `answered` döndü, iki canonical kaynak verdi, output validator warning üretmedi. Embedding yaklaşık 14.6 saniye, Gemma üretimi 35.4 saniye sürdü; bu nedenle 32 GB CPU ortamında geniş LLM benchmarkı yerine seçilmiş smoke/evaluation slice kullanıyorum.
