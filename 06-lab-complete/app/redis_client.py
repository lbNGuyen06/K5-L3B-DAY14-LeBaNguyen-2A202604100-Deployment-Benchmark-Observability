"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

Yêu cầu:
  • Đọc REDIS_URL từ config
  • App vẫn phải KHỞI ĐỘNG ĐƯỢC khi Redis chưa sẵn sàng (đừng ping Redis lúc import)
  • redis_healthy() dùng cho GET /ready: Redis không kết nối được → False
"""

"""
Kết nối Redis dùng chung cho rate limiter và cost guard.
"""
import redis
from app.config import settings

# Khởi tạo client kết nối Redis từ config (kết nối lười/lazy connection, không crash lúc import)
r = redis.from_url(settings.redis_url, decode_responses=True)


def redis_healthy() -> bool:
    """Kiểm tra Redis còn sống không. Dùng cho endpoint /ready."""
    try:
        return bool(r.ping())
    except Exception:
        return False
