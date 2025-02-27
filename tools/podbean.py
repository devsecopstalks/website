#!/usr/bin/env python3

import os
import re
import argparse
import requests
import mimetypes
import datetime
import webbrowser
import http.server
import pyyoutube.models as mds
from pyyoutube import Client as YoutubeClient
from pyyoutube.media import Media

from jinja2 import Environment, FileSystemLoader
import sys

# Podbean API docs
# https://developers.podbean.com/podbean-api-docs/

# get podbean auth token
# curl -u YOUR_CLIENT_ID:YOUR_CLIENT_SECRET https://api.podbean.com/v1/oauth/token -X POST -d 'grant_type=client_credentials'
def get_podbean_auth_token(client_id, client_secret, url="https://api.podbean.com/v1/oauth/token"):
    try:
        response = requests.post(
            url,
            data={"grant_type": "client_credentials", "expires_inoptional": 180},
            auth=(client_id, client_secret))
        access_token = response.json()['access_token']
        return access_token
    except Exception as e:
        print(f'An error occurred during getting podbean auth token: {str(e)}, response: {response.text}')
        raise e

# authorize file upload to podbean (get s3 presigned link)
# curl https://api.podbean.com/v1/files/uploadAuthorize -G -d 'access_token=YOUR_ACCESS_TOKEN' -d 'filename=abc.mp3' -d 'filesize=1291021' -d 'content_type=audio/mpeg'
def get_podbean_upload_link(access_token, filename, filesize, content_type="mp3", url="https://api.podbean.com/v1/files/uploadAuthorize"):
    response = requests.get(
        url,
        params={"access_token": access_token, "filename": filename, "filesize": filesize, "content_type": content_type})
    return response.json()

# upload file to podbean
# curl -v -H "Content-Type: image/jpeg" -T /your/path/file.ext "PRESIGNED_URL"
def upload_file_to_podbean(url, filepath):
    response = requests.put(url,
                            headers={"Content-Type": mimetypes.guess_type(filepath)[0]},
                            data=open(filepath, 'rb'))
    return response

# convert title into url safe string
def title_to_url_safe(title):
    return re.sub(r"[^0-9a-zA-Z]+", "-", title).lower()

# get last episode number by getting all episodes till there are no more left
# curl https://api.podbean.com/v1/episodes -G -d 'access_token=YOUR_ACCESS_TOKEN' -d 'offset=0' -d 'limit=10'
def get_last_episode_number(access_token, url="https://api.podbean.com/v1/episodes"):
    response = requests.get(url, params={"access_token": access_token, "limit": 100})
    return response.json()["count"]

# create new podbean episode
# curl https://api.podbean.com/v1/episodes -X POST -d access_token=YOUR_ACCESS_TOKEN -d title="Good day" \
# -d content="Time you <b>enjoy</b> wasting, was not wasted." -d status=publish -d type=public \
# -d media_key=audio.mp3 -d logo_key=logo.jpg -d transcripts_key=transcripts.srt -d season_number=1
# -d episode_number=1 -d apple_episode_type=full -d publish_timestamp=1667850511 -d content_explicit=clean
def create_podbean_episode(
        access_token, title, content, episode_number, media_key=None, status="draft", type="public",
        url="https://api.podbean.com/v1/episodes"):
    response = requests.post(
        url,
        data={"access_token": access_token, "title": title,
              "content": content, "status": status, "type": type,
              "media_key": media_key, "episode_number": episode_number}
        )
    return response.json()

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
    
    # Get the full redirect URL from the path
    response_uri = f"http://localhost:8080{server.last_request_path}"

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

def parse_args():
    parser = argparse.ArgumentParser(description="No more of manual episodes publishing")
    parser.add_argument("-f", "--filename", help="path to mp3 file", default=None)
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output", default=False)
    parser.add_argument("-s", "--scan", action="store_true", help="Scan current directory for mp3 and mp4 files and use them for upload", default=False)
    return parser.parse_args()

