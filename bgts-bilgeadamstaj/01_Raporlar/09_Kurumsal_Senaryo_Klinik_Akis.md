# Kurumsal Senaryo ve İlk Ürün Fikri — Klinik Akış

**Alan:** Sağlık teknolojisi içinde kurumsal yazılım (B2B SaaS)  
**İlk odak:** Türkiye'deki özel diş klinikleri  
**Durum:** Sonraki haftalarda geliştirilecek ürün fikri; bu rapor gerçek hasta pilotu, canlı otomasyon veya ticari sonuç iddiası değildir.

## 1. Problem

Özel diş kliniklerinde yeni hasta adaylarının önemli bir bölümü WhatsApp üzerinden hizmet, fiyat aralığı, hekim, uygun saat, randevu değişikliği ve iptal hakkında soru sorar. Küçük ve orta ölçekli klinikte bu görüşmeler resepsiyonist, telefon, takvim ve bazen Excel ya da mevcut klinik yazılımı arasında dağılır. Mesaj yoğun olduğunda geç yanıt, unutulan talep, yanlış bilgi, aynı saate çakışan randevu ve mesai dışı kaçan talep riski ortaya çıkar.

Problem “kliniğe chatbot yapalım” değildir. Operasyonel soru şudur:

> Klinik, WhatsApp'tan gelen **idari** randevu talebini doğru bilgiyle, gerçek uygunlukla ve insan denetimiyle nasıl yönetir?

Tıbbi teşhis, semptom yorumu, reçete, görüntü/X-ray analizi ve tedavi önerisi bu problemin dışındadır. Sistem bunları cevaplamaya çalışmak yerine resepsiyoniste veya yetkili kliniğe aktarır.

## 2. Kullanıcılar ve bugünkü iş akışı

| Kullanıcı | Bugünkü ihtiyacı | İlk ürünün görevi |
| --- | --- | --- |
| Hasta adayı | Hızlı ve net bilgi, uygun saat, insan desteği | WhatsApp üzerinden onaylı idari bilgiyi ve uygun slotu göstermek |
| Resepsiyonist | Dağınık konuşmaları yönetmek, hatalı talepleri ayıklamak | Tek inbox, otomatik taslak, devralma ve randevu aksiyonu |
| Klinik sahibi / operasyon sorumlusu | Kaçan talebi, yoğunluğu ve kalite hatasını görmek | Dönüşüm, handoff ve güvenlik metriği |
| Diş hekimi / klinik yöneticisi | Hizmet süresi, fiyat söylemi ve riskli dil üzerinde kontrol | Onaylı katalog/politika ve tıbbi sorularda zorunlu handoff |

Mevcut temel akış şöyledir:

```text
Hasta adayı → WhatsApp mesajı → resepsiyonistin yorumu
→ telefon / takvim kontrolü → manuel cevap → randevu veya kayıp talep
```

Önerilen dar akışta otomasyon yalnız yetkili sınırlar içinde çalışır:

```text
WhatsApp mesajı → niyet + risk sınıflandırması
→ onaylı klinik bilgisi / uygunluk verisi
→ güvenliyse cevap veya slot önerisi
→ belirsiz, tıbbi ya da düşük güvenli durumsa insan devralma
→ audit ve operasyon metriği
```

## 3. İlk dar MVP

İlk sürüm **tek özel diş kliniği, tek şube, tek WhatsApp hattı** ile sınırlı düşünülür.

### Kapsam içi

- Hizmet kataloğu, tahmini süre, çalışma saati ve klinik onaylı fiyat söylemi.
- İdari niyetler: hizmet/fiyat politikası, çalışma saati, randevu talebi, uygunluk, değişiklik ve iptal.
- Yapılandırılmış uygunluk üzerinden slot önerisi; randevu oluşturma işlemi sunucu tarafında doğrulanır.
- Klinik onaylı bilgi kaynağından kaynaklı cevap; bilinmeyen bilgi için no-answer/handoff.
- Tıbbi, acil, düşük güvenli veya prompt-injection içeren konuşmada insan devralma.
- Resepsiyonist inbox'ı, devralma nedeni ve işlem kaydı.
- Basit operasyon paneli: ilk yanıt, randevu talebi, handoff ve hata olayları.

