"""Upload episode video to YouTube via upload-post.com (SiRob/DevSecOps Talks integration)."""

import os
import re
import time
from pathlib import Path
from typing import Any

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from upload_post import UploadPostClient, UploadPostError
from upload_progress import ProgressBinaryReader, progress_enabled

import requests

# Log enough of error responses to debug gateway issues without megabytes of HTML.
_UPLOAD_POST_ERROR_BODY_MAX = 4096


def _upload_post_retry() -> Retry:
    """
    urllib3-level retries for flaky networks (connection drops, gateway errors).

    POST is included so a failed connection during multipart can retry.
    Env: UPLOAD_POST_HTTP_MAX_RETRIES (default 8), UPLOAD_POST_HTTP_BACKOFF (1.5),
    UPLOAD_POST_HTTP_BACKOFF_MAX_S (120), UPLOAD_POST_HTTP_RETRY_STATUS (comma list).
    """
    total = int(os.environ.get("UPLOAD_POST_HTTP_MAX_RETRIES", "8"))
    total = max(3, total)
    backoff = float(os.environ.get("UPLOAD_POST_HTTP_BACKOFF", "1.5"))
    backoff_max = int(os.environ.get("UPLOAD_POST_HTTP_BACKOFF_MAX_S", "120"))
    raw = (os.environ.get("UPLOAD_POST_HTTP_RETRY_STATUS") or "429,502,503,504,499").strip()
    status_forcelist: tuple[int, ...] = tuple(
        int(x.strip()) for x in raw.split(",") if x.strip().isdigit()
    ) or (429, 502, 503, 504, 499)
    # POST must be allowed or urllib3 will not retry upload requests.
    return Retry(
        total=total,
        connect=total,
        read=total,
        status=total,
        backoff_factor=backoff,
        backoff_max=backoff_max,
        status_forcelist=status_forcelist,
        allowed_methods=frozenset(
            ("DELETE", "GET", "HEAD", "OPTIONS", "POST", "PUT", "TRACE")
        ),
        raise_on_status=False,
    )


def _format_requests_error(exc: requests.exceptions.RequestException) -> str:
    """Human-readable diagnostics for upload-post / HTTP failures."""
    lines: list[str] = [f"{type(exc).__name__}: {exc}"]
    resp = getattr(exc, "response", None)
    if resp is not None:
        reason = getattr(resp, "reason", None) or ""
        lines.append(f"  HTTP {resp.status_code} {reason}".rstrip())
        hdr_lower = {k.lower(): v for k, v in resp.headers.items()}
        for h in ("cf-ray", "x-request-id", "request-id", "server", "retry-after"):
            v = hdr_lower.get(h)
            if v:
                lines.append(f"  {h}: {v}")
        ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
        if ct:
            lines.append(f"  content-type: {ct}")
        try:
            body = (resp.text or "").strip()
        except Exception:
            body = ""
        if body:
            if len(body) > _UPLOAD_POST_ERROR_BODY_MAX:
                body = body[:_UPLOAD_POST_ERROR_BODY_MAX] + f"\n  … ({len(resp.text)} response chars total)"
            body_lines = body.splitlines()
            lines.append("  response body:")
            for bl in body_lines[:80]:
                lines.append(f"    {bl}")
            if len(body_lines) > 80:
                lines.append("    … (more lines omitted)")
    req = getattr(exc, "request", None)
    if req is not None and resp is None:
        url = req.url or ""
        if len(url) > 240:
            url = url[:240] + "…"
        lines.append(f"  request: {req.method} {url}")
    c = exc.__cause__
    if c is not None:
        lines.append(f"  caused by: {type(c).__name__}: {c}")
    return "\n".join(lines)


