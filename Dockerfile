# syntax=docker/dockerfile:1
FROM python:3.10-slim

# Security: run as non-root user
RUN groupadd -r mmr && useradd -r -g mmr mmr

WORKDIR /app

# Install system dependencies for image processing and ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install renderer from your fork
ARG RENDERER_REPO=https://github.com/bounded-rationality/minimap_renderer.git
RUN pip install --no-cache-dir \
    git+${RENDERER_REPO}

# Apply patches to the installed renderer
COPY apply_patches.py .
RUN python apply_patches.py

# Copy application code
COPY main.py .
COPY bot/ bot/
COPY tasks/ tasks/
COPY utils/ utils/

# Security: switch to non-root user
USER mmr

# MODE is set at runtime: "bot" or "worker"
ENV MODE=bot

CMD ["sh", "-c", "python main.py -r ${MODE}"]
