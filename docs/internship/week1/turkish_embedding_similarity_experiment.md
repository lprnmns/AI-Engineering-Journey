# Türkçe Embedding ve Cosine Similarity Deneyi

Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`  
Ortam: Yerel Python, sentence-transformers 5.6.0  
Veri: 10 Türkçe cümle, 7 kontrollü çift  
Vektör boyutu: 384

## Sonuç tablosu

| Cümle çifti | Beklenti | Cosine similarity | Yorum |
| --- | --- | ---: | --- |
| Sanal ortam oluşturma / `venv` kurma | Yakın anlam | 0.512 | Aynı görevi farklı ifadelerle anlatıyor; skor, ilgisiz çiftlerden belirgin yüksek. |
| Sanal ortam / `pip` ile paket yükleme | Aynı teknik alan, farklı görev | 0.444 | Python bağlamı ortak, ancak görev aynı değil. |
| İzin talebini iletme / izin süresi | Aynı alan, farklı özellik | 0.593 | En kritik beklenmeyen sonuç: konu yakınlığı yüksek, fakat biri başvuru zamanı diğeri izin süresini soruyor. |
| Python sanal ortamı / Python yılanı | Ortak kelime, farklı anlam | 0.327 | Ortak `Python` kelimesi skoru tamamen sıfırlamadı; çevre bağlamı yine de teknik kullanım ile hayvan anlamını ayırdı. |
| Sanal ortam / makarna tarifi | İlgisiz | 0.022 | Çok düşük skor, beklenen davranış. |
| Pull request / hava durumu | İlgisiz | 0.050 | Çok düşük skor, beklenen davranış. |
| Vektör arama / `venv` kurulumu | Aynı genel teknik alan, farklı görev | 0.245 | İki cümle teknik olsa da görev ve kavramlar farklı. |

Ham veri: [JSON](turkish_embedding_similarity_results.json)

## Bu skorlar ne anlatır?

Embedding modeli cümleleri 384 boyutlu vektörlere dönüştürdü. Vektörler normalize edildiği için cosine similarity, vektör uzunluğundan çok yönlerinin ne kadar benzer olduğunu ölçer. `1` aynı yön, `0` yaklaşık ilişkisizlik, negatif değer ise zıt yön anlamına gelebilir. Gerçek cümle embeddinglerinde evrensel bir “0.50 üstü kesin alakalıdır” eşiği yoktur; eşik görev, dil, doküman ve modele göre değerlendirme verisiyle seçilir.

## En önemli mühendislik yorumu

İzin örneği, retrieval ile answerability arasındaki farkı gösterir. Vektör arama, yıllık izinle ilgili chunk'ı doğru biçimde üst sıralara getirebilir; fakat bu chunk kullanıcının sorduğu **izin süresi** bilgisini içermez. Bu nedenle production RAG sistemi yalnız yüksek cosine skoruna dayanarak cevap üretmemelidir. V3 prompt deneyindeki “özelliği ayır” kuralı ve no-answer denetimi bu boşluğu kapatmaya çalışır.

## Küçük anlamsal arama deneyi

Üç kullanıcı sorgusu, aynı 10 cümlenin tamamına karşı sıralandı:

| Sorgu | İlk sonuç | İlk skor | Yorum |
| --- | --- | ---: | --- |
| `Python için venv oluşturmak istiyorum.` | `Python'da venv kurmak için hangi adımları izlemeliyim?` | 0.802 | Doğru anlam alanı. Başlangıçta beklenen cümle ikinci sıradaydı; fakat o da aynı görevi anlatır. Tek bir “doğru belge” etiketi bu sorgu için gereğinden katıdır. |
| `İzin başvurumu ne zaman göndermeliyim?` | `Yıllık izin talebi en az 10 gün önce iletilmelidir.` | 0.575 | Doğru kaynak ilk sırada. İzin süresi cümlesi ikinci sırada kaldı; aynı alan yakınlığı yine görülüyor. |
| `Yarın İstanbul'da hava nasıl olacak?` | `İstanbul'da yarın hava yağmurlu olacak mı?` | 0.925 | Neredeyse aynı anlam; beklenen güçlü eşleşme. |

Bu deneyde retrieval değerlendirmesi için yeni bir kural ortaya çıktı: bazı sorguların tek doğru dokümanı değil, birden fazla kabul edilebilir doğru dokümanı olabilir. Bu nedenle gerçek RAG eval setinde tek `expected_doc_id` yerine gerektiğinde kabul edilebilir belge/fragment kümesi tanımlanmalıdır.

## Sınırlılıklar

- 10 cümle ve 7 çift, model kalitesi için benchmark değildir.
- Tek bir embedding modeli ve sabit cümleler kullanıldı.
- Skorlar semantic yakınlığı yaklaşıklar; doğruluk, güvenlik veya cevaplanabilirlik skoru değildir.
- İki cümleyi cosine ile karşılaştırmak, gerçek RAG'deki çok chunk'lı retrieval ve reranking aşamalarının yerine geçmez.
