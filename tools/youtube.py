import os
import webbrowser
import http.server
import pyyoutube.models as mds
from pyyoutube import Client as YoutubeClient
from pyyoutube.media import Media
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
import json

def upload_to_youtube(filename, title, description, private=True):
    """Upload video to YouTube using python-youtube library"""
    print(f"Uploading video to YouTube: {filename}")
    client_id = os.environ.get('YOUTUBE_CLIENT_ID')
    client_secret = os.environ.get('YOUTUBE_CLIENT_SECRET')
    channel_id = os.environ.get('YOUTUBE_CHANNEL_ID')
    scope = [
        "https://www.googleapis.com/auth/youtube",
        "https://www.googleapis.com/auth/youtube.force-ssl",
        "https://www.googleapis.com/auth/youtube.upload",
    ]
    
    if not client_id or not client_secret:
        raise ValueError("YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET environment variables must be set")

    # Allow OAuthlib to run without HTTPS for local testing.
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    
    credentials = None
    # Check for existing credentials file
    if os.path.exists('.youtube_credentials'):
        try:
            from google.oauth2.credentials import Credentials
            with open('.youtube_credentials', 'r') as f:
                creds_data = json.load(f)
                credentials = Credentials.from_authorized_user_info(creds_data)
        except Exception as e:
            print(f"Error loading credentials from file: {e}")
            credentials = None
    
    # If no valid credentials found, run the OAuth flow
    if not credentials:
        client_config = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8080"]
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, scope)
        credentials = flow.run_local_server(port=0)
        
        # Save credentials for future use
        creds_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        with open('.youtube_credentials', 'w') as f:
            json.dump(creds_data, f)
    
    # Build the YouTube API client
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
    
    # Define the request body with video metadata
    privacyStatus = "private" if private else "public"
    body=dict(
        snippet=dict(
            title=title,
            description=description,
            tags=[
                    'DevSecOps',
                    'Podcast', 
                    'Security', 
                    'Development',
                    'DevOps',
                    'Cloud',
                    'AWS',
                    'Docker',
                    'CI/CD',
                    'Continuous Integration',
                    'Continuous Deployment',
                    'Continuous Delivery',
                    'DevSecOps Talks',
                    'Infrastructure as Code',
                    'Terraform'
            ],
            categoryId=28  # Science & Technology
        ),
        status=dict(
            privacyStatus=privacyStatus
        )
    )
    
    # Prepare the video file for upload
    mediaFile = MediaFileUpload(filename, chunksize=-1, resumable=True)
    
    # Create the API request to insert (upload) the video
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=mediaFile,
        onBehalfOfContentOwner="YOUR_CONTENT_OWNER_ID",
        onBehalfOfContentOwnerChannel=channel_id
    )
    
    # Execute the upload in chunks for better error handling (resumable)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")
    video_id = response.get("id")
    print(f"Upload Complete! Video ID: {video_id}")
    return video_id
    """
    ytc = YoutubeClient(client_id=client_id, client_secret=client_secret)

    authorize_url, state = ytc.get_authorize_url(redirect_uri="http://localhost:8080", scope=scope)
    webbrowser.open(authorize_url)

    # Start local server to catch the OAuth redirect
    server = http.server.HTTPServer(('localhost', 8080), http.server.BaseHTTPRequestHandler)
    print("Waiting for OAuth redirect at http://localhost:8080...")
    
    # Handle one request then shutdown
    server.last_request_path = None
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            server.last_request_path = self.path
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"You can close this window now.")
    server.RequestHandlerClass = Handler
    server.handle_request()
    server.server_close()

    # since we are using http, we need to set this env variable
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    # Get the full redirect URL from the path
    response_uri = f"http://localhost:8080{server.last_request_path}"

    print(f"Response URI: {response_uri}")

    token = ytc.generate_access_token(authorization_response=response_uri, scope=scope)
    
    try:
        cli = YoutubeClient(access_token=token)
        body = mds.Video(
            snippet=mds.VideoSnippet(
                channelId=channel_id,
                title=title,
                description=description,
                tags=[
                    'DevSecOps',
                    'Podcast', 
                    'Security', 
                    'Development',
                    'DevOps',
                    'Cloud',
                    'AWS',
                    'Docker',
                    'CI/CD',
                    'Continuous Integration',
                    'Continuous Deployment',
                    'Continuous Delivery',
                    'DevSecOps Talks',
                    'Infrastructure as Code',
                    'Terraform'
                ],
                #privacyStatus='private' if private else 'public'
            )
        )
        media = Media(filename=filename)

        upload = cli.videos.insert(body=body, media=media, parts=["snippet"], notify_subscribers=True)

        response = None
        while response is None:
            print(f"Uploading video...")
            status, response = upload.next_chunk()
            if status is not None:
                print(f"Uploading video progress: {status.progress()}...")

        # Use video class to representing the video resource.
        video = mds.Video.from_dict(response)
        print(f"Video id {video.id} was successfully uploaded.")
        return video.id
    except Exception as e:
        print(f'An error occurred during upload: {str(e)}')
        raise e 
    """