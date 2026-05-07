"""Cloudflare R2 (S3-compatible) helpers for staging large videos before upload-post fetches by URL."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from upload_progress import make_boto3_upload_callback

R2_BUCKET = os.environ.get("R2_BUCKET", "podcast-staging")
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL", "")


def _r2_botocore_config():
    """Retries and long reads for large multipart uploads on flaky networks."""
    from botocore.config import Config

    attempts = int(os.environ.get("R2_MAX_RETRY_ATTEMPTS", "12"))
    read_timeout = int(os.environ.get("R2_READ_TIMEOUT_S", "3600"))
    return Config(
        retries={"max_attempts": max(3, attempts), "mode": "standard"},
        connect_timeout=60,
        read_timeout=max(60, read_timeout),
    )


def _r2_transfer_config():
    """
    Multipart tuning for bad uplinks: fewer parallel parts, optional larger chunks.

    R2_MULTIPART_MAX_CONCURRENCY (default 2): lower to 1 if uploads still drop.
    R2_MULTIPART_CHUNKSIZE_MB (default 32): min 8; fewer/larger parts vs many small.
    """
    from boto3.s3.transfer import TransferConfig

    concurrent = int(os.environ.get("R2_MULTIPART_MAX_CONCURRENCY", "2"))
    chunk_mb = int(os.environ.get("R2_MULTIPART_CHUNKSIZE_MB", "32"))
    chunk = max(8, chunk_mb) * 1024 * 1024
    return TransferConfig(
        multipart_threshold=8 * 1024 * 1024,
        multipart_chunksize=chunk,
        max_concurrency=max(1, concurrent),
        use_threads=True,
    )


def _r2_s3_client():
    """Return boto3 S3 client for R2, or None if credentials missing."""
    import boto3

    account_id = os.environ.get("R2_ACCOUNT_ID", "")
    access_key = os.environ.get("R2_ACCESS_KEY_ID", "")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY", "")
    if not all([account_id, access_key, secret_key]):
        return None
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=_r2_botocore_config(),
    )


def r2_public_uploads_configured() -> bool:
    """True when R2 credentials and public base URL are available."""
    return bool(R2_PUBLIC_URL and _r2_s3_client())


def _video_content_type_from_suffix(suffix: str) -> str:
    return {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
    }.get(suffix.lower(), "application/octet-stream")


def _video_content_type(path: str) -> str:
    return _video_content_type_from_suffix(Path(path).suffix.lower())


def _format_r2_staging_error(exc: BaseException) -> str:
    """Log-friendly detail for R2 multipart / boto failures."""
    try:
        import botocore.exceptions

        if isinstance(exc, botocore.exceptions.ClientError):
            err = exc.response.get("Error", {})
            meta = exc.response.get("ResponseMetadata", {})
            rid = meta.get("RequestId")
            parts = [
                f"ClientError {err.get('Code', '?')}: {err.get('Message', str(exc))}",
            ]
            if rid:
                parts.append(f"RequestId={rid}")
            return " | ".join(parts)
    except ImportError:
        pass
    lines = [f"{type(exc).__name__}: {exc}"]
    c = exc.__cause__
    if c is not None:
        lines.append(f"  caused by: {type(c).__name__}: {c}")
    return "\n".join(lines)


def upload_staging_video_to_r2(local_video_path: str, ep_num: int, verbose=False):
    """
    Upload a local video to a temporary R2 key for upload-post to fetch by URL.
    Returns (public_url, r2_key) or None on failure.

    ``verbose`` is accepted for API symmetry with call sites; extra logging is not implemented yet.
    """
    s3 = _r2_s3_client()
    if not s3 or not R2_PUBLIC_URL:
        return None

    ext = Path(local_video_path).suffix.lower() or ".mp4"
    r2_key = f"podcast/youtube-staging/{ep_num:03d}-{uuid.uuid4().hex[:12]}{ext}"
    public_url = f"{R2_PUBLIC_URL.rstrip('/')}/{r2_key}"
    vid_size = os.path.getsize(local_video_path)
    file_size_mb = vid_size / (1024 * 1024)

    print(f"Staging video on R2 for upload-post ({file_size_mb:.0f} MB): {r2_key}...")
    try:
        cb = make_boto3_upload_callback(vid_size, "R2 YouTube staging")
        upload_kw: dict = {
            "ExtraArgs": {"ContentType": _video_content_type_from_suffix(ext)},
            "Config": _r2_transfer_config(),
        }
        if cb is not None:
            upload_kw["Callback"] = cb
        s3.upload_file(local_video_path, R2_BUCKET, r2_key, **upload_kw)
    except Exception as e:
        print("⚠ R2 staging upload failed:")
        for line in _format_r2_staging_error(e).splitlines():
            print(f"  {line}")
        return None

    print(f"✓ Staged at {public_url}")
    return (public_url, r2_key)


def delete_r2_object(r2_key: str, verbose=False):
    """Remove an object from R2 (e.g. staging file after YouTube ingest). ``verbose`` is reserved."""
    s3 = _r2_s3_client()
    if not s3:
        print(f"⚠ Cannot delete R2 object (no client): {r2_key}")
        return False
    try:
        s3.delete_object(Bucket=R2_BUCKET, Key=r2_key)
        print(f"✓ Deleted staging object from R2: {r2_key}")
        return True
    except Exception as e:
        print(f"⚠ Could not delete R2 object {r2_key}: {e}")
        return False


def wants_r2_staging_for_local_video(local_path: str, args) -> bool:
    """
    Policy: this local file should use R2 staging (before checking R2 env).
    True when size >= YOUTUBE_VIDEO_R2_THRESHOLD_MB (default 400) or --youtube-via-r2.
    """
    if not os.path.isfile(local_path):
        return False
    if getattr(args, "youtube_no_r2_staging", False):
        return False
    if getattr(args, "youtube_via_r2", False):
        return True
    threshold_mb = int(os.environ.get("YOUTUBE_VIDEO_R2_THRESHOLD_MB", "400"))
    size_mb = os.path.getsize(local_path) / (1024 * 1024)
    return size_mb >= threshold_mb


def _read_r2_youtube_staging_marker(marker_path: str) -> tuple[str | None, str | None, int | None]:
    """Parse url=, key=, episode= from a staging marker file."""
    if not os.path.isfile(marker_path):
        return None, None, None
    try:
        text = Path(marker_path).read_text(encoding="utf-8")
    except OSError:
        return None, None, None
    url, key, ep = None, None, None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("url="):
            url = line[4:].strip()
        elif line.startswith("key="):
            key = line[4:].strip()
        elif line.startswith("episode="):
            try:
                ep = int(line[8:].strip())
            except ValueError:
                ep = None
    return url, key, ep


def load_r2_youtube_staging_marker(marker_path: str, expected_ep: int) -> tuple[str, str] | None:
    """
    Return (public_url, r2_key) if marker exists and matches expected_ep.
    Public HTTPS URL is used for upload-post; key is for cleanup after YouTube succeeds.
    """
    url, key, ep = _read_r2_youtube_staging_marker(marker_path)
    if (
        url
        and key
        and ep == expected_ep
        and url.lower().startswith("https://")
    ):
        return (url, key)
    return None


def save_r2_youtube_staging_marker(
    marker_path: str, public_url: str, r2_key: str, ep_num: int
) -> None:
    """Persist staged MP4 location so a failed YouTube step can retry without re-uploading to R2."""
    with open(marker_path, "w", encoding="utf-8") as f:
        f.write(f"url={public_url}\nkey={r2_key}\nepisode={ep_num}\n")


def remove_r2_youtube_staging_marker(marker_path: str) -> None:
    """Delete the R2 staging object and remove the marker (after successful YouTube or manual embed)."""
    if not os.path.isfile(marker_path):
        return
    _url, key, _ep = _read_r2_youtube_staging_marker(marker_path)
    if key:
        delete_r2_object(key)
    try:
        os.remove(marker_path)
    except OSError:
        pass
