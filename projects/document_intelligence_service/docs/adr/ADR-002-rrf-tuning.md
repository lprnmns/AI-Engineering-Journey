# ADR-002: RRF parametresi ve tuning politikası

## Bağlam

Dense ve sparse rank listelerinde skor ölçekleri farklıdır. Ham skorları toplamak bir retriever'ı haksız biçimde öne çıkarabilir.

## Alternatifler

1. Ham dense/BM25 skorlarını toplamak.
2. Rank Fusion ile RRF kullanmak.
3. Öğrenilmiş ağırlıklı ranker kullanmak.

## Karar

İlk üretim adayı dense top-30 + sparse top-30 → RRF top-20 → reranker top-5 akışıdır. RRF sabiti ve candidate limitleri settings üzerinden tutulacak; magic constant olarak endpoint içine gömülmeyecektir.

## Ölçüm/kanıt

Golden set üzerinde Recall@k, MRR, nDCG ve p95 latency; query type ve dil slice'larıyla raporlanacak. İlk 44-vaka smoke'unda hybrid RRF Recall@5 `0.934`, MRR@10 `0.883`, nDCG@10 `0.963`, p95 `28.1 ms` verdi. Hybrid + reranker Recall@5 `0.912`, MRR@10 `0.833`, nDCG@10 `0.933`, p95 `1128.5 ms` kaldı.

Bu nedenle ilk local varsayılan `hybrid + reranker` değil, `hybrid` ve reranker kapalıdır. Reranker yalnız validation setinde kalite kazanımı ve latency bütçesi birlikte sağlanırsa açılabilir.

## Bilinen sınır

RRF iyi bir başlangıçtır; veri büyüdükçe candidate limitleri ve reranker maliyeti yeniden ölçülmelidir.
