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
