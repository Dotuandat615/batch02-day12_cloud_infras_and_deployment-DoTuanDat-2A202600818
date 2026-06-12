# ============================================================
# Stateless Scaling Demo — Multi-stage build
# 
# 3 instances + Redis + Nginx load balancer
# ============================================================

# ──────────────────────────────────────
# STAGE 1: Builder
# ──────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY 05-scaling-reliability/production/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ──────────────────────────────────────
# STAGE 2: Runtime
# ──────────────────────────────────────
FROM python:3.11-slim AS runtime

RUN groupadd -r agent && useradd -r -g agent agent

WORKDIR /app

COPY --from=builder /root/.local /home/agent/.local

COPY 05-scaling-reliability/production/app.py .
COPY 05-scaling-reliability/production/utils/ ./utils/
COPY utils/ ./utils/

ENV PATH=/home/agent/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

USER agent

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
