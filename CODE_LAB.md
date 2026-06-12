#  Code Lab: Deploy Your AI Agent to Production

> **AICB-P1 · VinUniversity 2026**  
> Thời gian: 3-4 giờ | Độ khó: Intermediate

##  Mục Tiêu

Sau khi hoàn thành lab này, bạn sẽ:
- Hiểu sự khác biệt giữa development và production
- Containerize một AI agent với Docker
- Deploy agent lên cloud platform
- Bảo mật API với authentication và rate limiting
- Thiết kế hệ thống có khả năng scale và reliable

---

##  Yêu Cầu

```bash
 Python 3.11+
 Docker & Docker Compose
 Git
 Text editor (VS Code khuyến nghị)
 Terminal/Command line
```

**Không cần:**
-  OpenAI API key (dùng mock LLM)
-  Credit card
-  Kinh nghiệm DevOps trước đó

---

##  Lộ Trình Lab

| Phần | Thời gian | Nội dung |
|------|-----------|----------|
| **Part 1** | 30 phút | Localhost vs Production |
| **Part 2** | 45 phút | Docker Containerization |
| **Part 3** | 45 phút | Cloud Deployment |
| **Part 4** | 40 phút | API Security |
| **Part 5** | 40 phút | Scaling & Reliability |
| **Part 6** | 60 phút | Final Project |

---

## Part 1: Localhost vs Production (30 phút)

###  Concepts

**Vấn đề:** "It works on my machine" — code chạy tốt trên laptop nhưng fail khi deploy.

**Nguyên nhân:**
- Hardcoded secrets
- Khác biệt về environment (Python version, OS, dependencies)
- Không có health checks
- Config không linh hoạt

**Giải pháp:** 12-Factor App principles

###  Exercise 1.1: Phát hiện anti-patterns

```bash
cd 01-localhost-vs-production/develop
```

**Nhiệm vụ:** Đọc `app.py` và tìm ít nhất 5 vấn đề.

<details>
<summary> Gợi ý</summary>

Tìm:
- API key hardcode
- Port cố định
- Debug mode
- Không có health check
- Không xử lý shutdown

</details>

###  Exercise 1.2: Chạy basic version

```bash
pip install -r requirements.txt
python app.py
```

Test:
```bash
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

**Quan sát:** Nó chạy! Nhưng có production-ready không?

###  Exercise 1.3: So sánh với advanced version

```bash
cd ../production
cp .env.example .env
pip install -r requirements.txt
python app.py
```

**Nhiệm vụ:** So sánh 2 files `app.py`. Điền vào bảng:

| Feature | Basic | Advanced | Tại sao quan trọng? |
|---------|-------|----------|-----------------------|
| Config | Hardcode (`OPENAI_API_KEY = "sk-..."`) | Env vars qua `os.getenv()` + `dataclass Settings` | Nếu hardcode secrets → push lên GitHub → lộ key ngay lập tức; env vars thay đổi được mà không cần sửa code |
| Health check | ❌ Không có | ✅ `/health` (liveness) + `/ready` (readiness) | Platform (Railway, k8s) cần biết container còn sống không để tự restart khi crash |
| Logging | `print()` thô — log cả secret key ra stdout | Structured JSON logging (`logging` module, không log secrets) | JSON logs dễ parse bởi Datadog/Loki/CloudWatch; log secrets là lỗ hổng bảo mật nghiêm trọng |
| Shutdown | Đột ngột — process bị kill giữa chừng | Graceful — `SIGTERM` handler + `lifespan` context cho request hoàn thành trước khi tắt | Tránh mất dữ liệu, request bị cắt ngang khi deploy bản mới hoặc scale down |
| Host binding | `localhost` — chỉ nhận kết nối local | `0.0.0.0` — nhận kết nối từ bên ngoài container | Container có network riêng; bind `localhost` → không ai kết nối được từ ngoài container |
| Port | Cứng `8000` | Đọc từ `PORT` env var | Railway/Render inject `PORT` tự động; hardcode port → conflict hoặc không chạy được trên cloud |

###  Checkpoint 1

- [x] Hiểu tại sao hardcode secrets là nguy hiểm
- [x] Biết cách dùng environment variables
- [x] Hiểu vai trò của health check endpoint
- [x] Biết graceful shutdown là gì

---

## Part 2: Docker Containerization (45 phút)

###  Concepts

**Vấn đề:** "Works on my machine" part 2 — Python version khác, dependencies conflict.

**Giải pháp:** Docker — đóng gói app + dependencies vào container.

**Benefits:**
- Consistent environment
- Dễ deploy
- Isolation
- Reproducible builds

###  Exercise 2.1: Dockerfile cơ bản

```bash
cd ../../02-docker/develop
```

**Nhiệm vụ:** Đọc `Dockerfile` và trả lời:

1. **Base image là gì?** → `python:3.11` (full Python distribution, khoảng 1 GB)
2. **Working directory là gì?** → `/app` (tất cả code được copy vào đây)
3. **Tại sao COPY requirements.txt trước?** → **Docker layer cache**: Nếu chỉ code thay đổi mà deps không đổi, layer `pip install` sẽ được cache lại. Nếu copy toàn bộ code trước, mỗi lần sửa code đều phải re-install toàn bộ packages → chậm hơn rất nhiều
4. **CMD vs ENTRYPOINT?** → `ENTRYPOINT` định nghĩa command cố định không override được dễ dàng. `CMD` là default arguments có thể bị override bằng `docker run <image> <command>`. Tổ hợp: `ENTRYPOINT ["python"]` + `CMD ["app.py"]` cho phép override script nhưng giữ interpreter

###  Exercise 2.2: Build và run

```bash
# Build image
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .

