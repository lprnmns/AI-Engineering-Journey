# V4 Doğrudan Cevap / Üslup Deneyi

Model: `gemma3:4b`  
Set: 8 genişletilmiş vaka  
V4 ek kuralı: Kaynak cümlesini kopyalamadan, kullanıcı sorusunu doğrudan ve yüklem içeren tek cümleyle cevapla.

## Sonuç

| Metrik | V4 |
| --- | ---: |
| Kaynaklı cevap başarısı | `%100` |
| No-answer doğruluğu | `%0` |
| Injection direnci | `%100` |
| Genel bilgi/doğruluk başarısı | `%75` |
| Hedef üslup eşleşmesi | `%25` |

Ham sonuç: [JSON](gemma3_4b_local_rag_eval_v4.json)

## Neden V4 seçilmedi?

V4, “yıllık izin kaç gündür?” türü kaynak dışı sorularda `YETERLİ BAĞLAM YOK` demek yerine kaynak cümlesini tekrar etti. Böylece V3'te doğru çalışan no-answer davranışı bozuldu.

Bu deney ayrıca otomatik kalite ölçümünün sınırını gösterdi. `Ekip yöneticisinden yazılı onay alınmalıdır.` dilbilgisel olarak tam ve doğrudan bir cümledir; ancak mekanik hedefimiz yalnız `almalısınız` ifadesini aradığı için bunu hedef üsluba uymadı saydı. Bu değer genel “cevap kalitesi” değildir, yalnız dar bir **hedef üslup eşleşmesi**dir.

## Mühendislik kararı

- Güvenilirlik için V3 prompt politikası korunur.
- V4'ün doğrudan cevap kuralı güvenlik metriğini bozduğu için kullanılmaz.
- Üslup/dil kalitesi, kaynaklılık ve no-answer kontrolünden ayrı değerlendirilmelidir. Gerekirse uygulama tarafında yanıt şablonu veya daha güçlü bir modelle ikinci aşama düzenleme düşünülür; bu düzenleme de kaynaktan sapmama açısından ayrıca ölçülmelidir.
