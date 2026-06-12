# Lab 12 — Complete Production Agent

Kết hợp TẤT CẢ những gì đã học trong 1 project hoàn chỉnh.

## Checklist Deliverable

- [x] Dockerfile (multi-stage, < 500 MB)
- [x] docker-compose.yml (agent + redis)
- [x] .dockerignore
- [x] Health check endpoint (`GET /health`)
- [x] Readiness endpoint (`GET /ready`)
- [x] API Key authentication
- [x] Rate limiting
- [x] Cost guard
- [x] Config từ environment variables
- [x] Structured logging
- [x] Graceful shutdown
- [x] Public URL ready (Railway / Render config)

---

## Cấu Trúc

```
06-lab-complete/
├── app/
│   ├── main.py         # Entry point — kết hợp tất cả
│   ├── config.py       # 12-factor config
│   ├── auth.py         # API Key authentication
│   ├── rate_limiter.py # Rate limiting
│   └── cost_guard.py   # Budget protection
├── Dockerfile          # Multi-stage, production-ready
├── docker-compose.yml  # Full stack
├── railway.toml        # Deploy Railway
├── render.yaml         # Deploy Render
├── .env.example        # Template
├── .dockerignore
└── requirements.txt
```

---

## Chạy Local

```bash
# 1. Setup
cp .env.example .env

# 2. Chạy với Docker Compose
docker compose up

# 3. Test
curl http://localhost:8000/health

# 4. Lấy API key từ .env, test endpoint
API_KEY=$(grep AGENT_API_KEY .env | cut -d= -f2)
curl -H "X-API-Key: $API_KEY" \
     -X POST http://localhost:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"user_id": "test", "question": "What is deployment?"}'
```

### Scale local

```bash
docker compose up -d --build --scale agent=3
docker compose ps
```

Docker Compose maps the three agent replicas to ports `8000-8002`.

---

## API Documentation

### `GET /health`

Liveness probe. Returns `200` when the process is alive.

```bash
curl http://localhost:8000/health
```

### `GET /ready`

Readiness probe. Pings Redis and returns `200` when the app can receive traffic.

```bash
curl http://localhost:8000/ready
```

### `POST /ask`

Protected agent endpoint. Requires `X-API-Key`.

Request:

```json
{"user_id":"test","question":"Hello"}
```

Response:

```json
{
  "user_id": "test",
  "question": "Hello",
  "answer": "...",
  "model": "gpt-4o-mini",
  "timestamp": "2026-06-12T00:00:00+00:00"
}
```

### `GET /metrics`

Protected operational metrics endpoint. Requires `X-API-Key`.

---

## Architecture

```text
Client
  |
  | HTTPS + X-API-Key
  v
Railway public domain
  |
  v
FastAPI agent service
  |-- API key authentication
  |-- Redis-backed rate limiting
  |-- Redis-backed monthly cost guard
  |-- Redis-backed conversation history
  |
  v
Railway Redis service
```

Local scaling:

```text
Client -> agent replica 1/2/3 -> Redis
```

All production state used by conversation history, rate limiting, and budget
tracking is stored in Redis so any replica can serve the next request.

---

## Deploy Railway (< 5 phút)

```bash
# Cài Railway CLI
npm i -g @railway/cli

# Login và deploy
railway login
railway init
railway variables set OPENAI_API_KEY=<optional-openai-key>
railway variables set AGENT_API_KEY=your-secret-key
railway variables set RATE_LIMIT_PER_MINUTE=10
railway variables set MONTHLY_BUDGET_USD=10
# Set REDIS_URL từ Railway Redis service/plugin
railway up

# Nhận public URL!
railway domain
```

---

## Deploy Render

1. Push repo lên GitHub
2. Render Dashboard → New → Blueprint
3. Connect repo → Render đọc `render.yaml`
4. Set secrets: `OPENAI_API_KEY`, `AGENT_API_KEY`
5. Set `REDIS_URL`, `RATE_LIMIT_PER_MINUTE=10`, `MONTHLY_BUDGET_USD=10`
6. Deploy → Nhận URL!

---

## Kiểm Tra Production Readiness

```bash
python check_production_ready.py
```

Script này kiểm tra tất cả items trong checklist và báo cáo những gì còn thiếu.
