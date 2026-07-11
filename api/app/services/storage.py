"""Object storage adapter (plan P4-BE-02).

One interface, two backends: Cloudflare R2 (S3-compatible, via boto3) when
configured, else a local-disk fallback so attachments work in dev without any
credentials. Photos are downscaled on upload to keep objects small.
"""

import io
import logging
import uuid
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("trackbit.storage")

_MAX_DIM = 1600  # px; downscale the long edge on upload


def make_key(*, org_id: uuid.UUID, instance_id: uuid.UUID, filename: str) -> str:
    ext = Path(filename or "").suffix.lower() or ".bin"
    return f"{org_id}/{instance_id}/{uuid.uuid4().hex}{ext}"


def maybe_downscale(data: bytes, content_type: str) -> bytes:
    """Best-effort image shrink. No-op if Pillow is absent or it isn't an image."""
    if not content_type.startswith("image/"):
        return data
    try:
        from PIL import Image  # noqa: PLC0415
    except ImportError:
        return data
    try:
        img = Image.open(io.BytesIO(data))
        img.thumbnail((_MAX_DIM, _MAX_DIM))
        out = io.BytesIO()
        fmt = (img.format or "JPEG")
        if fmt.upper() in ("JPG", "JPEG"):
            img = img.convert("RGB")
        img.save(out, format=fmt)
        return out.getvalue()
    except Exception:  # noqa: BLE001 — never block an upload on resize
        logger.exception("downscale failed; storing original")
        return data


def save_bytes(key: str, data: bytes, content_type: str) -> str:
    """Persist bytes and return a fetchable URL."""
    if settings.storage_configured:
        return _r2_put(key, data, content_type)
    return _local_put(key, data)


def _local_put(key: str, data: bytes) -> str:
    path = Path(settings.MEDIA_DIR) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return f"{settings.MEDIA_BASE_URL.rstrip('/')}/{key}"


def _r2_client():
    try:
        import boto3  # noqa: PLC0415
    except ImportError as exc:  # configured but SDK missing
        raise RuntimeError("boto3 is required for R2 storage. `uv add boto3`.") from exc
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def _r2_put(key: str, data: bytes, content_type: str) -> str:
    client = _r2_client()
    client.put_object(Bucket=settings.R2_BUCKET, Key=key, Body=data, ContentType=content_type)
    base = settings.R2_PUBLIC_BASE_URL.rstrip("/")
    if base:
        return f"{base}/{key}"
    # No public base configured -> hand back a time-limited presigned GET.
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": settings.R2_BUCKET, "Key": key}, ExpiresIn=3600
    )


# ── key-based API (HS-1) ─────────────────────────────────────────────────────
# session_media stores object *keys*; URLs are minted per read because presigned
# GETs expire. All helpers fall back to local disk when R2 is unconfigured, so
# the flows stay testable offline (same pattern as the AI client).

def url_for(key: str, expires: int = 3600) -> str:
    """Fetchable URL for a stored object key (presigned GET on a private bucket)."""
    if not settings.storage_configured:
        return f"{settings.MEDIA_BASE_URL.rstrip('/')}/{key}"
    base = settings.R2_PUBLIC_BASE_URL.rstrip("/")
    if base:
        return f"{base}/{key}"
    return _r2_client().generate_presigned_url(
        "get_object", Params={"Bucket": settings.R2_BUCKET, "Key": key}, ExpiresIn=expires
    )


def presign_put(key: str, content_type: str, expires: int = 900) -> str | None:
    """Direct-to-R2 upload URL, or None when R2 isn't configured — the caller
    then uses the pass-through upload endpoint (dev/local fallback)."""
    if not settings.storage_configured:
        return None
    return _r2_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.R2_BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=expires,
    )


def object_stat(key: str) -> tuple[int, str] | None:
    """(size_bytes, content_type) of a stored object, or None if it doesn't exist.
    Used by media *confirm* to verify a presigned upload actually landed."""
    if not settings.storage_configured:
        path = Path(settings.MEDIA_DIR) / key
        if not path.is_file():
            return None
        import mimetypes  # noqa: PLC0415
        return path.stat().st_size, mimetypes.guess_type(key)[0] or "application/octet-stream"
    try:
        head = _r2_client().head_object(Bucket=settings.R2_BUCKET, Key=key)
        return head["ContentLength"], head.get("ContentType") or "application/octet-stream"
    except Exception:  # noqa: BLE001 — missing key or transient error: not confirmable
        return None


def delete_object(key: str) -> None:
    """Best-effort delete; an orphaned object is preferable to a failed request."""
    try:
        if settings.storage_configured:
            _r2_client().delete_object(Bucket=settings.R2_BUCKET, Key=key)
        else:
            (Path(settings.MEDIA_DIR) / key).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        logger.exception("delete_object failed for %s", key)
