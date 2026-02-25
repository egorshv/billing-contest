FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml README.md ./
COPY app ./app
COPY schema.sql ./schema.sql

RUN pip install --upgrade pip && pip install .

RUN mkdir -p /app/data && chown -R app:app /app

USER app

EXPOSE 8000

ENV DATABASE_URL=sqlite:////app/data/billing.db

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