def main():
    args = parse_args()

    # Find audio and video files
    audio_file = None
    video_file = None
    
    if args.filename:
        if args.filename.endswith('.mp3'):
            audio_file = args.filename
        elif args.filename.endswith('.mp4'):
            video_file = args.filename
    elif args.scan:
        # find mp3 and mp4 files in current directory
        for file in os.listdir():
            if file.endswith(".mp3"):
                audio_file = file
            elif file.endswith(".mp4"):
                video_file = file

    if not audio_file:
        print("No mp3 file found for Podbean upload.")
        sys.exit(1)
    mime_type = mimetypes.guess_type(audio_file)[0]
    if mime_type != "audio/mpeg":
        print(f"File {audio_file} is not mp3 file.")
        return
    if not video_file:
        print("No mp4 file found for YouTube upload.")
        sys.exit(1)

    print(f"Going to use: {audio_file} and {video_file}")

    # Calculate episode
    # read podbean creds from env
    client_id = os.environ.get('PODBEAN_CLIENT_ID')
    client_secret = os.environ.get('PODBEAN_CLIENT_SECRET')

    # get podbean auth token
    print("Getting podbean auth token...")
    auth_token = get_podbean_auth_token(client_id, client_secret)

    # get last episode number
    print("Calculating episode number...")
    episode_number = int(get_last_episode_number(auth_token)) + 1
    print(f"This episode number: {episode_number}")

    # ask for episode title
    title = input("Podcast title: ").title()

    # ask for episode description
    description = input("Podcast description: ")

    # get presigned url for upload
    print("Getting presigned url for upload...")
    file_size = os.path.getsize(audio_file)
    episode_file_name_mp3 = f"{episode_number:03d}-{title_to_url_safe(title)}.mp3"
    episode_file_name_md = f"{episode_number:03d}-{title_to_url_safe(title)}.md"
    presigned_url_response = get_podbean_upload_link(auth_token, episode_file_name_mp3, file_size)
    print(presigned_url_response)
    presigned_url = presigned_url_response["presigned_url"]
    media_key = presigned_url_response["file_key"]
    print(f"presigned_url: {presigned_url}")
    print(f"media_key: {media_key}")

    # upload file to podbean
    print(f"Uploading file to podbean as {episode_file_name_mp3} ...")
    upload_response = upload_file_to_podbean(presigned_url, audio_file)
    if args.verbose:
        print(upload_response)

    # add prefix to the title
    title = f"#{episode_number} - {title}"

    # add standart ending to description
    description = f"{description}<p>&nbsp;</p><p>Connect with us on LinkedIn or Twitter (see info at https://devsecops.fm/about/). We are happy to answer any questions, hear suggestions for new episodes, or hear from you, our listeners.</p>"
 
    # print all received information
    print("Podcast title:", title)
    print("Podcast description:", description)

    # Update YouTube upload call
    youtube_id = upload_to_youtube(video_file, title, description)
    print(f"YouTube video id: {youtube_id}")

    # create new episode
    print("Creating new episode...")
    create_episode_response = create_podbean_episode(
        auth_token, title, description, episode_number, media_key=media_key
    )
    if args.verbose:
        print(create_episode_response)

    podbean_id = create_episode_response["episode"]["player_url"].split('=')[-1]
    print(f"Podbean episode id: {podbean_id}")

    # Use Jinja2 to render episode.md.j2 template with all the data collected above
    # and save it as episode.md
    env = Environment(loader=FileSystemLoader(os.path.dirname(__file__)))
    template = env.get_template("episode.md.j2")
    output = template.render(
        title=title,
        episode_number=episode_number,
        date=datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(),
        podbean_id=podbean_id,
        description=description,
        youtube_id=youtube_id,
    )
    # get a path to content/episodes directory relative to the script location
    episode_file = os.path.join(os.path.dirname(__file__), "../content/episodes", episode_file_name_md)
    with open(episode_file, 'w') as f:
        f.write(output)
    
    
    print("Done")

if __name__ == "__main__":
    main()