.PHONY: install test lint format build clean

install:
	uv pip install -e ".[dev]"

test:
	uv run python -m pytest tests/ -x -q

lint:
	uv run flake8 src/ tests/ --max-line-length=120 --ignore=E203,W503

format:
	uv run black src/ tests/ --line-length=120
	uv run isort src/ tests/ --profile=black

build:
	uv build

clean:
	rm -rf dist/ build/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
