"""
AI Podcast Generator — CLI Entry Point

Usage:
    python -m src --topic "Machine Learning basics"
    python -m src --topic "AI Safety" --language tamil --duration 15
    python -m src --topic "Climate Change" --format interview --provider groq
    python -m src --input paper.pdf --input https://example.com/article --topic "Summarize these"
"""

import argparse
import os
import sys
import logging
from pathlib import Path

# Load .env before anything else
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main():
    parser = argparse.ArgumentParser(
        prog="ai-podcast-generator",
        description="Generate podcast episodes from topics, documents, URLs, or audio files."
    )

    parser.add_argument(
        "--topic", "-t",
        required=True,
        help="Main topic or prompt for the podcast episode"
    )
    parser.add_argument(
        "--language", "-l",
        default="english",
        help="Target language (default: english)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=10,
        help="Target duration in minutes (default: 10)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["conversation", "interview", "monologue", "debate", "narrative"],
        default="conversation",
        help="Episode format (default: conversation)"
    )
    parser.add_argument(
        "--audience",
        choices=["beginner", "intermediate", "advanced", "expert"],
        default="intermediate",
        help="Audience expertise level (default: intermediate)"
    )
    parser.add_argument(
        "--input", "-i",
        action="append",
        default=[],
        help="Input file (PDF, audio) or URL. Can be specified multiple times."
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=os.environ.get("OUTPUT_DIR", "./output"),
        help="Output directory (default: ./output or OUTPUT_DIR env var)"
    )
    parser.add_argument(
        "--provider",
        choices=["anthropic", "together", "groq", "fireworks", "ollama", "openai"],
        default=None,
        help="LLM provider override (default: from LLM_PROVIDER env var)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    logger = logging.getLogger("podcast-cli")

    # Override provider if specified
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    # Build input contents list
    input_contents = []

    # Classify each --input by type
    for inp in args.input:
        if inp.startswith("http://") or inp.startswith("https://"):
            input_contents.append({"type": "url", "source": inp})
        elif Path(inp).suffix.lower() in (".pdf", ".docx", ".doc", ".txt"):
            input_contents.append({"type": "document", "source": str(Path(inp).resolve())})
        elif Path(inp).suffix.lower() in (".mp3", ".wav", ".m4a", ".flac", ".ogg"):
            input_contents.append({"type": "audio", "source": str(Path(inp).resolve())})
        else:
            input_contents.append({"type": "document", "source": str(Path(inp).resolve())})

    # Always add the topic as a topic-type input
    input_contents.append({"type": "topic", "source": args.topic})

    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    logger.info(f"Generating podcast: '{args.topic}'")
    logger.info(f"  Language: {args.language}, Duration: {args.duration}min, Format: {args.format}")
    logger.info(f"  Inputs: {len(input_contents)} items, Audience: {args.audience}")
    if args.provider:
        logger.info(f"  Provider: {args.provider}")

    # Run the pipeline
    from src.agents.graph import generate_podcast_sync

    try:
        final_state = generate_podcast_sync(
            user_request=args.topic,
            input_contents=input_contents,
            target_language=args.language,
            target_duration_minutes=args.duration,
            episode_format=args.format
        )

        # Report results
        status = final_state.get("processing_status")
        script = final_state.get("final_script", "")
        audio_path = final_state.get("audio_file_path")
        quality = final_state.get("overall_quality_score", 0)
        segments = final_state.get("script_segments", [])

        print("\n" + "=" * 60)
        print("GENERATION COMPLETE")
        print("=" * 60)
        print(f"Status: {status}")
        print(f"Segments: {len(segments)}")
        print(f"Quality Score: {quality:.2f}")

        if audio_path:
            print(f"Audio: {audio_path}")
        else:
            print("Audio: Not generated (TTS unavailable or failed)")

        if script:
            # Save script to file
            script_path = os.path.join(
                args.output_dir,
                f"script_{final_state.get('trace_id', 'unknown')[:8]}.txt"
            )
            with open(script_path, "w") as f:
                f.write(script)
            print(f"Script saved: {script_path}")

        print("=" * 60)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=args.verbose)
        sys.exit(1)


if __name__ == "__main__":
    main()
