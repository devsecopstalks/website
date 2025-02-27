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

from youtube import upload_to_youtube

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

def get_podcast_title():
    # Check for saved title in .podcast_title file
    saved_title = None
    if os.path.exists('.podcast_title'):
        with open('.podcast_title', 'r') as f:
            saved_title = f.read().strip()
        print(f"Found saved title: {saved_title}")
        print("Press Enter to use this title or type a new one")

    # ask for episode title
    title = input("Enter podcast title: ").strip()
    if not title and saved_title:
        title = saved_title
    else:
        # Save new title for potential re-runs
        with open('.podcast_title', 'w') as f:
            f.write(title)
        title = title.title()
    print(f"Podcast title: {title}")
    return title

def get_podcast_description():
    """Get podcast description from input or saved file"""
    # Check for saved description in .podcast_description file
    saved_description = None
    if os.path.exists('.podcast_description'):
        with open('.podcast_description', 'r') as f:
            saved_description = f.read().strip()
        print(f"Found saved description: {saved_description}")
        print("Press Enter to use this description or type a new one")

    # ask for episode description
    description = input("Enter podcast description: ").strip()
    if not description and saved_description:
        description = saved_description
    else:
        # Save new description for potential re-runs
        with open('.podcast_description', 'w') as f:
            f.write(description)
    print(f"Podcast description: {description}")
    return description

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

    title = get_podcast_title()
    description = get_podcast_description()

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
    extended_description = f"{description}<p>&nbsp;</p><p>Connect with us on LinkedIn or Twitter (see info at https://devsecops.fm/about/). We are happy to answer any questions, hear suggestions for new episodes, or hear from you, our listeners.</p>"
 
    # print all received information
    print("Podcast title:", title)
    print("Podcast extended description:", extended_description)

    # Update YouTube upload call
    youtube_id = upload_to_youtube(video_file, title, description)
    print(f"YouTube video id: {youtube_id}")

    # create new episode
    print("Creating new episode...")
    create_episode_response = create_podbean_episode(
        auth_token, title, extended_description, episode_number, media_key=media_key
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
        description=extended_description,
        youtube_id=youtube_id,
    )
    # get a path to content/episodes directory relative to the script location
    episode_file = os.path.join(os.path.dirname(__file__), "../content/episodes", episode_file_name_md)
    with open(episode_file, 'w') as f:
        f.write(output)
    
    
    print("Done")

if __name__ == "__main__":
    main()