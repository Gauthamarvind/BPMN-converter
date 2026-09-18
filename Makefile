.PHONY: dev run test lint build schemas templates docker-build docker-run

# Run Vite dev server on :3000 (proxying /api to :8000) and uvicorn on :8000
dev:
	@echo "Starting Process2BPMN in development mode (FastAPI:8000 + Vite:3000)..."
	bash -c 'trap "kill 0" EXIT; uvicorn backend.server:app --host 0.0.0.0 --port 8000 & npm run dev'

# Build frontend and serve everything from FastAPI uvicorn on :8000
run: build
	@echo "Serving built application on http://localhost:8000..."
	uvicorn backend.server:app --host 0.0.0.0 --port 8000

# Run full test suite: pytest backend tests + npm design & type lint
test:
	pytest -v
	npm run lint

# Lint design rules and TypeScript definitions
lint:
	npm run lint

# Build frontend production bundle and template assets
build: templates
	npm run build

# Download or refresh official OMG BPMN 2.0 XSD schemas
schemas:
	python3 scripts/fetch_bpmn_schemas.py

# Build template binaries and reference BPMN models
templates:
	python3 scripts/build_templates.py

# Build multi-stage production Docker image
docker-build:
	docker build -t process2bpmn .

# Run Docker container locally on :8000
docker-run:
	docker run -p 8000:8000 --env-file .env process2bpmn
