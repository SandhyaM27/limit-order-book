.PHONY: install test lint typecheck check bench run docker docker-run clean

install:
	pip install -r requirements-dev.txt && pip install -e .

test:
	pytest -q

lint:
	ruff check . && ruff format --check .

typecheck:
	mypy

check: lint typecheck test

bench:
	python -m lob.benchmarks.benchmark

run:
	streamlit run dashboard/app.py

docker:
	docker build -t lob-dashboard .

docker-run:
	docker run --rm -p 8501:8501 lob-dashboard

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info benchmark_results.json
