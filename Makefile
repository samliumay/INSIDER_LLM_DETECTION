.PHONY: data validate smoke baseline eval test publish-results
RESULTS_REPO ?= logicBombExe/INSIDER_LLM_DETECTION_RESULTS
CONFIG ?= configs/smoke.yaml

data:            ## rebuild benchmark conditions from upstream templates
	uv run python ../INSIDER_LLM_DETECTION_BENCHMARK/build_conditions.py

validate:        ## run the benchmark's validation gate
	cd ../INSIDER_LLM_DETECTION_BENCHMARK && python3 validate.py

smoke:           ## run the smoke-test config end to end
	uv run ild run --config $(CONFIG)

baseline:        ## model-log-only and random detectors on a results dir — NOT YET IMPLEMENTED
	@echo "ild baseline is not implemented yet (audit 2026-09-01); see evaluation_plan.md §7" && exit 1

eval:            ## regenerate ../results/tables.md and INDEX.md from all runs
	uv run ild eval

publish-results: ## mirror ../results/ to the HF results dataset repo (hf CLI must be logged in)
	hf upload $(RESULTS_REPO) ../results . --repo-type dataset --commit-message "results: $$(date -u +%Y-%m-%dT%H:%M:%SZ)"

test:
	uv run python -m pytest tests/ -q
