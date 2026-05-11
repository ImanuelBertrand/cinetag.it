"""Helpers for rotating HMAC signing keys without invalidating live tokens.

A token is signed with the primary key and stamped with a `kid` header that
matches the current key id. On decode, tokens whose `kid` matches the current
id are verified with the primary key; everything else (including tokens with
no `kid` predating this code) is verified with the fallback key, if one is
configured. After one refresh-token lifetime the fallback can be dropped.
"""

from typing import Any

import jwt
from flask import current_app


def encode_with_kid(
    payload: dict[str, Any],
    key_config: str,
    kid_config: str,
    algorithm: str = "HS256",
) -> str:
    """Sign `payload` with the primary key and stamp the current kid header."""
    key = current_app.config[key_config]
    kid = current_app.config.get(kid_config, "primary")
    return jwt.encode(payload, key, algorithm=algorithm, headers={"kid": kid})


def decode_with_fallback(
    token: str,
    key_config: str,
    fallback_key_config: str,
    kid_config: str,
    algorithms: list[str] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Decode `token`, trying the fallback key for tokens not signed under the
    current kid. Raises the standard PyJWT exceptions on failure."""
    algorithms = algorithms or ["HS256"]
    primary_key = current_app.config[key_config]
    fallback_key = current_app.config.get(fallback_key_config)
    current_kid = current_app.config.get(kid_config, "primary")

    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        return jwt.decode(token, primary_key, algorithms=algorithms, **kwargs)

    if header.get("kid") == current_kid or not fallback_key:
        return jwt.decode(token, primary_key, algorithms=algorithms, **kwargs)
    return jwt.decode(token, fallback_key, algorithms=algorithms, **kwargs)
