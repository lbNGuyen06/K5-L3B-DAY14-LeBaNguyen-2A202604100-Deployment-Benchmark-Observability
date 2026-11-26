"""
Cost guard (tiêu chí 8).
"""
import time
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _get_budget_key() -> str:
    today = time.strftime("%Y-%m-%d")
    return f"budget:daily:{today}"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    key = _get_budget_key()
    try:
        current_spent = float(r.get(key) or 0.0)
    except Exception:
        current_spent = 0.0

    if current_spent >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail=f"Budget exceeded. Limit: ${settings.daily_budget_usd}, spent: ${current_spent:.6f}",
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng trong Redis."""
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    key = _get_budget_key()
    try:
        r.incrbyfloat(key, cost)
        r.expire(key, 86400 * 2)  # Giữ trong 2 ngày rồi tự hủy
    except Exception:
        pass
    return cost
