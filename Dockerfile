# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md ./
COPY advisor ./advisor
COPY main.py ./

RUN uv sync --frozen --no-dev

CMD ["uv", "run", "--no-dev", "python", "main.py"]
