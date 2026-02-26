FROM python:3.11-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY pyproject.toml README.md ./
COPY app ./app

RUN pip install --upgrade pip build && \
    python -m build --wheel --outdir /dist


FROM python:3.11-alpine AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATABASE_URL=sqlite:////app/data/billing.db

WORKDIR /app

RUN addgroup -S app && adduser -S -G app app

COPY --from=builder /dist/*.whl /tmp/
COPY schema.sql ./schema.sql

RUN pip install --upgrade pip && \
    pip install /tmp/*.whl && \
    rm -f /tmp/*.whl

RUN mkdir -p /app/data && chown -R app:app /app

USER app

EXPOSE 8000


FROM scratch AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATABASE_URL=sqlite:////app/data/billing.db

WORKDIR /app

COPY --from=runtime / /

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