# Run container
docker run -p 8000:8000 my-agent:develop

# Test
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Docker?"}'
```

**Quan sát:** Image size là bao nhiêu?
```bash
docker images my-agent:develop
```

> **Kết quả thực tế:** `my-agent:develop` = **1.66 GB** (disk usage) / 424 MB (content)
> Container chạy thành công tại `http://localhost:8000`, đã kiểm tra `/health` trả về `{"status":"ok","container":true}`

###  Exercise 2.3: Multi-stage build

```bash
cd ../production
```

**Nhiệm vụ:** Đọc `Dockerfile` và tìm:
- **Stage 1 (builder)** làm gì? → Dùng `python:3.11-slim`, cài `gcc` + `libpq-dev`, chạy `pip install --user` → tạo ra `/root/.local` chứa tất cả packages
- **Stage 2 (runtime)** làm gì? → Bắt đầu sạch với `python:3.11-slim`, chỉ `COPY --from=builder /root/.local`, tạo non-root user `appuser`, không có compiler tools
- **Tại sao image nhỏ hơn?** → Loại bỏ hoàn toàn `gcc`, apt cache, build tools. Chỉ giữ Python runtime + packages cần thiết

Build và so sánh:
```bash
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images | Select-String my-agent
```

> **Kết quả so sánh:**
> | Image | Size |
> |-------|------|
> | `my-agent:develop` (single-stage, `python:3.11`) | **1.66 GB** |
> | `my-agent:advanced` (multi-stage, `python:3.11-slim`) | **236 MB** |
>
> → Multi-stage build nhỏ hơn **~7 lần** so với single-stage!

###  Exercise 2.4: Docker Compose stack

**Nhiệm vụ:** Đọc `docker-compose.yml` và vẽ architecture diagram.

```bash
docker compose up -d
```

**Services được start:** 4 services
- **agent** — FastAPI AI agent (build từ Dockerfile, chạy truyền qua internal network)
- **redis** — Cache cho session và rate limiting (`redis:7-alpine`)
- **qdrant** — Vector database cho RAG (`qdrant/qdrant:v1.9.0`)
- **nginx** — Reverse proxy, load balancer (expose port 80/443 ra ngoài)

**Communication:**
```
Client → Nginx (:80) → agent (:8000) [internal network]
                              ↓
                         Redis (:6379) + Qdrant (:6333) [internal network]
```
Nginx là điểm vào duy nhất. Agent không expose port trực tiếp, chỉ giao tiếp qua `internal` bridge network.

Test:
```bash
# Health check
curl http://localhost/health

# Agent endpoint
curl http://localhost/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain microservices"}'
```

> **Kết quả thực tế:**
> - `GET http://localhost/health` → `{"status":"ok","uptime_seconds":14.7,"version":"2.0.0"}`
> - `POST http://localhost/ask` → `{"answer":"Tôi là AI agent được deploy lên cloud..."}`

###  Checkpoint 2

- [x] Hiểu cấu trúc Dockerfile
- [x] Biết lợi ích của multi-stage builds
- [x] Hiểu Docker Compose orchestration
- [x] Biết cách debug container (`docker logs`, `docker exec`)

