import os
import webbrowser
import http.server
import pyyoutube.models as mds
from pyyoutube import Client as YoutubeClient
from pyyoutube.media import Media

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