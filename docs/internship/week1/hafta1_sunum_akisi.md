# Hafta 1 — 15 Dakikalık Teknik Sunum Akışı

## Amaç

Tanım ezberlemek yerine şu teknik hikâyeyi savunmak:

> Güvenilir AI uygulaması model çağırmaktan ibaret değildir; veriyi doğru temsil etmek, kanıtı seçmek, belirsizlikte durmak, ölçmek ve gerçek iş riskini sınırlamak gerekir.

## Süre planı

| Slayt | Süre | Ana mesaj | Gösterilecek kanıt |
| ---: | ---: | --- | --- |
| 1. Problem ve hafta hedefi | 0:45 | Bu hafta araç değil, ölçülebilir karar zinciri kuruldu | Teslim manifesti |
| 2. Model metni nasıl işler? | 1:30 | Token → embedding + position → attention → sıradaki token; akıcılık doğruluk değildir | Gün 1 teknik nottaki kısa şema |
| 3. Prompt rolleri ve risk | 1:15 | System/user davranışı template'e bağlıdır; injection yalnız promptla çözülmez | Prompt deneyi: kullanıcı kuralının ezildiği örnek |
| 4. Embedding deneyi | 1:30 | 384 boyutlu vektör, cosine ve “yakın konu ≠ cevap” dersi | İzin başvurusu/izin süresi: 0.593 beklenmeyen sonuç |
| 5. PDF RAG başlangıcı | 1:15 | Chunk boyutu bağlam ve aday kalitesini değiştirir | 53 küçük / 14 büyük chunk tablosu |
| 6. RAG'i güvenilir hâle getirme | 2:00 | Section-aware ingestion → Qdrant → reranker → parent section → no-answer | Mimari diyagram + 48 point kalıcılık sonucu |
| 7. Ölçüm ve hata analizi | 1:30 | 18 vakada 0.45 geçici eşik; 0.40 injection false positive, 0.50 false negative üretti | Kalibrasyon tablosu |
| 8. Yerel model karşılaştırması | 2:00 | Gemma/Qwen: RAM, gecikme, görünür cevap, kod ve injection trade-off'u | 3 konfigürasyon benchmark tablosu |
| 9. Seçilen kurumsal problem | 1:30 | Özel diş kliniklerinde WhatsApp randevu operasyonu | Hasta → inbox → onaylı bilgi/slot → handoff akışı |
| 10. MVP, risk ve sonraki faz | 1:30 | Tıbbi karar yok; shadow mode ile doğrulama | Kapsam içi/dışı, KVKK ve handoff sınırı |
| 11. Kapanış | 0:30 | En büyük ders: doğru model değil, doğru sistem ve ölçüm | 3 karar: Qdrant, Gemma, human handoff |

Toplam: yaklaşık **14:50**. Sorular için pay bırakır.

## Kısa demo akışı

Canlı demo, yalnız bu repodaki mentor PDF RAG zincirinden yapılır; Klinik Akış canlı ürün demosu yapılmaz.

1. `Yerel model karşılaştırmasında hangi değerler ölçülmelidir?` sorusunu göster.
2. Qdrant'ın dense adayını, reranker seçimini ve `local_model` parent-section context'ini göster.
3. Gemma'nın kaynak içinden “ilk cevap süresi, toplam süre, bellek” cevabını göster.
4. `Stajyer maaşı ne kadar?` veya injection örneğinde sistemin no-answer/handoff sınırını göster.
5. “Bu aynı güvenlik sınırı, sonraki haftalarda Klinik Akış'ın idari randevu asistanında kullanılacak” diye bağla.

## Sunumda kullanılmayacak iddialar

- “Klinik Akış gerçek hasta verisinde çalışıyor.”
- “AI resepsiyonisti/diş hekimini tamamen değiştirir.”
- “0.45 bütün RAG sistemleri için doğru eşiktir.”
- “Gemma injection'a dayanıklıdır.”
- “Üç bağımsız model ailesini benchmarkladım.”

Doğru ifade: İki model ailesi ve üç yerel serving konfigürasyonu, küçük ve sabit bir Türkçe görev setinde ölçüldü.
