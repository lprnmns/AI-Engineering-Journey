# Retrieval Benchmark Report — Initial Protocol

## Status

Bu dosya benchmark protokolünün ilk sürümüdür. Golden vaka sözleşmesi, offline
metric runner ve gerçek Qdrant ablation sonuçları aşağıda kayıtlıdır. Output
validation için ayrıca sınırlı gerçek Gemma smoke'u bulunur; bu, geniş LLM kalite
benchmarkı olarak yorumlanmamalıdır.

## Dataset

Primary dataset:

```text
data/evaluations/mentor_program_pdf_rag_golden_v1.jsonl
```

Toplam 44 vaka vardır: 30 answerable, 14 no-answer/injection/leakage hazırlık vakası. Kategoriler ve development/validation/test split'i dataset contract testiyle doğrulanır.

Gold hedefleri generated child point ID yerine section title üzerinden tutulur. Böylece ingestion pipeline version değiştiğinde etiketlerin anlamı korunur. Birden fazla section gerektiren vakalar `multi_evidence` olarak ayrıca işaretlenir.

## Protocol

Her retrieval strategy aynı golden soru sırasını kullanır:

```text
dense, bm25, hybrid
hybrid + reranker
```

İlk warm-up soruları kalite ortalamasına katılmaz. Reranker öncesi bounded candidate window ve final evidence ayrı kaydedilir. Timeout veya dependency error sonuçları silinmez; failure rate ve hata nedeni olarak raporlanır.

## Metrics

| Alan | Metrik | Yorum |
| --- | --- | --- |
| Candidate coverage | Candidate Recall@20 | Reranker'a ulaşan havuz doğru section'ı içeriyor mu? |
| Final retrieval | Recall@1/3/5 | Doğru gold hedef final sıralamada bulundu mu? |
| Ranking | MRR@5/10 | İlk doğru kanıt ne kadar yukarıda? |
| Graded ranking | nDCG@5/10 | Birden fazla/öncelikli kanıtın sırası |
| Runtime | p50/p95 | Toplam, embedding, search, rerank süreleri |
| Answerability | no-answer FP/FN | Gereksiz ret ve corpus dışı cevap ayrımı |

Section'a ait duplicate child chunk'lar tek gold hedef sayılır. Bu, overlap nedeniyle metriklerin yapay olarak şişmesini önler.

## Current evidence

```text
Golden contract validation: passed
Metric/runner unit tests: passed
Mypy for evaluation slice: clean
Real Qdrant retrieval ablation: recorded
Real Gemma output-validation smoke: recorded (1 bounded query)
Structured query trace: request ID, question hash, stage latency and reason code
```

İlk protokol tamamlandı; retrieval strategy kararı aşağıdaki aynı corpus snapshot, aynı query sırası ve aynı warm-up protokolüyle alınmıştır. Yeni corpus veya model değişiminde bu sonuçlar otomatik olarak genellenmeyecektir.

## Measured ablation — 2026-08-10

Run manifest:

```text
git_sha: 6e0c748354a755e073e99f27ce1fa663a1e42e5b
active Qdrant points: 26 (collection toplamı: 26; eski/inactive version yok)
qdrant collection: document_chunks_v2_bm25
pipeline: section_aware_v1 + paraphrase-multilingual-MiniLM-L12-v2 + bm25_qdrant_idf_v2
golden cases: 44 (retrieval quality denominator: 30 answerable)
top_k: 5
warm-up: 3 query, quality hesabı dışında
LLM: çağrılmadı
```

| Strategy | Candidate Recall@20 | Recall@5 | MRR@10 | nDCG@10 | Total p50 | Total p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 0.993 | 0.901 | 0.875 | 0.930 | 29.5 ms | 39.3 ms |
| Sparse/BM25 mode | 0.987 | 0.818 | 0.784 | 0.838 | 5.6 ms | 7.8 ms |
| Hybrid RRF | 0.993 | **0.923** | **0.878** | **0.952** | 30.9 ms | **37.3 ms** |
| Dense + reranker | 0.993 | 0.912 | 0.836 | 0.933 | 1087.7 ms | 1364.7 ms |
| Hybrid + reranker | 0.993 | 0.912 | 0.833 | 0.933 | 1061.9 ms | 1402.1 ms |

