FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.ia.txt .
RUN pip install --no-cache-dir -r requirements.ia.txt

COPY ia/ ./ia/

RUN mkdir -p /app/ia/models /app/ia/reports /app/data/ml

CMD ["sh", "-c", "\
  echo '=== STEP 1 — Datasets multi-horizon ===' && \
  python -m ia.src.ml.run_pipeline && \
  echo '=== STEP 2 — Entraînement / sélection temporelle ===' && \
  python -m ia.src.ml.run_training && \
  echo '=== STEP 3 — Validation des artefacts ===' && \
  python -m ia.src.ml.validate_artifacts && \
  echo '=== Pipeline IA multi-horizon terminé ==='\
"]
