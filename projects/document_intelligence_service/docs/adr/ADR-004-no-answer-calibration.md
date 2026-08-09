# ADR-004: No-answer sinyalleri ve threshold kalibrasyonu

## Bağlam

Tek bir cosine threshold, farklı query türleri ve dillerde güvenilir değildir. Benzer görünen fakat soruyu desteklemeyen evidence yanlış cevap üretebilir.

## Alternatifler

1. Tek dense cosine eşiği.
2. Multi-signal answerability gate.

## Karar

Gate; evidence boşluğu, calibrated final/rerank score, top-1/top-2 margin, evidence coverage ve ACL/document filter sonucunu birlikte kullanacak. Threshold'lar golden validation split üzerinde kalibre edilecek; test split karar vermek için kullanılmayacak. Direct prompt injection ise score threshold'ı değil, retrieval'dan önce çalışan ayrı `PromptSafetyPolicy` kararıdır.

İlk dikey dilimde `AnswerabilityPolicy` bu sinyalleri framework bağımsız olarak üretiyor. Hybrid RRF adayları RRF sırasındayken dense top-score/margin hesabının yanlış sırayı kullandığı tespit edildi; `5036c5c` ile karşılaştırılabilir score kind içinde sıralama düzeltildi. Direct injection için yeni policy retrieval'dan önce çalışıyor ve `SECURITY_POLICY` dönen vakalarda score üretmiyor. Score-bearing security dışı 9 validation vakasında false negative maliyeti `3.0` ile seçilen score threshold `0.337857395` (`0.338`) oldu; bu küçük alt küme güçlü genelleme kanıtı değil. Mevcut operasyon varsayılanı, daha geniş validation setiyle tekrar kalibre edilene kadar konservatif `0.379` olarak korunuyor.

Sparse `0.1`, rerank `-5.0`, margin `0.0` ve coverage `0.0` henüz aynı yöntemle kalibre edilmedi; bunlar provisional değerlerdir. Eşikler `DIS_ANSWERABILITY_*` ayarlarıyla değiştirilebilir. Test split yalnız final rapor içindir ve threshold seçimine giremez.

Validation threshold'ı injection riskini tek başına çözmedi; bu nedenle direct injection artık ayrı `PromptSafetyPolicy` ile retrieval'dan önce kesiliyor. Frozen test'te prompt-injection `2/2` geçti, fakat bu modelin veya rule setinin genel olarak güvenli olduğu anlamına gelmez. No-answer gate, prompt safety, structured prompt, source provenance ve output validation defense-in-depth zincirinin ayrı katmanlarıdır.

Frozen test split'te konservatif `0.379` runtime threshold ile 30 answerable
vakanın hiçbiri gereksiz reddedilmedi; 14 no-answer vakadan 3'ü cevaplanabilir
göründü. Prompt injection vakaları bu sayıya score false negative olarak değil,
security policy kararı olarak dahil edilir. Test sonucu threshold'u geriye dönük
seçmek için kullanılmaz.

## Ölçüm/kanıt

False answer, false rejection, no-answer precision/recall ve LLM skip rate raporlanacak.

## Bilinen sınır

Calibration setindeki leakage veya dengesiz answerable/unanswerable dağılımı sonucu bozabilir.
