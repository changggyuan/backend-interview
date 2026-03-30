from __future__ import annotations

import secrets

from passlib.context import CryptContext  # type: ignore[import-untyped]

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """將明文字串密碼轉為 bcrypt 雜湊值。"""

    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """比對輸入密碼與已儲存 bcrypt 雜湊值是否一致。"""

    return _pwd_context.verify(password, password_hash)


def create_token() -> str:
    """產生隨機 64 字元（32 bytes）十六進位 Token。"""

    return secrets.token_hex(32)
