.PHONY: help install test lint format clean docker-build docker-up docker-down run analyze-tables

help:
	@echo "Multi-Agent Orchestrator - Available Commands:"
	@echo ""
	@echo "  make install          - Install dependencies"
	@echo "  make install-dev      - Install with development dependencies"
	@echo "  make test             - Run tests"
	@echo "  make test-cov         - Run tests with coverage"
	@echo "  make lint             - Run linting (ruff)"
	@echo "  make format           - Format code (black)"
	@echo "  make clean            - Clean build artifacts"
	@echo "  make docker-build     - Build Docker image"
	@echo "  make docker-up        - Start Docker containers"
	@echo "  make docker-down      - Stop Docker containers"
	@echo "  make run              - Run the orchestrator CLI"
	@echo "  make analyze-tables   - Analyze Unity Catalog tables"
	@echo ""

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -e .

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

lint:
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports

format:
	black src/ tests/
	ruff check src/ tests/ --fix

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d
	@echo "Services started! Redis available at localhost:6379"
	@echo "To view logs: docker-compose logs -f"

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

run:
	python src/main.py

analyze-tables:
	python -c "from src.main import MultiAgentOrchestrator; o = MultiAgentOrchestrator(); print(o.analyze_tables())"

# Development helpers
dev-setup: install-dev
	cp .env.example .env
	@echo "Created .env file - please edit with your credentials"
	mkdir -p data/logs data/vector_stores data/sessions data/cache
	@echo "Development environment ready!"

# Quick test a specific file
test-file:
	@echo "Usage: make test-file FILE=tests/test_basic.py"
	pytest $(FILE) -v

# Generate requirements from current environment
freeze:
	pip freeze > requirements.txt

# Check for security vulnerabilities
security:
	pip install safety
	safety check

# View system stats
stats:
	python -c "from src.main import MultiAgentOrchestrator; o = MultiAgentOrchestrator(); import json; print(json.dumps(o.get_stats(), indent=2))"
