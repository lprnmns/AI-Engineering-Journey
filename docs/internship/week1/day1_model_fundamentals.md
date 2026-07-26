# Staj 1. Hafta — Model Temelleri Çalışma Notu

**Durum:** Tamamlandı — `%100`

**Başlangıç tarihi:** 20 Temmuz 2026

**Nihai çıktı:** Transformer, attention, token, context window, prompt rolleri ve açık model ailelerini birbiriyle ilişkilendiren 2–3 sayfalık teknik değerlendirme ve model karşılaştırma tablosu.

## Çalışma yöntemi

Bu çalışma yalnız tanım toplamaya dayanmayacak. Her ana iddia için mümkün olduğunda şu üç kaynak türü birlikte kullanılacak:

1. Birincil teknik makale
2. Resmi ürün/kütüphane dokümanı
3. İncelenen modelin resmi model kartı veya sağlayıcı dokümanı

Her deneyde kullanılan varsayım, ölçüm, beklenmeyen sonuç ve sınırlama ayrıca yazılacak. Bir model için “daha iyi” denmeden önce hangi görevde, hangi donanımda ve hangi ölçüte göre daha iyi olduğu belirtilecek.

## Çalışma sırası

- [x] Metin → token → token ID → embedding akışını açıkla
- [x] Position bilgisi ve context window ilişkisini açıkla
- [x] Self-attention içinde query, key ve value rollerini örnekle açıkla
- [x] Causal mask ve sıradaki token üretimini açıkla
- [x] Transformer bloğundaki attention, residual, normalization ve MLP katmanlarını bağla
- [x] Aynı soruyla system prompt/user message kontrollü deneyi yap
- [x] Llama, Qwen, Gemma, Mistral ve DeepSeek ailelerini resmi kaynaklarla karşılaştır
- [x] Sonuçları 2–3 sayfalık teknik değerlendirme ve tabloya dönüştür

## İlerleme takibi

| Alan | Durum |
| --- | --- |
| Transformer ve context mantığı | Tamamlandı |
| Prompt rolleri ve yerel deneyler | Tamamlandı; ölçümler ayrı deney notlarında kayıtlı |
| Model ailesi karşılaştırması | Tamamlandı; resmi kaynak karar tablosu yazıldı |
| Nihai 2–3 sayfalık teknik değerlendirme | Tamamlandı: `day1_technical_evaluation.md` |

## 1. Model neden doğrudan kelimelerle çalışmaz?

Bir dil modeli ham metni doğrudan anlayan bir program değildir. Sinir ağı katmanları sayısal tensörler üzerinde çalışır. Bu nedenle giriş yaklaşık olarak şu dönüşümden geçer:

```text
ham metin
→ tokenizer
→ token parçaları
→ token ID'leri
→ embedding vektörleri + konum bilgisi
→ Transformer katmanları
→ sonraki token olasılıkları
```

Burada üç kavram birbirinden ayrılmalıdır:

- **Token:** Tokenizer'ın metinde ayırdığı parça. Tam kelime, kelime parçası, noktalama veya byte tabanlı bir parça olabilir.
- **Token ID:** Tokenın tokenizer sözlüğündeki sayısal sıra numarasıdır. ID'nin büyüklüğü anlamın büyüklüğünü göstermez.
- **Embedding:** Token ID üzerinden seçilen, modelin katmanlarının işleyebileceği yoğun vektördür. Anlamsal ve bağlamsal işlemler ID üzerinde değil bu sayısal temsiller üzerinde yapılır.

### Neden yalnız kelime tabanlı tokenization kullanılmıyor?

Her kelimeyi ayrı sözlük girdisi yapmak ilk bakışta kolay görünür; ancak dilde çekimler, ekler, yazım çeşitleri, özel isimler ve yeni kelimeler vardır. Türkçede `kitap`, `kitabım`, `kitaplarımız` ve `kitaplarımızdan` gibi biçimlerin her biri ayrı sözlük girdisi olursa sözlük çok büyür. Sözlükte olmayan yeni kelimeler de bilinmeyen tokena düşebilir.

### Neden yalnız karakter tabanlı tokenization kullanılmıyor?

Karakter sözlüğü küçüktür ve bilinmeyen kelime sorunu azalır; fakat metin çok daha uzun bir diziye dönüşür. `mühendislik` kelimesini tek veya birkaç parça yerine karakter karakter işlemek daha fazla konum, attention hesabı ve üretim adımı gerektirir. Tek karakter ayrıca çoğu zaman kelime parçasından daha az anlam taşır.

### Subword yaklaşımının amacı

Modern tokenizerlar çoğunlukla kelime ile karakter arasında bir uzlaşma kurar. Sık görülen parçalar tek token olabilir; daha nadir veya ekli sözcükler birkaç parçaya ayrılır. Bunun sonucunda:

- Sözlük tamamen kontrolden çıkmaz.
- Yeni kelimeler bilinen alt parçalardan oluşturulabilir.
- Karakter tabanlı yaklaşıma göre dizi genellikle daha kısa kalır.

