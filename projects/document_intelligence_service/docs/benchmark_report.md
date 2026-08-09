# Retrieval Benchmark Report — Initial Protocol

## Status

Bu dosya benchmark protokolünün ilk sürümüdür. Golden vaka sözleşmesi, offline
metric runner ve gerçek Qdrant ablation sonuçları aşağıda kayıtlıdır. Output
validation için ayrıca sınırlı gerçek Gemma smoke'u bulunur; bu, geniş LLM kalite
benchmarkı olarak yorumlanmamalıdır.

## Dataset

Primary dataset:

```text
data/evaluations/mentor_program_pdf_rag_golden_v1.jsonl
```

Toplam 44 vaka vardır: 30 answerable, 14 no-answer/injection/leakage hazırlık vakası. Kategoriler ve development/validation/test split'i dataset contract testiyle doğrulanır.

Gold hedefleri generated child point ID yerine section title üzerinden tutulur. Böylece ingestion pipeline version değiştiğinde etiketlerin anlamı korunur. Birden fazla section gerektiren vakalar `multi_evidence` olarak ayrıca işaretlenir.

## Protocol

Her retrieval strategy aynı golden soru sırasını kullanır:

```text
dense, bm25, hybrid
hybrid + reranker
```

İlk warm-up soruları kalite ortalamasına katılmaz. Reranker öncesi bounded candidate window ve final evidence ayrı kaydedilir. Timeout veya dependency error sonuçları silinmez; failure rate ve hata nedeni olarak raporlanır.

## Metrics

| Alan | Metrik | Yorum |
| --- | --- | --- |
| Candidate coverage | Candidate Recall@20 | Reranker'a ulaşan havuz doğru section'ı içeriyor mu? |
| Final retrieval | Recall@1/3/5 | Doğru gold hedef final sıralamada bulundu mu? |
| Ranking | MRR@5/10 | İlk doğru kanıt ne kadar yukarıda? |
| Graded ranking | nDCG@5/10 | Birden fazla/öncelikli kanıtın sırası |
| Runtime | p50/p95 | Toplam, embedding, search, rerank süreleri |
| Answerability | no-answer FP/FN | Gereksiz ret ve corpus dışı cevap ayrımı |

Section'a ait duplicate child chunk'lar tek gold hedef sayılır. Bu, overlap nedeniyle metriklerin yapay olarak şişmesini önler.

## Current evidence

```text
Golden contract validation: passed
Metric/runner unit tests: passed
Mypy for evaluation slice: clean
Real Qdrant retrieval ablation: recorded
Real Gemma output-validation smoke: recorded (1 bounded query)
```

İlk protokol tamamlandı; retrieval strategy kararı aşağıdaki aynı corpus snapshot, aynı query sırası ve aynı warm-up protokolüyle alınmıştır. Yeni corpus veya model değişiminde bu sonuçlar otomatik olarak genellenmeyecektir.

## Measured ablation — 2026-08-09

Run manifest:

```text
git_sha: 928e60868ab8cb67f8859acd297c394e7ff938fd
active Qdrant points: 26 (collection toplamı: 53; 27 eski version inactive)
golden cases: 44 (retrieval quality denominator: 30 answerable)
top_k: 5
warm-up: 3 query, quality hesabı dışında
LLM: çağrılmadı
```

| Strategy | Candidate Recall@20 | Recall@5 | MRR@10 | nDCG@10 | Total p50 | Total p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 0.993 | 0.901 | 0.875 | 0.930 | 22.8 ms | 25.2 ms |
| Sparse/BM25 mode | 0.987 | 0.840 | 0.778 | 0.860 | 3.0 ms | 3.5 ms |
| Hybrid RRF | 0.993 | **0.934** | **0.883** | **0.963** | 23.7 ms | **28.1 ms** |
| Dense + reranker | 0.993 | 0.912 | 0.836 | 0.933 | 844.7 ms | 1224.6 ms |
| Hybrid + reranker | 0.993 | 0.912 | 0.833 | 0.933 | 842.9 ms | 1128.5 ms |

Sparse/BM25 mode bu sürümde ayrı bir klasik BM25 motoru değil; deterministic `HashingSparseEncoder` + Qdrant IDF sparse search'tür. Bu nedenle tablo “BM25 modu” olarak okunmalı, Türkçe morfoloji çözülmüş tam BM25 iddiası olarak değil.

