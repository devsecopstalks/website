import os
import time
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from upload_post import UploadPostClient


def upload_to_youtube(video_path, title, description, poll_interval=15, poll_timeout=600, max_retries=2):
    """
    Upload video to YouTube using async mode to avoid gateway timeouts.

    Args:
        video_path: Path to the video file
        title: Video title
        description: Video description
        poll_interval: Seconds between status checks (default 15)
        poll_timeout: Max seconds to wait for completion (default 600 = 10 min)
        max_retries: Number of upload retries on failure (default 2)

    Returns:
        Final status response dict
    """
    api_key = os.environ["UPLOAD_POST_API_KEY"]
    user = os.environ["UPLOAD_POST_USER"]

    client = UploadPostClient(api_key=api_key)

    # Configure retries and generous timeout for large file uploads
    retry_strategy = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    client.session.mount("https://", adapter)

    file_size_mb = Path(video_path).stat().st_size / (1024 * 1024)
    # Scale timeout: 10 min base + 1 min per 100MB
    upload_timeout = 600 + int(file_size_mb / 100) * 60
    print(f"File size: {file_size_mb:.0f} MB, upload timeout: {upload_timeout}s")

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
            wait = 2 ** attempt * 5
            print(f"Retrying in {wait}s...")
            time.sleep(wait)

    request_id = response.get("request_id")
    if not request_id:
        return response

    print(f"Polling for completion (request_id: {request_id})...")
    elapsed = 0
    while elapsed < poll_timeout:
        time.sleep(poll_interval)
        elapsed += poll_interval

        status = client.get_status(request_id)
        state = status.get("status", "unknown")
        print(f"  [{elapsed}s] status: {state}")

        if state == "completed":
            print("YouTube upload completed:", status)
            return status
        elif state == "error":
            raise RuntimeError(f"YouTube upload failed: {status}")

    raise TimeoutError(f"YouTube upload did not complete within {poll_timeout}s (request_id: {request_id})")
