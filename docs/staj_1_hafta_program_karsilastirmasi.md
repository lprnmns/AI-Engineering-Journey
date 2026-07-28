# Staj 1. Hafta Programı — Mevcut Durum ve Yol Haritası Entegrasyonu

**Değerlendirme tarihi:** 20 Temmuz 2026

**İncelenen program:** `Alperen_Manas_Staj_Programi_1_Hafta 1.pdf`

**Ana karar:** Mentor programı mevcut AI Engineering Journey'den kopuk veya tamamen yeni bir program değildir. Özellikle embedding, retrieval, chunking, reranking ve ölçüm yaklaşımı doğrudan mevcut çalışmalarla örtüşür. Programın farkı, bildiğimiz parçaları gerçek PDF, yerel LLM, teknoloji seçimi, kurumsal problem ve sunum içeren tek bir savunulabilir teslim paketine dönüştürmesidir.

## İki farklı ilerleme ölçüsü

- **Teknik altyapı açısından:** Programın yaklaşık `%40–45`lik bölümünde önceden çalışma veya doğrudan kullanılabilir kod bulunuyor.
- **Mentorun istediği teslim paketi açısından:** Tam istenen biçimde hazır olan bölüm yaklaşık `%20–25`. Çünkü mevcut kod güçlü olsa da raporlar, gerçek PDF deneyi, yerel model benchmarkı, ürün analizi ve sunum henüz hazırlanmadı.

Bu iki oran çelişmez. Bir konuyu öğrenmiş veya onun bileşenini yazmış olmak, mentorun istediği deney, ölçüm, yorum ve sunumun tamamlandığı anlamına gelmez.

## Program maddelerinin mevcut çalışmalarla eşleşmesi

| Mentor aşaması | Mevcut durum | Repodaki kanıt | Tamamlanması gereken |
|---|---|---|---|
| 1. Transformer, attention, token, context window, prompt ve model aileleri | Büyük ölçüde yeni | Dense embedding modelinin giriş/çıkış mantığı ve 384 boyutlu vektörler konuşuldu; ancak transformer katmanları için tamamlanmış teknik çalışma yok | 2–3 sayfalık teknik not, system/user prompt deneyi, Llama–Qwen–Gemma–Mistral–DeepSeek karşılaştırması |
| 2. En az 10 cümleyle embedding ve cosine similarity deneyi | Güçlü biçimde kısmi | `DenseVectorizer`, Sentence Transformers bağımlılığı, cosine similarity, dense semantic search ve paraphrase benchmarkı var | En az 10 cümlelik sabit deney seti, tüm eşleşmelerin sonuç tablosu, beklenen/beklenmeyen sonuç yorumu |
| 3. PDF'den cevaba tam RAG akışı | Güçlü biçimde kısmi | Chunking, metadata, TF-IDF, dense store, hybrid retrieval, ağırlık deneyi, no-answer, answerability eval ve bağımsız cross-encoder reranker var | Gerçek PDF parser, iki chunk boyutu karşılaştırması, kalıcı vector DB, dense → rerank birleşik pipeline, gerçek LLM ile kaynaklı cevap |
| 4. İki yerel açık modeli karşılaştırma | Tamamlandı | Gemma 3 4B ile Qwen3'ün iki yerel template konfigürasyonu aynı altı Türkçe vakada ölçüldü | Daha geniş model ailesi/tekrar benchmarkı ileri serving çalışmasında yapılacak |
| 5. Gerçek kurumsal problem ve ürün fikri | Yeni; altyapı fikri var | Yol haritasında gerçek kullanıcı, ölçülebilir değer, privacy ve risk şartları tanımlı | Tek alan seçimi, kullanıcı/veri/mevcut süreç/problem tanımı, mimari ve teknoloji gerekçesi, riskler |
| 6. Teknik rapor ve 15 dakikalık sunum | Kısmi hazırlık var | Git geçmişi, testler, benchmark kodları ve yol haritası anlatının kanıtlarını sağlıyor | Teslimatların tek hikâyede birleştirilmesi, mimari diyagram, ölçüm tabloları, kısa demo ve sunum |

## Daha önce gerçekten yaptıklarımız

