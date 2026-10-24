FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED=1
ENV PYTHONUTF8=1
ENV HOME=/tmp
WORKDIR /workspace
