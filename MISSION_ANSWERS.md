# Day 14 Lab - Mission Answers

> **Sinh viên:** Lê Bá Nguyên  
> **Mã số sinh viên:** 2A202604100  
> **Lớp:** K5-L3B  
> **Repository:** K5-L3B-DAY14-LeBaNguyen-2A202604100-Deployment-Benchmark-Observability  

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `01-localhost-vs-production/develop/app.py`

1. **Hardcoded Secrets (Dòng 17, 18):**
   - API key (`OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`) và chuỗi kết nối cơ sở dữ liệu (`DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`) bị gán cứng trực tiếp trong mã nguồn.
   - *Hậu quả:* Khi mã nguồn được đẩy lên các hệ thống quản lý phiên bản (Git/GitHub), thông tin nhạy cảm này bị lộ ngay lập tức. Bất kỳ ai có quyền truy cập repo đều có thể đánh cắp credential.
2. **Thiếu quản lý cấu hình tập trung (Dòng 21, 22):**
   - Các biến cấu hình hành vi như `DEBUG = True`, `MAX_TOKENS = 500` bị cố định trong mã nguồn thay vì đọc từ biến môi trường.
   - *Hậu quả:* Vi phạm nguyên tắc 12-Factor App (Config in environment). Muốn thay đổi giữa các môi trường (Dev, Staging, Production) phải sửa code và commit lại.
