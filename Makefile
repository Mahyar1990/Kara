PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: setup up down status logs doctor check check-model prepare-analysis prepare-review prepare-planning prepare-base-agent

setup:
	$(PYTHON) scripts/local_dify.py setup

up:
	$(PYTHON) scripts/local_dify.py up

down:
	$(PYTHON) scripts/local_dify.py down

status:
	$(PYTHON) scripts/local_dify.py status

logs:
	$(PYTHON) scripts/local_dify.py logs

doctor:
	$(PYTHON) scripts/local_dify.py doctor

check:
	$(PYTHON) scripts/check_project.py
	$(PYTHON) scripts/build_klassor_analysis.py --check
	$(PYTHON) scripts/build_klassor_review.py --check
	$(PYTHON) scripts/build_klassor_planning.py --check
	$(PYTHON) scripts/build_base_agent.py --check
	$(PYTHON) -m unittest discover -s scripts -p 'test_*.py'

check-model:
	$(PYTHON) scripts/check_company_model.py

prepare-analysis:
	$(PYTHON) scripts/build_klassor_analysis.py --local

prepare-review:
	$(PYTHON) scripts/build_klassor_review.py --local

prepare-planning:
	$(PYTHON) scripts/build_klassor_planning.py --local --model AIFA-Sand

prepare-base-agent:
	$(PYTHON) scripts/build_base_agent.py --local --model AIFA-Sand
