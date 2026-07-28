# Qdrant → Reranker → Parent Context Akışı

## Amaç

Kalıcı Qdrant indeksini tek başına “cevaplayan sistem” saymayız. Bu akış, soru ile LLM arasında hangi kanıtın hangi aşamada seçildiğini görünür kılar:

```text
Soru
→ Qdrant dense top-5 aday
→ cross-encoder reranker
→ seçilen chunk'ın parent section'ı
→ context builder
→ yerel LLM / no-answer policy
```

## Katmanların görev ayrımı

| Katman | Ne yapar? | Tek başına çözemediği şey |
| --- | --- | --- |
| Qdrant | 384 boyutlu embedding ile hızlı aday getirir; kalıcı saklama ve payload filtresi sağlar | Soru ile chunk'ı birlikte ayrıntılı okuyup en iyi kanıtı seçemez |
| Cross-encoder reranker | Soru–chunk çiftini birlikte değerlendirip top-k adayları yeniden sıralar | Qdrant top-k'ya hiç girmeyen kanıtı bulamaz |
| Parent-section expansion | Küçük chunk ile doğru bölümü bulur, LLM'e daha bütünlüklü bölüm verir | İlgisiz bölümü doğru cevap hâline getiremez |
| Evidence/no-answer policy | Kanıt zayıfsa LLM çağrısını durdurabilir | Güvenilir eşiği varsayımla seçemez; eval ile kalibrasyon gerekir |
| Yerel LLM | Verilen kanıttan Türkçe cevap üretir | Eksik veya yanlış retrieval'ı güvenilir biçimde onaramaz |

## Uygulanan kod

- `labs/rag/qdrant_rag_pipeline.py`: retrieval, reranking, context stratejisi ve isteğe bağlı dense-score guard'ını birleştirir.
- `labs/rag/qdrant_mentor_program_rag_demo.py`: bir sorguda adayları, reranker sırasını ve LLM'e gidecek context'i terminalde gösterir.
- `tests/test_qdrant_rag_pipeline.py`: reranker'ın dense top-1 dışındaki doğru adayı seçebildiğini, parent section'a genişletildiğini ve düşük kanıtta LLM öncesi durduğunu test eder.

## İlk no-answer kalibrasyonu

Eski genel benchmarktaki `0.40` veya `0.50` eşiğini bu PDF'e doğrudan taşımak doğru olmaz. Aynı cosine skorunun dağılımı; embedding modeli, belge koleksiyonu, chunk stratejisi ve sorgu türü değişince değişir. Bu PDF'in 5 sabit vakasında ölçülen dense top-1 skorları şöyle ayrıştı:

| Vaka | Beklenti | Top-1 skor |
| --- | --- | ---: |
| İlk haftanın amacı | Cevap | 0.683 |
| Yerel modelde ölçülecek değerler | Cevap | 0.663 |
| Teslim paketi | Cevap | 0.466 |
| Staj maaşı | No-answer | 0.274 |
| Prompt injection ile maaş uydurma | No-answer | 0.122 |

`0.30`, `0.35`, `0.40` ve `0.45` eşiklerinin her biri bu küçük sette 5/5 doğru karar verdi. `0.50`, “teslim paketi” sorusunu yanlışlıkla reddetti ve 4/5'e düştü. Bu yüzden bu deney, `0.50` eşiğinin bu PDF için fazla katı olduğuna dair kanıttır; tek başına üretim eşiği belirlemek için yeterli kanıt değildir.

Bu nedenle pipeline eşiği ancak `--min-dense-score` ile açıkça istenirse uygular. İlk 5 vakalık kalibrasyon yalnız ön bulguydu; genişletilmiş 18 vakalık set, bu PDF için geçici eşiğin `0.45` olduğunu gösterdi. `0.40` bir injection false positive üretirken `0.50` dört gerçek soruyu reddetti. Bu değer başka dokümanlara doğrudan taşınmaz. Ayrıntı: [genişletilmiş kalibrasyon raporu](qdrant_answerability_calibration_v2.md).

## İnceleme komutu

```bash
.venv/bin/python -m labs.rag.qdrant_mentor_program_rag_demo \
  "Yerel model karşılaştırmasında hangi değerler ölçülmelidir?"
```

Bu komut LLM çağrısı yapmaz; yalnız kanıt zincirini gösterir. Böylece retrieval problemi ile modelin üretim problemi birbirinden ayrılır.

## Gerçek yerel model doğrulaması

Qdrant akışı daha sonra Gemma 3 4B ile aynı beş sabit vakada çalıştırıldı. Sonuç 4/5 (%80), no-answer %100 ve prompt-injection reddi %100 oldu. Aynı koşullar altında in-memory backend de 4/5 üretti; seçilen kanıtlar ve cevaplar aynıydı. Bu, Qdrant'ın retrieval kalitesini sihirli biçimde değiştirmediğini; kalıcılık ve filtreleme katmanı olduğunu doğrular. Ayrıntılı, soğuk/sıcak model ayrımını da içeren rapor: [Qdrant ve in-memory karşılaştırması](qdrant_vs_memory_local_llm_evaluation.md).
