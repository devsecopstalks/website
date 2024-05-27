#!/usr/bin/env python3

import os
import re
import argparse
import requests
import mimetypes
import datetime

from jinja2 import Environment, FileSystemLoader
import sys

# Podbean API docs
# https://developers.podbean.com/podbean-api-docs/

# get podbean auth token
# curl -u YOUR_CLIENT_ID:YOUR_CLIENT_SECRET https://api.podbean.com/v1/oauth/token -X POST -d 'grant_type=client_credentials'
def get_podbean_auth_token(client_id, client_secret, url="https://api.podbean.com/v1/oauth/token"):
    response = requests.post(
        url,
        data={"grant_type": "client_credentials", "expires_inoptional": 180},
        auth=(client_id, client_secret))
    return response.json()['access_token']

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
    return re.sub(r"^\W", "", title).replace(" ", "-").replace(":", "-").lower()

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

def parse_args():
    parser = argparse.ArgumentParser(description="No more of manual episodes publishing")
    parser.add_argument("-f", "--filename", help="path to mp3 file", default=None)
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output", default=False)
    parser.add_argument("-s", "--scan", action="store_true", help="Scan current directory for mp3 file and use it for upload", default=False)
    return parser.parse_args()


def main():
    args = parse_args()

    path_file = None
    if args.filename:
        path_file = args.filename
        # check that file exists and it is mp3 file
        if not os.path.isfile(args.filename):
            print(f"File {args.filename} does not exist.")
            sys.exit(1)
    elif args.scan:
        # find mp3 file in current directory
        for file in os.listdir():
            if file.endswith(".mp3"):
                path_file = file
                break
        if not path_file:
            print("No mp3 files found in current directory.")
            sys.exit(1)
    else:
        print("Please provide path to mp3 file using --filename option or use --scan option to scan current directory for mp3 file.")
        sys.exit(1)
    mime_type = mimetypes.guess_type(path_file)[0]
    if mime_type != "audio/mpeg":
        print(f"File {path_file} is not mp3 file.")
        return

    print(f"Going to use: {path_file}")

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

    # get presigned url for upload
    print("Getting presigned url for upload...")
    file_size = os.path.getsize(path_file)
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
    upload_response = upload_file_to_podbean(presigned_url, path_file)
    if args.verbose:
        print(upload_response)

    # ask for episode description
    description = input("Podcast description: ")

    # add prefix to the title
    title = f"#{episode_number} - {title}"

    # add standart ending to description
    description = f"{description}<p>&nbsp;</p><p>Connect with us on LinkedIn or Twitter (see info at https://devsecops.fm/about/). We are happy to answer any questions, hear suggestions for new episodes, or hear from you, our listeners.</p>"
 
    # print all received information
    print("Podcast title:", title)
    print("Podcast description:", description)

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
        eposide_number=episode_number,
        date=datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(),
        podbean_id=podbean_id,
        description=description
    )
    # get a path to content/episodes directory relative to the script location
    episode_file = os.path.join(os.path.dirname(__file__), "../content/episodes", episode_file_name_md)
    with open(episode_file, 'w') as f:
        f.write(output)
    
    
    print("Done")

if __name__ == "__main__":
    main()