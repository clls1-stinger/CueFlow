FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive QT_QPA_PLATFORM=offscreen
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl build-essential pkg-config xz-utils python3-pip \
    libgl1 libegl1 libxkbcommon0 libdbus-1-3 libxcb-cursor0 libfontconfig1 \
    libxrender1 libxext6 libxi6 libsm6 libice6 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.11.22
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --python 3.12 --extra dev --no-install-project
COPY scripts/build_ffmpeg.sh scripts/build_ffmpeg.sh
RUN bash scripts/build_ffmpeg.sh > /tmp/ffmpeg-build.log 2>&1 || (tail -80 /tmp/ffmpeg-build.log && exit 1)
COPY . .
RUN uv sync --frozen --extra dev && uv run pytest -q
RUN uv run python scripts/collect_licenses.py && uv run pyinstaller --noconfirm --clean CueFlow.spec
RUN ./dist/CueFlow/CueFlow --self-test && uv run python scripts/package.py