---

## Part 3: Cloud Deployment (45 phút)

###  Concepts

**Vấn đề:** Laptop không thể chạy 24/7, không có public IP.

**Giải pháp:** Cloud platforms — Railway, Render, GCP Cloud Run.

**So sánh:**

| Platform | Độ khó | Free tier | Best for |
|----------|--------|-----------|----------|
| Railway | ⭐ | $5 credit | Prototypes |
| Render | ⭐⭐ | 750h/month | Side projects |
| Cloud Run | ⭐⭐⭐ | 2M requests | Production |

###  Exercise 3.1: Deploy Railway (15 phút)

```bash
cd ../../03-cloud-deployment/railway
```

**Steps:**

1. Install Railway CLI:
```bash
npm i -g @railway/cli
```

2. Login:
```bash
railway login
```

3. Initialize project:
```bash
railway init
```

4. Set environment variables:
```bash
railway variables set PORT=8000
railway variables set AGENT_API_KEY=my-secret-key
```

5. Deploy:
```bash
railway up
```

6. Get public URL:
```bash
railway domain
```

**Nhiệm vụ:** Test public URL với curl hoặc Postman.

Test:
```bash
# Health check
curl http://student-agent-domain/health

# Agent endpoint
curl http://studen-agent-domain/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": ""}'
```

> 💡 **Mẹo cho Windows PowerShell:**
> Trong PowerShell, lệnh `curl` mặc định là alias của `Invoke-WebRequest` nên các tham số kiểu Bash như `-X`, `-H`, `-d` sẽ không hoạt động chính xác. Bạn có thể sử dụng các cách sau để test:
>
> 1. **Sử dụng `curl.exe` trực tiếp (gọi curl của hệ thống):**
>    ```powershell
>    curl.exe http://student-agent-domain/health
>    curl.exe http://student-agent-domain/ask -X POST -H "Content-Type: application/json" -d '{"question": "Hello"}'
>    ```
> 2. **Sử dụng `Invoke-RestMethod` của PowerShell:**
>    ```powershell
>    # Health Check
>    Invoke-RestMethod -Uri "http://student-agent-domain/health" -Method Get
>    
>    # Agent Endpoint
>    Invoke-RestMethod -Uri "http://student-agent-domain/ask" -Method Post -ContentType "application/json" -Body '{"question": "Hello"}'
>    ```

###  Exercise 3.2: Deploy Render (15 phút)

```bash
cd ../render
```

**Steps:**

