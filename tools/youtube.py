import os
import time
from upload_post import UploadPostClient


def upload_to_youtube(video_path, title, description, poll_interval=15, poll_timeout=600):
    """
    Upload video to YouTube using async mode to avoid gateway timeouts.

    Args:
        video_path: Path to the video file
        title: Video title
        description: Video description
        poll_interval: Seconds between status checks (default 15)
        poll_timeout: Max seconds to wait for completion (default 600 = 10 min)

    Returns:
        Final status response dict
    """
    api_key = os.environ["UPLOAD_POST_API_KEY"]
    user = os.environ["UPLOAD_POST_USER"]

    client = UploadPostClient(api_key=api_key)

    print("Submitting async upload...")
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

    request_id = response.get("request_id")
    if not request_id:
        # Sync response came back immediately (small file or already done)
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
