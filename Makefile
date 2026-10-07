PYTHON ?= python3

.PHONY: setup up down status logs doctor check check-model

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
	$(PYTHON) -m unittest discover -s scripts -p 'test_company_model.py'

check-model:
	$(PYTHON) scripts/check_company_model.py
