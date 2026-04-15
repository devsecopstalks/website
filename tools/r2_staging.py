"""Cloudflare R2 (S3-compatible) helpers for staging large videos before upload-post fetches by URL."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

R2_BUCKET = os.environ.get("R2_BUCKET", "podcast-staging")
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL", "")


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
    )


def r2_public_uploads_configured() -> bool:
    """True when R2 credentials and public base URL are available."""
    return bool(R2_PUBLIC_URL and _r2_s3_client())


def _video_content_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
    }.get(ext, "application/octet-stream")


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
    file_size_mb = os.path.getsize(local_video_path) / (1024 * 1024)

    print(f"Staging video on R2 for upload-post ({file_size_mb:.0f} MB): {r2_key}...")
    try:
        s3.upload_file(
            local_video_path,
            R2_BUCKET,
            r2_key,
            ExtraArgs={"ContentType": _video_content_type(local_video_path)},
        )
    except Exception as e:
        print(f"⚠ R2 staging upload failed: {e}")
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


def use_r2_staging_for_local_video(local_path: str, args) -> bool:
    """
    Whether to put the local MP4 on R2 first and give upload-post an HTTPS URL.
    Auto when file size >= YOUTUBE_VIDEO_R2_THRESHOLD_MB (default 400), or if
    --youtube-via-r2 is set.
    """
    if not os.path.isfile(local_path):
        return False
    if getattr(args, "youtube_no_r2_staging", False):
        return False
    if not r2_public_uploads_configured():
        return False
    if getattr(args, "youtube_via_r2", False):
        return True
    threshold_mb = int(os.environ.get("YOUTUBE_VIDEO_R2_THRESHOLD_MB", "400"))
    size_mb = os.path.getsize(local_path) / (1024 * 1024)
    return size_mb >= threshold_mb
