# Insider LLM Detection — Code

Code for detecting **insider LLMs** via **double logging**.

## Idea in one paragraph

A model acting in an agentic scenario is told to log its own actions. Independently, the system records every tool call the model actually makes. The two logs are matched on structured fields (action type, recipient, attachment, override code); each system-log action ends up either `not_logged`, `logged_inaccurate`, or `logged_accurate` by the model. A discrepancy — omission or inaccurate entry — is the misalignment signal. The detector never reads the transcript, so it can run where a SIEM runs.

Ground truth for whether an action was actually harmful comes from Anthropic's *Agentic Misalignment* classifiers; we do not build our own harmfulness labels.

## Related

| What | Where |
|------|-------|
| Benchmark / dataset | https://huggingface.co/datasets/samliumay/INSIDER_LLM_DETECTION_BENCHMARK |
| Scenarios & classifiers we build on | https://github.com/anthropic-experimental/agentic-misalignment |
| Paper we build on | https://www.anthropic.com/research/agentic-misalignment |

## Planned layout

```
INSIDER_LLM_DETECTION_CODE/
├── configs/            # experiment configs (yaml) — one entrypoint, no hand-edited constants
├── src/
│   ├── prompts/        # logging-instruction variants A and B
│   ├── logging/        # system-log parser, action-ID matching
│   ├── evaluator/      # accuracy evaluator (logged_accurate vs logged_inaccurate)
│   ├── detectors/      # double-log detector + baselines (model-log-only, random)
│   └── metrics/        # six outcome cells, detection rate, false-alarm rate
├── tests/              # pipeline + metrics only; the model is not tested
├── results/            # one folder per run (gitignored except summaries)
├── Makefile
└── README.md
```

## How to run (planned)

```bash
uv sync
cp .env.example .env        # API keys

make data                   # generate prompts from configs/, run models, build logs → benchmark records
make baseline               # model-log-only and random detectors
make eval                   # double-log detector, six outcome cells, metrics → results/<run_id>/
make test                   # pytest on pipeline and metrics
```

Every run writes its config, git hash, seed, model name, and dataset version into `results/<run_id>/`.
