"""Upload episode video to YouTube via upload-post.com (SiRob/DevSecOps Talks integration)."""

import os
import re
import time
from pathlib import Path

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from upload_post import UploadPostClient, UploadPostError

import requests


class LongTimeoutUploadPostClient(UploadPostClient):
    """
    upload-post's client uses requests without timeouts; large MP4s can also hit
    proxy idle limits. More importantly, the API gateway may return 504 before
    the body finishes — for very large files prefer an HTTPS URL (server fetch).
    """

    _TIMEOUT_MULTIPART = (120.0, 4 * 60 * 60)  # connect 2m, read 4h
    _TIMEOUT_DEFAULT = (60.0, 600.0)

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
            error_msg = str(e)
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("message") or error_data.get("detail") or str(error_data)
                except (ValueError, KeyError):
                    pass
            raise UploadPostError(f"API request failed: {error_msg}") from e


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

    retry_strategy = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    client.session.mount("https://", adapter)

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
            print(f"Upload attempt {attempt} failed: {e}")
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