### Bilinçli kapsam dışı

- Teşhis, tedavi planı, reçete, tıbbi görüntü ve hasta klinik kaydı.
- Ödeme, sigorta, toplu pazarlama, çoklu kanal, çoklu şube ve tam EHR/HIS entegrasyonu.
- “AI tüm resepsiyonisti değiştirir” iddiası.

Bu sınır ürünün zayıflığı değil, güvenli ilk deney için tasarım kararıdır.

## 4. Veri ve AI tasarımı

İlk sürümde veri mümkün olduğunca iki sınıfa ayrılır:

| Veri | Kaynak | Kullanım | Risk / kontrol |
| --- | --- | --- | --- |
| Hizmet, süre, çalışma saati, fiyat politikası | Klinik yöneticisinin onayladığı yapılandırılmış katalog | Deterministik cevap ve slot hesabı | Sürüm, onay ve audit |
| Randevu uygunluğu | Yetkili takvim/randevu sistemi | Slot önerisi ve rezervasyon | Sunucu tarafı çakışma kontrolü |
| WhatsApp mesajı ve iletişim bilgisi | Hasta adayı | Niyet, handoff ve görüşme bağlamı | Veri minimizasyonu, erişim kontrolü, saklama politikası |
| Klinik bilgi metinleri | Klinik onaylı SSS/politika | RAG ile açıklayıcı idari cevap | Kaynak/citation, no-answer ve insan onayı |

AI'nin yapacağı iş serbestçe “doğru cevabı tahmin etmek” değildir. Niyet sınıflandırma, güvenli dil üretimi ve onaylı kaynaktan açıklama yapmaktır. Fiyat, çalışma saati ve slot gibi gerçekler LLM belleğinden değil yapılandırılmış kaynaktan gelir.

Bu nedenle bu haftaki RAG dersleri doğrudan ürüne bağlanır:

- **Embedding ve Qdrant:** Klinik onaylı SSS/politika içinden ilgili kanıtı bulmak.
- **Reranker ve parent context:** Yakın ama yanlış paragraf yerine daha uygun kanıtı seçmek.
- **Answerability threshold:** Kanıt yetersizse uydurma yerine handoff/no-answer vermek.
- **Gemma ölçümü:** Küçük yerel modelin injection'da uydurma yaptığını gördük; model tek başına güvenlik katmanı değildir.

İlk mimari hedefi şöyledir:

```text
WhatsApp webhook
→ tenant / izin / mesaj doğrulama
→ intent ve risk policy
→ structured facts + uygunluk sorgusu
→ gerekirse Qdrant retrieval + rerank + answerability
→ güvenliyse taslak/cevap veya slot
→ aksi durumda insan handoff
→ audit, metrik ve düzeltme kaydı
```

## 5. Başarı ölçümü

İlk pilotta satış veya gelir garantisi değil, süreç etkisi ölçülür.

| Ölçüm | Tanım | Neden önemli |
| --- | --- | --- |
| Median first-response time | İlk hasta mesajından ilk yanıta süre | Mesai dışı ve yoğunluk etkisini görür |
| Qualified appointment conversion | Nitelikli randevu niyetinin onaylı randevuya dönüşümü | Ürünün operasyonel değerini ölçer |
| Human handoff rate | İnsan devralmaya giden güvenli/riskli konuşma oranı | Otomasyon kapsamını ve iş yükünü gösterir |
| Unsafe-answer / incorrect-price incident | Yanlış fiyat, tıbbi cevap veya kaynak dışı yanıt olayı | Hızın güvenlik pahasına kazanılmadığını kontrol eder |
| Invalid/double-booking incident | Geçersiz ya da çakışan randevu olayı | Takvim entegrasyonunun doğruluğunu ölçer |
| Human correction rate | İnsan tarafından düzeltilen AI taslağı oranı | Bilgi kalitesi ve politika eksiğini gösterir |

Başlangıç hedefleri hipotezdir. Örneğin “ilk yanıt süresini düşürmek” test edilebilir bir hedeftir; “geliri kesin artırır” iddiası değildir.

