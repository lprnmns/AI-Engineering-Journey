# ADR-005: Ollama host/container sınırı

## Bağlam

Geliştirme makinesinde 32 GB RAM vardır ve Ollama kurulumu host üzerinde kullanılmaktadır. API container'ı içinde ikinci bir model runtime'ı çalıştırmak bellek ve operasyon maliyetini artırır.

## Alternatifler

1. Ollama'yı API container'ına almak.
2. Ollama'yı host'ta tutup API/worker'dan erişmek.

## Karar

Ollama host'ta `:11434` üzerinde kalacak; API ve worker `host.docker.internal` üzerinden `gemma3:4b` modeline erişecek. Model request başına yüklenmeyecek; startup/warm-up ve latency ölçümleri ayrı raporlanacak.

## Ölçüm/kanıt

Warm/cold latency, resident memory, failure davranışı ve Firefox açıkken sistem stabilitesi ölçülecek.

## Bilinen sınır

Host erişim adresi işletim sistemi ve Docker network ayarlarına bağlıdır; Compose health check bunu açıkça raporlamalıdır.