- Dokümanı cümle tabanlı parçalara ayırma, overlap ve chunk metadata
- Term frequency, TF-IDF ve cosine similarity
- In-memory lexical vector store
- Sentence Transformers ile dense embedding üretme
- Dense vector store ve anlamsal/paraphrase retrieval
- TF-IDF ile dense retrieval sonuçlarını karşılaştırma
- Dense + lexical hybrid retrieval ve ağırlık deneyi
- Retrieval için Hit@1, Hit@K ve MRR ölçümü
- Zayıf kanıt filtreleme ve sistemin cevap vermemesi gereken durumu tasarlama
- Answerability threshold, profile ve hard-case deneyleri
- Cross-encoder reranker bileşeni
- Pytest, strict mypy, küçük commitler ve ölçüm odaklı çalışma disiplini

Bu nedenle mentor programının embedding ve RAG bölümlerine sıfırdan başlanmayacak. Mevcut bileşenler açıklanacak, deney setleri genişletilecek ve teslimat biçimine getirilecek.

## Gerçekten yeni veya eksik olanlar

- Transformer içinde token embedding, positional information, self-attention ve katman akışını teknik olarak açıklama
- System prompt ile user message etkisini kontrollü deneyle gösterme
- Açık model ailelerini lisans, Türkçe, kod, donanım ve yerel çalıştırma açısından karşılaştırma
- Gerçek PDF okuma, temizleme ve iki chunk boyutunu ölçme
- ChromaDB, Qdrant, Milvus ve Pinecone için kullanım senaryosu odaklı seçim notu
- Kalıcı bir vector database kullanma
- Retrieval adaylarını cross-encoder ile yeniden sıralayan birleşik akış ve benchmark
- Gerçek bir LLM ile grounded ve kaynaklı cevap üretme
- Ollama veya LM Studio üzerinde iki modelin hız, bellek ve cevap kalitesi benchmarkı
- Kurumsal kullanıcı ve iş problemi seçimi
- 15 dakikalık teknik sunum ve demo

## Dokuz aylık yol haritasıyla ilişkisi

| Mentor programı | Dokuz aylık plandaki yeri | Entegrasyon kararı |
|---|---|---|
| Modelin çalışma mantığı ve model aileleri | Month 4 — Transformer ve open model temeli | Giriş ve model seçimi bölümü Month 2'ye çekilecek; Month 4'te matematik, PyTorch ve daha derin uygulama devam edecek |
| Embedding deneyi | Month 2 — Dense embeddings | Mevcut kod kullanılarak mentor formatında raporlanacak |
| Tam RAG ve vector DB seçimi | Month 2 gerçek LLM + Month 3 ingestion/vector DB | Küçük bir uçtan uca sürüm şimdi kurulacak; production ingestion ve PostgreSQL/pgvector derinliği Month 3'te kalacak |
| Yerel model benchmarkı | Month 4 — Open-weight model serving | İlk karşılaştırma şimdi yapılacak; daha ileri serving/quantization çalışması Month 4'te kalacak |
| Kurumsal problem | Month 7 ve Month 8 — gerçek problem ve flagship ürün | Problem seçimi ve ilk ürün fikri şimdi yapılacak; geliştirme ve hardening sonraki aylarda sürecek |
| Sunum ve teknik savunma | Her ay dokümantasyon, Month 9 işe hazırlık | İlk kapsamlı teknik sunum bu staj sprintinde hazırlanacak |

Mentor programı ağırlıklı olarak Month 2'yi tamamlamaya yardım ederken Month 3, Month 4 ve Month 7–8'den bazı kararları erkene çekiyor. Bu, yol haritasını bozmaz; ileride yapılacak derin çalışmalar için gerçek bir problem ve ilk ölçüm tabanı oluşturur.

## Uygulanacak sıra ve kabul kriterleri

Mentorun verdiği sıra korunacak. Her aşama kod, ölçüm ve yorumla kapatılmadan sonraki teslimata geçilmeyecek.

### 1. Modelin nasıl çalıştığını anla

- [x] Token, tokenization ve context window ilişkisini örnekle açıkla
- [x] Embedding, positional information, self-attention, MLP ve residual katman akışını anlat
- [x] Aynı soruyu farklı system prompt ve user message düzenleriyle test et
- [x] Beş açık model ailesini ortak ölçütlerle karşılaştır
- [x] Teknik notta kullanılan resmi dokümanları ve model kartlarını belirt

### 2. Embedding deneyini teslimata dönüştür

- [x] Türkçe ağırlıklı, benzer ve ilgisiz en az 10 cümlelik versioned veri seti oluştur
- [x] Sentence Transformers ile embeddingleri tek seferde/batch üret
- [x] Cosine similarity sonuç tablosu oluştur
- [x] En az bir kolay, bir paraphrase, bir yanıltıcı ve bir beklenmeyen sonucu yorumla
- [x] Model adı, embedding boyutu ve çalışma ortamını raporla

