# ==============================================================================
# Stage 1: Build Vite React Frontend
# ==============================================================================
FROM node:20-slim AS frontend-builder

WORKDIR /app

# Copy package descriptors and install npm dependencies
COPY package.json ./
RUN npm install

# Copy frontend source files and build
COPY tsconfig.json vite.config.ts index.html metadata.json ./
COPY scripts/ ./scripts/
COPY src/ ./src/

RUN npm run build

# ==============================================================================
# Stage 2: Python FastAPI Production Runtime
# ==============================================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install system dependencies if required (e.g. libxml2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python backend dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code, templates, schemas, and assets
COPY backend/ ./backend/
COPY templates/ ./templates/
COPY profiles/ ./profiles/
COPY prompts/ ./prompts/
COPY data/ ./data/

# Copy built frontend distribution from builder stage
COPY --from=frontend-builder /app/dist ./dist

# Create volume mount point for dynamic templates
RUN mkdir -p /app/data/templates

EXPOSE 8000

CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8000"]
