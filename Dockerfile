# Stage 1: Build Frontend
FROM node:22 AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build



# Stage 2: Python Backend + Frontend Static Files
FROM ghcr.io/astral-sh/uv:python3.13-alpine

WORKDIR /app
COPY backend/pyproject.toml ./
RUN uv sync --no-dev
COPY backend/src ./src
COPY backend/main.py ./
COPY --from=frontend-builder /app/dist ./static
RUN mkdir -p /data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uv", "run", "python", "main.py"]
