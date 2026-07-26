# Mentor Programı PDF'i — Dense Retrieval ve Reranking Deneyi

Kaynak: `Alperen_Manas_Staj_Programi_1_Hafta 1.pdf` (5 sayfa)  
Chunk ayarı: 2 cümle, overlap 1 (53 chunk)  
İlk aşama: `paraphrase-multilingual-MiniLM-L12-v2` ile cosine similarity, top-5  
İkinci aşama: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` ile top-5 içinden yeniden sıralama, top-1

Ham ölçüm: [JSON](mentor_program_pdf_rerank_experiment.json)

## Akış

`Soru → 53 chunk içinde hızlı dense arama → en iyi 5 aday → her (soru, chunk) çiftini cross-encoder ile birlikte okuma → en iyi 1 parça`

Dense retrieval'da soru ve her chunk ayrı ayrı 384 boyutlu vektöre çevrilir; bu yüzden bütün koleksiyonda hızlı arama yapılabilir. Reranker ise vektör karşılaştırması yapmaz: soruyu ve bir adayı aynı token dizisinde birlikte okuyup doğrudan “bu aday bu soruyu cevaplar mı?” sinyali üretir. Bu daha pahalı olduğu için yalnızca ilk 5 adayda kullanıldı.

## Sonuçlar

| Sorgu | Dense top-1 | Reranker seçimi | Değerlendirme |
| --- | --- | --- | --- |
| `İlk haftanın amacı nedir?` | Chunk 004, 0.597, amaç bölümü | Aynı chunk; reranker 0.269 | Zaten doğru olan retrieval korundu. |
| `Yerel model karşılaştırmasında hangi değerler ölçülmelidir?` | Chunk 002, 0.536, genel program girişi | Aynı chunk; reranker -4.290 | İyileşmedi. Asıl yerel model bölümü dense top-5 adayına bile girmediği için reranker onu seçemez. |
| `Teslim paketinde hangi çalışmalar bulunur?` | Chunk 006, 0.451, genel çıktı yaklaşımı | Chunk 052; dense sırada 5, reranker 1.564 | İyileşti: `Teslim Paketi` tablosunun başladığı parçaya geçti. |

Reranker skorları yalnızca aynı sorgunun adaylarını sıralamak içindir. Örneğin `1.564`, `0.269` ve `-4.290` değerlerini farklı sorularda mutlak kalite puanı gibi karşılaştıramayız.

## Dürüst yorum

Bu katman sihirli bir düzeltme değildir. Reranker yalnız kendisine verilen adaylar arasında seçim yapabilir:

- Teslim paketi sorusunda dense retrieval doğru bölgeyi 5. sırada da olsa adaylara soktu; reranker bunu yukarı taşıdı.
- Yerel model sorusunda doğru bölüm ilk 5'e gelmedi; hata candidate-generation aşamasında kaldı.

Bu yüzden sonraki iyileştirme sırası şudur: PDF'den sayfa ve başlık metadata'sı çıkarmak, tablo metnini daha yapısal hale getirmek, dense top-k değerini ölçerek ayarlamak ve gerekirse hybrid retrieval (TF-IDF + dense) eklemek. Reranking, retrieval'ın yerine değil, onun üstüne eklenen bir hassasiyet katmanıdır.
