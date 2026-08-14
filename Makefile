.PHONY: setup test eval eval-train submit
PY := .venv/bin/python

setup:
	python3.12 -m venv .venv && .venv/bin/pip install -U pip numpy pytest

test:
	$(PY) -m pytest tests/ -q

eval:            ## the 120 public evaluation tasks
	$(PY) -m arc.evaluate evaluation

eval-train:      ## the 1000 public training tasks
	$(PY) -m arc.evaluate training

submit:          ## write submission.json
	$(PY) -m arc.submit data/evaluation