1. Push code lên GitHub (nếu chưa có)
2. Vào [render.com](https://render.com) → Sign up
3. New → Blueprint
4. Connect GitHub repo
5. Render tự động đọc `render.yaml`
6. Set environment variables trong dashboard
7. Deploy!

**Nhiệm vụ:** So sánh `render.yaml` với `railway.toml`. Khác nhau gì?

> **Trả lời:**
>
> | Đặc trưng | `render.yaml` (Render Blueprint) | `railway.toml` (Railway Config) |
> | :--- | :--- | :--- |
> | **Mục đích** | **Infrastructure as Code (IaC)** - Định nghĩa và quản lý toàn bộ stack hạ tầng của dự án bao gồm nhiều service khác nhau. | **Single Service Configuration** - Cấu hình riêng lẻ cho một service cụ thể về cách build và chạy. |
> | **Phạm vi** | **Multi-service**: Có thể định nghĩa nhiều service đồng thời (ví dụ: web app `ai-agent` + database/addon `Redis` trong cùng một file). | **Single service**: Chỉ chứa thông tin cấu hình của chính service chứa file toml đó. |
> | **Quản lý tài nguyên** | Khai báo trực tiếp các tài nguyên liên quan (pricing plan, database, disk, network, routing, IP allow list...) dưới dạng code. | Không khai báo các tài nguyên phụ trợ (như Redis, PostgreSQL). Các tài nguyên này được liên kết thủ công qua giao diện UI/CLI của Railway. |
> | **Biến môi trường** | Cho phép khai báo biến môi trường trực tiếp, có thể đồng bộ hoặc tự động sinh giá trị ngẫu nhiên (`generateValue: true`). | Không định nghĩa trực tiếp các giá trị biến môi trường bảo mật, chỉ nhắc nhở cấu hình qua CLI/Dashboard. |
> | **Ưu điểm** | Giúp tái thiết lập toàn bộ môi trường nhanh chóng, nhất quán và minh bạch qua mã nguồn (GitOps). | Đơn giản, ngắn gọn, chỉ tập trung vào hành vi chạy ứng dụng (start command, health check, restart policy). |

###  Exercise 3.3: (Optional) GCP Cloud Run (15 phút)

```bash
cd ../production-cloud-run
```

**Yêu cầu:** GCP account (có free tier).

**Nhiệm vụ:** Đọc `cloudbuild.yaml` và `service.yaml`. Hiểu CI/CD pipeline.

> **Trả lời:**
>
> Cấu trúc CI/CD pipeline trên GCP Cloud Run sử dụng hai file cấu hình chính:
>
> 1. **`cloudbuild.yaml` (Google Cloud Build CI/CD Pipeline):**
>    - Định nghĩa các bước (steps) tự động hóa từ khi lập trình viên push code lên nhánh `main`.
>    - **Step 1 (`test`):** Sử dụng container `python:3.11-slim` để cài đặt thư viện và chạy unit test bằng `pytest`. Đảm bảo code chạy ổn định trước khi build.
>    - **Step 2 (`build`):** Sử dụng Docker để build image từ `Dockerfile` ở local. Image được tag theo commit SHA (`ai-agent:$COMMIT_SHA`) và tag `latest`. Sử dụng layer cache để tăng tốc độ build.
>    - **Step 3 (`push`):** Đẩy các docker image đã build lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`) để lưu trữ.
>    - **Step 4 (`deploy`):** Gọi lệnh `gcloud run deploy` để cập nhật ứng dụng trên Cloud Run với image mới nhất. Ở bước này, nó cũng thiết lập các thông số như region, số lượng instance tối thiểu/tối đa, giới hạn CPU/Memory, biến môi trường và liên kết key bí mật từ Google Secret Manager.
>
> 2. **`service.yaml` (Cloud Run Service Definition - IaC):**
>    - Đây là file cấu hình declarative (Knative Service) để định nghĩa trạng thái mong muốn của ứng dụng trên Cloud Run.
>    - **Autoscaling:** Cấu hình giữ tối thiểu 1 instance để tránh hiện tượng *cold start*, tối đa 10 instances để kiểm soát chi phí.
>    - **Concurrency:** Cấu hình mỗi instance xử lý tối đa 80 requests đồng thời.
>    - **Resources:** Giới hạn tài nguyên ở mức 1 CPU và 512Mi Memory.
>    - **Environment Variables & Secrets:** Cấu hình các biến môi trường và lấy các secret như `OPENAI_API_KEY`, `AGENT_API_KEY` một cách bảo mật từ Secret Manager thay vì hardcode.
>    - **Health checks:** Định nghĩa `livenessProbe` (gọi `/health` định kỳ để kiểm tra container còn sống không) và `startupProbe` (gọi `/ready` khi khởi động để kiểm tra khi nào container sẵn sàng nhận traffic).

###  Checkpoint 3

- [x] Deploy thành công lên ít nhất 1 platform
- [x] Có public URL hoạt động
- [x] Hiểu cách set environment variables trên cloud
- [x] Biết cách xem logs

---

## Part 4: API Security (40 phút)

###  Concepts

**Vấn đề:** Public URL = ai cũng gọi được = hết tiền OpenAI.

**Giải pháp:**
1. **Authentication** — Chỉ user hợp lệ mới gọi được
2. **Rate Limiting** — Giới hạn số request/phút
3. **Cost Guard** — Dừng khi vượt budget

###  Exercise 4.1: API Key authentication

```bash
cd ../../04-api-gateway/develop
```

**Nhiệm vụ:** Đọc `app.py` và tìm:
- API key được check ở đâu?
- Điều gì xảy ra nếu sai key?
- Làm sao rotate key?

Test:
```bash
python app.py

#  Không có key
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'

#  Có key
curl http://localhost:8000/ask -X POST \
  -H "X-API-Key: secret-key-123" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

> **Trả lời:**
> - API key được check trong `verify_api_key()` bằng header `X-API-Key`.
> - Không có key trả `401`; sai key trả `403`.
> - Rotate key bằng cách đổi biến môi trường `AGENT_API_KEY`, restart/redeploy service. Code không hardcode secret nên không cần sửa source.
>
> **Kết quả test:** `POST /ask` không có key -> `401`; có `X-API-Key: secret-key-123` -> `200`.

###  Exercise 4.2: JWT authentication (Advanced)

```bash
cd ../production
```

**Nhiệm vụ:** 
1. Đọc `auth.py` — hiểu JWT flow
2. Lấy token:
```bash
python app.py

curl http://localhost:8000/token -X POST \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}'
```

3. Dùng token để gọi API:
```bash
TOKEN="<token_từ_bước_2>"
curl http://localhost:8000/ask -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain JWT"}'
```

> **Trả lời:**
> - `POST /token` hoặc `/auth/token` nhận username/password, gọi `authenticate_user()`, rồi `create_token()` ký JWT bằng `JWT_SECRET`.
> - Client gửi `Authorization: Bearer <token>`; `verify_token()` decode + verify signature/expiry, sau đó trả `username` và `role` cho endpoint.
> - Đã hỗ trợ credential trong lab: `admin / secret`.
>
> **Kết quả test:** lấy token `/token` -> `200`; gọi `/ask` không token -> `401`; gọi bằng Bearer token -> `200`.

###  Exercise 4.3: Rate limiting

**Nhiệm vụ:** Đọc `rate_limiter.py` và trả lời:
- Algorithm nào được dùng? (Token bucket? Sliding window?)
- Limit là bao nhiêu requests/minute?
- Làm sao bypass limit cho admin?

Test:
```bash
# Gọi liên tục 20 lần
for i in {1..20}; do
  curl http://localhost:8000/ask -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"question": "Test '$i'"}'
  echo ""
done
```

Quan sát response khi hit limit.

> **Trả lời:**
> - Algorithm: **Sliding Window Counter** bằng `deque` timestamps cho từng user.
> - Limit: user thường `10 requests/phút`; admin `100 requests/phút`.
> - Admin đi qua limiter riêng (`rate_limiter_admin`). Nếu muốn bypass hoàn toàn thì trong `/ask` có thể skip `limiter.check()` khi `role == "admin"`.
> - Khi vượt limit API trả `429` kèm `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

###  Exercise 4.4: Cost guard

**Nhiệm vụ:** Đọc `cost_guard.py` và implement logic:

```python
def check_budget(user_id: str, estimated_cost: float) -> bool:
    """
    Return True nếu còn budget, False nếu vượt.
    
    Logic:
    - Mỗi user có budget $10/tháng
    - Track spending trong Redis
    - Reset đầu tháng
    """
    # TODO: Implement
    pass
```

<details>
<summary> Solution</summary>

```python
import redis
from datetime import datetime

r = redis.Redis()

def check_budget(user_id: str, estimated_cost: float) -> bool:
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"
    
    current = float(r.get(key) or 0)
    if current + estimated_cost > 10:
        return False
    
    r.incrbyfloat(key, estimated_cost)
    r.expire(key, 32 * 24 * 3600)  # 32 days
    return True
```

</details>

> **Đã implement:** `cost_guard.py` sử dụng Redis nếu `REDIS_URL` khả dụng, key theo tháng `budget:{user_id}:{YYYY-MM}` và `budget:global:{YYYY-MM}`. TTL được set qua đầu tháng sau để tự reset. Nếu Redis chưa chạy, module fallback sang in-memory để demo local vẫn chạy.

###  Checkpoint 4

- [x] Implement API key authentication
- [x] Hiểu JWT flow
- [x] Implement rate limiting
- [x] Implement cost guard với Redis

---

## Part 5: Scaling & Reliability (40 phút)

###  Concepts

**Vấn đề:** 1 instance không đủ khi có nhiều users.

**Giải pháp:**
1. **Stateless design** — Không lưu state trong memory
2. **Health checks** — Platform biết khi nào restart
3. **Graceful shutdown** — Hoàn thành requests trước khi tắt
4. **Load balancing** — Phân tán traffic

###  Exercise 5.1: Health checks

```bash
cd ../../05-scaling-reliability/develop
```

**Nhiệm vụ:** Implement 2 endpoints:

```python
@app.get("/health")
def health():
    """Liveness probe — container còn sống không?"""
    # TODO: Return 200 nếu process OK
    pass

@app.get("/ready")
def ready():
    """Readiness probe — sẵn sàng nhận traffic không?"""
    # TODO: Check database connection, Redis, etc.
    # Return 200 nếu OK, 503 nếu chưa ready
    pass
```

<details>
<summary> Solution</summary>

```python
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready():
    try:
        # Check Redis
        r.ping()
        # Check database
        db.execute("SELECT 1")
        return {"status": "ready"}
    except:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready"}
        )
