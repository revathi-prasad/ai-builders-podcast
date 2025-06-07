"""
Helper script for processing podcast content between languages

This script provides simplified functionality for extracting content
and transforming it between languages.
"""

import argparse
import logging
import os
import sys
from typing import List, Dict

from config import Language, EpisodeType
from models import DialogueSegment, EpisodeContext
from cache import IntelligentCache
from transformation import TransformationEngine

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('content_processor.log')
    ]
)

def parse_transcript(transcript_path: str) -> List[DialogueSegment]:
    """Parse a transcript file into a list of DialogueSegment objects
    
    Args:
        transcript_path: Path to the transcript file
        
    Returns:
        List of DialogueSegment objects
    """
    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript_text = f.read()
    
    lines = transcript_text.split('\n')
    dialogue = []
    timestamp = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line == "[INTRO MUSIC]" or line == "[OUTRO MUSIC]":
            dialogue.append(DialogueSegment(
                speaker="MUSIC",
                text=line,
                timestamp=timestamp
            ))
            timestamp += 1
        elif ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                speaker, text = parts
                dialogue.append(DialogueSegment(
                    speaker=speaker.strip(),
                    text=text.strip(),
                    timestamp=timestamp
                ))
                timestamp += 1
    
    return dialogue

def extract_content(dialogue: List[DialogueSegment]) -> List[DialogueSegment]:
    """Extract main content segments, excluding intro and outro
    
    Args:
        dialogue: Full dialogue segments
        
    Returns:
        Content segments only
    """
    # Find intro and outro sections
    intro_end = 0
    outro_start = len(dialogue)
    
    # Look for intro music
    for i, segment in enumerate(dialogue):
        if segment.speaker == "MUSIC" and segment.text == "[INTRO MUSIC]":
            # Find the end of intro (next few segments)
            for j in range(i + 1, min(i + 10, len(dialogue))):
                if dialogue[j].speaker == "MUSIC":
                    intro_end = j + 1
                    break
            else:
                # If no music found, assume intro is first 5 segments
                intro_end = min(5, len(dialogue))
            break
    
    # Look for outro music
    for i in range(len(dialogue) - 1, -1, -1):
        if dialogue[i].speaker == "MUSIC" and dialogue[i].text == "[OUTRO MUSIC]":
            # Find the start of outro (previous few segments)
            for j in range(i - 1, max(0, i - 10), -1):
                if dialogue[j].speaker == "MUSIC":
                    outro_start = j
                    break
            else:
                # If no music found, assume outro is last 5 segments
                outro_start = max(0, len(dialogue) - 5)
            break
    
    # Extract content segments
    content = dialogue[intro_end:outro_start]
    
    logging.info(f"Extracted {len(content)} content segments (out of {len(dialogue)} total)")
    return content

def transform_content(content: List[DialogueSegment], source_lang: str, 
                   target_lang: str, topic: str) -> List[DialogueSegment]:
    """Transform content from source language to target language
    
    Args:
        content: Content segments
        source_lang: Source language code
        target_lang: Target language code
        topic: Topic of the content
        
    Returns:
        Transformed content segments
    """
    cache = IntelligentCache()
    transformation_engine = TransformationEngine(cache)
    
    logging.info(f"Transforming {len(content)} segments from {source_lang} to {target_lang}")
    
    result = transformation_engine.transform_content(
        original_segments=content,
        source_language=Language(source_lang),
        target_language=Language(target_lang),
        topic=topic,
        cost_tier="standard"
    )
    
    return result.transformed_content

