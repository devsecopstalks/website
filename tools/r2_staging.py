"""Cloudflare R2 (S3-compatible) helpers: video staging for upload-post, and episode covers."""

from __future__ import annotations

import hashlib
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


# Covers live in their own bucket: the staging bucket expires every object.
# Keys carry a digest of the PNG, so an object never changes and may be cached
# for good; a redraw is a new key, never an overwrite.
R2_COVERS_BUCKET = os.environ.get("R2_COVERS_BUCKET", "")
R2_COVERS_PUBLIC_URL = os.environ.get("R2_COVERS_PUBLIC_URL", "")
COVERS_PREFIX = "covers/"
IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"


class R2CoverError(RuntimeError):
    """The cover cannot be put on R2 safely; nothing should be published."""


def r2_public_url(r2_key: str) -> str:
    """A cover key's public URL."""
    if not R2_COVERS_PUBLIC_URL:
        raise R2CoverError("R2_COVERS_PUBLIC_URL is not set, so the cover has no public URL")
    return f"{R2_COVERS_PUBLIC_URL.rstrip('/')}/{r2_key}"


def cover_r2_key(ep_num: int, png_bytes: bytes) -> str:
    digest = hashlib.sha256(png_bytes).hexdigest()[:12]
    return f"{COVERS_PREFIX}{int(ep_num):03d}-{digest}.png"


def cover_public_url(png_path: str, ep_num: int) -> str:
    """The URL the cover will have once uploaded; known before the upload runs."""
    with open(png_path, "rb") as f:
        return r2_public_url(cover_r2_key(ep_num, f.read()))


def require_cover_client():
    """The R2 client for covers; raises R2CoverError naming what is not configured."""
    missing = [name for name, value in (("R2_COVERS_BUCKET", R2_COVERS_BUCKET),
                                        ("R2_COVERS_PUBLIC_URL", R2_COVERS_PUBLIC_URL)) if not value]
    s3 = _r2_s3_client()
    if s3 is None:
        missing.insert(0, "R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY")
    if missing:
        raise R2CoverError(f"R2 is not configured for covers: set {', '.join(missing)}")
    return s3


def _rule_prefixes(rule: dict) -> list[str]:
    """Key prefixes a lifecycle rule applies to; [""] when it has none (whole bucket)."""
    if "Prefix" in rule:  # legacy top-level form
        return [rule.get("Prefix") or ""]
    flt = rule.get("Filter") or {}
    if "And" in flt:
        flt = flt["And"] or {}
    return [flt.get("Prefix") or ""]


def expiring_cover_rules(lifecycle_rules: list[dict], prefix: str = COVERS_PREFIX) -> list[str]:
    """IDs of enabled expiring rules whose prefix is empty, a parent of ``prefix`` or inside it.

    Tag filters are ignored on purpose: stopping is cheaper than a page whose cover vanishes.
    """
    hits = []
    for rule in lifecycle_rules:
        if rule.get("Status", "Enabled") != "Enabled" or "Expiration" not in rule:
            continue
        if any(prefix.startswith(p) or p.startswith(prefix) for p in _rule_prefixes(rule)):
            hits.append(rule.get("ID") or "<unnamed>")
    return hits


def check_cover_lifecycle(s3=None) -> None:
    """Raise R2CoverError when a bucket lifecycle rule could expire ``covers/``."""
    import botocore.exceptions

    s3 = s3 or require_cover_client()
    try:
        rules = s3.get_bucket_lifecycle_configuration(Bucket=R2_COVERS_BUCKET).get("Rules", [])
    except botocore.exceptions.ClientError as e:
        if e.response.get("Error", {}).get("Code") == "NoSuchLifecycleConfiguration":
            return
        raise R2CoverError(
            f"Could not read the lifecycle rules of {R2_COVERS_BUCKET}: {_format_r2_staging_error(e)}"
        ) from e
    hits = expiring_cover_rules(rules)
    if hits:
        raise R2CoverError(
            f"Lifecycle rule(s) {', '.join(hits)} on bucket {R2_COVERS_BUCKET} could expire "
            f"{COVERS_PREFIX}, and published pages would lose their cover. Narrow the rule first."
        )


def r2_object_exists(s3, r2_key: str) -> bool:
    import botocore.exceptions

    try:
        s3.head_object(Bucket=R2_COVERS_BUCKET, Key=r2_key)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def upload_cover_to_r2(png_path: str, ep_num: int, s3=None) -> str:
    """Upload the cover under its content-addressed key unless it is there; return its URL."""
    s3 = s3 or require_cover_client()
    with open(png_path, "rb") as f:
        key = cover_r2_key(ep_num, f.read())
    url = r2_public_url(key)
    try:
        if r2_object_exists(s3, key):
            print(f"✓ Cover already on R2: {url}")
            return url
        s3.upload_file(
            png_path, R2_COVERS_BUCKET, key,
            ExtraArgs={"ContentType": "image/png", "CacheControl": IMMUTABLE_CACHE_CONTROL},
        )
    except Exception as e:
        raise R2CoverError(f"Cover upload failed: {_format_r2_staging_error(e)}") from e
    print(f"✓ Uploaded cover: {url}")
    return url