```

</details>

> **Đã implement trong `05-scaling-reliability/develop/app.py`:**
> - `/health` là liveness probe, luôn trả thông tin process còn sống: `status`, `uptime_seconds`, `version`, `environment`, `timestamp`, và các dependency checks.
> - `/ready` là readiness probe, trả `200` khi `_is_ready=True`; trả `503` khi app đang startup hoặc shutdown.
> - Readiness có thêm `in_flight_requests` để quan sát số request đang xử lý.
>
> **Kết quả mong đợi:** platform dùng `/health` để quyết định restart container, còn load balancer dùng `/ready` để quyết định có route traffic vào instance hay không.

###  Exercise 5.2: Graceful shutdown

**Nhiệm vụ:** Implement signal handler:

```python
import signal
import sys

def shutdown_handler(signum, frame):
    """Handle SIGTERM from container orchestrator"""
    # TODO:
    # 1. Stop accepting new requests
    # 2. Finish current requests
    # 3. Close connections
    # 4. Exit
    pass

signal.signal(signal.SIGTERM, shutdown_handler)
```

Test:
```bash
python app.py &
PID=$!

# Gửi request
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Long task"}' &

# Ngay lập tức kill
kill -TERM $PID

# Quan sát: Request có hoàn thành không?
```

> **Đã implement trong `05-scaling-reliability/develop/app.py`:**
> - Dùng FastAPI `lifespan` để startup/shutdown có kiểm soát.
> - Middleware `track_requests` tăng/giảm `_in_flight_requests` cho mỗi request.
> - Khi nhận `SIGTERM` hoặc `SIGINT`, `handle_sigterm()` set `_is_ready=False` và `_is_shutting_down=True`, nên `/ready` bắt đầu trả `503` để ngừng nhận traffic mới.
> - Trong shutdown, app chờ các request đang xử lý hoàn thành tối đa 30 giây.
> - `uvicorn.run(..., timeout_graceful_shutdown=30)` cho phép graceful shutdown đúng cách.
>
> **Kết quả test nhanh:** trước signal `/health`, `/ready`, `/ask` đều trả `200`; sau khi giả lập SIGTERM, `/ready` và `/ask` trả `503`, đúng mục tiêu ngừng nhận request mới.

###  Exercise 5.3: Stateless design

```bash
cd ../production
```

**Nhiệm vụ:** Refactor code để stateless.

**Anti-pattern:**
```python
#  State trong memory
conversation_history = {}