### 3. PDF üzerinde tam RAG akışını kur

- [x] Gizlilik açısından uygun gerçek bir PDF seç ve parse et (mentor programı PDF'i, section-aware ingestion)
- [x] İki farklı chunk boyutu/overlap ayarıyla parça sayısı ve bağlam bütünlüğünü karşılaştır (53 küçük chunk / 14 büyük chunk deneyi)
- [x] Mevcut dense/hybrid retrieval katmanını PDF chunkları üzerinde çalıştır; dense, reranker ve parent-section sonuçlarını ölç
- [x] Retrieval adaylarını cross-encoder reranker'a bağla; Qdrant → reranker → parent-section context akışını test et ve kanıt zincirini raporla
- [x] ChromaDB, Qdrant, Milvus ve Pinecone için teknoloji seçim notu yaz
- [x] Seçilen yerel vector DB ile kalıcı index oluştur (Qdrant, 48 point, restart sonrası kalıcılık ve payload filter doğrulandı)
- [x] Gerçek LLM ile kaynaklı cevap ve no-answer akışını tamamla (Gemma 3 4B ile ölçüldü; retrieval sınırları raporlandı)
- [x] RAG mimari diyagramını hazırla

### 4. Yerel model karşılaştırmasını yap

- [x] Donanıma uygun iki model ailesi ve Q4_K_M quantization seç (Gemma 3 4B, Qwen3 4B)
- [x] Türkçe teknik soru, kod üretme, kod açıklama, özet, mantık ve yanıltıcı soru test setini sabitle
- [x] İlk cevap süresi, toplam süre ve Ollama container bellek kullanımını ölç
- [x] Doğruluk, tutarlılık, gereksiz bilgi ve hallucination açısından insan değerlendirmesi yap
- [x] Gemma 3 4B'yi bu CPU/RAM ortamı için gerekçeli olarak seç

### 5. Kurumsal problem ve ürün fikrini seç

- [x] Alanı, kullanıcıyı, kullanılan veriyi ve bugünkü iş akışını tanımla (özel diş klinikleri için kurumsal yazılım)
- [x] Problemin ölçülebilir maliyetini/zaman kaybını baseline toplama planı ve formülle belirt
- [x] Başarı metriği, privacy, güvenlik ve yanlış cevap riskini yaz
- [x] Model, embedding, vector DB ve mimari kararlarını ihtiyaca göre savun
- [x] Ürünün ilk dar kapsamını ve kapsam dışını belirle

### 6. Haftayı tek teslim paketinde kapat

- [x] Model araştırma notu
- [x] Embedding kodu, sonuç tablosu ve yorum raporu
- [x] PDF chunk deneyi, RAG diyagramı ve vector DB karar notu
- [x] Yerel model kurulum notu, test seti ve benchmark tablosu
- [x] 4–5 sayfalık kurumsal senaryo ve ilk ürün fikri
- [x] 15 dakikalık sunum ve kısa demo akışı

## Güncel genel konum

- Kamuya açık 9 aylık programda **Month 1 tamamlandı**.
- Dense embedding, dense store, paraphrase benchmarkı, dense hybrid retrieval, ağırlık deneyi ve reranker sayesinde **Month 2 yaklaşık `%35–40`** seviyesinde.
- Dokuz aylık programın katı tamamlanma oranı yaklaşık **`%15–16`**.
- Mentorun ilk haftası tamamlandığında Month 2'nin önemli bir bölümü kapanacak; ancak 50+ eval case, BM25/nDCG, provider-independent LLM katmanı, API, Docker, CI ve deployment bitmeden Month 2 tamamlanmış sayılmayacak.

## Mühendislik yorumu

Mentor programının en güçlü yanı, mevcut çalışmaların yönünü değiştirmemesi; onları ürün ve karar seviyesine çıkarmasıdır. Repoda parça parça iyi RAG bileşenleri var. Şu an en büyük eksik yeni bir retrieval tekniği öğrenmek değil, şu zinciri gerçek veri üzerinde birleştirmektir:

```text
PDF
→ parse ve normalize
→ iki chunk stratejisini ölç
→ embedding
→ kalıcı vector DB
→ dense/hybrid retrieval
→ cross-encoder reranking
→ evidence/no-answer kararı
→ yerel veya gerçek LLM ile kaynaklı cevap
→ latency, kalite ve hata analizi
```

Bu sprint sonunda hedef “RAG yaptım” demek değil; hangi model, chunk ayarı, retriever ve vector database kararının hangi ölçüme dayandığını gösterebilmektir.
