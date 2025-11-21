#!/usr/bin/env python3

import os
import re
import json
import argparse
import requests
import mimetypes
import datetime
import sys
import tempfile
import subprocess
import shutil
from pathlib import Path
from openai import OpenAI
from jinja2 import Environment, FileSystemLoader

from youtube import upload_to_youtube

# Podbean API docs
# https://developers.podbean.com/podbean-api-docs/

# System prompt for ChatGPT
SYSTEM_PROMPT = """
The goal of this project is to generate podcast description and titles.
The podcast's name is DevSecOps Talks;
hosts are Andrey, Paulina, and Mattias.
The podcast is for DevSecOps practitioners from DevSecOps practitioners.
Below are examples of previous podcast descriptions for the style reference

General style guidelines:
- Use simple wording for podcast descriptions.
- Please do not use words like enlightening, warmly welcome, etc; keep it simple.
- Do not use the following words - delve, engaging.

Titles should be:
- Concise and catchy (max 80 characters)
- Capture the main topic or theme
- Be attention-grabbing

Descriptions should be:
- Informative and engaging (2-4 sentences)
- Summarize key points discussed
- Entice listeners to tune in
- Use more questions than statements

Output requirements:
- Output must be in JSON format with this exact structure:
{{
  "titles": ["title1", "title2", "title3", "title4", "title5"],
  "descriptions": ["desc1", "desc2", "desc3", "desc4", "desc5"]
}}
- You must output only JSON, no other text or comments.

Description example 1:
This time we got to talk about Lingon, an open-source project developed by Julian and Jacob who is a frequent podcast guest.
Discover the motivations behind Lingon's creation and how it bridges the gap between Terraform and Kubernetes.
Learn how Lingon simplifies infrastructure management, tackles frustrations with YAML and HCL, and offers greater control and automation.

Description example 2:
This is a mixed bag of an episode, we chat about all sorts of digital tools and security practices that we use in our day-to-day lives.
We start by talking about password managers, and why Julien still using LastPass after the recent LastPass data breach.
Julien gives us the lowdown on his personal approach to handling passwords and two-factor authentication (2FA) tokens,
showing us why strong security measures matter.

Description example 3:
Julien also shares his favorite email alias service and we discuss services for sharing sensitive information to keep mail inboxes cleaner and more private.
We also spoke about ChatGPT, an AI language model from OpenAI - will it replace jobs? should we be using it? And how?
Just a heads up, we aren't sponsored by companies we mention in this episode. We're just sharing our personal experiences and the stuff we like to use.

Description example 4:
AWS released AWS Bottlerocket OS in March of 2020, and version 1.0.0 got released in August 2020. What is it? Should you be using it? What are the benefits? Is it ready for prime time? We answer all of those questions during this episode of DevSecOps Talks. Tune in!

Description example 5:
The real cloud lock-in is security! Every service/cloud provider has its own levels of granularity regarding resources.
Cloud engineering is mainly about compute, storage, and networking and how to make them scale.
Scaling security is often left out as it is hard to measure on so many levels.
We think that it is a myth and that we can measure how many steps it takes to add, modify or remove access rights.
It all starts with monitoring; knowing what is there in a cloud infrastructure is a very good first step.
By making it easy to see and manage access rights, we make it easier for ourselves to keep resources secured."""


def compress_audio_for_transcription(audio_file_path, bitrate='32k', verbose=False):
    """
    Compress audio file using ffmpeg to reduce file size for Whisper API.
    
    Args:
        audio_file_path: Path to the audio file
        bitrate: Target bitrate (default '32k' for 32kbps mono)
        verbose: Whether to print verbose output
    
    Returns:
        Path to compressed file
    """
    if not shutil.which('ffmpeg'):
        print("Error: ffmpeg not found. Install with: brew install ffmpeg")
        sys.exit(1)
    
    base_name = os.path.splitext(audio_file_path)[0]
    compressed_file = f"{base_name}_compressed.mp3"
    
    original_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
    print(f"Compressing audio ({original_size_mb:.2f} MB) to {bitrate} mono...")
    
    cmd = [
        'ffmpeg', '-i', audio_file_path,
        '-ac', '1',  # Convert to mono
        '-b:a', bitrate,  # Set bitrate
        '-y',  # Overwrite output file
        compressed_file
    ]
    
    if not verbose:
        cmd.extend(['-loglevel', 'error'])
    
    try:
        subprocess.run(cmd, check=True, capture_output=not verbose)
        
        compressed_size_mb = os.path.getsize(compressed_file) / (1024 * 1024)
        reduction = ((original_size_mb - compressed_size_mb) / original_size_mb) * 100
        
        print(f"Compressed: {original_size_mb:.2f} MB → {compressed_size_mb:.2f} MB ({reduction:.1f}% reduction)")
        
        return compressed_file
    except subprocess.CalledProcessError as e:
        print(f"Error compressing audio: {e}")
        raise