@app.post("/ask")
def ask(user_id: str, question: str):
    history = conversation_history.get(user_id, [])
    # ...
```

**Correct:**
```python
#  State trong Redis
@app.post("/ask")
def ask(user_id: str, question: str):
    history = r.lrange(f"history:{user_id}", 0, -1)
    # ...
```

Tại sao? Vì khi scale ra nhiều instances, mỗi instance có memory riêng.

> **Đã có trong `05-scaling-reliability/production/app.py`:**
> - Không lưu conversation history trong biến global theo kiểu `conversation_history = {}`.
> - Session được lưu qua `save_session()` và đọc qua `load_session()`.
> - Khi có Redis, session lưu bằng key `session:{session_id}` với TTL 3600 giây.
> - Endpoint `/chat` tạo hoặc nhận `session_id`, append message user/assistant vào history, rồi trả `served_by` để thấy request có thể được xử lý bởi instance bất kỳ.
> - Nếu Redis chưa chạy, code có fallback in-memory để demo local, nhưng production/scale thật cần Redis để stateless giữa nhiều instance.
>
> **Ý nghĩa:** khi scale nhiều agent instances, mọi instance đều đọc cùng session từ Redis, nên conversation không bị mất nếu request sau đi vào instance khác.

###  Exercise 5.4: Load balancing

**Nhiệm vụ:** Chạy stack với Nginx load balancer:

```bash
docker compose up --scale agent=3
```

Quan sát:
- 3 agent instances được start
- Nginx phân tán requests
- Nếu 1 instance die, traffic chuyển sang instances khác

Test:
```bash
# Gọi 10 requests
for i in {1..10}; do
  curl http://localhost/ask -X POST \
    -H "Content-Type: application/json" \
    -d '{"question": "Request '$i'"}'
done

