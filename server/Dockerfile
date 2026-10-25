FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70
ENV PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY server/requirements.lock /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY cueflow/__init__.py cueflow/engine.py /app/cueflow/
COPY server /app/server
RUN useradd --uid 10001 --create-home cueflow && mkdir -p /data/cueflow && chown -R cueflow:cueflow /data
USER cueflow
ARG COMMIT=development
ENV CUEFLOW_COMMIT=$COMMIT
EXPOSE 8080
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log", "--workers", "1"]