class LongTimeoutUploadPostClient(UploadPostClient):
    """
    upload-post's client uses requests without timeouts; large MP4s can also hit
    proxy idle limits. More importantly, the API gateway may return 504 before
    the body finishes — for very large files prefer an HTTPS URL (server fetch).

    Timeouts are overridable via UPLOAD_POST_CONNECT_TIMEOUT_S,
    UPLOAD_POST_READ_TIMEOUT_MULTIPART_S, UPLOAD_POST_READ_TIMEOUT_DEFAULT_S.
    """

    def __init__(self, api_key: str):
        super().__init__(api_key)
        connect = float(os.environ.get("UPLOAD_POST_CONNECT_TIMEOUT_S", "120"))
        read_mp = float(
            os.environ.get("UPLOAD_POST_READ_TIMEOUT_MULTIPART_S", str(4 * 60 * 60))
        )
        read_def = float(os.environ.get("UPLOAD_POST_READ_TIMEOUT_DEFAULT_S", "600"))
        self._TIMEOUT_MULTIPART = (connect, read_mp)
        self._TIMEOUT_DEFAULT = (connect, read_def)

    def upload_video(
        self,
        video_path: str | Path,
        title: str | None = None,
        user: str = "",
        platforms: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        """
        Same as upload_post.UploadPostClient.upload_video, but wrap local files with
        ProgressBinaryReader when UPLOAD_PROGRESS is enabled (see upload_progress.py).
        """
        data: list[tuple] = []
        files: list[tuple] = []
        video_file = None

        try:
            video_str = str(video_path)
            if video_str.lower().startswith(("http://", "https://")):
                return super().upload_video(
                    video_path, title=title, user=user, platforms=platforms, **kwargs
                )

            video_p = Path(video_path)
            if not video_p.exists():
                raise UploadPostError(f"Video file not found: {video_p}")
            total = video_p.stat().st_size
            raw = video_p.open("rb")
            if progress_enabled() and total > 0:
                video_file = ProgressBinaryReader(
                    raw, total, "upload-post (video body)"
                )
            else:
                video_file = raw
            files.append(("video", (video_p.name, video_file)))

            self._add_common_params(data, user, title, platforms, **kwargs)

            if platforms and "tiktok" in platforms:
                self._add_tiktok_params(data, is_video=True, **kwargs)
            if platforms and "instagram" in platforms:
                self._add_instagram_params(data, is_video=True, **kwargs)
            if platforms and "youtube" in platforms:
                self._add_youtube_params(data, **kwargs)
            if platforms and "linkedin" in platforms:
                self._add_linkedin_params(data, **kwargs)
            if platforms and "facebook" in platforms:
                self._add_facebook_params(data, is_video=True, **kwargs)
            if platforms and "pinterest" in platforms:
                self._add_pinterest_params(data, is_video=True, **kwargs)
            if platforms and "x" in platforms:
                self._add_x_params(data, is_text=False, **kwargs)
            if platforms and "threads" in platforms:
                self._add_threads_params(data, **kwargs)

            return self._request("/upload", "POST", data=data, files=files if files else None)

        finally:
            if video_file is not None:
                video_file.close()

    def _request(
        self,
        endpoint: str,
        method: str = "GET",
        data=None,
        files=None,
        json_data=None,
        params=None,
    ):
        url = f"{self.BASE_URL}{endpoint}"
        timeout = self._TIMEOUT_MULTIPART if method == "POST" and files else self._TIMEOUT_DEFAULT
        try:
            if method == "GET":
                response = self.session.get(url, params=params, timeout=timeout)
            elif method == "POST":
                if json_data:
                    response = self.session.post(url, json=json_data, timeout=timeout)
                else:
                    response = self.session.post(url, data=data, files=files, timeout=timeout)
            elif method == "DELETE":
                if json_data:
                    response = self.session.delete(url, json=json_data, timeout=timeout)
                else:
                    response = self.session.delete(url, timeout=timeout)
            else:
                raise UploadPostError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            detail = _format_requests_error(e)
            api_hint = ""
            if getattr(e, "response", None) is not None:
                try:
                    error_data = e.response.json()
                    api_hint = error_data.get("message") or error_data.get("detail") or ""
                    if api_hint is not None and not isinstance(api_hint, str):
                        api_hint = str(api_hint)
                except (ValueError, TypeError, AttributeError):
                    api_hint = ""
            if api_hint:
                raise UploadPostError(f"API request failed: {api_hint}\n{detail}") from e
            raise UploadPostError(f"API request failed:\n{detail}") from e


def status_to_youtube_embed_url(status: dict) -> str | None:
    """
    Extract a YouTube embed URL from upload-post completion status.
    Response shapes vary; try common paths and normalize to /embed/VIDEO_ID.
    """
    if not isinstance(status, dict):
        return None

    candidates: list[object] = []

    # upload-post API v2+: results is a list of per-platform dicts
    results = status.get("results")
    if isinstance(results, list):
        for item in results:
            if not isinstance(item, dict):
                continue
            if item.get("platform") != "youtube" and not item.get("post_url"):
                continue
            if item.get("platform_post_id"):
                candidates.append(item["platform_post_id"])
            if item.get("post_url"):
                candidates.append(item["post_url"])

    for path in (
        lambda r: r.get("results", {}).get("youtube", {}).get("post_id")
        if isinstance(r.get("results"), dict)
        else None,
        lambda r: r.get("platforms", {}).get("youtube", {}).get("post_id"),
        lambda r: r.get("results", {}).get("youtube", {}).get("url")
        if isinstance(r.get("results"), dict)
        else None,
        lambda r: r.get("platforms", {}).get("youtube", {}).get("url"),
        lambda r: r.get("youtube", {}).get("post_id") if isinstance(r.get("youtube"), dict) else None,
        lambda r: r.get("youtube", {}).get("url") if isinstance(r.get("youtube"), dict) else None,
    ):
        try:
            v = path(status)
        except (KeyError, TypeError, AttributeError):
            v = None
        if v:
            candidates.append(v)

    for raw in candidates:
        s = str(raw).strip()
        if not s:
            continue
        if "youtube.com/embed/" in s or "youtu.be/" in s or "watch?v=" in s:
            m = re.search(r"(?:embed/|youtu\.be/|v=)([a-zA-Z0-9_-]{11})", s)
            if m:
                return f"https://www.youtube.com/embed/{m.group(1)}"
        if re.fullmatch(r"[a-zA-Z0-9_-]{11}", s):
            return f"https://www.youtube.com/embed/{s}"
    return None


def youtube_status_error_message(status: dict) -> str | None:
    """
    If the upload-post job finished but YouTube did not publish, return the first
    platform error string (e.g. session expired). Used to decide R2 staging cleanup.
    """
    if not isinstance(status, dict):
        return None
    results = status.get("results")
    if not isinstance(results, list):
        return None
    for item in results:
        if not isinstance(item, dict):
            continue
        if item.get("platform") != "youtube":
            continue
        if item.get("success") is True:
            continue
        msg = item.get("error_message") or item.get("message")
        if msg:
            return str(msg).strip() or None
    return None


def youtube_embed_url_to_video_id(embed_url: str) -> str:
    """Return 11-char video id for Hugo shortcode, or empty string."""
    if not embed_url:
        return ""
    m = re.search(r"(?:embed/|youtu\.be/|v=)([a-zA-Z0-9_-]{11})", embed_url)
    return m.group(1) if m else ""


def _is_http_video_source(video_path: str) -> bool:
    s = str(video_path).strip().lower()
    return s.startswith("https://") or s.startswith("http://")


def upload_to_youtube(
    video_path,
    title,
    description,
    poll_interval=15,
    poll_timeout=600,
    max_retries=4,
):
    """
    Upload video to YouTube using async mode to avoid gateway timeouts.

    ``video_path`` may be a local path or an **https://** URL to the same video.
    The upload-post API accepts URLs and fetches server-side — use this for
    multi‑GB files when direct multipart upload returns 499/504.

    Returns:
        Final status response dict from upload-post when completed.
    """
    api_key = os.environ["UPLOAD_POST_API_KEY"]
    user = os.environ["UPLOAD_POST_USER"]

    client = LongTimeoutUploadPostClient(api_key=api_key)

    pool = int(os.environ.get("UPLOAD_POST_POOL_MAXSIZE", "4"))
    pools = int(os.environ.get("UPLOAD_POST_POOL_CONNECTIONS", "4"))
    adapter = HTTPAdapter(
        max_retries=_upload_post_retry(),
        pool_connections=max(1, pools),
        pool_maxsize=max(1, pool),
    )
    client.session.mount("https://", adapter)
    client.session.mount("http://", adapter)

    use_url = _is_http_video_source(str(video_path))
    if use_url:
        print(f"Using video URL (upload-post fetches server-side): {video_path[:80]}...")
    else:
        file_size_mb = Path(video_path).stat().st_size / (1024 * 1024)
        print(f"File size: {file_size_mb:.0f} MB")
        if file_size_mb > 500:
            print(
                "⚠ Large file: if upload fails with 499/504, put the MP4 on a public HTTPS URL "
                "(e.g. R2) and pass it via --youtube-video-url or UPLOAD_POST_VIDEO_URL, "
                "or re-encode smaller (see tools/README.md)."
            )

    response = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Submitting async upload (attempt {attempt}/{max_retries})...")
            response = client.upload_video(
                video_path=video_path,
                title=title,
                description=description,
                user=user,
                platforms=["youtube"],
                privacyStatus="public",
                selfDeclaredMadeForKids=False,
                async_upload=True,
            )
            print("Upload submitted:", response)
            break
        except Exception as e:
            print(f"Upload attempt {attempt} failed:")
            for line in str(e).splitlines():
                print(f"  {line}")
            if attempt == max_retries:
                raise
            wait = 2**attempt * 5
            print(f"Retrying in {wait}s...")
            time.sleep(wait)

    request_id = response.get("request_id")
    if not request_id:
        return response

    # Scale poll budget for large jobs (YouTube processing after upload)
    effective_poll = poll_timeout
    if not use_url:
        file_size_mb = Path(video_path).stat().st_size / (1024 * 1024)
        effective_poll = max(poll_timeout, 600 + int(file_size_mb / 100) * 120)

    print(f"Polling for completion (request_id: {request_id}, timeout {effective_poll}s)...")
    elapsed = 0
    while elapsed < effective_poll:
        time.sleep(poll_interval)
        elapsed += poll_interval

        status = client.get_status(request_id)
        state = status.get("status", "unknown")
        print(f"  [{elapsed}s] status: {state}")

        if state == "completed":
            print("YouTube upload completed:", status)
            return status
        if state == "error":
            raise RuntimeError(f"YouTube upload failed: {status}")

    raise TimeoutError(f"YouTube upload did not complete within {effective_poll}s (request_id: {request_id})")
