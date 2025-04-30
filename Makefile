# Makefile
.PHONY: test test-cov test-html clean

PYTHONPATH := $(shell pwd)
export PYTHONPATH

test:
	pytest -v

test-cov:
	pytest --cov=src --cov-report=term-missing

test-html:
	pytest --cov=src --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

clean:
	rm -rf .coverage htmlcov/ .pytest_cache/ __pycache__/ */__pycache__/ */*/__pycache__/