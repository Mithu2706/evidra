# Single-container public demo: builds the React frontend and serves it from
# the FastAPI backend (same origin, so no CORS setup). Used by render.yaml.
#   docker build -t evidra-demo . && docker run -p 10000:10000 -e EVIDRA_SECRET_KEY=$(openssl rand -hex 32) evidra-demo

# --- Frontend build -----------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Guest demo mode is compiled into the bundle; the API is same-origin (/api).
ENV VITE_DEMO_MODE=true
RUN npm run build

# --- Backend runtime ----------------------------------------------------------
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.txt ./
# OCR is disabled in the demo (RapidOCR needs more RAM than the free tier has)
# and tests don't run here, so skip those packages to keep the image small.
RUN grep -vE '^(rapidocr-onnxruntime|pytest)' requirements.txt > runtime-requirements.txt \
    && pip install --no-cache-dir -r runtime-requirements.txt
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist

# Public demo defaults (fictional data, rebuilt on every start). Override with
# env vars; always supply EVIDRA_SECRET_KEY.
ENV EVIDRA_ENV=production \
    EVIDRA_DEMO_MODE=true \
    EVIDRA_AI_ENGINE=heuristic \
    EVIDRA_AUTO_SEED=true \
    EVIDRA_OCR_ENGINE=none \
    EVIDRA_DATABASE_URL=sqlite:////tmp/evidra/evidra.db \
    EVIDRA_STORAGE_DIR=/tmp/evidra/storage
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
