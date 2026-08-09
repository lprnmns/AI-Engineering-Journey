# ADR-004: No-answer sinyalleri ve threshold kalibrasyonu

## Bağlam

Tek bir cosine threshold, farklı query türleri ve dillerde güvenilir değildir. Benzer görünen fakat soruyu desteklemeyen evidence yanlış cevap üretebilir.

## Alternatifler

1. Tek dense cosine eşiği.
2. Multi-signal answerability gate.

## Karar

Gate; evidence boşluğu, calibrated final/rerank score, top-1/top-2 margin, evidence coverage ve ACL/document filter sonucunu birlikte kullanacak. Threshold'lar golden validation split üzerinde kalibre edilecek; test split karar vermek için kullanılmayacak.

İlk dikey dilimde `AnswerabilityPolicy` bu sinyalleri framework bağımsız olarak üretiyor. Hybrid RRF adayları RRF sırasındayken dense top-score/margin hesabının yanlış sırayı kullandığı tespit edildi; `5036c5c` ile karşılaştırılabilir score kind içinde sıralama düzeltildi. Düzeltmeden sonra 44 vakalık golden setin yalnız validation split'i üzerinde dense threshold tarandı; false negative maliyeti `3.0` alınarak seçilen runtime eşik `0.379` oldu. Validation sonucunda 7 answerable vakanın tamamı kabul edildi, 4 no-answer vakanın 3'ü reddedildi. Bu küçük split nedeniyle güven aralığı zayıftır; eşik başka corpus/model/chunk pipeline'larına genellenemez.

Sparse `0.1`, rerank `-5.0`, margin `0.0` ve coverage `0.0` henüz aynı yöntemle kalibre edilmedi; bunlar provisional değerlerdir. Eşikler `DIS_ANSWERABILITY_*` ayarlarıyla değiştirilebilir. Test split yalnız final rapor içindir ve threshold seçimine giremez.

Validation threshold'ı injection riskini tek başına çözmedi: final test smoke'unda iki prompt-injection vakası gate'i geçti. Bu nedenle no-answer gate, structured prompt, source provenance ve output validation'dan oluşan defense-in-depth zincirinin yalnız bir katmanıdır.

Frozen test split'te yeni threshold ile 30 answerable vakanın hiçbiri gereksiz
reddedilmedi; ancak 14 no-answer vakanın 5'i cevaplanabilir göründü. Bu sonuç
validation seçiminin testte genellenmediğini açıkça raporlar; test sonucu
threshold'u geriye dönük seçmek için kullanılmaz.

## Ölçüm/kanıt

False answer, false rejection, no-answer precision/recall ve LLM skip rate raporlanacak.

## Bilinen sınır

Calibration setindeki leakage veya dengesiz answerable/unanswerable dağılımı sonucu bozabilir.
