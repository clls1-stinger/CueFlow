FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70
ENV PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg bzip2 gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY server/requirements.lock /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
# Speaker diarization models (sherpa-onnx releases), pinned by checksum.
ADD --checksum=sha256:24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488 \
    https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2 /tmp/segmentation.tar.bz2
ADD --checksum=sha256:357a834f702b80161e5b981182c038e18553c1f2ca752ed6cec2052365d4129b \
    https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx /app/models/campplus-voxceleb-16k.onnx
RUN tar -xjf /tmp/segmentation.tar.bz2 -C /tmp \
    && mv /tmp/sherpa-onnx-pyannote-segmentation-3-0/model.int8.onnx /app/models/pyannote-segmentation-3-0.int8.onnx \
    && rm -rf /tmp/segmentation.tar.bz2 /tmp/sherpa-onnx-pyannote-segmentation-3-0 && chmod -R a+rX /app/models
COPY cueflow/__init__.py cueflow/engine.py /app/cueflow/
COPY server /app/server
RUN useradd --uid 10001 --create-home cueflow && mkdir -p /data/cueflow && chown -R cueflow:cueflow /data
USER cueflow
ARG COMMIT=development
ENV CUEFLOW_COMMIT=$COMMIT
EXPOSE 8080
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log", "--workers", "1"]
