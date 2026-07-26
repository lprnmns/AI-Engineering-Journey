# Gün 1 — Modelin Metni İşlemesi ve Yerel Model Seçimi

## Amaç ve yöntem

Bu değerlendirme, bir LLM'in metni tokenlar üzerinden nasıl işlediğini, Transformer içindeki attention akışını, context window sınırını ve prompt rollerinin uygulamadaki etkisini bir araya getirir. İddialar iki gruba ayrılmıştır:

- **Resmî kaynak bilgisi:** Model kartı veya sağlayıcı dokümanındaki lisans, boyut ve bağlam iddiası.
- **Yerel ölçüm:** 32 GB RAM, CPU ve Ollama ortamında yapılan somut deney.

Bu ayrım önemlidir: Bir model kartının benchmark iddiası, benim bilgisayarımdaki gecikme veya Türkçe RAG davranışımın kanıtı değildir.

## Model metni nasıl işler?

Model ham kelimelerle değil tokenlarla başlar. Tokenizer, metni tekrar birleştirilebilir küçük parçalara böler; her parçayı sözlükteki token ID'sine çevirir. ID yalnızca bir sıra numarasıdır. Model, bu ID için öğrenilmiş embedding vektörünü alır ve tokenın dizideki yerini position bilgisiyle ekler.

Transformer katmanında her token, diğer tokenlardan hangi bilgiyi alacağını attention ile hesaplar. Query “hangi bilgiye ihtiyacım var?”, key “bende hangi bilgi var?” ve value “aktaracağım içerik ne?” olarak düşünülebilir. Query-key uyumu arttıkça ilgili value daha yüksek ağırlıkla toplanır. Causal mask, sıradaki token üretilirken modelin gelecekteki tokenları görmesini engeller. Attention çıktısı residual bağlantı, normalization ve MLP katmanlarıyla işlenir; bu işlem katmanlar boyunca tekrarlandıktan sonra model sıradaki token için olasılık dağılımı üretir.

Bu nedenle modelin “anladığı” şey insan benzeri bir anlam deposu değil, bağlama göre güncellenen sayısal token temsilleridir. Akıcı bir cevap, otomatik olarak doğru çıkarım veya güvenilir kaynak kullanımı anlamına gelmez.

## Context window ve RAG ilişkisi

Context window modelin tek istekte görebildiği toplam token bütçesidir: system prompt, sohbet geçmişi, RAG ile eklenen chunklar, kullanıcı sorusu ve üretilecek cevap bu bütçeyi paylaşır. Daha çok doküman eklemek her zaman daha iyi cevap üretmez; ilgisiz chunklar dikkat dağıtabilir, gecikmeyi artırabilir ve cevap için ayrılan token alanını azaltabilir.

Bu yüzden RAG'de önce retrieval ile küçük bir aday kümesi bulunur, sonra kaynak yeterliliği değerlendirilir. Daha önceki mini RAG çalışmasındaki no-answer yolu burada ürün kararına dönüşür: yeterli kanıt yoksa modelin tahmin üretmesi yerine sistemin bunu açıkça söylemesi gerekir.

## Prompt rolleri: deney sonucu

Gemma 3 4B üzerinde system prompt, kullanıcı mesajı, no-answer ve injection davranışı kontrollü olarak denendi. Kullanıcı mesajındaki kural sonraki kullanıcı mesajıyla “önceki kuralları yok say” denilerek ezilebildi. Bu, kullanıcı promptunun güvenlik sınırı olmadığını gösterdi.

V1 promptu aşırı ret verdi; V2 kaynaklı soruları cevapladı ancak kaynakta olmayan izin süresini yanlışlıkla `10 gün` diye çıkardı. V3, sayının kaynakta bağlı olduğu özelliği koruma kuralıyla sekiz Türkçe vakada ve üç tekrarda başarılı oldu. Bu küçük bir umut verici ölçümdür, güvenlik kanıtı değildir. Ayrıntılar: [V1–V2–V3 özeti](gemma3_4b_prompt_policy_v1_v2_v3_summary.md) ve [paraphrase değerlendirmesi](gemma3_4b_v3_paraphrase_evaluation.md).

