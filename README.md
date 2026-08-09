# AI Engineering Journey

Hi, I'm Alperen. This repository documents my journey to become a production-oriented AI Engineer.

## Goal

Build practical skills in:

- Python engineering
- Machine learning
- Deep learning
- RAG systems
- LLM applications
- AI agents
- MLOps
- Cloud deployment
- Evaluation and monitoring

## Learning Format

Each day follows this structure:

1. Learn the concept
2. Build a small artifact
3. Commit the work
4. Document progress

## Current Progress

- Pre-roadmap foundation: Python engineering, SQL, EDA, baseline ML, validation, and experiment logging
- Month 1/9 completed: mini RAG from scratch with chunking, TF-IDF, hybrid retrieval, no-answer detection, and answerability evaluation
- Month 2/9 in progress: dense embeddings, semantic retrieval, dense/lexical hybrid retrieval, threshold experiments, and cross-encoder reranking

Current planning documents:

- [Revised 9-month AI Engineering roadmap](docs/ai_engineering_9_aylik_revize_plan_2026.md)
- [Internship Week 1 program comparison and integration](docs/staj_1_hafta_program_karsilastirmasi.md)
- [Internship Week 2 product engineering implementation plan](docs/internship/week2/hafta2_uygulama_plani.md)

## Week 2 Document Intelligence Service

The current local deployment is intentionally small: Qdrant, one API process,
and a static demo UI. Ollama stays on the host so the 32 GB RAM machine does
not run a second model container. The API uses the SQLite registry and a
bounded background ingestion task; a separate worker and Redis are deliberately
left for a later scale-out decision.

```bash
docker compose up --build -d
curl -i http://127.0.0.1:8010/v1/health/live
curl -i http://127.0.0.1:8010/v1/health/ready
open http://127.0.0.1:8501
```

The Compose Qdrant service is reachable from the host on `6335` by default,
because the earlier local demo may already occupy `6333`. Run the reproducible
smoke with:

```bash
./toolbox/scripts/run_document_service_compose_smoke.sh
```

The API listens on container port `8000` and host port `8010` by default,
because other local services occupy host ports `8000` and `8001`. Override either
host port explicitly with `API_HOST_PORT=8000` or `QDRANT_HOST_PORT=6333` only
after confirming that port is free.

If readiness is `503`, inspect the dependency checks; this is deliberately
reported as not-ready instead of allowing the UI to claim that answer queries
are available. On this workstation Ollama runs as the existing
`ai-journey-ollama` container and is bound to its Docker network rather than
the host gateway. The reproducible local check connects that container to the
Compose network and sets the correct URL automatically:

```bash
./toolbox/scripts/run_document_service_compose_smoke.sh
```

For a long-running local stack after that network connection exists, start it
with `DIS_OLLAMA_URL=http://ai-journey-ollama:11434 docker compose up --build -d`.
On another machine where Ollama is exposed through the host gateway, the
default `host.docker.internal:11434` remains the portable setting.

## Repository Philosophy

This is not a passive course repo.
Every folder should contain proof of work: scripts, notebooks, tests, reports, demos, or deployment artifacts.

## Local Git Hooks

This repository includes Git hooks under `.githooks`.

After cloning the repository, enable hooks with:

```bash
git config core.hooksPath .githooks
```

The current hook validates commit messages using the Conventional Commits format:

```text
type(scope): short description
```

Example:

```text
docs(repo): add contributing guide
```

## Current Artifacts

- `toolbox/`: shell scripts and CLI notes
- `labs/lin_alg/vec.py`: pure Python vector operations and cosine similarity
- `labs/lin_alg/text_similarity.py`: word-count based text similarity demo
- `labs/lin_alg/debug_examples.py`: handled debugging examples

## Weekly Summaries

- [Week 1 — Foundations](docs/week1_summary.md)

## Useful Commands

Run Week 1 checks:

```bash
./toolbox/scripts/run_week1_checks.sh
```

### Type Checking

- `pyproject.toml` configures mypy in strict mode.
- `examples/w2d2_type_check_demo.py` demonstrates typed DailyLog usage.

### Type Checking

- `pyproject.toml` configures mypy in strict mode.
- `examples/w2d2_type_check_demo.py` demonstrates typed DailyLog usage.

### Testing

- `tests/test_domain.py` covers Artifact, Milestone, and DailyLog behavior.
- `pytest` is used for automated unit tests.

### Matrix Multiplication

- `labs/lin_alg/matrix.py` implements pure Python matrix multiplication.
- `labs/lin_alg/matrix_benchmark.py` compares pure Python matrix multiplication with NumPy.

### Matrix Multiplication

- `labs/lin_alg/matrix.py` implements pure Python matrix multiplication.
- `labs/lin_alg/matrix_benchmark.py` compares pure Python matrix multiplication with NumPy.

### Pandas Basics

- `data/raw/students.csv` is a small toy dataset for EDA practice.
- `labs/data/pandas_basics.py` demonstrates loading CSV data, checking missing values, and simple groupby analysis.

### Data Cleaning

- `labs/data/clean_students.py` fills missing student data and writes a cleaned CSV.
- `data/processed/students_clean.csv` is generated from the raw student dataset.

### SQL Basics

- `labs/data/sql_basics.py` writes the cleaned student dataset to SQLite.
- SQL examples cover SELECT, WHERE, ORDER BY, LIMIT, and GROUP BY.

### EDA Report

- `labs/data/eda_report.py` generates a Markdown EDA report from the cleaned student dataset.
- `docs/w3_eda_report.md` summarizes missing values, target distribution, group statistics, and modeling readiness.


### Feature Dataset

- `labs/data/build_features.py` splits the cleaned student dataset into features and target.
- The generated files under `data/processed/` are ready for a baseline classification model.


### Baseline ML Classifier

- `labs/ml/train_baseline_classifier.py` trains a Logistic Regression baseline model.
- `docs/w3_baseline_model_report.md` summarizes accuracy, predictions, and model limitations.

## Week 3 — Data and Baseline ML

- [Week 3 Summary](docs/week3_summary.md)
- [W3 EDA Report](docs/w3_eda_report.md)
- [W3 Baseline Model Report](docs/w3_baseline_model_report.md)

Run Week 3 checks:

```bash
./toolbox/scripts/run_week3_checks.sh
```