def combine_with_standard_sections(content: List[DialogueSegment], language: str, 
                              topic: str) -> List[DialogueSegment]:
    """Combine content with standard intro and outro
    
    Args:
        content: Content segments
        language: Language code
        topic: Topic of the content
        
    Returns:
        Combined dialogue with standard intro and outro
    """
    cache = IntelligentCache()
    transformation_engine = TransformationEngine(cache)
    
    # Get standard intro and outro
    intro_text = transformation_engine.get_language_intro(Language(language))
    outro_text = transformation_engine.get_language_outro(Language(language))
    
    # Parse intro and outro
    intro_segments = []
    for part in intro_text.split("\n\n"):
        part = part.strip()
        if not part:
            continue
            
        if part.startswith("[INTRO MUSIC]"):
            intro_segments.append(DialogueSegment(
                speaker="MUSIC",
                text="[INTRO MUSIC]",
                timestamp=0
            ))
        elif ":" in part:
            speaker, text = part.split(":", 1)
            intro_segments.append(DialogueSegment(
                speaker=speaker.strip(),
                text=text.strip(),
                timestamp=0
            ))
    
    outro_segments = []
    for part in outro_text.split("\n\n"):
        part = part.strip()
        if not part:
            continue
            
        if part.startswith("[OUTRO MUSIC]"):
            outro_segments.append(DialogueSegment(
                speaker="MUSIC",
                text="[OUTRO MUSIC]",
                timestamp=0
            ))
        elif ":" in part:
            speaker, text = part.split(":", 1)
            outro_segments.append(DialogueSegment(
                speaker=speaker.strip(),
                text=text.strip(),
                timestamp=0
            ))
    
    # Combine all segments
    combined = []
    timestamp = 0
    
    # Add intro
    for segment in intro_segments:
        segment.timestamp = timestamp
        combined.append(segment)
        timestamp += 1
    
    # Add content
    for segment in content:
        segment.timestamp = timestamp
        combined.append(segment)
        timestamp += 1
    
    # Add outro
    for segment in outro_segments:
        segment.timestamp = timestamp
        combined.append(segment)
        timestamp += 1
    
    logging.info(f"Combined {len(content)} content segments with "
                f"{len(intro_segments)} intro and {len(outro_segments)} outro segments")
    
    return combined

def format_transcript(dialogue: List[DialogueSegment]) -> str:
    """Format dialogue as a transcript
    
    Args:
        dialogue: List of dialogue segments
        
    Returns:
        Formatted transcript text
    """
    transcript = []
    for entry in dialogue:
        if entry.speaker == "MUSIC":
            transcript.append(entry.text)
        else:
            transcript.append(f"{entry.speaker}: {entry.text}")
    
    return "\n\n".join(transcript)

def process_content(transcript_path: str, target_lang: str, topic: str, 
                 extract_only: bool = False, output_dir: str = "outputs"):
    """Process content from transcript to target language
    
    Args:
        transcript_path: Path to the transcript file
        target_lang: Target language code
        topic: Topic of the content
        extract_only: Whether to extract content only (no transformation)
        output_dir: Output directory
    """
    # Parse the transcript
    dialogue = parse_transcript(transcript_path)
    
    # Extract content
    content = extract_content(dialogue)
    
    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Save the extracted content
    content_path = os.path.join(output_dir, f"content_only_{os.path.basename(transcript_path)}")
    with open(content_path, "w", encoding="utf-8") as f:
        f.write(format_transcript(content))
    
    logging.info(f"Extracted content saved to: {content_path}")
    
    if extract_only:
        return
    
    # Determine source language from the file name
    filename = os.path.basename(transcript_path)
    source_lang = "english"  # Default
    for lang in ["english", "hindi", "tamil"]:
        if lang in filename:
            source_lang = lang
            break
    
    # Transform the content
    transformed = transform_content(content, source_lang, target_lang, topic)
    
    # Save the transformed content
    transformed_path = os.path.join(output_dir, f"transformed_{target_lang}_{os.path.basename(transcript_path)}")
    with open(transformed_path, "w", encoding="utf-8") as f:
        f.write(format_transcript(transformed))
    
    logging.info(f"Transformed content saved to: {transformed_path}")
    
    # Combine with standard sections
    combined = combine_with_standard_sections(transformed, target_lang, topic)
    
    # Save the combined content
    output_path = os.path.join(output_dir, f"combined_{target_lang}_{os.path.basename(transcript_path)}")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(format_transcript(combined))
    
    logging.info(f"Combined content saved to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Process podcast content between languages")
    
    parser.add_argument("--transcript", required=True, help="Path to the transcript file")
    parser.add_argument("--target-language", required=True, choices=["english", "hindi", "tamil"],
                      help="Target language for transformation")
    parser.add_argument("--topic", required=True, help="Topic of the content")
    parser.add_argument("--extract-only", action="store_true", 
                      help="Extract content only (no transformation)")
    parser.add_argument("--output-dir", default="outputs", help="Output directory")
    
    args = parser.parse_args()
    
    process_content(
        args.transcript,
        args.target_language,
        args.topic,
        args.extract_only,
        args.output_dir
    )

if __name__ == "__main__":
    main()