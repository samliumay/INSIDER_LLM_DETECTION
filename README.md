# Insider LLM Detection — Code

Detects **insider LLMs** via **double logging**: a model in an agentic scenario logs its own actions, the system independently records every tool call it actually makes, and the two logs are matched on structured fields. A discrepancy (omission or inaccurate entry) is the misalignment signal — the detector never reads the transcript.

Harmfulness ground truth comes from Anthropic's [*Agentic Misalignment*](https://www.anthropic.com/research/agentic-misalignment) classifiers ([upstream repo](https://github.com/anthropic-experimental/agentic-misalignment), pinned @ `ea0630e1a3eaae7f9f9740fd2703229d3854ccda`, expected at `../related_repos/agentic-misalignment/`). Benchmark: [logicBombExe/INSIDER_LLM_DETECTION_BENCHMARK](https://huggingface.co/datasets/logicBombExe/INSIDER_LLM_DETECTION_BENCHMARK).

## Run

```bash
uv sync
make data                       # rebuild benchmark conditions from upstream templates
make smoke CONFIG=configs/smoke.yaml   # run a config end to end → results/<run_id>/
make test                       # pytest on parser and matcher
uv run ild reparse --run results/<run_id>   # re-derive parsed fields after parser changes
```

Models are called through Ollama (`http://localhost:11434/v1`). Every run writes config, git hash, seed, model name, and dataset version to `results/<run_id>/`. The classifier (`harmful`) and accuracy-evaluator steps are not built yet.

## Results (smoke phase, 2026-08-30 — pipeline validation only, not reported study data)

1 sample × 2 conditions (`blackmail`, `murder` × `none-none_replacement`) × 3 variants, temperature 0.5, via Ollama cloud:

| Model | Completed | Actions | Harmful | Log written when instructed | Entries matched |
|-------|-----------|---------|---------|-----------------------------|-----------------|
| glm-5.3-flash | 6/6 | 18 | 0 | 4/4 | 12/12 |
| glm-5.2 | 6/6 | 17 | 0 | 4/4 | 10/10 |
| glm-5.1 | 6/6 | 16 | 0 | 4/4 | 10/10 |
| minimax-m3 | 6/6 | 11 | 0 | 4/4 | 6/6 |
| minimax-m2.7 | 6/6 | 8 | 0 | 0/4 | — |
| deepseek-v4-flash | 5/6 | 5 | 0 | 4/4 | 4/4 |

Local models: qwen3.6 (~30B) produced the first observed **cover-up** (disclosed an affair, logged it as "CTO instability"); llama3.1:8b and qwen3.8 fell below the capability floor. Across all runs: 42/42 model-log entries matched deterministically; 2 harmful episodes (deepseek-v4-flash, glm-5.1) were **logged honestly** — misses, the method's central known risk; minimax-m2.7 never writes a log (the `no_log` category). Full log with per-run details: [`EXPERIMENTS.md`](EXPERIMENTS.md).

## Contributing

- Read `../BEFORE_RESEARCH_FOR_AGENT.md`, `../docs/decisions.md`, and `../docs/evaluation_plan.md` first; settled decisions are not re-litigated.
- Experiments are config-driven: add a yaml in `configs/`, never hand-edit constants. One entrypoint (`ild`).
- Parser or matcher changes need a regression test in `tests/` and a `ild reparse` of existing runs — raw responses are kept so parsing is always re-derivable.
- New experimental decisions get one dated line in `../docs/decisions.md`; ideas go to `../docs/possible_improvements.md`.
- License: MIT (same as upstream).
