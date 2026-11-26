# Benchmark & Observability Report — Day 14

**Họ tên:** Le Ba Nguyen (MSSV 2A202604100)
**Ngày chạy:** 26–27/11/2026
**Môi trường:** Windows 11, WSL2 Ubuntu (Python 3.11.16 qua `uv`), Docker Desktop 29.6.2 (Docker Engine trên WSL2), Redis 7 alpine. Benchmark hiệu năng chạy trên develop (uvicorn, 1 process mỗi agent). Stack production chạy trên Docker Compose với 1–3 agent (giới hạn 0.5 CPU / 256 MB mỗi container).

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Đủ nhanh cho chatbot tương tác. Ngưỡng mặc định của `load_test.py`. Trong thí nghiệm, p95 ở tải thường là ~220 ms, nên còn dư địa cho các request chậm. |
| Error rate `/ask` | < 2 % | Mock LLM có ~1 % lỗi 503 mặc định. Ngưỡng 2 % cho phép dao động nhẹ nhưng bắt được lỗi hệ thống. Alert hạ tầng dùng 5 % (`AgentHighErrorRate`), SLO chặt hơn để cảnh báo sớm. |
| Accuracy trên golden dataset | ≥ 85 % | Quality gate trong CI (`--min-accuracy 0.85`). Đủ cao để chặn regression lớn, và đủ thấp để không chặn vì 1–2 câu trả lời khác từ khóa. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

Mỗi mức chạy 300 request, `MOCK_SLOW_RATE` mặc định (0.03).

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3.89 | 190.2 | 220.5 | 1704.3 | 1.00 % | PASS |
| 10 | 38.45 | 190.3 | 217.6 | 1685.1 | 1.00 % | PASS |
| 50 | 105.01 | 197.2 | 245.8 | 1676.3 | 0.33 % | PASS |
| 100 | 82.92 | 333.3 | 3058.0 | 3213.0 | 0.33 % | FAIL (p95) |

**Nhận xét:** RPS tăng gần tuyến tính từ concurrency 1 đến 50 (3.9 → 105 req/s), vì mỗi request chủ yếu là chờ LLM mock (~190 ms) chứ không tốn CPU của agent, nên nhiều request có thể chạy song song. Ở concurrency 100, RPS giảm xuống 83 và p95 vượt 3 giây: hàng đợi xuất hiện, request phải chờ. Đây là điểm bão hòa của một process uvicorn. Nhìn chung, p50 gần như không đổi trong khi p95/p99 mới phản ánh được tải cao.

### 2.2 Tail latency

Chạy với concurrency 20, 300 request mỗi mức.

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 189.0 | 217.4 | 224.2 |
| 0.03 (mặc định) | 224.0 | 220.0 | 1679.4 |
| 0.1 | 305.1 | 1680.5 | 1706.8 |

**Nhận xét:** p99 nhạy nhất với request chậm: chỉ 3 % request chậm đã đẩy p99 lên ~1,7 giây. p95 chỉ "vỡ" khi tỉ lệ chậm vượt 5 %: ở 10 % thì p95 nhảy lên 1,68 giây và SLO p95 FAIL, trong khi avg chỉ tăng ~60 % (189 → 305 ms). Average không nên dùng làm SLO vì nó bị kéo xuống bởi phần lớn request nhanh và che mất phần đuôi mà người dùng thực sự gặp. SLO nên đặt theo p95 hoặc p99.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3 % (1/23) | 91.3 % (21/23) | 100 % (23/23) |
| Avg tokens / câu | 56.6 | 109.1 | 113.7 |
| Tổng cost (USD) | 0.000397 | 0.000762 | 0.000790 |
| Cost / câu đúng (USD) | 0.000397 | 0.000036 | 0.000034 |
| Quality gate (≥ 80 %, không regression) | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 | `token`, `hết hạn`, `chữ ký` | Thêm mục `jwt` vào `KNOWLEDGE_BASE` (`utils/mock_llm.py`): API key không hết hạn, JWT là token có chữ ký số và thời điểm hết hạn. |
| scaling-03 | `cpu`, `memory`, `custom metrics` | Thêm mục `hpa`, `kubernetes`, `autoscal` vào `KNOWLEDGE_BASE`: HPA scale pod theo CPU, memory hoặc custom metrics. |

Sau khi sửa không có câu nào regression (0 câu bị giảm điểm so với v1), 22 câu được cải thiện.

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:** v2 (có retrieval) tăng accuracy từ 4.3 % lên 91.3 % (trước khi sửa KB), đổi lại số token tăng gấp đôi (56.6 → 109.1) và chi phí tổng tăng gần gấp đôi. Chi phí trên mỗi câu đúng lại thấp hơn nhiều ở v2, vì v1 hầu như trả lời sai. Latency p95 của eval tăng nhẹ (181 → 213 ms) do thêm bước retrieval. Đây là trade-off có lợi: chất lượng tăng rất nhiều so với chi phí và latency tăng thêm.

Lưu ý: golden dataset chỉ 23 câu, và phần KB được thêm đúng cho các câu sai nên đạt 100 % không chứng minh agent tổng quát tốt. Đây là dạng "học theo đề thi" cần ghi nhận.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals): `screenshots/grafana-dashboard.png`
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian): `screenshots/jaeger-slow-trace.png`
- [x] Một trace lỗi trong Jaeger (có event `exception`): `screenshots/jaeger-error-trace.png`
- [x] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**: `screenshots/prometheus-alert-firing.png` (hai alert `AgentHighErrorRate` và `AgentHighLatencyP95` cùng firing)

