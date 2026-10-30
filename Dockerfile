FROM node:22-bookworm-slim AS results-workbench

WORKDIR /build
COPY package.json package-lock.json vite.results-workbench.config.mjs ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY frontend/app /build/frontend/app
RUN npm run build:results-workbench

FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend
COPY frontend /app/frontend
COPY --from=results-workbench /build/frontend/assets/dist/results-workbench-vue-shell.js /app/frontend/assets/dist/results-workbench-vue-shell.js
COPY research /app/research
COPY openspec /app/openspec
COPY docs /app/docs
COPY tests /app/tests

ENV PYTHONUNBUFFERED=1
ENV BACKTEST_V2_ROOT=/app/backend/core

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
