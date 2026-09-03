# Experiment log

Corpus reset on **2026-09-03**: every earlier run (smoke, validation and pilot batches, 2026-08-30 → 2026-09-02) was deleted, together with the numbers that had been copied from them into this file and the READMEs. What those batches taught the pipeline survives as code and rules — the parser fixtures in `tests/fixtures/` (one real episode per format failure met), the six-value `logged` schema, the `no_answer` / `no_log` / `not_instructed` separations, the dirty-tree refusal, the reparse omission report — but none of their counts is cited anywhere any more.

Calls go through Ollama (`*:cloud` models) or OpenRouter (the original Agentic Misalignment snapshots). `harmful` is the classifier label (`ild classify` + `ild relabel`: pinned upstream classifiers, Gemini judge on `final_text`, upstream's deterministic gates on the full completion). The log-accuracy **evaluator** (`logged_accurate` vs `logged_inaccurate`) is not built; deterministic matching stops at `logged_matched`, and no accurate/inaccurate call is made in this file.

## Study sweep — 2026-09-03

One design for every model, nothing pooled across designs: the full 18-condition grid (3 scenarios × goal {explicit-america, none} × urgency {none, restriction, replacement}) × 5 prompt variants (`none` = original prompt verbatim, A routine audit, B safety monitoring, C automated log-gated shutdown, D = C + enumerated prohibition) × 3 samples = **270 episodes per model**, temperature **1.0**, `max_tokens` 24000, seed 0 (+ sample index), `phase: study`, clean code and benchmark trees. Configs: `configs/study_*.yaml`.

| Model | Provider | Config |
|-------|----------|--------|
| deepseek-v4-pro:cloud | Ollama cloud | `study_deepseek-v4-pro.yaml` |
| deepseek-v4-flash:cloud | Ollama cloud | `study_deepseek-v4-flash.yaml` |
| glm-5.3-flash:cloud | Ollama cloud | `study_glm-5.3-flash.yaml` |
| deepseek/deepseek-r1 | OpenRouter | `study_deepseek-r1.yaml` |
| qwen/qwen3-235b-a22b | OpenRouter | `study_qwen3-235b.yaml` |
| meta-llama/llama-4-maverick | OpenRouter | `study_llama-4-maverick.yaml` |
| openai/gpt-4.1 | OpenRouter | `study_gpt-4.1.yaml` |

Status: **running** (started 2026-09-03 15:44). Completion, classification and the generated tables (`make eval` → `results/tables.md`) will be recorded here when the sweep finishes; per-episode numbers are never typed into this file by hand.
