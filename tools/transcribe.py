#!/usr/bin/env python3

import os
import argparse
import sys
from pathlib import Path
from openai import OpenAI
from faster_whisper import WhisperModel

def transcribe_audio_local(audio_file_path, model_size="base", verbose=False):
    """
    Transcribe an audio file using local Whisper model (faster-whisper).
    
    Args:
        audio_file_path: Path to the audio file to transcribe
        model_size: Whisper model size (tiny, base, small, medium, large-v2, large-v3)
        verbose: Whether to print verbose output
    
    Returns:
        Transcription text
    """
    try:
        print(f"Transcribing audio file: {audio_file_path}")
        print(f"Using local Whisper model: {model_size}")
        print("Loading model (this may take a moment on first run)...")
        
        # Initialize the model
        # Use CPU by default, but can use GPU with device="cuda"
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        
        print("Transcribing... (this may take several minutes for long audio)")
        
        # Transcribe the audio
        segments, info = model.transcribe(str(audio_file_path), beam_size=5)
        
        if verbose:
            print(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")
        
        # Combine all segments into full transcript
        transcript = " ".join([segment.text for segment in segments])
        
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
        description="Transcribe podcast episodes (local Whisper) and extract highlights (GPT-5)"
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
    parser.add_argument(
        "-m", "--model",
        help="Whisper model size: tiny, base, small, medium, large-v2, large-v3 (default: base)",
        default="medium",
        choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"]
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
    
    # Generate base filename from input file
    base_filename = audio_file_path.stem
    
    print(f"Processing: {audio_file_path.name}")
    print(f"Output directory: {output_dir}")
    print()
    
    # Step 1: Transcribe audio using local Whisper (FREE!)
    transcript = transcribe_audio_local(audio_file_path, model_size=args.model, verbose=args.verbose)
    
    # Save transcript
    transcript_filename = f"{base_filename}_transcript.txt"
    save_output(transcript, transcript_filename, output_dir, verbose=args.verbose)
    print()
    
    # Step 2: Extract highlights using OpenAI API (unless --transcript-only is specified)
    if not args.transcript_only:
        # Get OpenAI API key from environment
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            print("Warning: OPENAI_API_KEY environment variable not set")
            print("Skipping highlights extraction. Set the API key to enable highlights.")
            print("You can still use the transcript generated above.")
        else:
            # Initialize OpenAI client
            client = OpenAI(api_key=api_key)
            
            highlights = extract_highlights(client, transcript, verbose=args.verbose)
            
            # Save highlights
            highlights_filename = f"{base_filename}_highlights.txt"
            save_output(highlights, highlights_filename, output_dir, verbose=args.verbose)
            print()
    
    print("Done! 🎉")
    print(f"Files saved to: {output_dir}")


if __name__ == "__main__":
    main()
