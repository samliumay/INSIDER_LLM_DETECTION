.PHONY: data smoke baseline eval test
CONFIG ?= configs/smoke.yaml

data:            ## rebuild benchmark conditions from upstream templates
	cd ../INSIDER_LLM_DETECTION_BENCHMARK && python build_conditions.py

smoke:           ## run the smoke-test config end to end (no classifier)
	uv run ild run --config $(CONFIG)

baseline:        ## model-log-only and random detectors on a results dir — NOT YET IMPLEMENTED
	@echo "ild baseline is not implemented yet (audit 2026-08-31); see evaluation_plan.md §7" && exit 1

eval:            ## six outcome cells + metrics on a results dir — NOT YET IMPLEMENTED
	@echo "ild eval is not implemented yet (audit 2026-08-31); see evaluation_plan.md §5-6" && exit 1

test:
	uv run python -m pytest -q
