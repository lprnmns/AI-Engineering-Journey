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

Henüz bu dosyada retrieval strategy seçimi yapılmamıştır. Seçim, aynı corpus snapshot, aynı query sırası ve aynı warm-up protokolü üzerinde kalite kazanımı ile p95 maliyeti birlikte görüldükten sonra yapılacaktır.

