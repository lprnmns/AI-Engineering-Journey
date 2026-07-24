# Staj 1. Hafta — Yerel Model Kurulumu ve İlk Baseline

**Tarih:** 24 Temmuz 2026

**Durum:** Qwen3 4B kurulumu ve ilk ölçüm tamamlandı; ikinci model karşılaştırması için Gemma 3 4B indiriliyor.

## Amaç

Bu çalışma, system prompt ve user message deneyini bulut modeline bağlı kalmadan yapabilecek yerel ortamı kurar. Aynı ortam daha sonra iki açık modelin kalite, hız ve bellek karşılaştırması için kullanılacaktır.

## Donanım ve çalışma sınırı

| Bileşen | Gözlenen değer | Karar üzerindeki etkisi |
|---|---|---|
| İşlemci | Intel Core i7-1165G7, 4 fiziksel çekirdek / 8 thread | Inference CPU üzerinde çalışacak; cevap gecikmesi ölçülecek |
| RAM | 31 GiB | 4B sınıfı quantized modeller uygun; eşzamanlı büyük model çalıştırılmayacak |
| NVIDIA GPU | Yok | CUDA/VRAM varsayımı yapılmayacak |
| Ollama varsayılan context | 4096 token | İlk deneylerde küçük context ile başlayıp context maliyetini ayrıca ölçeceğiz |
| Disk | Kurulum öncesi Docker cache temizliğinden sonra yaklaşık 40 GiB boş alan | İki 4B model ve web arayüzü için yeterli çalışma alanı oluştu |

## Kurulum mimarisi

```text
Tarayıcı
  → Open WebUI (yalnız 127.0.0.1:3003)
  → Ollama (yalnız 127.0.0.1:11434)
  → yerel model ağırlıkları
```

- `ai-journey-ollama`: resmî `ollama/ollama` container'ı
- `ai-journey-webui`: resmî `ghcr.io/open-webui/open-webui:main` container'ı
- İki container aynı özel Docker ağı üzerinde haberleşir.
- Web arayüzü yalnız loopback adresine bağlanır; yerel ağdaki başka cihazlara yayın yapılmaz.
- Open WebUI adresi: `http://127.0.0.1:3003`

İlk açılışta Open WebUI yerel admin hesabı oluşturulmasını ister. Arayüz model seçimi, system prompt, sohbet geçmişi ve yerel model testlerini görsel olarak yönetmek içindir; benchmark kayıtları ayrıca bu repoda saklanacaktır.

## Başlangıç model seçimi: Qwen3 4B

İlk model olarak Ollama'nın `qwen3:4b` paketi seçildi.

| Ölçüt | Gözlem | Yorum |
|---|---|---|
| Ollama paket boyutu | 2.5 GB | Disk ve 31 GiB RAM sınırına uygundur |
| Model artifact'i | Qwen3 4B Thinking 2507 | Bu paket reasoning odaklıdır; kısa cevap testlerinde düşünme bütçesi etkisi ayrıca ölçülmelidir |
| Quantization | Q4_K medium, yaklaşık 4.95 bit/weight | Tam hassasiyetli 4B ağırlıklara göre CPU/RAM için pratik bir trade-off |
| Lisans | Apache-2.0 | Model kartına göre ticari kullanıma izin veren açık lisans |
| Dil iddiası | 100+ dil ve lehçe desteği | Sağlayıcının iddiasıdır; Türkçe performansı yerel test setiyle ayrıca doğrulanmalıdır |
| Yerel context | İlk koşuda 4096 token | Modelin teorik üst sınırı değil, bu CPU ortamı için ilk operasyonel ayar |

Qwen model kartı 32.768 token native context ve 100+ dil/lehçe desteği bildirir. Bu değerler donanımımızda doğrudan kullanılacak context boyutu değildir; context büyüdükçe CPU bellek ve gecikme ölçümü yapılmalıdır.

## İlk gözlem: thinking modu bir ürün kararıdır

Kontrollü istek:

```text
Yalnızca şu kelimeyi yaz: hazır
```

İlk ölçüm koşulu:

```text
model       = qwen3:4b
temperature = 0
num_predict = 8
```