### Yorum

- Hybrid, bu corpus'ta dense'e göre Recall@5'i yaklaşık `+0.033`, sparse baseline'a göre `+0.094` artırdı.
- Üç yöntemde de Candidate Recall@20 çok yüksek (`0.987–0.993`). Sorun çoğunlukla doğru section'ın aday havuzuna girmemesi değil, final sıralamadaki yeridir.
- Reranker, hybrid'e göre Recall@5'i `0.934`ten `0.912`ye, MRR@10'u `0.883`ten `0.833`e düşürdü; p95'i `28.1 ms`ten `1128.5 ms`e çıkardı.
- Reranker `multi_evidence` slice'ında `0.508`ten `0.592`ye katkı verdi; fakat `near_miss` slice'ında `1.000`den `0.833`e düştü. `near_miss_02`, hybrid'in bulduğu `rag` section'ını reranker'ın final top-5'ten çıkardığı somut negatif flip'tir.

Karar: reranker varsayılan kapalı kalıyor. İleride farklı cross-encoder, daha iyi section-aware evidence aggregation veya validation split üzerinde threshold/reranker tuning yapılmadan varsayılan açılmayacak.

## Answerability gate smoke — 2026-08-09

Hybrid retrieval ile, Ollama çağırmadan aynı 44 vaka üzerinde gate çalıştırıldı:

```text
expected answerable: 30
expected no-answer: 14
predicted answerable: 35
predicted no-answer: 9
```

Bu provisional eşiklerde:

```text
no-answer false positive: 0 / 30 = 0.0%
  → answerable vaka gereksiz reddedildi

no-answer false negative: 5 / 14 = 35.7%
  → corpus dışı vakalar cevaplanabilir sanıldı

gate total p50/p95: 43.4 ms / 63.3 ms
LLM çağrısı: 0
```

Bu sonuç validation'dan seçilen `0.379` threshold'un frozen test'te genellenmediğini gösteriyor: answerable vakalar gereksiz reddedilmedi, fakat corpus dışı vakaların 5'i cevaplanabilir göründü. Test split'e bakarak threshold'u geriye dönük ayarlamıyorum; bu hata, daha güçlü provenance/injection ve output policy katmanlarına ihtiyaç olduğunu gösteren raporlanmış bir sınırdır.

## Validation-only threshold calibration

```text
dataset_sha256: 5e822afa5d648656b18339b0d552c53a2c234c8e4e8213c5da782f51a53e369e
calibration split: validation only
validation cases: 11 (7 answerable, 4 no-answer)
test split used: false
false-negative cost: 3.0
selected threshold: 0.37884022
rounded runtime threshold: 0.379
validation false-positive: 0 / 7 = 0.0%
validation false-negative: 1 / 4 = 25.0%
```

Bu sonuç küçük validation split nedeniyle güçlü genelleme kanıtı değildir; threshold yalnız aynı embedding, corpus ve pipeline snapshot'ı için uygulanmıştır. Calibration çıktısı [hybrid_threshold_calibration.json](../eval/results/hybrid_threshold_calibration.json) dosyasındadır.

### Skor sırası düzeltmesi

Gerçek query smoke'unda RRF sırasındaki ilk candidate'ın dense skoru `0.456`,
ikinci candidate'ın dense skoru `0.488` olmasına rağmen eski margin hesabı
`0.456 - 0.488` yapıyordu. RRF sırası dense skor sırası olmadığı için valid bir
soru negatif margin ile reddedilebiliyordu. `5036c5c` commit'inde top-score ve
margin, seçilen score kind içindeki karşılaştırılabilir skorlar sıralanarak
hesaplandı. Benchmark ve calibration bu düzeltmeden sonra `57867ba` ile yeniden
üretildi.

## Security gate regression — test split

Prompt-injection ve cross-document leakage vakaları threshold seçimine dahil edilmeden yalnız frozen `test` split'te değerlendirildi:

```text
test security cases: 4
passed: 2 / 4 = 50%
leakage_acl: 2 / 2 passed
prompt_injection: 0 / 2 passed
failures: injection_03, injection_04
LLM çağrısı: 0
```

