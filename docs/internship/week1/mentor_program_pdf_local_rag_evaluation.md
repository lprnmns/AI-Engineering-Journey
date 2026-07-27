# Mentor Programı PDF'i — Yerel LLM ile Uçtan Uca RAG Değerlendirmesi

Model: `gemma3:4b` (Q4_K_M, CPU)  
Retrieval: bölüm-bilinçli ingestion → dense top-5 → cross-encoder reranking  
Üretim politikası: yalnız verilen context, kaynak dışı bilgi için `YETERLİ BAĞLAM YOK`  
Çıktı limiti: 64 token

## Neyi tamamladık?

Önceki aşamalarda PDF'den doğru section/chunk buluyor ve rerank ediyorduk. Bu deney o kanıtı gerçek yerel modele bağladı:

`PDF → section-aware ingestion → chunk → dense top-5 → rerank → context → Gemma 3 4B → cevap veya no-answer`

## V1 — Yalnız en iyi chunk context'i

Ham sonuç: [top-1 JSON](mentor_program_pdf_local_rag_eval_top1.json)

| Ölçüm | Sonuç |
| --- | ---: |
| Toplam vaka | 5 |
| Genel doğruluk | 3/5 = %60 |
| Kaynaklı cevap doğruluğu | 1/3 = %33 |
| Kaynak dışı maaş sorusunu reddetme | 1/1 = %100 |
| Prompt injection'ı reddetme | 1/1 = %100 |

Kaynak dışı iki vaka doğru biçimde reddedildi. Ancak amaç ve yerel model ölçüm sorularında seçilen tek chunk cevap için eksik kaldı. Örneğin `local_model_chunk_006` hız/doğruluk değerlendirmesini taşıyordu; “ilk cevap süresi, toplam süre, bellek” bilgisinin bir kısmı komşu chunkta kaldı. Model, eksik kanıttan sayı veya özellik uydurmak yerine no-answer verdi. Bu yanlış cevap değil, eksik context tasarımı bulgusudur.

Gözlenen duvar saati gecikmesi 19.6–83.6 saniye/vaka aralığındaydı. Teslim paketi tablosu yaklaşık 1.147 karakter context ile 64 token sınırına ulaştı ve cevabı listeyi tamamlamadan kesildi.

## V2 — Top-3 chunk ve 900 karakter context bütçesi

Hedef, komşu kanıtı eklemekti. Yerel model vakasında reranker top-3 sonucu context'e verildi:

`chunk_006, chunk_003, chunk_002` → 834 karakter

Ham sonuç: [top-3 / 900 karakter JSON](mentor_program_pdf_local_rag_eval_top3_context900_local_model.json)

Bu vaka yine no-answer verdi. Nedeni context'in kısa olması değil, seçilen üç child chunkın “ilk cevap süresi / toplam süre / bellek” cümlesini birlikte taşımamasıydı. Sadece top-k büyütmek doğru kanıtı garanti etmez.

Tam beş vakalık top-3 koşusu, bu makinedeki eşzamanlı CPU/RAM yükünde sonuç dosyası yazmadan sonlandı. Bu nedenle ona doğruluk oranı atanmamıştır; sonuç yalnızca kontrolsüz context büyütmenin mevcut yerel ortamda kararlı bir çözüm olmadığını göstermektedir.

## V3 — Small-to-big / parent-section context

Bu tasarımda küçük chunklar yalnız doğru section'ı bulmak için kullanıldı. Reranker `local_model_chunk_006` ile `local_model` section'ını seçti; LLM'e tek chunk yerine o section'ın tamamı verildi.

`child chunk ile bul → parent section ile cevapla`

Ham sonuç: [parent-section JSON](mentor_program_pdf_local_rag_eval_parent_section_local_model.json)

| Vaka | Sonuç | Context | Gecikme |
| --- | --- | ---: | ---: |
| Yerel modelde hangi değerler ölçülür? | Başarılı: “İlk cevap süresi, toplam süre ve mümkünse bellek kullanımı...” | 742 karakter | 109.5 sn |

Bu tek vaka, parent-section genişletmenin kanıt yeterliliğini düzelttiğini gösterir; tüm beş vaka için genelleme değildir. Gecikme yüksek olduğu için sonraki optimizasyon konusu nettir: section'ı tam vermek yerine cevapla ilgili sentence'ları seçmek veya daha hızlı yerel model kullanmak.

## Türkçe evaluation hatası

İlk parent-section cevabı doğru olduğu halde otomatik test başarısız görünüyordu. Sebep model değil, Unicode normalizasyonuydu: büyük `İ`, `casefold()` sonrası `i` + birleşik nokta işareti oluyordu; eski regex bunu `i lk` biçimine ayırıyordu. Normalizasyon NFKD + birleşik işaret temizleme ile düzeltildi ve bu durum iki testle güvenceye alındı.

Bu da LLM evaluation'da metin eşleştirmenin kendisinin de test edilmesi gerektiğini gösterir. Yanlış evaluator, doğru modeli yanlış kararlarla değiştirmeye yöneltebilir.

## Mühendislik sonucu

Bu aşamada sistemin tamamı çalışıyor; ancak “production-ready” demiyoruz. Bilinen sonuçlar:

1. Section-aware ingestion doğru bölümü bulmayı iyileştiriyor.
2. Reranking candidate sırasını iyileştiriyor ama eksik chunk bağlamını kendiliğinden tamamlamıyor.
3. Small-to-big retrieval cevap doğruluğunu artırabilir.
4. 32 GB RAM / CPU ortamında Gemma 3 4B ile context ve output bütçesi doğrudan kullanıcı gecikmesine dönüşüyor.
5. No-answer ve injection reddi küçük test setinde olumlu; daha geniş test seti ve bağımsız retrieval guard kalibrasyonu hâlâ gerekli.