Sparse/BM25 mode artık exact vocabulary kullanan `BM25SparseEncoder` kullanır.
BM25 term-frequency saturation encoder'da, corpus-level IDF Qdrant'ın IDF
modifier'ında uygulanır. Online index'te eski vektörleri stale yapmamak için
`b=0` seçilmiştir; bu tam BM25'in açıkça belgelenmiş bir online varyantıdır.
Türkçe morfoloji yine ayrı bir tokenizer/lemmatizer kapsamıdır.

### Yorum

- Hybrid, bu temiz corpus'ta dense'e göre Recall@5'i yaklaşık `+0.022`, sparse baseline'a göre `+0.106` artırdı.
- Üç yöntemde de Candidate Recall@20 çok yüksek (`0.987–0.993`). Sorun çoğunlukla doğru section'ın aday havuzuna girmemesi değil, final sıralamadaki yeridir.
- Reranker, hybrid'e göre Recall@5'i `0.923`ten `0.912`ye, MRR@10'u `0.878`den `0.833`e düşürdü; bu koşuda p95'i `37.3 ms`ten `1402.1 ms`e çıkardı.
- Reranker'ın candidate recall'ı artırmadı (`0.993` → `0.993`); doğru kanıt zaten aday havuzundaydı. Ablation'da `8` pozitif ve `12` negatif flip raporlandı. Somut negatif örneklerden biri `near_miss_02`; hybrid'in bulduğu `rag` section'ı reranker final top-5'ten çıkardı.

Karar: reranker varsayılan kapalı kalıyor. İleride farklı cross-encoder, daha iyi section-aware evidence aggregation veya validation split üzerinde threshold/reranker tuning yapılmadan varsayılan açılmayacak.

## Answerability gate smoke — 2026-08-10

Hybrid retrieval ile, Ollama çağırmadan aynı 44 vaka üzerinde gate çalıştırıldı:

```text
expected answerable: 30
expected no-answer: 14
predicted answerable: 32
predicted no-answer: 12
```

Bu provisional eşiklerde:

```text
no-answer false positive: 0 / 30 = 0.0%
  → answerable vaka gereksiz reddedildi

no-answer false negative: 4 / 14 = 28.6%
  → corpus dışı vakalar cevaplanabilir sanıldı

gate total p50/p95: 34.9 ms / 39.0 ms
LLM çağrısı: 0
```

Temiz section-aware corpus'ta validation-only seçilen `0.331` runtime threshold
answerable vakaları gereksiz reddetmedi. Score gate açısından kalan false
negative'ler `no_answer_05`, `no_answer_06` ve leakage hazırlık vakalarından
oluşuyor; direct injection ve ACL filter bypass istekleri artık score gate'e
bırakılmadan `SECURITY_POLICY` ile kesiliyor. Threshold test sonucu üzerinden
geriye dönük ayarlanmadı; corpus dışı benzerlikler için provenance, ACL principal
ve daha güçlü evidence/claim policy hâlâ gereklidir.

## Validation-only threshold calibration

```text
dataset_sha256: 5e822afa5d648656b18339b0d552c53a2c234c8e4e8213c5da782f51a53e369e
calibration split: validation only; security categories excluded from score calibration
validation cases: 9 (7 answerable, 2 score-based no-answer)
test split used: false
false-negative cost: 3.0
selected score threshold: 0.330817965
rounded score threshold: 0.331
validation false-positive: 0 / 7 = 0.0%
validation false-negative: 0 / 2 = 0.0%
```

`0.331` yalnız score-bearing, security dışı dokuz vakalık küçük validation
alt kümesinin önerisidir; güçlü genelleme kanıtı değildir. Runtime default bu
temiz corpus snapshot'ına hizalanmıştır; yeni corpus/model/chunk ayarında tekrar
kalibrasyon gerekir. Böylece security policy'nin skor üretmediği vakalarla
threshold kararı birbirine karıştırılmıyor. Calibration çıktısı
[hybrid_threshold_calibration.json](../eval/results/hybrid_threshold_calibration.json)
dosyasındadır.