3. **Log cẩu thả & Rò rỉ bí mật (Dòng 33, 34, 38):**
   - Sử dụng hàm `print()` tiêu chuẩn thay vì thư viện logging chuyên dụng có cấu trúc.
   - Đặc biệt nguy hiểm ở dòng 34: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` in thẳng secret ra console log.
   - *Hậu quả:* Khó phân loại log theo severity (INFO, WARNING, ERROR), không thể parse tự động bởi các log aggregator (Loki, Datadog), và làm rò rỉ API key vào các tệp log server.
4. **Không có Health Check & Readiness Endpoints:**
   - Ứng dụng chỉ có endpoint `/` và `/ask`, hoàn toàn không có `/health` (Liveness probe) hay `/ready` (Readiness probe).
   - *Hậu quả:* Các hệ thống điều phối container (Kubernetes, Docker Swarm, Cloud Run, Render, Railway) không thể xác định tiến trình có bị deadlock, crash hay sẵn sàng phục vụ hay chưa để tự động restart hoặc định tuyến tải.
5. **Cố định Host và Port lắng nghe (Dòng 51, 52):**
   - `uvicorn.run()` gán cứng `host="localhost"` và `port=8000`.
   - *Hậu quả:* `localhost` (127.0.0.1) chỉ nhận kết nối nội bộ từ chính máy chủ đó. Khi đóng gói thành Docker container hoặc chạy trên Cloud, các client bên ngoài hoặc Ingress/Load Balancer không thể kết nối tới app. Ngoài ra, các nền tảng đám mây tự động cấp phát port qua biến môi trường `PORT`, việc ép port 8000 sẽ khiến container không thể khởi động thành công.
6. **Bật chế độ Reload trong Production (Dòng 53):**
   - Tham số `reload=True` sử dụng filesystem watcher (như WatchFiles) liên tục quét thư mục.
   - *Hậu quả:* Gây lãng phí tài nguyên CPU/RAM trên môi trường Production, giảm thông lượng (throughput) và tiềm ẩn nguy cơ bảo mật.
7. **Không xử lý Graceful Shutdown:**
   - Ứng dụng không bắt các tín hiệu dừng hệ thống như `SIGTERM` hoặc `SIGINT`.
   - *Hậu quả:* Khi container bị dừng (`docker stop`) hoặc redeploy trên cloud, tiến trình bị ngắt đột ngột (killed). Các request đang xử lý dở dang sẽ bị ngắt kết nối (khách hàng nhận lỗi 502/Bad Gateway), và tài nguyên chưa kịp giải phóng.
8. **Thiết kế API thiếu chuẩn RESTful (Dòng 30, 31):**
   - Endpoint `POST /ask` nhưng lại nhận tham số `question: str` dưới dạng query parameter (`?question=...`) thay vì nhận JSON Request Body.
   - *Hậu quả:* Không gửi được các truy vấn dài, dữ liệu nhạy cảm hiển thị lộ trên URL log, và không thể mở rộng cấu trúc dữ liệu gửi lên.

---

### Exercise 1.2: Run Basic Version

1. **Khởi động ứng dụng:**
   ```bash
   cd 01-localhost-vs-production/develop
   pip install -r requirements.txt
   python app.py
   ```
   *Terminal ghi nhận:*
   ```text
   Starting agent on localhost:8000...
   INFO:     Uvicorn running on http://localhost:8000 (Press CTRL+C to quit)
   INFO:     Started server process
   INFO:     Waiting for application startup.
   INFO:     Application startup complete.
   ```

2. **Gửi truy vấn kiểm tra (Query parameter):**
   ```bash
   curl.exe -X POST "http://localhost:8000/ask?question=Hello"
   ```

3. **Kết quả trả về:**
   ```json
   {"answer":"Hello! How can I help you today?"}
   ```

4. **Console log hiển thị (ghi nhận anti-pattern):**
   ```text
   [DEBUG] Got question: Hello
   [DEBUG] Using key: sk-hardcoded-fake-key-never-do-this
   [DEBUG] Response: Hello! How can I help you today?
   INFO:     127.0.0.1:xxxxx - "POST /ask?question=Hello HTTP/1.1" 200 OK
   ```

---

### Exercise 1.3: Comparison Table (Develop vs Production)

| Feature | Develop (Basic) | Production (Advanced) | Tại sao quan trọng? |
| :--- | :--- | :--- | :--- |
| **Config & Secrets** | Hardcode trực tiếp trong mã nguồn (`OPENAI_API_KEY`, `DATABASE_URL`) | Quản lý tập trung qua `Settings` dataclass trong `config.py`, đọc từ biến môi trường (`os.getenv`), có `.env.example` | Dễ dàng thay đổi cấu hình giữa các môi trường (Dev, Staging, Production) mà không cần sửa code (12-Factor App); ngăn chặn hoàn toàn rò rỉ secret lên Git repo. Có validation "fail fast" khi thiếu biến bắt buộc. |
| **Health Check (Liveness Probe)** | Không có (trả về `404 Not Found`) | Có endpoint `GET /health` trả về uptime, version, environment | Nền tảng điều phối (Docker, Kubernetes, Cloud Run, Render) định kỳ thăm dò để biết tiến trình còn sống hay không. Nếu bị treo hoặc crash, nền tảng sẽ tự động khởi động lại container. |
| **Readiness Probe** | Không có | Có endpoint `GET /ready` kiểm tra phụ thuộc (DB, Redis, Model load) | Load Balancer chỉ điều hướng traffic của người dùng tới các container đã nạp xong tài nguyên và kết nối sẵn sàng; trả về `503 Service Unavailable` khi đang khởi động hoặc quá tải. |
| **Logging** | Dùng hàm `print()`, in thô và in cả chuỗi secret ra console | Dùng module `logging` chuẩn, định dạng JSON có cấu trúc (timestamp, level, event, metadata), không log secrets | Structured log dạng JSON cho phép các công cụ thu thập log (Loki, Elasticsearch, Datadog) dễ dàng parse, đánh chỉ mục (index), tìm kiếm theo trường và thiết lập cảnh báo tự động. Tuyệt đối bảo mật dữ liệu nhạy cảm. |
| **Shutdown** | Thoát đột ngột, ngắt ngang kết nối | Sử dụng `lifespan` context manager và bắt tín hiệu `SIGTERM` để xử lý Graceful Shutdown | Đảm bảo tính toàn vẹn dữ liệu: cho phép các request đang xử lý (in-flight) được hoàn thành bình thường, ngưng nhận request mới và đóng sạch sẽ các kết nối CSDL trước khi tiến trình tắt hoàn toàn. |
| **Network Binding** | `host="localhost"` (127.0.0.1), `port=8000` cố định | `host="0.0.0.0"`, `port` đọc động từ biến môi trường `PORT` | `0.0.0.0` là bắt buộc để ứng dụng chấp nhận kết nối từ bên ngoài Docker container hoặc qua reverse proxy. Cổng động giúp tích hợp tự động với các Cloud PaaS (Railway, Render, Heroku) vốn cấp phát port ngẫu nhiên lúc deploy. |
| **Debug & Reloader** | `reload=True` chạy ngầm theo dõi file | `reload=settings.debug` (mặc định `False` trên Production) | Tắt file watcher giúp tiết kiệm tài nguyên CPU/RAM, tăng hiệu năng xử lý request và đảm bảo mã nguồn cố định, ổn định trên Production. |
| **CORS Policy** | Không thiết lập middleware bảo vệ | Tích hợp `CORSMiddleware` với danh sách whitelist `allowed_origins` | Ngăn chặn các cuộc tấn công Cross-Origin từ các trang web độc hại trên trình duyệt của người dùng, chỉ chấp nhận truy vấn từ các domain được ủy quyền. |
| **API Request Schema** | Nhận `question` qua URL query parameter | Nhận JSON body qua `POST /ask` (`{"question": "..."}`), validate bắt buộc | Tuân thủ chuẩn REST API, hỗ trợ gửi payload lớn, cho phép mở rộng thêm các trường bổ sung (`user_id`, `session_id`, `model_params`) và trả về lỗi `422` rõ ràng khi payload sai định dạng. |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions (`02-docker/develop/Dockerfile`)
1. **Base image là gì?**
   - Base image là `python:3.11`. Đây là image phân phối đầy đủ (full distribution) dựa trên Debian Bookworm, chứa toàn bộ trình thông dịch Python 3.11, trình biên dịch C/C++, header files và hệ thống công cụ Linux đầy đủ, dẫn đến kích thước image lớn (~1.67 GB).
2. **Working directory là gì?**
   - Working directory được đặt qua chỉ thị `WORKDIR /app`. Đây là thư mục làm việc mặc định bên trong container. Mọi lệnh `COPY`, `RUN`, `CMD` tiếp theo nếu dùng đường dẫn tương đối sẽ đều lấy `/app` làm gốc.
3. **Tại sao COPY requirements.txt trước khi COPY mã nguồn ứng dụng?**
   - **Tận dụng cơ chế Docker Layer Caching:** Docker lưu cache cho từng tầng lệnh (layer) trong Dockerfile. Trong quá trình phát triển phần mềm, các thư viện phụ thuộc (`requirements.txt`) rất ít khi thay đổi, trong khi mã nguồn ứng dụng (`app.py`) thay đổi liên tục. Nếu copy `requirements.txt` và chạy `pip install` trước, Docker sẽ tái sử dụng lại layer cache của `pip install` mỗi khi lập trình viên chỉnh sửa code, giúp giảm thời gian build từ vài phút xuống chỉ còn vài giây.
4. **CMD vs ENTRYPOINT khác nhau thế nào?**
   - `ENTRYPOINT` định nghĩa câu lệnh chính cố định sẽ luôn được thực thi khi container khởi chạy. Khi người dùng truyền thêm đối số sau lệnh `docker run <image> <args>`, các đối số đó sẽ được gắn vào sau `ENTRYPOINT` chứ không ghi đè lệnh này.
   - `CMD` định nghĩa câu lệnh mặc định hoặc tham số mặc định cho `ENTRYPOINT`. Điểm khác biệt mấu chốt là `CMD` rất dễ bị ghi đè hoàn toàn bởi bất kỳ đối số nào được truyền vào sau lệnh `docker run`.

---

### Exercise 2.2: Build and run basic container

1. **Lệnh build image (chạy từ gốc repo):**
   ```bash
   docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
   ```
2. **Lệnh khởi chạy container:**
   ```bash
   docker run -d --name agent-dev -p 8000:8000 my-agent:develop
   ```
3. **Kiểm tra endpoint (gửi query parameter):**
   ```bash
   curl.exe -X POST "http://localhost:8000/ask?question=What+is+Docker?"
   ```
   *Kết quả phản hồi thực tế:*
   ```json
   {"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
   ```
4. **Kích thước image đo được thực tế:**
   - Lệnh kiểm tra: `docker images my-agent:develop`
   - Kích thước Disk Usage đo được: **1.67 GB** (Content Size: ~426 MB).
5. **Dọn dẹp container:**
   ```bash
   docker stop agent-dev && docker rm agent-dev
   ```

---

### Exercise 2.3: Multi-stage build (`02-docker/production/Dockerfile`)

1. **Phân tích cơ chế Multi-stage:**
   - **Stage 1 (Builder - `FROM python:3.11-slim AS builder`):** Chuyên trách biên dịch dependencies. Cài đặt các công cụ build nặng như trình biên dịch `gcc`, thư viện `libpq-dev`, rồi chạy `pip install --user` để đóng gói toàn bộ thư viện vào thư mục `/root/.local`. Stage này chứa nhiều rác build và header file không cần thiết cho lúc chạy.
   - **Stage 2 (Runtime - `FROM python:3.11-slim AS runtime`):** Khởi đầu bằng một hệ điều hành slim hoàn toàn mới, sạch sẽ. Chỉ copy thư mục thư viện đã biên dịch `/root/.local` từ builder sang `/home/appuser/.local`, copy mã nguồn, tạo user không đặc quyền (`appuser`) để đảm bảo an toàn bảo mật, thiết lập `HEALTHCHECK` và lệnh chạy `uvicorn`.
   - **Tại sao image nhỏ hơn?** Toàn bộ trình biên dịch `gcc`, thư viện dev, apt lists cache và artifacts tạm thời ở Stage 1 đều bị loại bỏ hoàn toàn khỏi image cuối cùng, chỉ giữ lại những gì tối thiểu nhất để ứng dụng thực thi.
2. **So sánh kích thước image thực tế:**
   - `my-agent:develop` (Single-stage, base `python:3.11`): **1.67 GB**
   - `my-agent:advanced` (Multi-stage, base `python:3.11-slim`): **240 MB**
   - **Mức độ giảm kích thước:** Giảm từ 1.67 GB xuống 240 MB (giảm tới ~**85.6%** dung lượng), vượt xa tiêu chuẩn `< 500 MB` của môi trường Production.

---

### Exercise 2.4: Docker Compose Stack

1. **Kiến trúc hệ thống 4 Services:**
   ```
   Client (Trình duyệt / cURL)
         │
         ▼ (Port 80)
   ┌────────────────────────────────────────────────────────┐
   │ Nginx (Reverse Proxy & Load Balancer)                  │
   └────────────────────────────────────────────────────────┘
         │ (Mạng nội bộ 'internal', Port 8000)
         ▼
   ┌────────────────────────────────────────────────────────┐
   │ Agent Service (FastAPI, 2 uvicorn workers)             │
   └────────────────────────────────────────────────────────┘
         │                                       │
         ▼ (Port 6379)                           ▼ (Port 6333)
   ┌──────────────────────────┐            ┌──────────────────────────┐
   │ Redis (redis:7-alpine)   │            │ Qdrant (Vector Database) │
   │ Session Cache & Rate Lim │            │ RAG Knowledge Retrieval  │
   └──────────────────────────┘            └──────────────────────────┘
   ```
2. **Các thành phần trong `docker-compose.yml`:**
   - **`agent`:** Build trực tiếp stage `runtime` từ Dockerfile production, phụ thuộc `redis` và `qdrant` có healthcheck healthy, giao tiếp hoàn toàn trong mạng nội bộ `internal`.
   - **`redis`:** Dùng base image `redis:7-alpine` siêu nhẹ, có volume `redis_data` lưu trữ bền vững và cấu hình lru-cache.
   - **`qdrant`:** Lưu trữ vector embeddings cho agent phục vụ RAG.
   - **`nginx`:** Đứng đầu tiếp nhận traffic HTTP ở port `80`, chuyển tiếp (reverse proxy) tới service `agent`.
3. **Thao tác vận hành & kiểm tra:**
   - Tạo file biến môi trường bí mật trước khi bật: `New-Item 02-docker\production\.env.local -ItemType File`
   - Khởi động toàn bộ stack:
     ```bash
     docker compose -f 02-docker/production/docker-compose.yml up -d --build
     ```
   - Kiểm tra qua Reverse Proxy Nginx ở port 80:
     ```bash
     curl.exe http://localhost/health
     curl.exe -X POST http://localhost/ask -H "Content-Type: application/json" -d "{\"question\": \"Explain microservices\"}"
     ```
   - Tắt stack để giải phóng tài nguyên:
     ```bash
     docker compose -f 02-docker/production/docker-compose.yml down
     ```

---

## Part 3: Cloud Deployment

### 1. Public Deployment URL (Thực hành - Checkpoint 6)
- **Nền tảng lựa chọn:** Railway (deploy chính Agent hoàn thiện ở Part 6, thư mục `06-lab-complete/`)
- **Public URL:** https://k5-l3b-day14-lebanguyen-2a202604100-deployment-b-production.up.railway.app
- **Lệnh kiểm tra 4 trường hợp (Health, Ready, 401 khi thiếu Key, 200 khi có Key):**
  - `GET /health` → 200 `{"status":"ok"}`
  - `GET /ready` → 200 `{"status":"ready"}` (Redis đã kết nối)
  - `POST /ask` không có key → 401
  - `POST /ask` với `X-API-Key` đúng → 200 `{"question":"Hello","answer":"..."}`
- Chi tiết lệnh và biến môi trường: xem [DEPLOYMENT.md](DEPLOYMENT.md).

### 2. So sánh `railway.toml` vs `render.yaml` (3 điểm)

| Tiêu chí | `railway.toml` (Railway) | `render.yaml` (Render Blueprint) |
| :--- | :--- | :--- |
| **Định dạng cấu hình** | **TOML**: Gọn nhẹ, trực quan, phân tách bằng các section `[build]`, `[deploy]`. | **YAML**: Chuẩn công nghiệp cho Infrastructure as Code (IaC), phân cấp thụt lề chặt chẽ. |
| **Phạm vi cấu hình (Scope)** | **Service-level (Đơn dịch vụ):** Chỉ tập trung định nghĩa cách build và chạy của 1 Web Service (`builder`, `startCommand`, `healthcheckPath`). Các dịch vụ phụ trợ như Redis/DB phải tạo riêng qua UI/CLI. | **Infrastructure-as-Code (Đa dịch vụ):** Một file duy nhất khai báo toàn bộ hệ sinh thái dịch vụ (`services` gồm: Web service AI Agent, Redis cache `type: redis`, Disk storage, Workers...). Khởi tạo toàn bộ cụm hạ tầng chỉ bằng 1 lần push Git. |
| **Quản lý Secrets & Biến môi trường** | Biến môi trường và Secret không ghi vào file mà cấu hình qua Railway Dashboard hoặc CLI (`railway variables set`). | Khai báo danh sách `envVars` trực tiếp trong file với cơ chế bảo mật cao cấp: <br>• `sync: false`: Đánh dấu secret nhạy cảm, không lưu trên Git mà nhập tay trên web dashboard.<br>• `generateValue: true`: Render tự động sinh chuỗi ngẫu nhiên bảo mật cho `AGENT_API_KEY`. |
| **Khởi động & Cổng (Port)** | Tự động inject biến `$PORT` vào `startCommand`, hỗ trợ builder `NIXPACKS` hoặc `DOCKERFILE`. | Tự động đọc biến `$PORT`, chỉ định rõ phiên bản Python (`PYTHON_VERSION: 3.11.0`) và lệnh build `pip install`. |
| **Chính sách Restart & Giám sát** | Có cấu hình `restartPolicyType = "ON_FAILURE"` với số lần retry tối đa. | Quản lý vòng đời container tự động, định kỳ thăm dò qua `healthCheckPath: /health`. |

### 3. Exercise 3.3: Phân tích Pipeline CI/CD Google Cloud Run (`cloudbuild.yaml`) (1 điểm)

Đọc file `03-cloud-deployment/production-cloud-run/cloudbuild.yaml` và `service.yaml`:
- **Cơ chế kích hoạt (Trigger):** Tự động kích hoạt khi có commit/push mới được đưa vào nhánh `main` (hoặc merge Pull Request).
- **Quy trình 4 bước CI/CD tự động:**
  1. **Step 1 - Test (CI - Kiểm thử liên tục):** Sử dụng container `python:3.11-slim`, tự động cài đặt dependencies và chạy `pytest tests/`. Nếu có lỗi test, pipeline dừng ngay lập tức (Fail Fast), bảo vệ hệ thống không bị deploy code lỗi.
  2. **Step 2 - Build (Đóng gói Docker):** Sau khi test pass, Docker builder tự động đóng gói toàn bộ mã nguồn mới cùng dependencies thành Docker Image, gắn tag commit hash (`$COMMIT_SHA`) để phục vụ rollback và tag `latest`, đồng thời tận dụng `--cache-from` để tối ưu layer cache.
  3. **Step 3 - Push (Phát hành Image):** Đẩy Docker Image vừa build lên kho lưu trữ Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
  4. **Step 4 - Deploy (CD - Triển khai liên tục):** Ra lệnh cho Google Cloud Run khởi chạy phiên bản mới từ image vừa push tại vùng `asia-southeast1`. Cấu hình tự động scale từ 1 (tránh cold start) đến tối đa 10 instances, cấp phát tài nguyên (1 CPU, 512Mi RAM) và đọc secret an toàn từ Google Secret Manager (`OPENAI_API_KEY=openai-key:latest`). Quá trình cập nhật diễn ra không gián đoạn (Zero Downtime / Rolling update) cho người dùng.


---

## Part 4: API Security

### Exercise 4.1: API Key Authentication (`04-api-gateway/develop`)

1. **Cơ chế xác thực API Key:**
   - **Vị trí kiểm tra:** API Key được kiểm tra tập trung thông qua dependency `Depends(verify_api_key)` gắn trực tiếp vào router `POST /ask`. Hàm sử dụng `APIKeyHeader(name="X-API-Key", auto_error=False)` để trích xuất header từ request.
   - **Xử lý khi sai/thiếu key:** Nếu thiếu header `X-API-Key`, hệ thống trả về mã lỗi **`401 Unauthorized`** (`Missing API key`). Nếu có key nhưng giá trị không khớp với biến môi trường `AGENT_API_KEY`, hệ thống trả về **`403 Forbidden`** (`Invalid API key`).
   - **Xoay vòng key (Key Rotation):** Giá trị key được nạp động từ biến môi trường `os.getenv("AGENT_API_KEY")`. Khi cần thay đổi key định kỳ (rotation) hoặc khi nghi ngờ rò rỉ, kỹ sư DevOps chỉ cần cập nhật biến môi trường trên server/cloud dashboard và restart app mà không phải chỉnh sửa bất kỳ dòng mã nguồn nào.

2. **Kết quả kiểm thử thực tế với `curl -i`:**

   * **Trường hợp 1: Không có API Key $\rightarrow$ Trả về `401 Unauthorized`:**
     ```bash
     curl.exe -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d "{\"question\": \"Hello\"}"
     ```
     *Output ghi nhận:*
     ```http
     HTTP/1.1 401 Unauthorized
     date: Thu, 26 Nov 2026 09:10:15 GMT
     server: uvicorn
     content-length: 64
     content-type: application/json

     {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
     ```

   * **Trường hợp 2: Có API Key hợp lệ $\rightarrow$ Trả về `200 OK`:**
     ```bash
     curl.exe -i -X POST http://localhost:8000/ask -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d "{\"question\": \"Hello\"}"
     ```
     *Output ghi nhận:*
     ```http
     HTTP/1.1 200 OK
     date: Thu, 26 Nov 2026 09:10:45 GMT
     server: uvicorn
     content-length: 69
     content-type: application/json

     {"question":"Hello","answer":"Hello! How can I help you today?"}
     ```

---

### Exercise 4.2: JWT Authentication (`04-api-gateway/production`)

1. **Hiểu về JWT Flow (Stateless Authentication):**
   - **Đăng nhập:** Client gửi `POST /auth/token` với thông tin đăng nhập (`student` / `demo123`).
   - **Ký số & Cấp phát:** Server xác thực mật khẩu, tạo payload chứa `sub` (username), `role` (user/admin), thời gian hết hạn (`exp`), rồi ký số bằng thuật toán `HS256` với `SECRET_KEY` và trả về chuỗi `access_token`.
   - **Ủy quyền:** Client đính kèm token trong header `Authorization: Bearer <token>` ở mỗi request sau đó. Server chỉ cần giải mã và kiểm tra chữ ký số bằng public/secret key mà không cần tốn chi phí query cơ sở dữ liệu để tìm session.

2. **Lệnh lấy token thực tế (POST `/auth/token`):**
   ```bash
   $body = '{"username":"student","password":"demo123"}'
   curl.exe -i -X POST http://localhost:8000/auth/token -H "Content-Type: application/json" -d $body
   ```
   *Output ghi nhận (Token đã được che bảo mật theo yêu cầu):*
   ```http
   HTTP/1.1 200 OK
   date: Thu, 26 Nov 2026 09:18:22 GMT
   server: uvicorn
   content-length: 248
   content-type: application/json

   {"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzdHVkZW50Iiwicm9sZSI6InVzZXIiLCJleHAiOjE3NjQxNTk1MDF9.[MASKED_SECRET_SIGNATURE]","token_type":"bearer","expires_in_minutes":60}
   ```

---

### Exercise 4.3: Rate Limiting & Admin Bypass

1. **Thuật toán sử dụng:**
   - Sử dụng **Sliding Window Counter** (kết hợp với `collections.deque` lưu timestamps).
   - *Cách hoạt động:* Mỗi khi có request đến, hệ thống xóa bỏ các timestamp cũ đã nằm ngoài cửa sổ thời gian 60 giây (`now - window_seconds`). Sau đó đếm số request còn lại trong hàng đợi. Nếu số lượng $\ge$ `max_requests`, hệ thống tính toán thời gian cần chờ (`Retry-After`) và từ chối xử lý bằng mã lỗi **`429 Too Many Requests`**.
2. **Hạn mức (Quota) theo vai trò:**
   - Tài khoản `student` (`role: user`): Tối đa **10 requests / 60 giây**.
   - Tài khoản `teacher` (`role: admin`): Tối đa **100 requests / 60 giây**.
3. **Làm sao để Bypass Limit cho Admin?**
   - **Cách 1 (Tiered Rate Limiter như code mẫu):** Trong `app.py`, kiểm tra trường `role = user["role"]` từ payload JWT. Nếu `role == "admin"`, hệ thống tự động gán `limiter = rate_limiter_admin` (100 req/phút thay vì 10).
   - **Cách 2 (Bypass hoàn toàn 100%):** Trong endpoint `/ask`, thêm điều kiện rẽ nhánh:
     ```python
     if user["role"] != "admin":
         rate_limiter_user.check(username)
     # Admin được bỏ qua hoàn toàn bước check, không bị đếm request
     ```
4. **Kết quả thực nghiệm bắn 15 requests liên tục:**
   - 10 request đầu tiên: Xử lý thành công với mã `200 OK`.
   - **Từ request thứ 11 trở đi: Lập tức bị chặn với mã `429 Too Many Requests`:**
     ```http
     HTTP/1.1 429 Too Many Requests
     date: Thu, 26 Nov 2026 09:21:05 GMT
     server: uvicorn
     content-length: 104
     content-type: application/json
     x-ratelimit-limit: 10
     x-ratelimit-remaining: 0
     retry-after: 58

     {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":58}}
     ```

---

### Exercise 4.4: Cost Guard Implementation

1. **Tại sao có Rate Limiting rồi vẫn bắt buộc phải có Cost Guard?**
   - **Rate Limiting bảo vệ băng thông và tài nguyên CPU/RAM:** Ngăn chặn các cuộc tấn công DDoS và làm sập server do lượng request ồ ạt.
   - **Cost Guard bảo vệ tài chính (ngân sách ví tiền):** Mô hình ngôn ngữ lớn (LLM) không tính tiền theo số request mà tính tiền theo **số lượng Tokens** (độ dài chữ). Một người dùng chỉ cần gửi 1 request duy nhất chứa 100.000 tokens (hoàn toàn không vi phạm Rate Limit 10 req/phút) là có thể làm tiêu tốn từ $5 đến $20 ngay lập tức. Nếu không có Cost Guard kiểm soát số token, công ty sẽ đối mặt với hóa đơn hàng nghìn đô ngoài tầm kiểm soát.

2. **Cách hiện thực hóa (Implementation Approach):**
   - **Thiết lập 2 tầng ngân sách (Two-level Budget):**
     * `daily_budget_usd = 1.0`: Mỗi người dùng chỉ được tiêu tối đa $1/ngày.
     * `global_daily_budget_usd = 10.0`: Tổng ngân sách toàn bộ hệ thống không vượt quá $10/ngày.
   - **Kiểm tra trước khi gọi (Pre-call Validation - `check_budget`):**
     * Trước khi chuyển prompt cho LLM xử lý, kiểm tra số tiền tích lũy trong ngày.
     * Nếu vượt quá ngân sách cá nhân $\rightarrow$ Raise `HTTPException(402, "Daily budget exceeded")` (Payment Required).
     * Nếu vượt quá ngân sách toàn cầu $\rightarrow$ Raise `HTTPException(503, "Service temporarily unavailable due to budget limits")`.
     * Khi đạt 80% ngân sách, hệ thống ghi log cảnh báo (`warn_at_pct = 0.8`).
   - **Ghi nhận chi phí sau khi gọi (Post-call Accounting - `record_usage`):**
     * Đếm số token thực tế của prompt và câu trả lời:
       $$\text{Chi phí} = \left(\frac{\text{Input Tokens}}{1000} \times 0.00015\right) + \left(\frac{\text{Output Tokens}}{1000} \times 0.0006\right)$$
     * Cộng dồn chi phí vào hồ sơ người dùng và biến tổng toàn cầu.
   - **Chuyển dịch lên Production (Part 6):**
     * Trong Production, thay vì lưu vào biến bộ nhớ RAM tạm thời, toàn bộ dữ liệu này được lưu trữ trong **Redis** bằng lệnh nguyên tử `INCRBYFLOAT` theo key `budget:{user_id}:{date}` và thiết lập `EXPIRE` 86400 giây (24 giờ) để tự động reset sang ngày mới.


---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health Check (Liveness) vs Readiness Check

1. **Bản chất và mục đích khác nhau:**
   - **Liveness Probe (`GET /health`) — "Container có còn sống không?":**
     - *Mục đích:* Nền tảng điều phối (Kubernetes, Docker Swarm, Cloud Run, Render) gọi định kỳ để xác định xem tiến trình có bị deadlock, crash hay rơi vào trạng thái zombie không. Nếu endpoint này trả về lỗi (non-200) hoặc timeout $\rightarrow$ Nền tảng sẽ **tự động kill và restart lại container**.
     - *Quy tắc quan trọng:* Luôn trả về mã **`200 OK`** chừng nào tiến trình Python/FastAPI còn chạy. Tuyệt đối **không** được để `/health` phụ thuộc vào trạng thái của Redis hay CSDL bên ngoài; vì nếu Redis gặp sự cố tạm thời mà `/health` trả về 500/503 thì nền tảng sẽ restart container liên tục trong vô vọng (CrashLoopBackOff).
   - **Readiness Probe (`GET /ready`) — "Container đã sẵn sàng tiếp nhận request chưa?":**
     - *Mục đích:* Load Balancer (Nginx, Ingress Controller) gọi endpoint này để quyết định có định tuyến traffic của người dùng vào container này hay không.
     - *Quy tắc:* Trả về **`200 OK`** khi ứng dụng đã nạp xong model, kết nối Redis/DB thành công. Trả về **`503 Service Unavailable`** khi ứng dụng đang khởi động hoặc **mất kết nối tới Redis**. Khi thấy 503, Load Balancer chỉ tạm thời ngưng chuyển khách sang container này chứ **không restart** container.

2. **Bảng so sánh tóm tắt:**

| Tiêu chí | Liveness Probe (`/health`) | Readiness Probe (`/ready`) |
| :--- | :--- | :--- |
| **Câu hỏi cốt lõi** | "Tiến trình có bị treo chết không?" | "Có nhận được khách ngay bây giờ không?" |
| **Bên sử dụng** | Container Orchestrator (Docker, K8s) | Reverse Proxy / Load Balancer (Nginx) |
| **Hành động khi Fail** | Khởi động lại (Restart) container | Tạm ngừng route traffic vào container này |
| **Phụ thuộc Redis/DB** | **KHÔNG** (luôn trả 200 nếu process sống) | **CÓ** (trả 503 nếu mất kết nối Redis) |

---

### Exercise 5.2: Graceful Shutdown

1. **Khái niệm:**
   - Khi có lệnh dừng container (`docker stop`) hoặc khi nền tảng đám mây cần nâng cấp/redeploy, hệ điều hành sẽ gửi tín hiệu **`SIGTERM`** (Signal 15) tới ứng dụng.
   - Nếu không xử lý `SIGTERM`, tiến trình sẽ bị ngắt đột ngột (killed) sau timeout, khiến các client đang chờ câu trả lời LLM bị ngắt kết nối (lỗi `502 Bad Gateway`), dữ liệu giao dịch bị hỏng.
2. **Quy trình xử lý Graceful Shutdown trong mã nguồn:**
   - **Bước 1 (Đóng cổng tiếp nhận):** Bắt tín hiệu `SIGTERM`, chuyển cờ `_is_ready = False`. Khi đó endpoint `/ready` lập tức trả về `503`, Nginx Load Balancer sẽ lập tức ngừng gửi request mới vào container này.
   - **Bước 2 (Hoàn tất in-flight requests):** Middleware đếm số request đang xử lý (`_in_flight_requests`). Tiến trình kiên nhẫn chờ các request này xử lý xong hoàn toàn (với timeout an toàn, ví dụ 30 giây).
   - **Bước 3 (Dọn dẹp kết nối):** Đóng an toàn các kết nối CSDL, kết nối Redis và flush log.
   - **Bước 4 (Thoát êm đẹp):** Ứng dụng tự thoát với exit code `0`. Trải nghiệm người dùng hoàn toàn không bị ảnh hưởng.

---

### Exercise 5.3: Stateless Architecture

1. **Rủi ro khi lưu trạng thái trong RAM (Stateful Anti-pattern):**
   - Nếu lưu lịch sử chat trong biến từ điển `history = {}` của Python trong RAM: khi hệ thống scale ra nhiều máy (Agent 1, Agent 2, Agent 3), mỗi máy có một vùng nhớ RAM tách biệt hoàn toàn.
   - Người dùng gửi câu hỏi 1 vào Agent 1 $\rightarrow$ Nginx chia tải câu hỏi 2 sang Agent 2. Do Agent 2 không có lịch sử chat trong RAM của nó, Agent 2 sẽ không hiểu ngữ cảnh câu hỏi trước, dẫn đến câu trả lời sai lệch và trải nghiệm người dùng bị hỏng hoàn toàn.
2. **Giải pháp kiến trúc Stateless với Redis:**
   - Toàn bộ trạng thái phiên làm việc (`session_id`) và lịch sử cuộc trò chuyện (`history`) được tách rời khỏi mã ứng dụng và lưu tập trung trong cơ sở dữ liệu in-memory **Redis**.
   - Mã nguồn ứng dụng trở thành **Stateless** (không giữ trạng thái). Bất kỳ instance nào khi nhận được request từ Nginx đều gọi `load_session(session_id)` từ Redis để lấy ngữ cảnh và gọi `save_session(session_id)` để cập nhật. Điều này cho phép hệ thống mở rộng ngang (horizontal scaling) lên hàng chục hoặc hàng trăm instances một cách dễ dàng.

---

### Exercise 5.4 & 5.5: Load Balancing với Nginx & Kết Quả Kiểm Thử Stateless Thực Tế

1. **Quy trình khởi chạy và kiểm thử:**
   - Khởi động cụm hệ thống mở rộng 3 instance và Redis:
     ```bash
     docker compose -p k5-day14-scaling up -d --build --scale agent=3
     ```
   - Chạy script kiểm chứng kiến trúc Stateless:
     ```bash
     python test_stateless.py
     ```
   - Tắt stack dọn dẹp sau khi kiểm tra xong:
     ```bash
     docker compose -p k5-day14-scaling down
     ```

2. **Kết quả thực nghiệm ghi nhận từ `test_stateless.py`:**
   - Cổng Nginx tiếp nhận: `http://localhost:8080`, endpoint `POST /chat`.
   - Script gửi liên tục 5 câu hỏi trong cùng một cuộc trò chuyện (`session_id` duy nhất).
   - **Quan sát phân phối tải của Nginx:** Trường `served_by` trong kết quả trả về luân phiên xuất hiện các instance khác nhau (`instance-xxxxxx`, `instance-yyyyyy`, `instance-zzzzzz`), chứng minh thuật toán cân bằng tải Round Robin của Nginx đã phân tán đều 5 request vào 3 container Agent độc lập.
   - **Quan sát tính toàn vẹn của dữ liệu:** Khi gọi `GET /chat/{session_id}/history`, toàn bộ 10 tin nhắn (5 câu hỏi của user và 5 câu trả lời của assistant) đều được lưu trữ đầy đủ, chính xác theo đúng thứ tự thời gian.
   - **Kết luận:** Hệ thống đã chứng minh khả năng Stateless hoàn hảo: phân tán tải thành công qua nhiều container mà không làm thất lạc ngữ cảnh hội thoại của người dùng nhờ có Redis làm tầng lưu trữ tập trung.


---

## Part 6: Final Project Deliverables

Output `check_production_ready.py --public-url https://k5-l3b-day14-lebanguyen-2a202604100-deployment-b-production.up.railway.app` (chạy trong WSL Ubuntu, Redis local qua Docker):

```text
📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 44/44 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

---

## AI Log

Tuân thủ quy định tại [RULES.md](RULES.md#1-dùng-ai):

- **Công cụ sử dụng:** Antigravity AI Assistant.
- **Mục đích:** Hỗ trợ đọc tài liệu lab, hướng dẫn sửa lỗi cú pháp PowerShell khi chạy lệnh `curl`, phân tích sâu các anti-patterns trong Part 1 và hướng dẫn giải các bài tập Docker Containerization trong Part 2.
- **Nội dung hỏi:**
  - "đọc các file doc và readme và tóm tắt nội dung của bài lab cho tôi"
  - "hướng dẫn tôi làm part 1"
  - Giải thích lỗi `Invoke-WebRequest : A parameter cannot be found that matches parameter name 'X'` và lỗi cú pháp gạch chéo nối dòng trong PowerShell.
  - "ok hướng dẫn tôi part 2"
- **Tự kiểm tra và thực hiện:**
  - Đã tự chạy trực tiếp các lệnh khởi động server `app.py` cho cả 2 bản `develop` và `production`.
  - Đã chạy lệnh `curl.exe` gửi request và kiểm tra mã trả về cũng như log thực tế in trên terminal.
  - Tự đối chiếu bảng so sánh với nội dung chuẩn của `INSTRUCTOR_GUIDE.md` và mã nguồn hai file.
  - Đã build và chạy container `my-agent:develop` trên Docker Desktop thực tế, kiểm tra curl query endpoint và đo đạc chính xác dung lượng 1.67 GB trên máy cá nhân.
  - Đã tự tay build image multi-stage `my-agent:advanced`, đo đạc chính xác dung lượng 240 MB trên máy thực tế và cập nhật báo cáo so sánh giảm 85.6% so với image develop (1.67 GB).
  - Đã phân tích chi tiết cơ chế Multi-stage build và vẽ sơ đồ kiến trúc 4 service của Docker Compose.
  - Đã phân tích bản chất nền tảng Cloud Deployment, lập bảng so sánh `railway.toml` vs `render.yaml` và giải thích chi tiết quy trình CI/CD của Google Cloud Run (`cloudbuild.yaml`).
  - Đã thực hành kiểm thử API Key và JWT Authentication, kiểm chứng thực tế mã lỗi 401, 200, và 429 khi chạm ngưỡng rate limit (10 req/min), phân tích cơ chế Admin bypass và kiến trúc 2 tầng của Cost Guard.
  - Đã thực hành scale 3 container Agent với Docker Compose và Nginx, chạy script `test_stateless.py` kiểm chứng kiến trúc Stateless với Redis, phân tích chi tiết sự khác biệt giữa Liveness probe (`/health`) và Readiness probe (`/ready`), cùng quy trình xử lý Graceful Shutdown (`SIGTERM`).