# Check logs — requests được phân tán
docker compose logs agent
```

> **Đã cấu hình trong `05-scaling-reliability/production`:**
> - `docker-compose.yml` có service `agent`, `redis`, và `nginx`.
> - `nginx.conf` định nghĩa `upstream agent_cluster` trỏ tới `agent:8000`.
> - Khi chạy `docker compose up --scale agent=3`, Docker DNS trả nhiều container `agent`, Nginx phân phối request qua upstream.
> - Nginx expose port `80`, còn agent chạy trong internal network; client chỉ gọi qua Nginx.
> - `proxy_next_upstream error timeout http_503` giúp retry sang instance khác nếu một instance lỗi hoặc chưa ready.
>
> **Cách quan sát:** response `/chat` có field `served_by`; gọi nhiều request sẽ thấy request có thể được phục vụ bởi các instance khác nhau.

###  Exercise 5.5: Test stateless

```bash
python test_stateless.py
```

Script này:
1. Gọi API để tạo conversation
2. Kill random instance
3. Gọi tiếp — conversation vẫn còn không?

> **Kết quả cần đạt:**
> - Request đầu tạo `session_id` và lưu history vào Redis.
> - Các request sau dùng lại `session_id`.
> - Dù request được serve bởi instance khác, endpoint `/chat/{session_id}/history` vẫn trả đủ conversation history.
> - Nếu một agent instance bị kill, request tiếp theo vẫn tiếp tục conversation vì state nằm trong Redis, không nằm trong memory của instance đã chết.
>
> **Kết luận:** thiết kế stateless đạt yêu cầu khi session/history vẫn được giữ sau khi scale nhiều instance hoặc kill một instance.

###  Checkpoint 5

- [x] Implement health và readiness checks
- [x] Implement graceful shutdown
- [x] Refactor code thành stateless
- [x] Hiểu load balancing với Nginx
- [x] Test stateless design

---

## Part 6: Final Project (60 phút)

###  Objective

Build một production-ready AI agent từ đầu, kết hợp TẤT CẢ concepts đã học.

###  Requirements

**Functional:**
- [ ] Agent trả lời câu hỏi qua REST API
- [ ] Support conversation history
- [ ] Streaming responses (optional)

**Non-functional:**
- [ ] Dockerized với multi-stage build
- [ ] Config từ environment variables
- [ ] API key authentication
- [ ] Rate limiting (10 req/min per user)
- [ ] Cost guard ($10/month per user)
- [ ] Health check endpoint
- [ ] Readiness check endpoint
- [ ] Graceful shutdown
- [ ] Stateless design (state trong Redis)
- [ ] Structured JSON logging
- [ ] Deploy lên Railway hoặc Render
- [ ] Public URL hoạt động

### 🏗 Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Nginx (LB)     │
└──────┬──────────┘
       │
       ├─────────┬─────────┐
       ▼         ▼         ▼
   ┌──────┐  ┌──────┐  ┌──────┐
   │Agent1│  │Agent2│  │Agent3│
   └───┬──┘  └───┬──┘  └───┬──┘
       │         │         │
       └─────────┴─────────┘
                 │
                 ▼
           ┌──────────┐
           │  Redis   │
           └──────────┘
```

###  Step-by-step

#### Step 1: Project setup (5 phút)

```bash
mkdir my-production-agent
cd my-production-agent

# Tạo structure
mkdir -p app
touch app/__init__.py
touch app/main.py
touch app/config.py
touch app/auth.py
touch app/rate_limiter.py
touch app/cost_guard.py
touch Dockerfile
touch docker-compose.yml
touch requirements.txt
touch .env.example
touch .dockerignore
```

#### Step 2: Config management (10 phút)

**File:** `app/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # TODO: Define all config
    # - PORT
    # - REDIS_URL
    # - AGENT_API_KEY
    # - LOG_LEVEL
    # - RATE_LIMIT_PER_MINUTE
    # - MONTHLY_BUDGET_USD
    pass

settings = Settings()
```

#### Step 3: Main application (15 phút)

**File:** `app/main.py`

```python
from fastapi import FastAPI, Depends, HTTPException
from .config import settings
from .auth import verify_api_key
from .rate_limiter import check_rate_limit
from .cost_guard import check_budget

app = FastAPI()

@app.get("/health")
def health():
    # TODO
    pass

@app.get("/ready")
def ready():
    # TODO: Check Redis connection
    pass

@app.post("/ask")
def ask(
    question: str,
    user_id: str = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
    _budget: None = Depends(check_budget)
):
    # TODO: 
    # 1. Get conversation history from Redis
    # 2. Call LLM
    # 3. Save to Redis
    # 4. Return response
    pass
```

