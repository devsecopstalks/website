#!/usr/bin/env python3

import os
import argparse
import sys
from pathlib import Path
from openai import OpenAI

def transcribe_audio(client, audio_file_path, verbose=False):
    """
    Transcribe an audio file using OpenAI's Whisper API.
    
    Args:
        client: OpenAI client instance
        audio_file_path: Path to the audio file to transcribe
        verbose: Whether to print verbose output
    
    Returns:
        Transcription text
    """
    try:
        print(f"Transcribing audio file: {audio_file_path}")
        
        with open(audio_file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
        
        if verbose:
            print(f"Transcription completed. Length: {len(transcript)} characters")
        
        return transcript
    
    except Exception as e:
        print(f'An error occurred during transcription: {str(e)}')
        raise e


def extract_highlights(client, transcript, verbose=False):
    """
    Extract highlights from a transcript using GPT-5.
    
    Args:
        client: OpenAI client instance
        transcript: Full transcription text
        verbose: Whether to print verbose output
    
    Returns:
        Extracted highlights text
    """
    try:
        print("Extracting highlights from transcript...")
        
        prompt = """You are an expert at analyzing podcast transcripts. Please analyze the following transcript and extract the key highlights, insights, and important points discussed in the podcast.

Format your response as a bulleted list of highlights, organized by topic or theme if applicable. Each highlight should be concise but informative.

Transcript:
{transcript}

Please provide the highlights:"""
        
        response = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts key highlights from podcast transcripts."},
                {"role": "user", "content": prompt.format(transcript=transcript)}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        highlights = response.choices[0].message.content
        
        if verbose:
            print(f"Highlights extracted. Length: {len(highlights)} characters")
        
        return highlights
    
    except Exception as e:
        print(f'An error occurred during highlight extraction: {str(e)}')
        raise e


def save_output(content, filename, output_dir, verbose=False):
    """
    Save content to a text file in the specified directory.
    
    Args:
        content: Text content to save
        filename: Name of the file to create
        output_dir: Directory to save the file in
        verbose: Whether to print verbose output
    """
    try:
        output_path = Path(output_dir) / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Saved: {output_path}")
        
        if verbose:
            print(f"File size: {len(content)} characters")
    
    except Exception as e:
        print(f'An error occurred while saving file {filename}: {str(e)}')
        raise e


def parse_args():
    parser = argparse.ArgumentParser(
        description="Transcribe podcast episodes and extract highlights using OpenAI API"
    )
    parser.add_argument(
        "audio_file",
        help="Path to the MP3 audio file to transcribe"
    )
    parser.add_argument(
        "-o", "--output-dir",
        help="Output directory for transcription and highlights (default: ~/Downloads)",
        default=os.path.expanduser("~/Downloads")
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose output",
        default=False
    )
    parser.add_argument(
        "--transcript-only",
        action="store_true",
        help="Only generate transcript, skip highlights extraction",
        default=False
    )
    return parser.parse_args()


def main():
    args = parse_args()
    
    # Validate audio file
    audio_file_path = Path(args.audio_file)
    if not audio_file_path.exists():
        print(f"Error: Audio file not found: {audio_file_path}")
        sys.exit(1)
    
    if not audio_file_path.suffix.lower() in ['.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm']:
        print(f"Warning: File {audio_file_path.suffix} may not be supported. Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm")
    
    # Validate output directory
    output_dir = Path(args.output_dir)
    if not output_dir.exists():
        print(f"Error: Output directory not found: {output_dir}")
        sys.exit(1)
    
    # Get OpenAI API key from environment
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Please set it using: export OPENAI_API_KEY=your_api_key")
        sys.exit(1)
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Generate base filename from input file
    base_filename = audio_file_path.stem
    
    print(f"Processing: {audio_file_path.name}")
    print(f"Output directory: {output_dir}")
    print()
    
    # Step 1: Transcribe audio
    transcript = transcribe_audio(client, audio_file_path, verbose=args.verbose)
    
    # Save transcript
    transcript_filename = f"{base_filename}_transcript.txt"
    save_output(transcript, transcript_filename, output_dir, verbose=args.verbose)
    print()
    
    # Step 2: Extract highlights (unless --transcript-only is specified)
    if not args.transcript_only:
        highlights = extract_highlights(client, transcript, verbose=args.verbose)
        
        # Save highlights
        highlights_filename = f"{base_filename}_highlights.txt"
        save_output(highlights, highlights_filename, output_dir, verbose=args.verbose)
        print()
    
    print("Done! 🎉")
    print(f"Files saved to: {output_dir}")


if __name__ == "__main__":
    main()
