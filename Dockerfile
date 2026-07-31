# syntax=docker/dockerfile:1
# Single free-tier image: build SPA, serve API + static from FastAPI.
# Base: frontend-vis (presenter/viewer UI + backend).

FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY Frontend/package.json Frontend/package-lock.json ./
RUN npm ci
COPY Frontend/ ./
# Same-origin /api in production; never ship mock mode.
ENV VITE_USE_MOCK=false
# Leave VITE_API_TARGET unset → relative /api
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    STATIC_DIR=/app/static

RUN apt-get update && apt-get install -y --no-install-recommends \
      fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY Backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY Backend/ ./
COPY --from=frontend /frontend/dist ${STATIC_DIR}

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
