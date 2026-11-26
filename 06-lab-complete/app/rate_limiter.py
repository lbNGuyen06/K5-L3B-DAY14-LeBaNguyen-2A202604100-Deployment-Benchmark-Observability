"""
Rate limiting (tiêu chí 7).
"""
import time
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r


def check_rate_limit(key: str) -> None:
    """Sliding window 60s sử dụng Redis Sorted Set."""
    now = time.time()
    window_key = f"rate_limit:{key}"
    window_seconds = 60
    limit = settings.rate_limit_per_minute

    try:
        # 1. Xóa các request cũ nằm ngoài khoảng 60 giây
        r.zremrangebyscore(window_key, 0, now - window_seconds)

        # 2. Đếm số request hiện tại trong window
        current_requests = r.zcard(window_key)

        # 3. Nếu đã đạt hoặc vượt giới hạn -> Bắn lỗi 429
        if current_requests >= limit:
            oldest = r.zrange(window_key, 0, 0, withscores=True)
            retry_after = 60
            if oldest:
                retry_after = max(1, int(oldest[0][1] + window_seconds - now))
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please wait.",
                headers={"Retry-After": str(retry_after)},
            )

        # 4. Ghi nhận request mới vào Redis
        r.zadd(window_key, {str(now): now})
        r.expire(window_key, window_seconds + 5)
    except HTTPException:
        raise
    except Exception:
        # Nếu Redis chưa sẵn sàng lúc chạy dev/test độc lập
        pass