Bu bir “model güvenli” sonucu değildir; tam tersine mevcut uygulama gate'inin iki direct/system-prompt injection hazırlık vakasını kaçırdığını gösteren kırmızı sonuçtur. `AnswerabilityPolicy` yalnız evidence score ve coverage ile çalıştığı için, sorunun talimat kısmını güvenilir kabul edip etmemeyi tek başına çözemez. Sonraki savunma katmanı structured prompt, output fact/evidence validation ve gerektiğinde güvenli handoff olmalıdır. Ham rapor [security_test_gate.json](../eval/results/security_test_gate.json) dosyasındadır.

## Real local Gemma output-validation smoke — 2026-08-09

Gerçek Ollama `gemma3:4b` çağrısı, aynı Qdrant snapshot'ı ve bounded `top_k=2`,
`max_output_tokens=64` ayarlarıyla çalıştırıldı:

```text
decision: answered
model: ollama / gemma3:4b
answer: Yerel model karşılaştırmasında teknik doğruluk, uygulama kalitesi ve mühendislik yorumu ölçülmelidir.
warnings: []
canonical sources: 2
embedding: 14607.8 ms
LLM: 35406.6 ms
total: 50042.6 ms
```

Bu gerçek model cevabında numeric validator warning üretmedi; bu tek soru için
grounding sinyalinin olumlu olduğunu gösterir, genel hallucination oranını
kanıtlamaz. Tekrar üretilebilir ham çıktı
[local_gemma_output_validation_smoke.json](../eval/results/local_gemma_output_validation_smoke.json)
dosyasındadır. LLM yaklaşık 35 saniye sürdüğü için 32 GB RAM/CPU ortamında
geniş gerçek-model evaluation koşusu yerine önce bounded smoke ve sonra seçilmiş
test slice'ları kullanılmalıdır.

## Output/evidence validation slice — 2026-08-09

### Problem

`answered` kararı yalnızca answerability gate'in geçildiğini gösterir. Gate doğru
section'ı bulsa bile local LLM evidence içinde olmayan bir sayı üretebilir.
Örneğin evidence `32 GB` içerirken cevap `64 GB` diyebilir. Retrieval başarısı
ile generation grounding başarısını aynı metrikte birleştirmemek için output
validation ayrı bir domain adımı olarak eklendi.

### İlk sözleşme

```text
generated answer + final RetrievedChunk evidence
  → numeric mention extraction
  → normalized numeric comparison
  → zero veya bir structured warning
```

Response örneği:

```json
{
  "warnings": [
    {
      "code": "UNSUPPORTED_NUMBER",
      "message": "Cevapta geçen bazı sayılar getirilen kanıtta bulunamadı; cevap insan incelemesine gönderilmelidir.",
      "values": ["64"]
    }
  ]
}
```

Modelin yazdığı kaynak adları doğrulama için kullanılmaz. `sources` listesi
retrieval'ın canonical payload'ından üretilmeye devam eder; böylece modelin
uydurduğu bir source ID API response'una güvenilir kaynak olarak giremez.

### Ne doğrulanıyor, ne doğrulanmıyor?

- Tam sayı ve ondalık sayıların evidence'ta bulunup bulunmadığı kontrol ediliyor.
- Türkçe ondalık virgül (`0,456`) ve nokta (`0.456`) aynı sayısal değer olarak ele alınıyor.
- Liste numaraları (`1.`, `2)`) ve `gemma3:4b` gibi model identifier parçaları
  factual number olarak işaretlenmiyor.
- Bu sürüm sayının geçtiği cümlenin anlamını, birimini veya neden-sonuç
  ilişkisini kanıtlamıyor.
- Warning şu an otomatik no-answer değildir; policy kararı için validation
  setinde warning precision/recall ve insan inceleme maliyeti ölçülmelidir.

### Kanıt

Domain, QueryService ve API contract seviyelerinde desteklenen sayı,
unsupported number, injection-style unsupported claim, canonical source ve
no-answer/LLM-skip davranışları test edildi. Hedefli testler ve mypy temizdir.
Fake generator testlerine ek olarak bir gerçek `gemma3:4b` smoke'u da çalıştırıldı;
tek cevapta warning oranı `0/1` gözlendi. Bu geniş bir grounding oranı değildir;
gerçek modelin numeric warning precision/recall dağılımı seçilmiş query slice'ları
üzerinde ayrıca ölçülmelidir.
