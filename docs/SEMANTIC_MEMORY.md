# Optional offline semantic memory

The default remains lexical retrieval. To enable semantic retrieval in a Python 3.12 environment:

```bash
python -m pip install torch==2.9.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-semantic.txt
python -m titan.semantic --download
export TITAN_MEMORY_MODE=semantic
export HF_HUB_OFFLINE=1
python -m tests.semantic_acceptance
```

Run the API/worker with those variables and the same provisioned model cache. The base Docker image does not include these optional dependencies or weights: provision them in a derived image and make the cache readable to its non-root runtime user before enabling semantic mode. Requests never download models. Missing weights/dependencies fail explicitly, without pretending lexical results are semantic.

Pinned all-MiniLM-L6-v2 weights execute on CPU, with remote code disabled and safetensors required. Model download requires internet; subsequent embedding inference does not require a provider key or transmit memory text to a model service. CPU, RAM and disk still consume host resources.

Retrieval searches the latest 500 nonexpired records in the requested project. It embeds up to the first 4,000 characters per record in four chunks; longer records are labelled truncated. Vectors persist in SQLite, are tied to content hashes and model identity, and regenerate when content changes. Database snapshots include them. Literal memory search remains available separately.

This is bounded English semantic retrieval. Six frozen paraphrase queries passed with the real model in CI, together with scope, expiry, update and restart-cache checks. This small benchmark does not establish multilingual accuracy or production-scale latency. Cold indexing is synchronous and can be slow; do not equate a six-query benchmark with a load test.

Evidence: `docs/evidence/semantic-acceptance.json` and GitHub Actions run 41295972496. Chat/debate inference remains separately unverified.
