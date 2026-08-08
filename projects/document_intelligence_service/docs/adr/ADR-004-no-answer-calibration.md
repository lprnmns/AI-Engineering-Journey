# ADR-004: No-answer sinyalleri ve threshold kalibrasyonu

## Bağlam

Tek bir cosine threshold, farklı query türleri ve dillerde güvenilir değildir. Benzer görünen fakat soruyu desteklemeyen evidence yanlış cevap üretebilir.

## Alternatifler

1. Tek dense cosine eşiği.
2. Multi-signal answerability gate.

## Karar

Gate; evidence boşluğu, calibrated final/rerank score, top-1/top-2 margin, evidence coverage ve ACL/document filter sonucunu birlikte kullanacak. Threshold'lar golden validation split üzerinde kalibre edilecek; test split karar vermek için kullanılmayacak.

## Ölçüm/kanıt

False answer, false rejection, no-answer precision/recall ve LLM skip rate raporlanacak.

## Bilinen sınır

Calibration setindeki leakage veya dengesiz answerable/unanswerable dağılımı sonucu bozabilir.

