"""
Authentication helpers: password hashing, JWT issuing/verification,
the get_current_user dependency used to protect user routes, and
HMAC-SHA256 signature verification for ESP32 IoT telemetry ingestion.
"""

from datetime import datetime, timedelta
import hashlib
import hmac
import logging
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app import models

logger = logging.getLogger("auth")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

REPLAY_WINDOW_SECONDS = 300

# In-memory TTL cache for anti-replay deduplication
seen_signatures: set[str] = set()
_signature_timestamps: dict[str, float] = {}


def purge_expired_signatures(current_time: Optional[float] = None) -> None:
    """Purges signatures older than REPLAY_WINDOW_SECONDS to prevent unbounded memory growth."""
    now = current_time if current_time is not None else time.time()
    expired = [sig for sig, ts in _signature_timestamps.items() if now - ts > REPLAY_WINDOW_SECONDS]
    for sig in expired:
        _signature_timestamps.pop(sig, None)
        seen_signatures.discard(sig)


def reset_signature_cache() -> None:
    """Helper to clear replay cache for testing."""
    seen_signatures.clear()
    _signature_timestamps.clear()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_identifier = str(payload.get("sub"))
        if not user_identifier or user_identifier == "None":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    if user_identifier.isdigit():
        user = db.query(models.User).filter(models.User.id == int(user_identifier)).first()
    else:
        user = db.query(models.User).filter(models.User.email == user_identifier).first()

    if user is None or not user.is_active:
        raise credentials_exception
    return user


# ---------------- IoT ESP32 HMAC-SHA256 Telemetry Verification ----------------


def compute_hmac_sha256(secret: str, message: bytes) -> str:
    """Computes hexadecimal HMAC-SHA256 signature for given bytes."""
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_hmac_signature(
    secret: str,
    timestamp_str: str,
    raw_body: bytes,
    provided_signature: str,
) -> bool:
    """
    Verifies that the provided HMAC signature matches the calculated digest
    over timestamp + '.' + body (or timestamp + body).
    """
    if not secret or not provided_signature:
        return False

    clean_provided = provided_signature.strip().lower()

    # Pattern 1: timestamp + "." + raw_body
    msg1 = f"{timestamp_str}.".encode("utf-8") + raw_body
    sig1 = compute_hmac_sha256(secret, msg1).lower()
    if hmac.compare_digest(sig1, clean_provided):
        return True

    # Pattern 2: timestamp + raw_body (without dot)
    msg2 = timestamp_str.encode("utf-8") + raw_body
    sig2 = compute_hmac_sha256(secret, msg2).lower()
    if hmac.compare_digest(sig2, clean_provided):
        return True

    # Pattern 3: timestamp + "." + stripped raw_body
    msg3 = f"{timestamp_str}.".encode("utf-8") + raw_body.strip()
    sig3 = compute_hmac_sha256(secret, msg3).lower()
    if hmac.compare_digest(sig3, clean_provided):
        return True

    return False


async def verify_device_hmac(request: Request) -> bool:
    """
    FastAPI dependency for ESP32 telemetry endpoints.
    Enforces HMAC-SHA256 authentication with timestamp freshness (anti-replay window: +/- 300s).
    Also supports fallback device token authentication.
    """
    # 1. Check for legacy/token fallback header
    token_header = (
        request.headers.get("x-device-token")
        or request.headers.get("x-esp32-token")
    )
    secret_key = getattr(settings, "DEVICE_HMAC_SECRET", "esp32_super_secret_hmac_key_production_2026")

    if token_header:
        if hmac.compare_digest(token_header.strip(), secret_key.strip()):
            return True
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device token",
        )

    # 2. Extract signature and timestamp headers
    signature_header = (
        request.headers.get("x-esp32-signature")
        or request.headers.get("x-device-signature")
        or request.headers.get("x-signature-sha256")
    )
    timestamp_header = (
        request.headers.get("x-esp32-timestamp")
        or request.headers.get("x-device-timestamp")
        or request.headers.get("x-timestamp")
    )

    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device authentication failed: missing HMAC signature or device token",
            headers={"WWW-Authenticate": "HMAC-SHA256"},
        )

    if not timestamp_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device authentication failed: missing timestamp header",
        )

    # 3. Validate timestamp format and anti-replay window (+/- 300 seconds)
    try:
        ts_val = float(timestamp_header.strip())
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device authentication failed: invalid timestamp format",
        )

    current_epoch = time.time()
    time_diff = abs(current_epoch - ts_val)
    if time_diff > REPLAY_WINDOW_SECONDS:
        logger.warning(
            "Replay attack detected or clock desynchronized: timestamp %f differs by %.1fs (> %ds)",
            ts_val,
            time_diff,
            REPLAY_WINDOW_SECONDS,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Replay attack detected: timestamp delta ({int(time_diff)}s) exceeds window ({REPLAY_WINDOW_SECONDS}s)",
        )

    # 4. Extract raw body and verify cryptographic digest
    raw_body = await request.body()
    if not verify_hmac_signature(secret_key, timestamp_header.strip(), raw_body, signature_header):
        logger.warning("Invalid HMAC signature received from %s", request.client.host if request.client else "unknown")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device authentication failed: signature mismatch",
        )

    clean_sig = signature_header.strip().lower()
    purge_expired_signatures(current_epoch)

    # 5. Check if valid signature was already processed within active window (anti-replay)
    if clean_sig in seen_signatures:
        logger.warning(
            "Replay attack detected: signature %s already used within %ds window",
            clean_sig,
            REPLAY_WINDOW_SECONDS,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Replay attack detected: signature already used",
        )

    # Cache valid signature with current timestamp
    seen_signatures.add(clean_sig)
    _signature_timestamps[clean_sig] = current_epoch

    return True