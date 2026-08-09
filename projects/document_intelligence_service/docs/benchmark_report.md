# Retrieval Benchmark Report — Initial Protocol

## Status

Bu dosya benchmark protokolünün ilk sürümüdür. Golden vaka sözleşmesi ve offline metric runner hazırdır; gerçek Qdrant ablation sayıları henüz bu rapora yazılmamıştır.

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
Real Qdrant benchmark: pending
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
predicted answerable: 24
predicted no-answer: 20
```

Bu provisional eşiklerde:

```text
no-answer false positive: 8 / 30 = 26.7%
  → answerable vaka gereksiz reddedildi

no-answer false negative: 2 / 14 = 14.3%
  → corpus dışı injection vakası cevaplanabilir sanıldı

gate total p50/p95: 70.3 ms / 133.0 ms
LLM çağrısı: 0
```

Sonuç, önceki `0.45` dense threshold'un evrensel olmadığını gösteriyor. Validation-only calibration, false negative maliyeti `3.0` ile `0.456` önerdi. Özellikle iki injection false negative, yalnız similarity eşiğinin prompt güvenliğini tek başına çözmediğini gösteriyor.

## Validation-only threshold calibration

```text
dataset_sha256: 5e822afa5d648656b18339b0d552c53a2c234c8e4e8213c5da782f51a53e369e
calibration split: validation only
validation cases: 11 (7 answerable, 4 no-answer)
test split used: false
false-negative cost: 3.0
selected threshold: 0.45634224
rounded runtime threshold: 0.456
validation false-positive: 1 / 7 = 14.3%
validation false-negative: 0 / 4 = 0%
```

Bu sonuç küçük validation split nedeniyle güçlü genelleme kanıtı değildir; threshold yalnız aynı embedding, corpus ve pipeline snapshot'ı için uygulanmıştır. Calibration çıktısı [hybrid_threshold_calibration.json](../eval/results/hybrid_threshold_calibration.json) dosyasındadır.
