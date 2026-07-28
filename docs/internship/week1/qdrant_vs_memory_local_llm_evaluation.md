# Qdrant ve In-Memory Retrieval — Yerel Gemma Karşılaştırması

**Tarih:** 28 Temmuz 2026  
**Model:** `gemma3:4b` (Ollama, CPU)  
**Sabitler:** Aynı PDF, aynı 5 eval vakası, aynı multilingual MiniLM embedding modeli, cosine retrieval, top-5 aday, aynı cross-encoder reranker, parent-section context ve aynı deterministic prompt.

## Soru

Qdrant'a geçmek cevap kalitesini veya uçtan uca gecikmeyi değiştiriyor mu?

Bu doğru bir karşılaştırmada tek değişken retrieval'ın saklandığı katman olmalıdır. Bu nedenle memory ve Qdrant çalıştırmalarında chunking, embedding, reranking, context stratejisi ve Gemma prompt'u sabit tutuldu.

## Kalite sonucu

| Backend | Başarılı vaka | Toplam doğruluk | Cevap doğruluğu | No-answer | Injection reddi |
| --- | ---: | ---: | ---: | ---: | ---: |
| In-memory | 4/5 | %80 | %66,7 | %100 | %100 |
| Qdrant | 4/5 | %80 | %66,7 | %100 | %100 |

Beş vakanın seçilen section/chunk'ları, dense skorları, reranker skorları ve Gemma cevapları iki backend'de aynıydı. Bu beklenen bir sonuçtur: Qdrant, embedding modelini veya cosine aramanın anlamını değiştirmez. Aynı vektörler ve aynı arama mantığı kullanıldığında aynı adayları döndürmelidir.

“Teslim paketi” vakası doğru `deliverables` bölümünden üretildi ama eval için gereken tam ifade `model araştırma notu` yerine “model ailelerini teknik ve kurumsal açıdan karşılaştıran kısa rapor” dedi. Bu semantik olarak yakın, fakat golden-phrase kuralına göre eksik sayıldı. Dolayısıyla bu vaka retrieval hatası değildir; cevap kapsamı/eval rubric hassasiyeti problemidir.

## Gecikme sonucu

| Koşu | Toplam Gemma wall time | Ortalama / vaka | Yorum |
| --- | ---: | ---: | --- |
| Qdrant, ilk/soğuk koşu | 312,3 sn | 62,5 sn | Yerel modelin ilk yüklemesi ve CPU inference etkili; backend benchmarkı olarak kullanılmaz. |
| In-memory, sıcak model | 56,9 sn | 11,4 sn | Aynı model süreçte zaten yüklüydü. |
| Qdrant, sıcak model | 69,3 sn | 13,9 sn | Küçük fark tek koşu ve CPU dalgalanması içinde yorumlanmalıdır. |

İlk soğuk Qdrant koşusunu belgeliyoruz ancak memory ile kıyaslamıyoruz; iki koşunun model durumu eşit değildi. Sıcak iki koşuda kalite aynı, gecikme ise aynı mertebededir. Beş vaka ve tek tekrar istatistiksel performans iddiası için yetersizdir. Anlamlı latency karşılaştırması için tekrar sayısı, p50/p95 ve retrieval-only süreleri ayrıca ölçülmelidir.

## Mühendislik kararı

Bu deney Qdrant seçimini “daha doğru cevap veriyor” diye gerekçelendirmez. Seçim gerekçesi şudur:

- embedding ve metadata'nın kalıcı olması,
- tekrar ingestion'da idempotent upsert,
- `section_id` gibi payload alanlarıyla filtreleme,
- client/server veri katmanını gerçekçi biçimde öğrenme.

Kaliteyi belirleyen asıl zincir hâlâ chunking, candidate recall, reranker, parent-section context, prompt ve LLM davranışıdır.

## Kanıt dosyaları

- [`mentor_program_pdf_memory_rag_eval_parent_section.json`](mentor_program_pdf_memory_rag_eval_parent_section.json)
- [`mentor_program_pdf_qdrant_rag_eval_parent_section.json`](mentor_program_pdf_qdrant_rag_eval_parent_section.json) — soğuk model koşusu
- [`mentor_program_pdf_qdrant_rag_eval_parent_section_warm.json`](mentor_program_pdf_qdrant_rag_eval_parent_section_warm.json) — sıcak model koşusu
