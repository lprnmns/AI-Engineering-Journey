# Mentor Programı PDF RAG — Qdrant Kalıcı İndeks Deneyi

**Tarih:** 27 Temmuz 2026  
**Collection:** `mentor_program_pdf_v1`  
**Embedding:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 boyut)  
**Servis:** `qdrant/qdrant:v1.18.3`, yerel Docker

## Amaç

In-memory dense store, Python süreci bittiğinde kaybolur. Bu deneyde mentor PDF'inin section-aware chunk'larını Qdrant'a kalıcı olarak yazdım; tekrar ingestion'ın duplicate üretmediğini, servis yeniden başladıktan sonra verinin korunduğunu ve payload filtresinin çalıştığını ölçtüm.

## Uygulama tasarımı

- Qdrant yalnız `127.0.0.1:6333` ve `127.0.0.1:6334` portlarına bağlıdır; ağdaki başka cihazlara açılmadı.
- Docker named volume `ai_journey_qdrant_data`, Qdrant'ın `/qdrant/storage` dizinine bağlandı.
- Her chunk için UUID5 ile deterministik bir point ID üretildi. Aynı `chunk_id` tekrar yüklenirse yeni kayıt yerine aynı point upsert edilir.
- Payload'da `chunk_id`, `section_id`, `section_title`, `text`, `source`, `chunk_index` ve `ingestion_version` tutuldu.

## Ölçülen sonuçlar

| Kontrol | Sonuç | Yorum |
| --- | ---: | --- |
| PDF bölüm sayısı | 7 | Section-aware parser'ın ürettiği mantıksal bölüm sayısı |
| Chunk sayısı | 48 | 2 cümle + 1 overlap ayarı |
| Vektör boyutu | 384 | Dense embedding modelinin çıkışıyla collection şeması eşleşiyor |
| İlk ingestion sonrası point sayısı | 48 | Her chunk için bir Qdrant point |
| İkinci aynı ingestion sonrası point sayısı | 48 | Duplicate yok; ingestion idempotent |
| Qdrant restart sonrası point sayısı | 48 | Named volume sayesinde indeks kalıcı |
| Health check | geçti | `GET /healthz` başarılı |

İlk ve ikinci ingestion çıktıları sırasıyla [`qdrant_ingestion_first_run.json`](qdrant_ingestion_first_run.json) ve [`qdrant_ingestion_second_run.json`](qdrant_ingestion_second_run.json) dosyalarında saklıdır.

## Retrieval ve filtre kontrolü

| Sorgu | Mod | En iyi sonuç | Skor | Yorum |
| --- | --- | --- | ---: | --- |
| İlk haftanın amacı nedir? | Dense top-3 | `purpose_chunk_015` | 0.683 | Doğru `purpose` bölümünden kanıt geldi. |
| Yerel model karşılaştırmasında hangi değerler ölçülmelidir? | `section_id=local_model` filtresi | `local_model_chunk_006` | 0.663 | Yalnız ilgili bölümde arandı; sonuç doğru bölüme sınırlı kaldı. |
| Teslim paketinde hangi çalışmalar bulunur? | Dense top-3 | `purpose_chunk_003` | 0.466 | Soru için dense retrieval tek başına zayıf kaldı. Önceki deneyde cross-encoder'ın bu tür aday sıralama sorunlarını düzeltebildiği görüldü. |

Qdrant, aynı embedding modeli ve cosine mesafesi kullanıldığı için in-memory dense retriever'ın semantik mantığını değiştirmez. Bu katmanın kazancı **kalıcılık, payload ile filtreleme ve client/server çalışma modelidir**. Son sorgudaki hata da bu ayrımı gösterir: Vector DB eklemek, retrieval kalitesini otomatik olarak artırmaz; chunking, candidate recall, reranking ve parent-section expansion hâlâ gereklidir.

## Doğrulama komutları

```bash
.venv/bin/python -m labs.rag.qdrant_mentor_program_ingestion \
  --output docs/internship/week1/qdrant_ingestion_first_run.json

docker compose -f docker-compose.qdrant.yml restart qdrant
curl --fail http://127.0.0.1:6333/healthz
```

## Sınırlar ve sonraki adım

Bu collection tek PDF ve 48 point ile küçük bir geliştirme indeksidir; gecikme veya ölçek benchmarkı değildir. Sonraki RAG entegrasyonunda Qdrant'tan gelen dense adaylar cross-encoder reranker'a, ardından gerekli olduğunda parent-section context builder'a verilecek; answerability/no-answer kararı üretim zincirinde korunacaktır.