def transcribe_audio_openai(client, audio_file_path, verbose=False):
    """
    Transcribe an audio file using OpenAI Whisper API.
    Automatically compresses large files if needed.
    
    Args:
        client: OpenAI client instance
        audio_file_path: Path to the audio file to transcribe
        verbose: Whether to print verbose output
    
    Returns:
        Transcription text
    """
    try:
        print(f"Transcribing audio file: {audio_file_path}")
        
        # Check file size and compress if needed
        file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
        max_size_mb = 24  # Stay under 25MB limit
        
        file_to_transcribe = audio_file_path
        cleanup_file = None
        
        if file_size_mb > max_size_mb:
            print(f"File size ({file_size_mb:.2f} MB) exceeds {max_size_mb} MB limit")
            file_to_transcribe = compress_audio_for_transcription(audio_file_path, verbose=verbose)
            cleanup_file = file_to_transcribe
        
        print("Using OpenAI Whisper API...")
        
        with open(file_to_transcribe, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text",
                language="en"  # Force English transcription
            )
        
        # Clean up compressed file if created
        if cleanup_file and os.path.exists(cleanup_file):
            os.remove(cleanup_file)
            if verbose:
                print(f"Removed temporary file: {cleanup_file}")
        
        if verbose:
            print(f"Transcription completed. Length: {len(transcript)} characters")
        
        return transcript
    
    except Exception as e:
        print(f'An error occurred during transcription: {str(e)}')
        raise e


def generate_title_and_description_options(client, transcript, additional_prompt=None, verbose=False):
    """
    Generate title and description options from transcript using ChatGPT with structured output.
    
    Args:
        client: OpenAI client instance
        transcript: Full transcription text
        additional_prompt: Optional additional guidance for regeneration
        verbose: Whether to print verbose output
    
    Returns:
        Dictionary with 'titles' and 'descriptions' lists
    """
    try:
        if additional_prompt:
            print(f"Regenerating with additional guidance: {additional_prompt}")
        else:
            print("Generating title and description options...")
        
        prompt = f"""Based on the following podcast transcript, generate 5 different title options 
and 5 different description options for this podcast episode.

{f"Additional guidance: {additional_prompt}" if additional_prompt else ""}

Transcript:
{transcript}

"""
        content = None
        
        if verbose:
            print(f"Making API request to model: gpt-5")
            print(f"Prompt length: {len(prompt)} characters")
            print(f"System prompt length: {len(SYSTEM_PROMPT)} characters")
        
        response = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=8000  # Increased to accommodate reasoning tokens + actual output
        )
        
        if verbose:
            print(f"API response received")
            print(f"Response object type: {type(response)}")
            print(f"Response attributes: {dir(response)}")
            print(f"Response dict: {response.model_dump()}")
        
        # Log response structure
        print(f"Number of choices in response: {len(response.choices)}")
        if response.choices:
            print(f"First choice attributes: {dir(response.choices[0])}")
            print(f"First choice message: {response.choices[0].message}")
            print(f"First choice finish_reason: {response.choices[0].finish_reason}")
        
        content = response.choices[0].message.content
        
        print(f"Content extracted from response: {content is not None}")
        print(f"Content length: {len(content) if content else 0} characters")
        
        if verbose:
            print(f"Raw response content from GPT-5:")
            print(content)
            print("-" * 80)
        
        if not content:
            print(f"ERROR: Empty content received!")
            print(f"Full response object: {response}")
            print(f"Response model_dump: {response.model_dump()}")
            raise ValueError("Empty response from GPT-5")
        
        result = json.loads(content)
        
        if verbose:
            print(f"Generated {len(result.get('titles', []))} titles and {len(result.get('descriptions', []))} descriptions")
        
        return result
    
    except Exception as e:
        print(f'An error occurred during content generation: {str(e)}')
        print(f'Content variable: {content}')
        print(f'Response object available: {response if "response" in locals() else "No response object"}')
        if "response" in locals():
            print(f'Response model_dump: {response.model_dump()}')
        raise e


