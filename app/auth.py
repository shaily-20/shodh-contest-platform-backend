import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Account, Identity

ALGORITHM = "HS256"
TOKEN_LIFETIME_SECONDS = 60 * 60 * 12
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256" or int(rounds) != 600_000:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(identity_id: int, role: str) -> str:
    return jwt.encode(
        {"sub": str(identity_id), "role": role, "exp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).timestamp() + TOKEN_LIFETIME_SECONDS},
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


async def current_account(token: str = Depends(oauth2_scheme)) -> tuple[Identity, Account]:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        identity_id = int(claims["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise unauthorized
    async with SessionLocal() as session:
        result = await session.execute(
            select(Identity, Account).join(Account, Account.identity_id == Identity.id)
            .where(Identity.id == identity_id)
        )
        row = result.first()
        if row is None:
            raise unauthorized
        identity, account = row
        return identity, account


async def organizer_account(account_pair=Depends(current_account)) -> tuple[Identity, Account]:
    identity, account = account_pair
    if account.role != "organizer":
        raise HTTPException(status_code=403, detail="Organizer access required")
    return identity, account
