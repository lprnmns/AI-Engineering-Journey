# Mentor Programı PDF'i — Bölüm-Bilinçli Ingestion Deneyi

Kaynak: `Alperen_Manas_Staj_Programi_1_Hafta 1.pdf` (5 sayfa)  
Embedding: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`  
Reranker: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`

Ham ölçüm: [JSON](mentor_program_section_retrieval_experiment.json)

## Problem

İlk PDF deneyi tüm sayfaları tek düz metne birleştirip cümle bazlı chunk'ladı. Bu yaklaşımda iki hata görüldü:

1. Her sayfada tekrarlayan `BILGEADAM ... Sayfa` üst bilgisi çok sayıda chunka gürültü ekledi.
2. `04 Yerel modeli ayağa kaldır ve karşılaştır` bölümü sayfa 3'ün sonunda başladı; `Büyük` kelimesi bir sayfada, `model` diğer sayfada kaldı. Düz page-splitting bunu daha da böldü.

Bu nedenle PDF'in görsel sayfa sınırını değil, metnin mantıksal bölüm sınırını korumayı denedik.

## Uygulanan tasarım

PDF sayfaları ayrı ayrı çıkarıldı, tekrarlayan üst bilgi kaldırıldı ve ardından metin sayfa sırasıyla tekrar birleştirildi. Böylece sayfa geçişindeki `Büyük model` ifadesi korunur. Bu mentor belgesinde bilinen yedi başlık configuration olarak tanımlandı:

`Programın Amacı`, `01 ...`, `02 ...`, `03 ...`, `04 Yerel modeli ...`, `05 ...`, `Teslim Paketi`.

Her section ayrı document oldu; section başlığı chunk title/metadata olarak taşındı. Sonra aynı ayarla chunking uygulandı:

`section document → 2 cümlelik chunk, overlap 1 → dense top-5 → cross-encoder top-1`

Bu tasarım 48 chunk üretti. Önceki düz metin deneyi 53 chunk üretmişti.

## Ölçüm sonucu

| Sorgu | Önceki düz PDF bulgusu | Bölüm-bilinçli dense sonuç | Reranker sonucu |
| --- | --- | --- | --- |
| `İlk haftanın amacı nedir?` | Amaç bölümü dense top-1 | Beklenen `purpose` bölümü dense top-1, skor 0.683 | Aynı bölümdeki gerçek amaç paragrafını seçti. |
| `Yerel model karşılaştırmasında hangi değerler ölçülmelidir?` | Doğru bölüm dense top-5'te yoktu | Beklenen `local_model` bölümü dense top-1, skor 0.663 | Aynı bölümde ölçüm kriterlerini içeren chunkı korudu. |
| `Teslim paketinde hangi çalışmalar bulunur?` | Teslim tablosu dense top-1 değildi; reranker ilgili bölgeye geçti | Beklenen `deliverables` bölümü dense top-5 içinde 4. sırada | `deliverables` chunkını 1. sıraya taşıdı. |

Reranker skorları farklı sorular arasında mutlak kalite puanı değildir; yalnız o sorunun adaylarını sıralamak için kullanılır. Yerel model sorusundaki negatif skor, adaylar içindeki en iyi seçimin yine doğru section olduğu gerçeğini değiştirmez.

## Ne öğrendik?

RAG kalitesi yalnız embedding modeli veya reranker seçimi değildir. Ingestion aşamasında document structure kaybolursa, sonraki katmanlar kaybolan başlığı ve bölünmüş cümleyi tam olarak geri getiremez.

Bu deneyde section başlıkları bilinen, tek bir mentor PDF'i için açıkça configuration olarak verildi. Bu bir genel PDF parser değildir. Farklı belge ailelerinde başlıkların, tabloların, OCR kalitesinin ve metadata kurallarının ayrı değerlendirilmesi gerekir. Üretim sisteminde bu kural document family bazında sürümlenir ve golden query setiyle test edilir.

Sonuç olarak doğru sıra şudur:

`ingestion kalitesi → candidate generation → reranking → answerability → cevap`

Reranking, kötü ingestion'ın yerine geçen bir katman değil; doğru adaylar üretildikten sonra hassasiyet ekleyen katmandır.