def select_option(options, option_type="option", allow_regenerate=False):
    """
    Present options to user and let them choose or edit.
    
    Args:
        options: List of options to choose from
        option_type: Type of option (for display purposes)
        allow_regenerate: If True, allow 'r' command to request regeneration
    
    Returns:
        Selected/edited option or tuple ('regenerate', additional_prompt) for regeneration
    """
    print(f"\n{option_type.capitalize()} Options:")
    print("-" * 80)
    
    for i, option in enumerate(options, 1):
        print(f"{i}. {option}")
    
    print(f"{len(options) + 1}. Enter custom {option_type}")
    print("-" * 80)
    
    help_text = f"\nSelect {option_type} (1-{len(options) + 1}), 'e' to edit"
    if allow_regenerate:
        help_text += ", or 'r' to regenerate with additional guidance"
    help_text += ": "
    
    while True:
        try:
            choice = input(help_text).strip()
            
            if choice.lower() == 'e':
                num = input(f"Enter number to edit (1-{len(options)}): ").strip()
                idx = int(num) - 1
                if 0 <= idx < len(options):
                    print(f"\nCurrent: {options[idx]}")
                    edited = input(f"Enter edited {option_type}: ").strip()
                    if edited:
                        return edited
                    return options[idx]
            elif choice.lower() == 'r' and allow_regenerate:
                additional = input(f"\nEnter additional guidance for regeneration (e.g., 'focus more on security aspects'): ").strip()
                if additional:
                    return ('regenerate', additional)
                else:
                    print("No guidance provided, staying with current options")
                    continue
            else:
                idx = int(choice) - 1
                if idx == len(options):
                    custom = input(f"Enter custom {option_type}: ").strip()
                    if custom:
                        return custom
                elif 0 <= idx < len(options):
                    return options[idx]
                
            print(f"Invalid selection. Please enter 1-{len(options) + 1}")
        except ValueError:
            print(f"Invalid input. Please enter a number 1-{len(options) + 1}")
        except KeyboardInterrupt:
            print("\nOperation cancelled by user")
            sys.exit(1)


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

def parse_args():
    parser = argparse.ArgumentParser(description="Automated podcast publishing with AI-powered transcription and content generation")
    parser.add_argument("-f", "--filename", help="Path to audio file (mp3)", default=None)
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output", default=False)
    parser.add_argument("-s", "--scan", action="store_true", help="Scan current directory for mp3 and mp4 files", default=False)
    parser.add_argument("--skip-transcription", action="store_true", help="Skip transcription step (use existing transcript)", default=False)
    parser.add_argument("-t", "--transcript", help="Path to existing transcript file", default=None)
    return parser.parse_args()