### Skor sırası düzeltmesi

Gerçek query smoke'unda RRF sırasındaki ilk candidate'ın dense skoru `0.456`,
ikinci candidate'ın dense skoru `0.488` olmasına rağmen eski margin hesabı
`0.456 - 0.488` yapıyordu. RRF sırası dense skor sırası olmadığı için valid bir
soru negatif margin ile reddedilebiliyordu. `5036c5c` commit'inde top-score ve
margin, seçilen score kind içindeki karşılaştırılabilir skorlar sıralanarak
hesaplandı. Benchmark ve calibration temiz active snapshot üzerinde `6e0c748`
ile yeniden üretildi.

## Security gate regression — test split

Prompt-injection ve cross-document leakage vakaları threshold seçimine dahil edilmeden yalnız frozen `test` split'te değerlendirildi:

```text
test security cases: 4
passed: 4 / 4 = 100%
leakage_acl: 2 / 2 passed
prompt_injection: 2 / 2 passed
failures: none
LLM çağrısı: 0
```

Bu sonuç modelin tek başına güvenli olduğunu göstermez; direct injection için
uygulama seviyesinde ayrı bir politika eklendiğini gösterir. `PromptSafetyPolicy`
yüksek güvenli kalıpları retrieval'dan önce kontrol ediyor: önceki kuralları
geçersiz kılma, kaynakları görmezden gelme, system prompt/gizli kural çıkarma,
kaynaksız kesin iddia ve ACL/document filter bypass. Engellenen istek
`SECURITY_POLICY` no-answer döner,
source listesi boş kalır ve LLM çağrılmaz. Kavramsal “system prompt nedir?”
soruları ise engellenmez. Ham rapor [security_test_gate.json](../eval/results/security_test_gate.json)
dosyasındadır.

### Defense-in-depth sınırı

Bu katman yalnız direct user-query injection'ını dar ve deterministik kurallarla
ele alır. Bilinmeyen saldırılar ve PDF içindeki instruction-like metinler için
Ollama system prompt'unda evidence açıkça `UNTRUSTED_EVIDENCE` olarak işaretlenir;
çıktı kaynakları model metninden değil canonical retrieval nesnelerinden alınır.
Bu yüzden güvenlik kararı tek bir regex veya tek bir LLM prompt'una değil,
`PromptSafetyPolicy → answerability → structured prompt → output validation`
zincirine yayılır. Rule set büyütülürken benign soru false positive oranı ayrıca
ölçülmelidir.

### Indirect evidence smoke

PDF içindeki talimat benzeri metnin doğrudan model komutuna dönüşmemesi için
`EvidenceSafetyPolicy` eklendi. Üç yüksek güvenli indirect injection fixture'ı
context'e girmeden çıkarıldı; prompt güvenliğini konu alan bir benign evidence
parçası korundu:

```text
indirect attacks: 3
blocked: 3 / 3
benign evidence allowed: 1 / 1
LLM çağrısı: 0
```

Bu deterministik smoke yalnız uygulama filtresini ölçer; gerçek LLM'in saldırı
metni karşısındaki üretim davranışının ayrıca ölçülmesi gerekir. Ham sonuç
[indirect_injection_smoke.json](../eval/results/indirect_injection_smoke.json)
dosyasındadır.

## Evidence coverage diagnostic — 2026-08-10

Golden setteki answerable vakaların `expected_phrases` etiketleri, final
retrieved evidence text'iyle ayrı bir diagnostic olarak karşılaştırıldı:

```text
answerable labeled cases: 30
fully covered: 25 / 30 = 83.3%
mean evidence phrase coverage: 94.3%
LLM çağrısı: 0
```

Bu ölçüm exact phrase yokluğunu doğrudan yanlış cevap saymaz; doğru bir
paraphrase etiketteki kelimeyi kullanmadan da geçerli olabilir. Ancak özellikle
multi-evidence vakalarında hangi beklenen unsurun final evidence'a girmediğini
göstermek için kullanılır. Ham vaka bazlı sonuç
[hybrid_evidence_coverage.json](../eval/results/hybrid_evidence_coverage.json)
dosyasındadır.

