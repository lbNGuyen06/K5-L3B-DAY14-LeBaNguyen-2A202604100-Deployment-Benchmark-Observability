# Deployment Information

## Public URL

https://k5-l3b-day14-lebanguyen-2a202604100-deployment-b-production.up.railway.app

## Platform

Railway (deploy từ GitHub repo, Root Directory = `/06-lab-complete`, build bằng `Dockerfile`, cấu hình trong `06-lab-complete/railway.toml`).

Services trong project:
- `agent` — FastAPI app (Dockerfile multi-stage, non-root, HEALTHCHECK).
- `Redis` — Redis service trong cùng project, agent kết nối qua private network.

## Test Commands

Thay `<API_KEY>` bằng giá trị `AGENT_API_KEY` đã đặt trên Railway.

### Health Check (không cần key)
```bash
curl -i https://k5-l3b-day14-lebanguyen-2a202604100-deployment-b-production.up.railway.app/health
# Expected: HTTP 200 {"status":"ok","environment":"development"}
```

### Readiness Check (không cần key)
```bash
curl -i https://k5-l3b-day14-lebanguyen-2a202604100-deployment-b-production.up.railway.app/ready
# Expected: HTTP 200 {"status":"ready"}   (Redis đã kết nối)
```

### API không có key → 401
```bash
curl -i -X POST https://k5-l3b-day14-lebanguyen-2a202604100-deployment-b-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
# Expected: HTTP 401 {"detail":"Invalid or missing API key. Include header: X-API-Key: <key>"}
```

### API có key → 200
```bash
curl -i -X POST https://k5-l3b-day14-lebanguyen-2a202604100-deployment-b-production.up.railway.app/ask \
  -H "X-API-Key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
# Expected: HTTP 200 {"question":"Hello","answer":"..."}
```

## Environment Variables Set

| Biến | Giá trị | Ghi chú |
| --- | --- | --- |
| `PORT` | `8080` (Railway cấp) | Target port trên Networking = 8080 |
| `ENVIRONMENT` | `development` | Mặc định trong app |
| `AGENT_API_KEY` | (secret, không ghi trong tài liệu) | Đặt trên Railway Variables |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` | Reference tới service Redis |
| `RATE_LIMIT_PER_MINUTE` | `10` | Giới hạn 10 request/phút |
| `DAILY_BUDGET_USD` | `1.0` | Ngân sách ngày |

## Kiểm tra bằng script

```bash
python check_production_ready.py --public-url https://k5-l3b-day14-lebanguyen-2a202604100-deployment-b-production.up.railway.app
```

Kết quả: PASS 12/12 (44/44 checks), gồm tiêu chí 12 "Public URL ready" và các kiểm tra runtime chạy cục bộ với Redis.

## Screenshots

Chưa có. Cần chụp: trang deployment trên Railway, service đang Active, và kết quả test `/health` trong `screenshots/` (tên file theo `DAY14_DELIVERY_CHECKLIST.md`).
