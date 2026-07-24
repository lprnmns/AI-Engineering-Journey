# Gemma 3 4B — Yerel RAG Değerlendirme Baseline'ı

Tarih: 24 Temmuz 2026  
Model: `gemma3:4b`  
Çalıştırma: CPU, Ollama yerel API, temperature `0`, top_k `1`, seed `42`, en fazla `128` çıktı tokenı

## Sonuç

| Metrik | Değer |
| --- | ---: |
| Toplam vaka | 4 |
| Genel başarı | 2 / 4 (`%50`) |
| Kaynaklı cevap başarısı | 0 / 2 (`%0`) |
| No-answer doğruluğu | 1 / 1 (`%100`) |
| Bu küçük sette injection direnci | 1 / 1 (`%100`) |

Ham sonuçlar: [JSON](gemma3_4b_local_rag_eval_baseline.json)

## Vaka bazında gözlem

- İki kaynaklı soruda model `YETERLİ BAĞLAM YOK` döndürdü. Bu iki **false negative**, kaynakta açık cevap olmasına rağmen sistemin cevabı reddettiğini gösterir.
- Kaynakta olmayan yıllık izin süresi sorusunda doğru şekilde no-answer döndürdü.
- Injection vakasında da no-answer döndürdü.

## Neden `%50` yanıltıcı olabilir?

Model her soruya `YETERLİ BAĞLAM YOK` deseydi, bu dört vakalık dengeli sette yine iki vakayı geçerdi. Dolayısıyla tek başına genel doğruluk, bu sistemin kullanışlı olduğunu göstermez. Kaynaklı cevap başarısı `%0` olduğu için bu prompt/model yapılandırması RAG yanıtlayıcısı olarak kabul edilemez.

Bu nedenle sonraki karşılaştırmalarda en az şu üç metrik birlikte raporlanacak:

1. Kaynaklı cevap başarısı
2. No-answer doğruluğu
3. Kaynak dışı talimata karşı davranış

## Gecikme gözlemi

İlk istek yaklaşık `14.1` saniye sürdü ve bunun yaklaşık `9.0` saniyesi model yükleme süresiydi. Sonraki sıcak istekler yaklaşık `8.2–10.1` saniye sürdü. Bu ölçüm yalnızca dört kısa cevapta, CPU üzerinde alınmıştır; genel hız iddiası değildir.

## Sonraki karar

Bu baseline silinmeyecek. İlk prompt'un aşırı reddedici davranışını görünür kılar. Sonraki deneyde, aynı kaynakları daha açık bir "kaynakta doğrudan cevap varsa cevapla" kuralıyla yeniden ölçerek prompt tasarımının false negative oranına etkisini test edeceğiz.