## Real local Gemma output-validation smoke — 2026-08-10

Gerçek Ollama `gemma3:4b` çağrısı, aynı Qdrant snapshot'ı ve bounded `top_k=2`,
`max_output_tokens=64` ayarlarıyla çalıştırıldı:

```text
decision: answered
model: ollama / gemma3:4b
answer: Yerel model karşılaştırmasında teknik doğruluk, uygulama kalitesi, mühendislik yorumu ve bağımsız ilerleme değerleri ölçülmelidir.
warnings: []
canonical sources: 2
embedding: 11406.7 ms
LLM: 39702.6 ms
total: 51134.0 ms
```

Bu gerçek model cevabında numeric validator warning üretmedi; ancak phrase
coverage smoke'u beklenen `ilk cevap süresi`, `toplam süre` ve `bellek`
unsurlarının hiçbirini cevapta bulamadı (`0/3`). Yani retrieval ve numeric
grounding olumlu görünürken cevap kapsamı eksik kalabildi. Bu tek soru genel
hallucination oranını kanıtlamaz; fakat `answered` kararının cevap kalitesi
garantisi olmadığını gösterir. Tekrar üretilebilir ham çıktı
[local_gemma_output_validation_smoke.json](../eval/results/local_gemma_output_validation_smoke.json)
dosyasındadır. LLM yaklaşık 35 saniye sürdüğü için 32 GB RAM/CPU ortamında
geniş gerçek-model evaluation koşusu yerine önce bounded smoke ve sonra seçilmiş
test slice'ları kullanılmalıdır.

## Output/evidence validation slice — 2026-08-10

### Problem

`answered` kararı yalnızca answerability gate'in geçildiğini gösterir. Gate doğru
section'ı bulsa bile local LLM evidence içinde olmayan bir sayı üretebilir.
Örneğin evidence `32 GB` içerirken cevap `64 GB` diyebilir. Retrieval başarısı
ile generation grounding başarısını aynı metrikte birleştirmemek için output
validation ayrı bir domain adımı olarak eklendi.

### İlk sözleşme

```text
generated answer + final RetrievedChunk evidence
  → numeric mention extraction
  → normalized numeric comparison
  → zero veya bir structured warning
```

Response örneği:

```json
{
  "warnings": [
    {
      "code": "UNSUPPORTED_NUMBER",
      "message": "Cevapta geçen bazı sayılar getirilen kanıtta bulunamadı; cevap insan incelemesine gönderilmelidir.",
      "values": ["64"]
    }
  ]
}
```

Modelin yazdığı kaynak adları doğrulama için kullanılmaz. `sources` listesi
retrieval'ın canonical payload'ından üretilmeye devam eder; böylece modelin
uydurduğu bir source ID API response'una güvenilir kaynak olarak giremez.

### Ne doğrulanıyor, ne doğrulanmıyor?

- Tam sayı ve ondalık sayıların evidence'ta bulunup bulunmadığı kontrol ediliyor.
- Türkçe ondalık virgül (`0,456`) ve nokta (`0.456`) aynı sayısal değer olarak ele alınıyor.
- Liste numaraları (`1.`, `2)`) ve `gemma3:4b` gibi model identifier parçaları
  factual number olarak işaretlenmiyor.
- Bu sürüm sayının geçtiği cümlenin anlamını, birimini veya neden-sonuç
  ilişkisini kanıtlamıyor.
- Warning şu an otomatik no-answer değildir; policy kararı için validation
  setinde warning precision/recall ve insan inceleme maliyeti ölçülmelidir.

### Kanıt

Domain, QueryService ve API contract seviyelerinde desteklenen sayı,
unsupported number, injection-style unsupported claim, canonical source ve
no-answer/LLM-skip davranışları test edildi. Hedefli testler ve mypy temizdir.
Fake generator testlerine ek olarak bir gerçek `gemma3:4b` smoke'u da çalıştırıldı;
tek cevapta warning oranı `0/1` gözlendi. Bu geniş bir grounding oranı değildir;
gerçek modelin numeric warning precision/recall dağılımı seçilmiş query slice'ları
üzerinde ayrıca ölçülmelidir.