| Ölçüt | Sonuç |
|---|---:|
| İlk istek toplam süresi | 15.04 sn |
| Model yükleme süresi | 11.79 sn |
| Prompt token sayısı | 21 |
| Üretilen token sayısı | 8 |
| Görünür cevap | Boş |

Neden görünür cevap boş kaldı?

- İndirilen Qwen artifact'i `Thinking` olarak etiketlidir.
- Model önce internal reasoning üretmeye başladı.
- `num_predict=8`, görünür nihai cevaba geçmeden tükendi.

Bu “model çalışmadı” sonucu değildir. Şu mühendislik sonucunu gösterir:

> Token bütçesi, thinking ayarı ve chat template; model kalitesinden bağımsız olarak ürünün gecikmesini ve görünür cevabını değiştirebilir.

İkinci uzun koşuda model yaklaşık `4.45 token/sn` üretim hızına ulaştı. Ancak kısa ve kesin talepte bile reasoning metnini uzattığı için bu model, system/user prompt deneyinde tek başına kullanılmayacak; reasoning davranışının kalite/latency maliyetini temsil eden model olarak tutulacaktır.

## Chat template bulgusu

Ollama paketinin template'i yeni assistant turunu `<think>` ile başlatıyordu. API'deki `think: false` denemesi bu artifact'te beklenen şekilde kısa cevap moduna geçmedi.

`tools/ollama/Modelfile.qwen3-4b-instruct-local` dosyası, resmî Qwen tokenizer template'indeki `enable_thinking=false` yaklaşımını incelemek için oluşturuldu. Aynı model ağırlıklarını tekrar indirmeden `qwen3:4b-instruct-local` adlı yerel türev yaratır.

Bu türev ilk kısa testte reasoning etiketini kapatsa da modelin meta-muhakeme metni üretmesini tamamen engellemedi. Bu da iki farklı olguyu ayırmamız gerektiğini gösterir:

1. **Chat template davranışı:** Başlangıçta `<think>` açılması
2. **Model davranışı:** Ağırlıkların kısa talepte bile uzun muhakemeye eğilim göstermesi

Template değişikliği yalnız ilkini etkiler; modelin öğrenilmiş üretim eğilimini tek başına değiştiremez.

## İkinci model ve karşılaştırma planı

İkinci aday `gemma3:4b` indirilmekte. Aynı 4B sınıfında olduğu için Qwen3 ile karşılaştırma daha anlamlı olacaktır.

Her iki modelde de aşağıdaki koşullar sabit tutulacak:

- Aynı CPU, RAM, Ollama sürümü ve context uzunluğu
- Aynı chat template kategorisi ve max output token sınırı
- `temperature=0` ve sabit seed, desteklendiği yerde
- Aynı Türkçe teknik soru, kod üretme, kod açıklama, özetleme, mantık ve yanıltıcı soru seti
- İlk cevap süresi, toplam süre, token/sn ve bellek kullanımı

Değerlendirme yalnız hız üzerinden yapılmayacak:

| Boyut | Soru |
|---|---|
| Doğruluk | Yanıt referans bilgiyle uyumlu mu? |
| Talimat uyumu | System prompt ve istenen formatı izliyor mu? |
| Groundedness | Verilmeyen bilgiyi uyduruyor mu? |
| Tutarlılık | Aynı koşulda benzer davranıyor mu? |
| Verimlilik | İlk token, toplam süre ve token/sn ne? |
| Bellek | Çalışırken RAM kullanımı ne? |

## Kullanılan kaynaklar

- Qwen resmî model kartı: https://huggingface.co/Qwen/Qwen3-4B
- Qwen resmî tokenizer/chat template'i: https://huggingface.co/Qwen/Qwen3-4B/blob/main/tokenizer_config.json
- Ollama Qwen3 kütüphane kaydı: https://ollama.com/library/qwen3
- Open WebUI resmî imajı: https://github.com/open-webui/open-webui

## Sıradaki adım

1. Gemma 3 4B indirmesini tamamla ve aynı kısa testle ilk latency ölçümünü al.
2. Open WebUI içinden iki modelin de görünürlüğünü doğrula.
3. System prompt ile user message deney setini versioned dosya olarak oluştur.
4. Aynı test setini iki modelde çalıştır; sonuçları tablo ve yorum raporuna dönüştür.
