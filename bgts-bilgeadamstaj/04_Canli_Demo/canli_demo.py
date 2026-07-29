"""Hafta 1 RAG teslimi için tek komutluk, canlı ve açıklamalı demo.

Çalıştırma:
    .venv/bin/python 02_Kod/canli_demo.py demo

Bu betik, PDF'i bilinen başlıklara göre section-aware parçalar; 384 boyutlu
embeddingleri Qdrant'a upsert eder; dense top-k adayları reranker ile yeniden
sıralar; kanıt eşiğini uygular ve (varsa) Ollama/Gemma ile kaynaklı cevap üretir.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import requests
from pypdf import PdfReader
from qdrant_client import QdrantClient, models
from sentence_transformers import CrossEncoder, SentenceTransformer

ROOT = Path(__file__).resolve().parent
PDF_PATH = ROOT / "Alperen_Manas_Staj_Programi_1_Hafta.pdf"
QDRANT_URL = "http://127.0.0.1:6333"
OLLAMA_URL = "http://127.0.0.1:11434"
COLLECTION = "mentor_program_pdf_v1"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RERANKER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
MIN_DENSE_SCORE = 0.45  # Yalnız bu PDF + bu ingestion sürümü için kalibre edilmiştir.
HEADER = "BILGEADAM TEKNOLOJI | STAJYER GELİŞİM PROGRAMI Sayfa"
SECTIONS = [
    ("purpose", "Programın Amacı", "Programın Amacı"),
    ("model_fundamentals", "01 Modelin nasıl düşündüğünü anla", "01 Modelin nasıl düşündüğünü anla"),
    ("embedding", "02 Embedding ve anlamsal aramayı somutlaştır", "02 Embedding ve anlamsal aramayı somutlaştır"),
    ("rag", "03 RAG akışının tamamını kur", "03 RAG akışının tamamını kur"),
    ("local_model", "04 Yerel modeli ayağa kaldır ve karşılaştır", "04 Yerel modeli ayağa kaldır ve karşılaştır"),
    ("corporate_problem", "05 Gerçek bir kurumsal problem seç", "05 Gerçek bir kurumsal problem seç"),
    ("deliverables", "Teslim Paketi", "Teslim Paketi"),
]


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    section_id: str
    title: str
    text: str
    parent_text: str
    chunk_index: int


def heading(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def wait(message: str) -> None:
    if sys.stdin.isatty():
        input(f"\n{message} [Enter]")


def section_aware_chunks(pdf_path: Path) -> list[Chunk]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF bulunamadı: {pdf_path}")
    pages = []
    for page in PdfReader(str(pdf_path)).pages:
        text = " ".join((page.extract_text() or "").split())
        pages.append(text.removeprefix(HEADER).strip())
    full_text = " ".join(page for page in pages if page)
    positions = []
    for section_id, title, marker in SECTIONS:
        position = full_text.find(marker)
        if position < 0:
            raise RuntimeError(f"PDF içinde bölüm başlığı bulunamadı: {marker}")
        positions.append((position, section_id, title))
    if positions != sorted(positions):
        raise RuntimeError("PDF bölüm başlıkları beklenen sırada değil")

    chunks: list[Chunk] = []
    for index, (start, section_id, title) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(full_text)
        parent = full_text[start:end].strip()
        sentences = [item.strip() for item in __import__("re").split(r"(?<=[.!?])\s+", parent) if item.strip()]
        # İkişer cümle ve bir cümle overlap: son tek-cümlelik tekrar chunkı
        # üretmeyiz. Bu, teslimde ölçülen 48 chunk stratejisiyle aynıdır.
        offsets = range(0, max(len(sentences) - 1, 1), 1)
        for chunk_index, offset in enumerate(offsets, start=1):
            text = " ".join(sentences[offset : offset + 2])
            if text:
                chunks.append(Chunk(f"{section_id}_chunk_{chunk_index:03d}", section_id, title, text, parent, chunk_index))
    return chunks


def qdrant() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, timeout=15)


def start_qdrant() -> None:
    heading("1/5 — Qdrant başlatılıyor")
    # Aynı makinede repo geliştirme ortamının Qdrant'ı zaten açık olabilir.
    # Bu durumda ikinci container port 6333'e bağlanamaz; mevcut sağlıklı
    # servisi kullanmak hem doğru hem de demo için yeterlidir.
    try:
        info = qdrant().get_collections()
        print(f"OK: Qdrant zaten erişilebilir ({len(info.collections)} collection). Mevcut servis kullanılacak.")
        return
    except Exception:
        pass
    subprocess.run(["docker", "compose", "up", "-d", "qdrant"], cwd=ROOT, check=True)
    try:
        qdrant().get_collections()
    except Exception as exc:  # pragma: no cover - environment specific
        raise RuntimeError("Qdrant başlatılamadı veya health check başarısız") from exc
    print("OK: Qdrant yerelde 127.0.0.1:6333 üzerinde erişilebilir.")


def check_environment(require_ollama: bool = False) -> bool:
    heading("Ortam kontrolü")
    print(f"PDF: {'OK' if PDF_PATH.exists() else 'YOK'} — {PDF_PATH.name}")
    try:
        info = qdrant().get_collections()
        print(f"Qdrant: OK — {len(info.collections)} collection görüldü")
    except Exception:
        print("Qdrant: KAPALI — `python 02_Kod/canli_demo.py up` çalıştırın")
    try:
        tags = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3).json().get("models", [])
        names = {item.get("name") for item in tags}
        print(f"Ollama: {'OK' if 'gemma3:4b' in names else 'Gemma 3 4B YOK'}")
        if require_ollama and "gemma3:4b" not in names:
            print("Not: retrieval demosu çalışır; LLM cevabı için `ollama pull gemma3:4b` gerekir.")
            return False
        return True
    except requests.RequestException:
        print("Ollama: KAPALI — retrieval demosu yine çalışabilir.")
        return not require_ollama


def ingest() -> int:
    heading("2/5 — Section-aware PDF ingestion")
    chunks = section_aware_chunks(PDF_PATH)
    model = SentenceTransformer(EMBEDDING_MODEL)
    vectors = model.encode([f"{chunk.title} {chunk.text}" for chunk in chunks], normalize_embeddings=True, show_progress_bar=False)
    store = qdrant()
    if store.collection_exists(COLLECTION):
        store.delete_collection(COLLECTION)
    store.create_collection(COLLECTION, vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE))
    points = [
        models.PointStruct(
            id=str(uuid5(NAMESPACE_URL, f"week1/{chunk.chunk_id}")),
            vector=vector.tolist(),
            payload={"chunk_id": chunk.chunk_id, "section_id": chunk.section_id, "title": chunk.title, "text": chunk.text, "parent_text": chunk.parent_text, "chunk_index": chunk.chunk_index, "ingestion_version": "section-aware-v1"},
        )
        for chunk, vector in zip(chunks, vectors)
    ]
    store.upsert(COLLECTION, points, wait=True)
    count = store.count(COLLECTION, exact=True).count
    print(f"OK: {len(SECTIONS)} section, {count} kalıcı Qdrant point, 384 boyutlu vektör.")
    return count


def ask(question: str, generate: bool = True, step: int = 3) -> bool:
    heading(f"{step}/5 — Soru: {question}")
    embedder = SentenceTransformer(EMBEDDING_MODEL)
    hits = qdrant().query_points(COLLECTION, query=embedder.encode(question, normalize_embeddings=True).tolist(), limit=5, with_payload=True).points
    if not hits:
        raise RuntimeError("İndeks boş. Önce `ingest` çalıştırın.")
    print("Dense top-5 aday:")
    for hit in hits:
        print(f"- {hit.payload['chunk_id']} | {hit.payload['section_id']} | cosine={hit.score:.3f}")
    if hits[0].score < MIN_DENSE_SCORE:
        print(f"\nKARAR: YETERLİ BAĞLAM YOK (top dense {hits[0].score:.3f} < {MIN_DENSE_SCORE:.2f})")
        print("LLM çağrılmadı: no-answer politikası modelden önce çalıştı.")
        return False
    reranker = CrossEncoder(RERANKER_MODEL, max_length=512)
    scores = reranker.predict([(question, f"{hit.payload['title']} {hit.payload['text']}") for hit in hits], show_progress_bar=False)
    best, score = max(zip(hits, scores), key=lambda item: float(item[1]))
    context = str(best.payload["parent_text"])[:3000]
    print(f"\nReranker seçimi: {best.payload['chunk_id']} | score={float(score):.3f}")
    print(f"Parent section: {best.payload['section_id']} | context={len(context)} karakter")
    print(f"Kanıt önizleme: {best.payload['text']}")
    if not generate:
        return True
    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate", json={"model": "gemma3:4b", "prompt": f"Yalnız aşağıdaki KAYNAK ile Türkçe, kısa cevap ver. Kaynak soruyu cevaplamıyorsa tam olarak YETERLİ BAĞLAM YOK yaz.\n\nKAYNAK:\n{context}\n\nSORU:\n{question}", "stream": False, "options": {"temperature": 0, "top_k": 1, "seed": 42}}, timeout=600)
        response.raise_for_status()
        print(f"\nGemma cevabı:\n{response.json().get('response', '').strip()}")
    except requests.RequestException as exc:
        print(f"\nOllama yok/erişilemedi; kanıt zinciri yine başarıyla gösterildi. ({exc})")
    return True


def guided_demo() -> None:
    heading("HAFTA 1 — CANLI RAG DEMOSU")
    print("Akış: ortam → kalıcı indeks → kaynaklı soru → kaynak dışı soru → mühendislik yorumu")
    start_qdrant()
    wait("Ortam kontrolünü göstermek için devam et")
    check_environment(require_ollama=False)
    wait("PDF'i section-aware biçimde indekslemek için devam et")
    ingest()
    wait("Cevaplanabilir örneği göstermek için devam et")
    ask("Yerel model karşılaştırmasında hangi değerler ölçülmelidir?")
    wait("No-answer davranışını göstermek için devam et")
    ask("Stajyer maaşı ne kadar?", generate=False, step=4)
    heading("5/5 — Kapanış cümlesi")
    print("Dense retrieval aday bulur; reranker kanıtı seçer; eşik zayıf kanıtta LLM çağrısını keser.")
    print("Bu yüzden RAG, yalnız top-k chunk getirip modelden cevap istemek değildir.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hafta 1 için canlı, section-aware RAG demosu")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("up", help="Qdrant containerını başlat")
    sub.add_parser("check", help="PDF, Qdrant ve Ollama durumunu göster")
    sub.add_parser("ingest", help="PDF'i section-aware biçimde Qdrant'a indeksle")
    ask_parser = sub.add_parser("ask", help="Kanıt zinciri ve isteğe bağlı Gemma cevabı göster")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--no-generate", action="store_true", help="Ollama çağrısını atla")
    sub.add_parser("demo", help="Sunumda kullanılacak adım adım interaktif akışı çalıştır")
    args = parser.parse_args()
    if args.command == "up":
        start_qdrant()
    elif args.command == "check":
        check_environment()
    elif args.command == "ingest":
        ingest()
    elif args.command == "ask":
        ask(args.question, generate=not args.no_generate)
    else:
        guided_demo()


if __name__ == "__main__":
    main()
