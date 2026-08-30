.PHONY: data smoke baseline eval test
CONFIG ?= configs/smoke.yaml

data:            ## rebuild benchmark conditions from upstream templates
	cd ../INSIDER_LLM_DETECTION_BENCHMARK && python build_conditions.py

smoke:           ## run the smoke-test config end to end (no classifier)
	uv run ild run --config $(CONFIG)

baseline:        ## model-log-only and random detectors on a results dir
	uv run ild baseline --run $(RUN)

eval:            ## six outcome cells + metrics on a results dir
	uv run ild eval --run $(RUN)

test:
	uv run pytest -q
