"""Caller identity. The Next route handlers authenticate the user, then call this service with a
shared internal key and the user id; the service is never exposed to the browser."""

from __future__ import annotations

import os
import secrets
import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException


def current_user(
    x_a9_internal_key: Annotated[str | None, Header()] = None,
    x_a9_user_id: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    expected = os.environ.get("A9_INTERNAL_KEY")
    if not expected:
        raise HTTPException(503, "A9_INTERNAL_KEY is not configured")
    if x_a9_internal_key is None or not secrets.compare_digest(x_a9_internal_key, expected):
        raise HTTPException(401, "bad internal key")
    try:
        return uuid.UUID(x_a9_user_id or "")
    except ValueError:
        raise HTTPException(401, "missing or invalid user id") from None


User = Annotated[uuid.UUID, Depends(current_user)]