### Pilot öncesi baseline planı

Şu anda gerçek bir kliniğin mesaj hacmi veya personel maliyeti ölçülmüş değildir; bu nedenle bu rapor tasarruf ya da gelir rakamı uydurmaz. Faz 0'da, izinli ve kişisel veri minimize edilmiş iki haftalık bir örnek üzerinde aşağıdakiler kaydedilir:

- mesajın geldiği saat, ilk insan yanıtı ve konuşmanın çözülme zamanı;
- randevu niyeti, teklif edilen slot, onaylanan randevu ve kayıp talep;
- resepsiyonistin konuşmaya kaç kez dokunduğu;
- yanlış bilgi, yanlış slot veya insan devralma sebebi.

İş yükü maliyeti daha sonra şu şeffaf formülle hesaplanır: `toplam resepsiyonist dokunma süresi × saatlik personel maliyeti`. Ürün deneyi, bu baseline ile shadow-mode veya destekli akış sonucunu karşılaştırır. Böylece “zaman kazandırır” iddiası ölçülebilir hâle gelir.

## 6. Riskler ve güvenlik sınırları

1. **KVKK ve özel nitelikli veri:** Sağlık bağlamındaki konuşma verisi hassastır. Gerçek hasta verisi için veri sorumlusu/işleyen rolleri, saklama, erişim, aktarım ve sağlayıcı sözleşmeleri hukuk incelemesi gerektirir.
2. **Tıbbi aşım:** Semptom, teşhis ve tedavi sorularına AI cevap vermez; acil/riskli konuşma insan devralmaya gider.
3. **Uydurma veya prompt injection:** Bu haftaki yerel model deneyi, system promptun tek başına yeterli olmadığını gösterdi. Structured facts, tool izinleri, threshold, kaynak gösterimi ve audit birlikte gerekir.
4. **Çift randevu / yanlış slot:** Slot yalnız LLM metniyle oluşturulmaz; atomik sunucu kontrolü ve idempotent işlem gerekir.
5. **Yetkisiz erişim:** Klinikler arası veri karışmamalı; rol, tenant izolasyonu, audit log ve destek erişimi sınırlandırılmalıdır.
6. **Yanlış ürün konumlandırması:** Ürün “AI doktor” değil, insan denetimli klinik operasyon katmanıdır.

## 7. Sonraki haftalar için geliştirme planı

| Faz | Hedef | Bu haftadan taşınan kanıt |
| --- | --- | --- |
| Faz 0 — problem doğrulama | 3–5 klinik resepsiyonistiyle görüşme; mesaj türü, yoğun saat, mevcut araç ve hata örnekleri | Şimdiki problem/maliyet varsayımdır, müşteri kanıtı değildir |
| Faz 1 — sentetik dar demo | Onaylı katalog, mock WhatsApp, slot önerisi, handoff ve audit | RAG pipeline, no-answer, model seçimi |
| Faz 2 — shadow mode | Gerçek klinik politikasında AI yalnız taslak üretir; insan gönderir | Handoff, düzeltme oranı ve kalite eval'i |
| Faz 3 — sınırlı otomasyon | Sadece düşük riskli idari cevap ve randevu akışı | Eşik, kaynak doğrulaması, rollback ve incident metriği |

`/home/alperen/klinik-ai/` altındaki mevcut Klinik Akış çalışması bu ürün fikri için mimari referans ve öğrenme kaynağıdır. Ancak bu staj tesliminde onu bitmiş canlı ürün, gerçek hasta pilotu veya ticari başarı kanıtı olarak sunmayacağım. Bu raporda savunulan ürün; yukarıdaki dar kapsam ve sonraki fazlardan oluşan **gelecek geliştirme planıdır**.

## Sonuç

Klinik Akış, sağlık teknolojisi alanında fakat ürün türü olarak kurumsal yazılımdır. AI'nin doğru yeri, klinik onaylı idari bilgiyi ve randevu akışını desteklemektir; klinik karar vermek değildir. İlk değer önerisi “daha akıllı sohbet” değil, WhatsApp talebini güvenli, ölçülebilir ve insan denetimli randevu operasyonuna dönüştürmektir.