def main():
    args = parse_args()

    # Initialize OpenAI client
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    
    client = OpenAI(api_key=api_key)

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
        sys.exit(1)

    print(f"Going to use: {audio_file} and {video_file}")

    # Step 1: Get episode number first
    # Read Podbean credentials from environment
    client_id = os.environ.get('PODBEAN_CLIENT_ID')
    client_secret = os.environ.get('PODBEAN_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("Error: PODBEAN_CLIENT_ID and PODBEAN_CLIENT_SECRET environment variables must be set")
        sys.exit(1)

    # get podbean auth token
    print("\nGetting podbean auth token...")
    auth_token = get_podbean_auth_token(client_id, client_secret)

    # get last episode number
    print("Calculating episode number...")
    episode_number = int(get_last_episode_number(auth_token)) + 1
    print(f"This episode number: {episode_number}")

    # Step 2: Transcribe audio (or load existing transcript)
    transcript = None
    transcript_file = f"episode{episode_number:03d}.txt"
    
    # Check if transcript already exists
    if os.path.exists(transcript_file) and not args.skip_transcription:
        print(f"Found existing transcript: {transcript_file}")
        print("Loading existing transcript (use --skip-transcription to force new transcription)...")
        with open(transcript_file, 'r', encoding='utf-8') as f:
            transcript = f.read()
    elif args.skip_transcription and args.transcript:
        print(f"Loading transcript from: {args.transcript}")
        with open(args.transcript, 'r', encoding='utf-8') as f:
            transcript = f.read()
    else:
        print("Transcribing audio file...")
        transcript = transcribe_audio_openai(client, audio_file, verbose=args.verbose)
        
        # Save transcript with episode number
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(transcript)
        print(f"Transcript saved to: {transcript_file}")

    # Step 3: Generate title and description options
    options = generate_title_and_description_options(client, transcript, verbose=args.verbose)
    
    # Step 4: Let user select title (with regeneration option)
    title = None
    while title is None:
        result = select_option(options.get('titles', []), "title", allow_regenerate=True)
        if isinstance(result, tuple) and result[0] == 'regenerate':
            # Regenerate with additional prompt
            options = generate_title_and_description_options(client, transcript, additional_prompt=result[1], verbose=args.verbose)
        else:
            title = result
    print(f"\nSelected title: {title}")
    
    # Step 5: Let user select description (with regeneration option)
    description = None
    while description is None:
        result = select_option(options.get('descriptions', []), "description", allow_regenerate=True)
        if isinstance(result, tuple) and result[0] == 'regenerate':
            # Regenerate with additional prompt
            options = generate_title_and_description_options(client, transcript, additional_prompt=result[1], verbose=args.verbose)
        else:
            description = result
    print(f"\nSelected description: {description}")

    # get presigned url for upload
    print("Getting presigned url for upload...")
    file_size = os.path.getsize(audio_file)
    episode_file_name_mp3 = f"{episode_number:03d}-{title_to_url_safe(title)}.mp3"
    episode_file_name_md = f"{episode_number:03d}-{title_to_url_safe(title)}.md"
    presigned_url_response = get_podbean_upload_link(auth_token, episode_file_name_mp3, file_size)
    
    if args.verbose:
        print(presigned_url_response)
    
    presigned_url = presigned_url_response["presigned_url"]
    media_key = presigned_url_response["file_key"]
    print(f"presigned_url: {presigned_url}")
    print(f"media_key: {media_key}")

    # upload file to podbean
    print(f"Uploading file to podbean as {episode_file_name_mp3}...")
    upload_response = upload_file_to_podbean(presigned_url, audio_file)
    if args.verbose:
        print(upload_response)

    # add prefix to the title
    full_title = f"#{episode_number} - {title}"

    # add standard ending to description
    extended_description = (f"{description}<p>&nbsp;</p>"
     + "<p>We are always happy to answer any questions, hear suggestions for new episodes, or hear from you, our listeners.</p>"
     + "<p><a href='https://www.linkedin.com/company/101418030'>DevSecOps Talks podcast LinkedIn page</a></p>"
     + "<p><a href='https://devsecops.fm/'>DevSecOps Talks podcast website</a></p>"
     + "<p><a href='https://youtube.com/channel/UCRjpE9xKxZeBkRgYiLErEjw'>DevSecOps Talks podcast YouTube channel</a></p>")

    # print all received information
    print("\nPodcast title:", full_title)
    print("Podcast extended description:", extended_description)

    # YouTube upload (placeholder for now)
    youtube_id = "Not yet implemented"

    # create new episode
    print("\nCreating new episode...")
    create_episode_response = create_podbean_episode(
        auth_token, full_title, extended_description, episode_number, media_key=media_key
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
        title=full_title,
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
    
    print(f"\nEpisode file created: {episode_file}")
    print("\nDone! 🎉")

if __name__ == "__main__":
    main()