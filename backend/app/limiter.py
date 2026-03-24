import os
from slowapi import Limiter
from slowapi.util import get_remote_address

RATE_LIMIT_LOGIN = os.getenv("RATE_LIMIT_LOGIN", "5/minute")
RATE_LIMIT_PUBLIC = os.getenv("RATE_LIMIT_PUBLIC", "30/minute")  # used by public endpoints (not yet applied)


def _get_real_ip(request) -> str:
    """Lê X-Real-IP (nginx) ou X-Forwarded-For, com fallback para TCP peer."""
    return (
        request.headers.get("X-Real-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or get_remote_address(request)
    )


limiter = Limiter(key_func=_get_real_ip)
