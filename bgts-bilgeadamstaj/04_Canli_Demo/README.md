# Canlı RAG Demo

Bu klasör, Hafta 1 teslimindeki section-aware RAG akışının tek komutluk, sunuma yönelik sürümüdür.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
docker compose up -d qdrant
.venv/bin/python canli_demo.py demo
```

`demo` komutu her aşamada Enter bekler: ortam kontrolü, PDF ingestion, kaynaklı soru ve kaynak dışı soru. İsteğe bağlı Gemma cevabı için Ollama'da `gemma3:4b` kurulu olmalıdır; model yoksa retrieval kanıt zinciri yine gösterilir.

Tek tek komutlar: `up`, `check`, `ingest`, `ask "..."` ve `demo`.

Not: `0.45` no-answer eşiği yalnız bu mentor PDF'i, bu embedding modeli ve bu section-aware ingestion sürümü için kalibre edilmiştir.
