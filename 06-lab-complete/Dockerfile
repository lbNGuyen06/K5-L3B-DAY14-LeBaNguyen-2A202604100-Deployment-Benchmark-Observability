# ============================================================
# STAGE 1: Builder (Biên dịch và cài đặt thư viện)
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Cài đặt gcc nếu có thư viện C cần biên dịch
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Copy và cài đặt dependencies vào thư mục người dùng (/root/.local)
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ============================================================
# STAGE 2: Runtime (Image chính thức xuất xưởng < 500 MB)
# ============================================================
FROM python:3.11-slim AS runtime

# Tạo user non-root để đảm bảo an ninh
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy các thư viện đã cài từ Stage 1 sang Stage 2
COPY --from=builder /root/.local /home/appuser/.local

# Copy toàn bộ mã nguồn của dự án
COPY . .

# Phân quyền thư mục cho appuser và chuyển user
RUN chown -R appuser:appuser /app
USER appuser

# Thiết lập biến môi trường PATH để Python tìm thấy thư viện
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PORT=8000

# Khai báo cổng
EXPOSE 8000

# Health check định kỳ gọi endpoint /health
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, os; port = os.getenv('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/health')" || exit 1

# Khởi chạy uvicorn với exec để uvicorn là PID 1, lắng nghe theo biến PORT
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