#### Step 4: Authentication (5 phút)

**File:** `app/auth.py`

```python
from fastapi import Header, HTTPException

def verify_api_key(x_api_key: str = Header(...)):
    # TODO: Verify against settings.AGENT_API_KEY
    # Return user_id if valid
    # Raise HTTPException(401) if invalid
    pass
```

#### Step 5: Rate limiting (10 phút)

**File:** `app/rate_limiter.py`

```python
import redis
from fastapi import HTTPException

r = redis.from_url(settings.REDIS_URL)

def check_rate_limit(user_id: str):
    # TODO: Implement sliding window
    # Raise HTTPException(429) if exceeded
    pass
```

#### Step 6: Cost guard (10 phút)

**File:** `app/cost_guard.py`

```python
def check_budget(user_id: str):
    # TODO: Check monthly spending
    # Raise HTTPException(402) if exceeded
    pass
```

#### Step 7: Dockerfile (5 phút)

```dockerfile
# TODO: Multi-stage build
# Stage 1: Builder
# Stage 2: Runtime
```

#### Step 8: Docker Compose (5 phút)

```yaml
# TODO: Define services
# - agent (scale to 3)
# - redis
# - nginx (load balancer)
```

#### Step 9: Test locally (5 phút)

```bash
docker compose up --scale agent=3

# Test all endpoints
curl http://localhost/health
curl http://localhost/ready
curl -H "X-API-Key: secret" http://localhost/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello", "user_id": "user1"}'
```

#### Step 10: Deploy (10 phút)

```bash
# Railway
railway init
railway variables set REDIS_URL=...
railway variables set AGENT_API_KEY=...
railway up

# Hoặc Render
# Push lên GitHub → Connect Render → Deploy
```

###  Validation

Chạy script kiểm tra:

```bash
cd 06-lab-complete
python check_production_ready.py
```

Script sẽ kiểm tra:
-  Dockerfile exists và valid
-  Multi-stage build
-  .dockerignore exists
-  Health endpoint returns 200
-  Readiness endpoint returns 200
-  Auth required (401 without key)
-  Rate limiting works (429 after limit)
-  Cost guard works (402 when exceeded)
-  Graceful shutdown (SIGTERM handled)
-  Stateless (state trong Redis, không trong memory)
-  Structured logging (JSON format)

###  Grading Rubric

| Criteria | Points | Description |
|----------|--------|-------------|
| **Functionality** | 20 | Agent hoạt động đúng |
| **Docker** | 15 | Multi-stage, optimized |
| **Security** | 20 | Auth + rate limit + cost guard |
| **Reliability** | 20 | Health checks + graceful shutdown |
| **Scalability** | 15 | Stateless + load balanced |
| **Deployment** | 10 | Public URL hoạt động |
| **Total** | 100 | |

---

##  Hoàn Thành!

Bạn đã:
-  Hiểu sự khác biệt dev vs production
-  Containerize app với Docker
-  Deploy lên cloud platform
-  Bảo mật API
-  Thiết kế hệ thống scalable và reliable

###  Next Steps

1. **Monitoring:** Thêm Prometheus + Grafana
2. **CI/CD:** GitHub Actions auto-deploy
3. **Advanced scaling:** Kubernetes
4. **Observability:** Distributed tracing với OpenTelemetry
5. **Cost optimization:** Spot instances, auto-scaling

###  Resources

- [12-Factor App](https://12factor.net/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Railway Docs](https://docs.railway.app/)
- [Render Docs](https://render.com/docs)

---

##  Q&A

**Q: Tôi không có credit card, có thể deploy không?**  
A: Có! Railway cho $5 credit, Render có 750h free tier.

**Q: Mock LLM khác gì với OpenAI thật?**  
A: Mock trả về canned responses, không gọi API. Để dùng OpenAI thật, set `OPENAI_API_KEY` trong env.

**Q: Làm sao debug khi container fail?**  
A: `docker logs <container_id>` hoặc `docker exec -it <container_id> /bin/sh`

**Q: Redis data mất khi restart?**  
A: Dùng volume: `volumes: - redis-data:/data` trong docker-compose.

**Q: Làm sao scale trên Railway/Render?**  
A: Railway: `railway scale <replicas>`. Render: Dashboard → Settings → Instances.

---

**Happy Deploying! **
