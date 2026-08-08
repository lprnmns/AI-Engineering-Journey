# ADR-001: Qdrant native sparse/BM25 veya ayrı adapter

## Bağlam

Hybrid retrieval için dense ve sparse adayları birleştirmek gerekiyor. Dense cosine skorları ile BM25 skorları doğrudan toplanmayacak; önce rank tabanlı RRF kullanılacak.

## Alternatifler

1. Qdrant'ın native sparse vector/BM25 yeteneklerini kullanmak.
2. BM25'i ayrı bir adapter veya arama motoruyla çalıştırmak.

## Karar

Başlangıç adayı Qdrant named dense + sparse collection yapısıdır. Gün 3'te küçük bir spike ile API sürümü, sparse payload davranışı, Türkçe tokenizasyonu ve persistence ölçülecek. Spike başarısızsa ayrı BM25 adapter'ına geçilecek.

## Ölçüm/kanıt

Recall@k, MRR, nDCG, p50/p95 latency ve kurulum karmaşıklığı karşılaştırılacak.

## Bilinen sınır

Native sparse desteği tek başına Türkçe morfolojisini çözmez; tokenizer ve evaluation slice ayrıca ölçülmelidir.

