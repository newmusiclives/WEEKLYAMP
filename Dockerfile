# ---- Builder stage ----
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Runtime stage ----
FROM python:3.12-slim

RUN useradd -m -u 1000 -s /bin/bash app

WORKDIR /app

COPY --from=builder /install /usr/local
COPY . .

RUN mkdir -p /app/data && chown -R app:app /app/data && chmod +x /app/docker-entrypoint.sh

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

USER app

ENTRYPOINT ["/app/docker-entrypoint.sh"]
