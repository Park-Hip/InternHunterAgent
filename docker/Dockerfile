FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /bin/uv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY config ./config
COPY main.py ./

RUN uv sync --frozen --no-dev

RUN addgroup --system app && adduser --system --ingroup app app
RUN chown -R app:app /app

USER app

EXPOSE 8000

CMD [".venv/bin/uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]