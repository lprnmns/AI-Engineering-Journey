# Hafta 1 Teslim Manifesti

Bu dosya, mentorun teslim paketindeki her öğeyi repodaki kanıtla eşleştirir. Amaç “çok dosya var” demek değil; her teknik kararın nerede anlatıldığını ve ölçümünün ne olduğunu görünür kılmaktır.

| Teslimat | Mentorun beklediği | Hazır kanıt | Durum |
| --- | --- | --- | --- |
| Model araştırma notu | Transformer/prompt bağlantısı, model aileleri ve seçim yorumu | [Gün 1 teknik değerlendirme](day1_technical_evaluation.md), [prompt deneyleri](day1_system_user_prompt_experiment.md) | Hazır |
| Embedding deneyi | 10+ cümle, cosine sonuçları, yorum | [Türkçe embedding deneyi](turkish_embedding_similarity_experiment.md), JSON sonuçları ve ekran görüntüsü | Hazır |
| RAG tasarımı | PDF chunking, mimari diyagramı, teknoloji seçimi | [Chunk deneyi](mentor_program_pdf_chunk_experiment.md), [RAG/DB kararı](rag_architecture_and_vector_db_decision.md), [Qdrant orkestrasyonu](qdrant_rag_orchestration.md) | Hazır |
| Yerel model çalışması | Kurulum, ortak test seti, benchmark | [Yerel model karşılaştırması](local_model_comparison.md), sabit [test seti](../../../data/evaluations/local_model_comparison_cases.json) | Hazır |
| Kurumsal senaryo | Problem, kullanıcı, veri, mimari, fayda, risk | [Klinik Akış senaryosu](kurumsal_senaryo_klinik_akis_fikir.md) | Hazır; gelecek ürün fikri olarak |
| Hafta sonu sunumu | 15 dakika, kod/ölçüm/sorun/karar anlatısı | [Sunum akışı](hafta1_sunum_akisi.md) | Hazır iskelet; anlatım provası ve kısa demo kalır |

## Sunumda dürüstlük sınırı

- Bu repo içindeki RAG, Qdrant ve yerel model ölçümleri **yapılmış deneylerdir**.
- Klinik Akış, bu haftanın seçilmiş kurumsal senaryosu ve sonraki haftaların geliştirme planıdır.
- Klinik Akış'ın ayrı kod tabanındaki çalışmalar, bu teslimde canlı hasta verisi, canlı otomasyon veya ticari sonuç kanıtı diye sunulmaz.
- Her “%”, skor ve gecikme ilgili rapordaki koşulla birlikte anlatılır; küçük eval setinden genel kalite iddiası çıkarılmaz.
