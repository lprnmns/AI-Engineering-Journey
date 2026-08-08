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

Golden set üzerinde Recall@30, MRR, nDCG ve p95 latency; query type ve dil slice'larıyla raporlanacak.

## Bilinen sınır

RRF iyi bir başlangıçtır; veri büyüdükçe candidate limitleri ve reranker maliyeti yeniden ölçülmelidir.

