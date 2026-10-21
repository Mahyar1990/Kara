PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: setup up down status logs doctor check check-model spec-bootstrap spec-check

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
	$(PYTHON) scripts/check_specs.py
	$(PYTHON) -m unittest discover -s scripts -p 'test_*.py'

spec-bootstrap:
	bash scripts/spec-kit.sh bootstrap

spec-check:
	$(PYTHON) scripts/check_specs.py

check-model:
	$(PYTHON) scripts/check_company_model.py
