# Mentor Programı PDF'i — Chunk Boyutu Deneyi

Kaynak: `Alperen_Manas_Staj_Programi_1_Hafta 1.pdf` (5 sayfa)  
Embedding modeli: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`  
Retrieval: normalize edilmiş dense embedding + cosine similarity, top-1

## Karşılaştırılan ayarlar

| Ayar | Chunk sayısı | Ortalama chunk uzunluğu |
| --- | ---: | ---: |
| Küçük: 2 cümle, overlap 1 | 53 | 252 karakter |
| Büyük: 5 cümle, overlap 1 | 14 | 639 karakter |

Ham ölçüm: [JSON](mentor_program_pdf_chunk_experiment.json)

## Gözlem tablosu

| Sorgu | Küçük chunk sonucu | Büyük chunk sonucu | Yorum |
| --- | --- | --- | --- |
| `İlk haftanın amacı nedir?` | Program amacı bölümü, skor 0.597 | İlk haftanın çalışma akışı çevresi, skor 0.502 | Küçük chunk hedef bölümü daha iyi izole etti. |
| `Yerel model karşılaştırmasında hangi değerler ölçülmelidir?` | Giriş/ölçüm vurgusu, skor 0.536 | İlk sayfa/giriş, skor 0.491 | İki ayar da asıl yerel model bölümünü top-1 getirmedi. |
| `Teslim paketinde hangi çalışmalar bulunur?` | Genel çıktı yaklaşımı, skor 0.451 | İlk sayfa/giriş, skor 0.454 | İki ayar da PDF sonundaki teslim paketi tablosunu top-1 getirmedi. |

## Ne öğrendik?

Küçük chunklar daha fazla aday üretir ve belirli bir paragrafı yakalama olasılığını artırır. Büyük chunklar daha geniş bağlam taşır; ancak bu PDF'de ilk sayfadaki genel program açıklaması çok sayıda sorguyla yüzeysel olarak ilişkili olduğu için retrieval'ı gölgeledi.

Bu deney “büyük chunk kötüdür” sonucunu vermez. Yalnızca bu belge, bu sorgular ve dense top-1 ayarında küçük chunkın amaç sorusunda daha isabetli olduğunu gösterir.

## Beklenmeyen sonuç ve sonraki iyileştirme

Teslim paketi sorgusunun iki ayarda da yanlış/genel chunk getirmesi önemli bir hata bulgusudur. Olası nedenler:

1. PDF text extraction, tablo yapısını düz metne dönüştürdü ve `Teslim Paketi` başlığının bağlamını zayıflattı.
2. Tek bir dense top-1 sonuç, yakın ama genel giriş metnini seçti.
3. Chunk'larda sayfa ve başlık metadata'sı yok; retrieval yalnız metin üzerinden karar verdi.

Sonraki adım, dense top-k adaylarını cross-encoder reranker'a vermek ve chunklara sayfa/başlık metadata'sı eklemektir. Böylece PDF ingestion → retrieval → reranking zinciri ölçülebilir hale gelir.
