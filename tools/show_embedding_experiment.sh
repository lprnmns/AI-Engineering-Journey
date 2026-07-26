#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
results="$repo_root/docs/internship/week1/turkish_embedding_similarity_results.json"

printf '\033c'
echo 'TÜRKÇE EMBEDDING VE SEMANTIC SEARCH DENEYİ'
echo
jq -r '"Model: \(.model_name) | Cümle: \(.sentence_count) | Boyut: \(.embedding_dimension)"' "$results"
echo
echo 'ÇİFT SKORLARI'
jq -r '.pair_results[] | "• \(.expectation): \(.cosine_similarity | tostring | .[0:5]) — \(.left_id) ↔ \(.right_id)"' "$results"
echo
echo 'SEMANTIC SEARCH — TOP 2'
jq -r '.query_rankings[] | "\nSorgu: \(.query_text)\n  1. \(.ranked_results[0].sentence_id) [\(.ranked_results[0].cosine_similarity | tostring | .[0:5])]\n  2. \(.ranked_results[1].sentence_id) [\(.ranked_results[1].cosine_similarity | tostring | .[0:5])]"' "$results"
echo
echo 'Kanıt: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
