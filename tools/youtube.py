import os
from upload_post import UploadPostClient


def upload_to_youtube(video_path, title, description):
    api_key = os.environ["UPLOAD_POST_API_KEY"]
    user = os.environ["UPLOAD_POST_USER"]

    client = UploadPostClient(api_key=api_key)
    response = client.upload_video(
        video_path=video_path,
        title=title,
        description=description,
        user=user,
        platforms=["youtube"],
        privacyStatus="public",
        selfDeclaredMadeForKids=False,
    )
    print("YouTube upload response:", response)
    return response