### 4.2 Thí nghiệm "phá hệ thống"

Thời gian đo từ lúc đổi cấu hình đến khi alert chuyển sang `firing` (theo Prometheus rules API, lấy từ lần chạy đầu tiên; Locust chạy liên tục 30 user).

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 96 s (pending sau 34 s) | Error rate (đỏ) và Golden Signals |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | 153 s (pending sau 32 s) | p95/p99 tăng mạnh, avg tăng ít hơn |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | 151 s (pending sau 31 s) | Cost USD/giờ và LLM panel |
| D | `docker pause` 1 instance | `AgentInstanceDown` | 40 s (pending sau 10 s) | Instances up giảm |
| E | `AGENT_VERSION=v1` | Không có | — (không alert nào trong 240 s) | Không có panel hạ tầng nào; chỉ thấy qua eval |

**Lưu ý thí nghiệm C:** alert cost có ngưỡng $2/giờ, và riêng tải Locust 30 user với model nhỏ đã tạo ~2,3–2,9 $/giờ. Vì vậy alert C không tách được tác động của việc đổi model. Sau khi khôi phục về model nhỏ, alert vẫn firing một lúc do cửa sổ rate 5 phút. Muốn đo đúng cần baseline không tải hoặc ngưỡng khác.

**Lưu ý thí nghiệm D:** khi pause một instance, `AgentHighErrorRate` không firing (vẫn `inactive`). Request tới instance bị pause gây lỗi ở Nginx (502/504) nên không được agent đếm.

Lần chạy A và B cùng lúc: `AgentHighErrorRate` firing sau 87–92 s, `AgentHighLatencyP95` sau 147–152 s (hai lần chạy).

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**
Lỗi chất lượng (v1 trả lời chung chung) không làm metric hạ tầng xấu đi: latency, error rate và số instance vẫn bình thường. Chỉ có eval trên golden dataset phát hiện được, và cần chạy trong CI trước khi deploy (quality gate). Trong production, còn có thể bổ sung: đo tỉ lệ câu trả lời được người dùng đánh giá tiêu cực, hoặc lấy mẫu định kỳ câu hỏi và chấm điểm tự động.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được (Jaeger, service `observable-agent`, sắp xếp Longest First):

- `trace_id`: `df8bd031f2944eb0fa486836da8a52eb`
- Tổng thời gian: 1718 ms (`POST /ask`)
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (1696 ms, ~99 % tổng thời gian). Phần `agent.retrieve_context` chỉ 19 ms, nên nút thắt là LLM chứ không phải code của agent.
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-26T19:34:09.016707+00:00", "level": "INFO", "service": "observable-agent", "instance": "2f41f1cafc0f", "event": "http_request", "trace_id": "df8bd031f2944eb0fa486836da8a52eb", "span_id": "f549cd7a29f4a614", "request_id": "9a7875dc6818", "method": "POST", "route": "/ask", "status": 200, "ms": 1717.6}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 64.19 | 190 | 250 | 1700 | 71 (0.93 %) |
| 3 | 65.60 | 190 | 220 | 1700 | 91 (1.17 %) |

**Giải thích kết quả:** Tăng từ 1 lên 3 instance gần như không cải thiện throughput (64 → 66 req/s). p95 giảm nhẹ (250 → 220 ms), p99.9 giảm (2900 → 1700 ms), nhưng sự khác biệt này nhỏ và có thể do dao động tự nhiên. Failure rate khác nhau trong khoảng nhiễu (~1 %, do mock LLM). Vì nhân bản agent không tăng RPS, nút thắt nằm ở phía client hoặc ở LLM, không nằm ở số lượng agent. Mình chưa xác minh chắc chắn: giả thuyết là Locust chạy một process đơn đã đạt giới hạn CPU, hoặc latency LLM mock cố định khiến mỗi request không nhanh hơn khi có thêm instance. Để kết luận chắc chắn cần đo CPU của Locust và của agent trong lúc chạy.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. **Average che giấu tail latency.** Ở tỉ lệ 3 % request chậm, avg chỉ tăng nhẹ nhưng p99 nhảy lên 1,7 giây. SLO phải đặt theo percentile.
  2. **Alert hạ tầng không phát hiện được lỗi chất lượng.** Thí nghiệm E cho thấy agent v1 chất lượng kém vẫn không làm alert nào firing. Eval trên golden dataset và quality gate trong CI là lớp bảo vệ riêng cần thiết.
  3. **Scale không tự động giải quyết nút thắt.** Nhân từ 1 lên 3 instance không tăng RPS trong bài này, nên cần đo đúng nơi nghẽn (CPU, LLM, client) trước khi scale.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  - Chi phí theo người dùng hoặc theo ngày, và alert khi vượt budget ngày (`DAILY_BUDGET_USD`), để không bị bất ngờ như cảnh báo cost trong thí nghiệm C.
  - Alert cho lỗi ở tầng load balancer (502/504 của Nginx), vì agent không đếm được các lỗi này khi instance bị pause.
  - Metric chất lượng: tỉ lệ câu trả lời bị người dùng đánh giá tiêu cực, và kết quả eval định kỳ trên traffic thật.
  - Synthetic check từ bên ngoài (gọi `/ask` định kỳ từ nhiều vùng), để phát hiện sự cố mà metric nội bộ không thấy.