Gemma'nın Ollama şablonunda system ve user rolleri aynı kullanıcı turuna dönüştürülebilir. Dolayısıyla “system her modelde mutlak üstündür” demek teknik olarak doğru değildir; davranış, modelin chat template'ine ve uygulamanın rol biçimlendirmesine bağlıdır.

## Model ailesi karar tablosu

| Aile / küçük yerel aday | Lisans | Resmî bağlam ve dil bilgisi | 32 GB CPU için yorum |
| --- | --- | --- | --- |
| Llama 3.2 3B Instruct | Llama Community License | 128K context; desteklenen diller sürüme göre belirtilir | Yaygın ekosistem ve 3B boyut avantajı. Ticari kullanım öncesi topluluk lisansı ayrıca incelenmeli; Türkçe için yerel test gerekir. |
| Qwen3 4B | Apache-2.0 | 4B parametre, 32K native context, 100+ dil/diyalekt iddiası | Türkçe/kod için güçlü aday. Yerelde 2.5 GB paketle çalıştı; yüklü thinking paketi kısa komutlarda gereksiz uzun akıl yürütme üretti. |
| Gemma 3 4B | Gemma kullanım şartları | 4B sınıfı, 128K context, 140+ dil iddiası | Yerelde 3.3 GB paketle çalıştı. Bu günün RAG ve prompt ölçümlerinde kullanılan modeldir; davranışını benchmark ile değil kendi test setiyle değerlendirdim. |
| Ministral 3 3B Instruct | Apache-2.0 | 3.4B dil modeli + 0.4B vision encoder, 256K context, çok dilli | Edge/local kullanım hedefi nedeniyle ileride karşılaştırma adayı. Resmî listede Türkçe için özel kalite iddiası yok; indirmeden önce görev testi planlanmalı. |
| DeepSeek-R1-Distill-Qwen-7B | MIT; Qwen tabanı Apache-2.0 | Reasoning için distill edilmiş 7B checkpoint | Akıl yürütme odaklı aday; CPU'da daha yüksek gecikme ve uzun çıktı riski var. Türkçe/RAG kalitesi için doğrudan test olmadan seçilmez. |

## Yerel seçim kararı

Şimdilik birincil yerel çalışma modeli **Gemma 3 4B** olarak kalır. Karar “en iyi model” olduğu için değil; kurulu, ölçülmüş ve deney altyapısına bağlı olduğu içindir. Qwen3 4B ikinci adaydır, fakat mevcut thinking paketi kısa isteklerde pratik gecikme sorunu gösterdi. Sonraki model karşılaştırması aynı sabit vakalarla yapılmalıdır: kaynaklı cevap, no-answer, injection, ilk istek gecikmesi ve sıcak istek gecikmesi.

Parametre sayısı tek seçim kriteri değildir. Quantization ağırlıkları RAM'de daha az yer kaplatır; fakat context için KV cache, işlemci hızı, chat template ve output davranışı da gerçek kullanıcı deneyimini belirler.

## Sonuç

Güvenilir AI sistemi yalnız daha büyük model seçmekle kurulmaz. Token bütçesini yöneten retrieval, kanıt yeterliliğini ölçen no-answer politikası, prompt-injection'a karşı uygulama katmanı kontrolleri ve görev odaklı değerlendirme birlikte gerekir. Bu günün en somut sonucu şudur: prompt değişikliği hem fayda hem yeni hata üretebilir; bu yüzden her değişiklik sabit testlerle ölçülmeli, kanıt ve sınırlamalarıyla kaydedilmelidir.

## Kaynaklar

1. Vaswani ve diğerleri, [Attention Is All You Need](https://arxiv.org/abs/1706.03762)
2. Hugging Face, [Tokenization algorithms](https://huggingface.co/docs/transformers/main/en/tokenizer_summary)
3. Qwen, [Qwen3 4B model card](https://huggingface.co/Qwen/Qwen3-4B)
4. Google, [Gemma 3 model card](https://ai.google.dev/gemma/docs/core/model_card_3)
5. Mistral AI, [Ministral 3 3B Instruct model card](https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512)
6. DeepSeek, [DeepSeek-R1 model card](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-7B)
7. Meta, [Llama 3.2 model card](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct) — erişim, Llama lisans koşullarının kabulünü gerektirebilir.
