from __future__ import annotations

import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from .config import settings


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: str | None = Security(api_key_header)) -> None:
    """配置 API_KEYS 后启用鉴权；未配置时保持本地开发兼容。"""
    if not settings.api_keys:
        return
    if not api_key:
        raise HTTPException(status_code=401, detail="缺少 X-API-Key")
    if not any(secrets.compare_digest(api_key, expected) for expected in settings.api_keys):
        raise HTTPException(status_code=403, detail="API Key 无效")
