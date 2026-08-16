# Contributing

AI Context Linker welcomes focused changes that preserve its privacy-first boundary.

## Before opening a change

1. Use only synthetic data in tests, examples, issues, and pull requests.
2. Do not paste source code, credentials, absolute local paths, or private runtime data into fixtures.
3. Keep facts, inference, and unknowns visibly separate.
4. Treat the graph as derived output, never as the source of truth.
5. Add a leakage or regression test for every schema, adapter, or filter change.

## Local checks

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ai_context_linker scan `
  --config examples/synthetic-workspace-config.json `
  --review-dir output/review
python -m ai_context_linker build `
  --manifest output/review/candidate-manifest.json `
  --output-dir output
python -m ai_context_linker slice `
  --manifest output/review/candidate-manifest.json `
  --question "What should I prioritize next?" `
  --output-dir output
```

## Pull requests

Explain the user problem, privacy impact, evidence used, and verification performed. Keep unrelated changes separate. New automatic adapters require an explicit security review before merge.
