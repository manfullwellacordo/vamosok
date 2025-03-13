.PHONY: install test lint format clean build docker-build docker-run

# Development
install:
	python -m pip install --upgrade pip
	pip install -r requirements.txt

dev:
	uvicorn app:app --reload --port 8001

test:
	pytest -v

coverage:
	pytest --cov=. tests/ --cov-report=html

lint:
	flake8 .
	black . --check
	isort . --check-only

format:
	black .
	isort .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +

# Build
build:
	python setup.py sdist bdist_wheel

# Docker
docker-build:
	docker build -t dashboard-contratos .

docker-run:
	docker run -p 8001:8001 dashboard-contratos

docker-compose-up:
	docker-compose up -d

docker-compose-down:
	docker-compose down

# Database
db-backup:
	@mkdir -p backups
	sqlite3 data/relatorio_dashboard.db ".backup 'backups/backup_$(shell date +%Y%m%d_%H%M%S).db'"

db-restore:
	@echo "Available backups:"
	@ls -1 backups/*.db
	@read -p "Enter backup file name: " file; \
	sqlite3 data/relatorio_dashboard.db ".restore 'backups/$$file'"

# Deployment
deploy-gcp:
	gcloud builds submit --tag gcr.io/$(PROJECT_ID)/dashboard-contratos
	gcloud run deploy dashboard-contratos \
		--image gcr.io/$(PROJECT_ID)/dashboard-contratos \
		--platform managed \
		--allow-unauthenticated \
		--region us-central1

deploy-heroku:
	git push heroku main

# Help
help:
	@echo "Available commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make dev         - Run development server"
	@echo "  make test        - Run tests"
	@echo "  make coverage    - Run tests with coverage report"
	@echo "  make lint        - Check code style"
	@echo "  make format      - Format code"
	@echo "  make clean       - Clean build files"
	@echo "  make build       - Build package"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run   - Run Docker container"
	@echo "  make docker-compose-up   - Start with Docker Compose"
	@echo "  make docker-compose-down - Stop Docker Compose"
	@echo "  make db-backup   - Backup database"
	@echo "  make db-restore  - Restore database"
	@echo "  make deploy-gcp  - Deploy to Google Cloud Run"
	@echo "  make deploy-heroku - Deploy to Heroku" 