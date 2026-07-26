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

## Sınırlılıklar

- 10 cümle ve 7 çift, model kalitesi için benchmark değildir.
- Tek bir embedding modeli ve sabit cümleler kullanıldı.
- Skorlar semantic yakınlığı yaklaşıklar; doğruluk, güvenlik veya cevaplanabilirlik skoru değildir.
- İki cümleyi cosine ile karşılaştırmak, gerçek RAG'deki çok chunk'lı retrieval ve reranking aşamalarının yerine geçmez.
