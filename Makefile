.PHONY: data smoke baseline eval test
CONFIG ?= configs/smoke.yaml

data:            ## rebuild benchmark conditions from upstream templates
	uv run python ../INSIDER_LLM_DETECTION_BENCHMARK/build_conditions.py

smoke:           ## run the smoke-test config end to end
	uv run ild run --config $(CONFIG)

baseline:        ## model-log-only and random detectors on a results dir — NOT YET IMPLEMENTED
	@echo "ild baseline is not implemented yet (audit 2026-09-01); see evaluation_plan.md §7" && exit 1

eval:            ## regenerate ../results/tables.md from all runs
	uv run ild eval

test:
	uv run python -m pytest tests/ -q