Bu çözüm kusursuz değildir. Eğitim verisinde daha az temsil edilen diller veya karakter dizileri aynı anlamı daha fazla tokenla ifade edebilir. Bu da context kullanımı, gecikme ve maliyet açısından önemlidir.

## 2. İlk gerçek tokenizer deneyi

Deneyde yalnız tokenizer dosyaları yüklenen `Qwen/Qwen3-0.6B` kullanıldı. Model ağırlıkları çalıştırılmadı. Amaç Qwen'in bütün model kalitesini ölçmek değil, gerçek bir açık model tokenizer'ının Türkçe metni nasıl böldüğünü gözlemlemekti.

| Metin | Token sayısı | Görülen parçalanma özeti |
|---|---:|---|
| `Python sanal ortam nasıl kurulur?` | 10 | Bazı Türkçe kelimeler birden fazla alt parçaya ayrıldı |
| `kitap` | 2 | `kit` + `ap` |
| `kitaplarımızdan` | 4 | Kök ve ek grupları birkaç alt parçaya ayrıldı |
| `Bugün yapay zekâ mühendisliği çalışıyoruz.` | 15 | Türkçe karakterler ve ekli kelimeler daha fazla parçalandı |

Tokenizerın bazı dahili token metinleri terminalde `Ã¼` veya `Ä±` benzeri byte gösterimleriyle göründü. Bu, orijinal metnin bozulduğu anlamına gelmedi: token ID'leri tekrar decode edildiğinde dört örnek de başlangıç metnine birebir döndü.

### Deneyden çıkarılan sonuç

`Bir kelime = bir token` varsayımı yanlıştır. Token sınırları modele ve tokenizer eğitimine bağlıdır. Aynı cümle başka bir model ailesinde farklı token sayısına sahip olabilir. Bu yüzden context window veya maliyet hesabı kelime sayısıyla değil, kullanılacak modelin kendi tokenizer'ıyla yapılmalıdır.

### Bu deney neyi kanıtlamaz?

- Qwen ailesinin diğer modellerden daha iyi veya kötü olduğunu kanıtlamaz.
- Token sayısı tek başına cevap kalitesini göstermez.
- Terminalde görülen token parçası, modelin o parçaya verdiği bağlamsal anlamı göstermez.
- Tokenizer çıktısı attention sonucunu göstermez; yalnız modele girecek ayrık parçaları ve ID'leri hazırlar.

## 3. Şimdilik kurulması gereken zihinsel model

Dil modeli cümleyi sözlükteki kelimeleri tek tek okuyarak anlamaz. Önce tokenizer metni yeniden birleştirilebilir parçalara böler. Her parça bir ID'ye, ardından öğrenilmiş bir vektöre çevrilir. Transformer katmanları bu vektörleri, diğer tokenlarla olan ilişkilerine ve konumlarına göre tekrar tekrar günceller. Son katman mevcut bağlama göre sıradaki token için bir olasılık dağılımı üretir.

Bu nedenle “model düşündü” ifadesini kullanırken teknik olarak şu süreci kastederiz:

```text
mevcut token temsillerini katmanlar boyunca dönüştürme
→ bağlam ilişkilerini attention ile toplama
→ sıradaki tokenlar için olasılık üretme
→ seçilen tokenı bağlama ekleyip işlemi tekrarlama
```

Bu süreç insan düşüncesiyle aynı değildir. Modelin iç durumu sayısal aktivasyonlardan oluşur ve üretilen akıcı açıklama, her zaman doğru bir iç muhakeme veya doğru bilgi anlamına gelmez.

## Kullanılan ilk kaynaklar

| Kaynak | Tür | Bu notta ne için kullanıldı? | Sınırlama |
|---|---|---|---|
| Vaswani ve diğerleri, [Attention Is All You Need](https://arxiv.org/abs/1706.03762) | Birincil teknik makale | Transformer, self-attention, token embedding, autoregressive decoder ve sonraki-token olasılığı | 2017'deki özgün mimariyi anlatır; modern LLM optimizasyonlarının tamamını kapsamaz |
| Hugging Face, [Tokenization algorithms](https://huggingface.co/docs/transformers/main/en/tokenizer_summary) | Resmi kütüphane dokümanı | Word, character ve subword tokenization trade-off'ları | Belirli bir model ailesinin kalite iddiası değildir |
| Qwen, [Qwen3-0.6B model card](https://huggingface.co/Qwen/Qwen3-0.6B) | Resmi model kartı/artifact | Gerçek tokenizer deneyi ve model kimliği | Bu ilk deney model ağırlıklarını veya cevap kalitesini ölçmedi |

## Sıradaki bölüm

Bir sonraki adımda aynı örnek cümle üzerinden şu soru cevaplanacak:

> Tokenlar embedding vektörlerine dönüştükten sonra model, bir tokenın hangi önceki tokenlardan bilgi alması gerektiğine nasıl karar verir?

Bu bölümde self-attention; query, key ve value kavramları ezberletilmeden, tokenların bilgi istemesi, eşleşmesi ve bilgi taşıması üzerinden anlatılacak. Ardından causal mask ve context window bu mekanizmaya bağlanacak.
