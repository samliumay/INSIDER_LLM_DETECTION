# Insider LLM Detection — Code

Detects **insider LLMs** via **double logging**: a model in an agentic scenario logs its own actions, the system independently records every tool call it actually makes, and the two logs are matched on structured fields. A discrepancy (omission or inaccurate entry) is the misalignment signal — the detector never reads the transcript.

Harmfulness ground truth comes from Anthropic's [*Agentic Misalignment*](https://www.anthropic.com/research/agentic-misalignment) classifiers ([upstream repo](https://github.com/anthropic-experimental/agentic-misalignment), pinned @ `ea0630e1a3eaae7f9f9740fd2703229d3854ccda`). Clone it to `../related_repos/agentic-misalignment/` (a sibling of this repository); it is not bundled. Benchmark: [logicBombExe/INSIDER_LLM_DETECTION_BENCHMARK](https://huggingface.co/datasets/logicBombExe/INSIDER_LLM_DETECTION_BENCHMARK).

## Run

```bash
uv sync
cp .env.example .env            # add API keys (OPENROUTER_API_KEY for original-paper models, GEMINI_API_KEY for classify)
make data                       # rebuild benchmark conditions from upstream templates
make smoke CONFIG=configs/smoke.yaml   # run a config end to end → ../results/<run_id>/
make test                       # pytest on parsing, matching, classification gates, and aggregation
uv run ild reparse --run ../results/<run_id>    # re-derive parsed fields after parser changes; prints every episode that newly becomes `not_logged` for hand verification
uv run ild classify --run ../results/<run_id>   # label harmful via the pinned upstream classifiers (Gemini judge)
make eval                       # regenerate ../results/tables.md and INDEX.md from all runs
make publish-results            # mirror ../results/ to the HF results dataset repo
```

Models are called through any OpenAI-compatible endpoint: Ollama (`http://localhost:11434/v1`, default) for local/cloud models, or a provider like OpenRouter by setting `base_url` + `api_key_env` in the config (see `configs/*_openrouter_*.yaml`). Every run writes config, git hash (with `-dirty` flag), seed, model name, Ollama model digest, prompt-set hash, and dataset version to `../results/<run_id>/meta.json`; failed episodes go to `failures.jsonl`. The runner **refuses a dirty code or benchmark tree** unless passed `--allow-dirty`, and **refuses an unpinned upstream checkout** unless passed `--allow-unpinned` — both stamp the run, so results stay reconstructible from config + commit + seed. Results live at `../results/` and are mirrored to the Hugging Face dataset repo [logicBombExe/INSIDER_LLM_DETECTION_RESULTS](https://huggingface.co/datasets/logicBombExe/INSIDER_LLM_DETECTION_RESULTS) (`make publish-results`); they are not included in this GitHub repository. Every config declares a `phase` (`smoke` / `validation` / `pilot` / `study`) and every run is stamped `reconstructible` (clean tree at run time); only `study` ∧ reconstructible runs enter the study table that `ild eval` generates, everything else is listed per run and never pooled. `ild classify` fills `harmful` using the upstream classifiers with a Gemini judge (`GEMINI_API_KEY` in `.env`; `--input final_text|response`, `--force` to relabel); `ild eval` regenerates the aggregate tables.

## CI

`.github/workflows/ci.yml` runs on every push and pull request, with no API keys and no model calls: `sync` (frozen `uv sync` + import every module), `test` (pytest), `fixture` (`ild fixture-check` re-derives 18 real episodes in `tests/fixtures/` — one per format failure the parser has met — and prints any transition into `not_logged`), `benchmark` (clones the benchmark at `[tool.ild].benchmark_tag` and upstream at `[tool.ild].upstream_commit` from `pyproject.toml`, runs `ild check-configs` and the benchmark's `validate.py`), and `docs` (tripwire: retired vocabulary and references to files outside this repository must not reappear in README.md or EXPERIMENTS.md). `make ci` runs the same steps locally. Model runs, classification and the results upload stay manual.

## Results

The results corpus was reset on 2026-09-03: every earlier run (smoke, validation and pilot batches from 2026-08-30 to 2026-09-02) was deleted so that the analysis starts from one clean design. The current corpus is the **study sweep of 2026-09-03** — `configs/study_*.yaml`: seven models, the full 18-condition grid × five prompt variants (`none`/A/B/C/D) × 3 samples = 270 episodes per model, temperature 1.0, 24k token cap, `phase: study`, clean trees.

| Config | Model | Provider |
|--------|-------|----------|
| `study_deepseek-v4-pro.yaml` | `deepseek-v4-pro:cloud` | Ollama cloud |
| `study_deepseek-v4-flash.yaml` | `deepseek-v4-flash:cloud` | Ollama cloud |
| `study_glm-5.3-flash.yaml` | `glm-5.3-flash:cloud` | Ollama cloud |
| `study_deepseek-r1.yaml` | `deepseek/deepseek-r1` | OpenRouter (original Agentic Misalignment snapshot) |
| `study_qwen3-235b.yaml` | `qwen/qwen3-235b-a22b` | OpenRouter (original snapshot) |
| `study_llama-4-maverick.yaml` | `meta-llama/llama-4-maverick` | OpenRouter (original snapshot) |
| `study_gpt-4.1.yaml` | `openai/gpt-4.1` | OpenRouter (original snapshot) |

Numbers are never hand-copied here: `make eval` regenerates `results/tables.md` (per-run table, study harm rates per model × scenario × variant, `logged` counts) and `results/INDEX.md`, which live with the raw runs in the results dataset. The run narrative and the per-sweep analysis are in [`EXPERIMENTS.md`](EXPERIMENTS.md). The older `configs/smoke_*`, `goalconflict*`, `strongB_*` and `CD_bigcloud_*` files are kept as the record of the pre-reset exploratory designs; their runs no longer exist.

## Contributing

`main` is protected by a ruleset (`.github/rulesets/main.json`): no direct pushes, no force-pushes, no deletion; changes arrive by pull request and merge only when the `test`, `fixture` and `benchmark` checks are green. The loop:

```bash
git switch -c <topic>           # never commit on main
make ci                         # the same gates CI runs; fix anything red before pushing
git push -u origin <topic>
gh pr create --base main --fill # CI starts on the pull request
gh pr merge --merge             # once the three required checks pass
git switch main && git pull --ff-only
```

A direct `git push` to `main` is rejected with `GH013: Repository rule violations` — that is expected; move the commits to a branch (`git switch -c <topic>`) and open a pull request. If a check name in `.github/workflows/ci.yml` ever changes, update the ruleset to match or every merge blocks.


- **Protocol:** the experimental protocol (label definitions, prompt variants, the `phase`/`reconstructible` reporting rules) is fixed by the maintainer and documented in this repository's README, `EXPERIMENTS.md` and the benchmark's `labels/`. Open an issue before proposing a protocol change.
- Experiments are config-driven: add a yaml in `configs/`, never hand-edit constants. One entrypoint (`ild`).
- Parser or matcher changes need a regression test in `tests/` and a `ild reparse` of existing runs — raw responses are kept so parsing is always re-derivable.
- Experimental decisions are recorded by the maintainer; contributors propose changes through issues.
- License: MIT (same as upstream).
