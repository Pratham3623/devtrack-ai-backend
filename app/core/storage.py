"""
Dual-backend storage abstraction for DevTrack AI — Phase 11.
Local disk backend (default, USE_S3=False) and S3 backend (USE_S3=True).
"""
from __future__ import annotations

import abc
import hashlib
import hmac
import os
import time
import uuid
from pathlib import Path
from typing import Optional, Tuple

from app.core.config import settings


# ─── Abstract base ────────────────────────────────────────────────────────────

class StorageBackend(abc.ABC):
    """Abstract storage backend."""

    @abc.abstractmethod
    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str,
        *,
        encrypt: bool = True,
    ) -> str:
        """Upload bytes and return the storage key."""

    @abc.abstractmethod
    async def download(self, key: str) -> bytes:
        """Download raw bytes for a storage key."""

    @abc.abstractmethod
    async def delete(self, key: str) -> None:
        """Permanently delete an object."""

    @abc.abstractmethod
    async def get_signed_url(self, key: str, expiry: int = 3600) -> str:
        """Return a temporary signed URL for downloading."""

    @property
    @abc.abstractmethod
    def backend_name(self) -> str:
        """Identifier string for the backend, stored in DB."""


# ─── Local disk backend ───────────────────────────────────────────────────────

class LocalStorageBackend(StorageBackend):
    """
    Writes files to LOCAL_UPLOAD_DIR on disk.
    Signed URLs are HMAC-signed tokens resolved via /api/v1/files/serve/{token}.
    """

    def __init__(self) -> None:
        self.upload_dir = Path(settings.LOCAL_UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    @property
    def backend_name(self) -> str:
        return "local"

    async def upload(self, key: str, data: bytes, content_type: str, *, encrypt: bool = True) -> str:
        dest = self.upload_dir / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return key

    async def download(self, key: str) -> bytes:
        dest = self.upload_dir / key
        if not dest.exists():
            raise FileNotFoundError(f"Storage key not found: {key}")
        return dest.read_bytes()

    async def delete(self, key: str) -> None:
        dest = self.upload_dir / key
        if dest.exists():
            dest.unlink()

    async def get_signed_url(self, key: str, expiry: int = 3600) -> str:
        """Generate HMAC-signed serve token. Resolved by /files/serve/{token}."""
        expires_at = int(time.time()) + expiry
        payload = f"{key}:{expires_at}"
        sig = hmac.new(
            settings.FILE_SIGNED_URL_SECRET.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        token = f"{payload}:{sig}"
        # Base64url-encode so it's URL-safe
        import base64
        encoded = base64.urlsafe_b64encode(token.encode()).decode()
        return f"/api/v1/files/serve/{encoded}"

    @staticmethod
    def verify_token(encoded_token: str) -> Optional[str]:
        """Verify token and return storage key, or None if invalid/expired."""
        import base64
        try:
            decoded = base64.urlsafe_b64decode(encoded_token.encode()).decode()
            parts = decoded.rsplit(":", 2)
            if len(parts) != 3:
                return None
            key, expires_at_str, sig = parts
            payload = f"{key}:{expires_at_str}"
            expected_sig = hmac.new(
                settings.FILE_SIGNED_URL_SECRET.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                return None
            if int(time.time()) > int(expires_at_str):
                return None
            return key
        except Exception:
            return None


# ─── S3 backend ───────────────────────────────────────────────────────────────

class S3StorageBackend(StorageBackend):
    """
    Stores files in AWS S3 with server-side AES-256 encryption.
    Requires: aioboto3, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET.
    """

    def __init__(self) -> None:
        try:
            import aioboto3  # type: ignore
            self._aioboto3 = aioboto3
        except ImportError as e:
            raise RuntimeError(
                "aioboto3 is required for S3 storage. Install it with: pip install aioboto3"
            ) from e

        self.bucket = settings.S3_BUCKET
        self.region = settings.S3_REGION
        self._session_kwargs = {
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID or None,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY or None,
            "region_name": self.region,
        }

    @property
    def backend_name(self) -> str:
        return "s3"

    def _session(self):
        return self._aioboto3.Session()

    async def upload(self, key: str, data: bytes, content_type: str, *, encrypt: bool = True) -> str:
        extra_args: dict = {"ContentType": content_type}
        if encrypt:
            extra_args["ServerSideEncryption"] = "AES256"
        async with self._session().client("s3", **self._session_kwargs) as s3:
            import io
            await s3.upload_fileobj(io.BytesIO(data), self.bucket, key, ExtraArgs=extra_args)
        return key

    async def download(self, key: str) -> bytes:
        import io
        buf = io.BytesIO()
        async with self._session().client("s3", **self._session_kwargs) as s3:
            await s3.download_fileobj(self.bucket, key, buf)
        return buf.getvalue()

    async def delete(self, key: str) -> None:
        async with self._session().client("s3", **self._session_kwargs) as s3:
            await s3.delete_object(Bucket=self.bucket, Key=key)

    async def get_signed_url(self, key: str, expiry: int = 3600) -> str:
        async with self._session().client("s3", **self._session_kwargs) as s3:
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expiry,
            )
        return url


# ─── Factory ──────────────────────────────────────────────────────────────────

_storage_instance: Optional[StorageBackend] = None


def get_storage() -> StorageBackend:
    """Return singleton storage backend based on USE_S3 config flag."""
    global _storage_instance
    if _storage_instance is None:
        if settings.USE_S3:
            _storage_instance = S3StorageBackend()
        else:
            _storage_instance = LocalStorageBackend()
    return _storage_instance


def make_storage_key(org_id: str, filename: str, *, prefix: str = "files") -> str:
    """Generate a unique namespaced storage key."""
    unique = str(uuid.uuid4()).replace("-", "")
    safe_name = filename.replace(" ", "_").replace("/", "_")
    return f"{prefix}/{org_id}/{unique[:8]}_{safe_name}"
