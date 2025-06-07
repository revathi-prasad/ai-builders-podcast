"""
Main entry point for the AI Builders Podcast System

This script provides a command-line interface for generating podcast episodes
using the AI Builders Podcast System.
"""

import argparse
import logging
import os
import sys
from typing import Dict, List, Optional, Any

from config import ConstellationConfig, Language, EpisodeType
from models import EpisodeContext
from orchestrator import ConstellationOrchestrator

def setup_logging():
    """Set up logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('ai_builders.log')
        ]
    )

def main():
    """Main entry point for the AI Builders Podcast System"""
    setup_logging()
    
    parser = argparse.ArgumentParser(description="AI Builders Podcast System")
    
    # Basic episode information
    parser.add_argument("--topic", required=True, help="Episode topic")
    parser.add_argument("--language", default="english", choices=["english", "hindi", "tamil"],
                      help="Primary language for the episode")
    parser.add_argument("--type", default="introduction", 
                      choices=["introduction", "build", "conversation", "interview", "summary"],
                      help="Episode type")
    
    # Additional configuration
    parser.add_argument("--cost-tier", default="standard", choices=["economy", "standard", "premium"],
                      help="Cost tier for generation")
    parser.add_argument("--duration", type=int, default=20, help="Target duration in minutes")
    parser.add_argument("--episode-number", type=int, default=0, help="Episode number")
    
    # Optional features
    parser.add_argument("--no-intro", action="store_true", help="Skip standard intro")
    parser.add_argument("--no-outro", action="store_true", help="Skip standard outro")
    parser.add_argument("--transcript-only", action="store_true", 
                      help="Generate only transcript without audio")
    parser.add_argument("--use-transcript", 
                      help="Use a pre-defined transcript file instead of generating new content")
    parser.add_argument("--reference-material", 
                      help="Path to reference material for content enrichment")
    
    # Secondary languages for transformation
    parser.add_argument("--secondary-languages", nargs="+", choices=["english", "hindi", "tamil"],
                      help="Secondary languages for transformation")
    parser.add_argument("--preserve-standard-sections", action="store_true",
                  help="Preserve standard intros and outros when transforming to secondary languages")
    
    # Document-related configuration
    parser.add_argument("--documents", nargs="+", 
                      help="Paths to custom documents for research")
    parser.add_argument("--documents-dir", 
                      help="Directory containing documents for research")
    parser.add_argument("--recursive", action="store_true",
                      help="Recursively search for documents in subdirectories")
    
    # Output configuration
    parser.add_argument("--output-dir", default="episodes", help="Output directory for episodes")
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Check API keys if not in transcript-only mode
    if not args.transcript_only:
        if ConstellationConfig.CLAUDE_API_KEY == "your_claude_api_key":
            print("⚠️ Please set your Claude API key in ConstellationConfig")
            return
        
        if ConstellationConfig.ELEVENLABS_API_KEY == "your_elevenlabs_api_key":
            print("⚠️ Please set your ElevenLabs API key in ConstellationConfig")
            return
    
    # Convert secondary languages to Language enum
    secondary_languages = []
    if args.secondary_languages:
        for lang in args.secondary_languages:
            if lang != args.language:  # Skip if same as primary language
                secondary_languages.append(Language(lang))
    
    # Load reference material if provided
    reference_material = None
    if args.reference_material:
        if os.path.exists(args.reference_material):
            with open(args.reference_material, "r", encoding="utf-8") as f:
                reference_material = f.read()
        else:
            print(f"⚠️ Reference material file not found: {args.reference_material}")
            return
    
    # Process document paths from arguments and directories
    document_paths = []
    
    # Add individual documents
    if args.documents:
        for doc_path in args.documents:
            if os.path.exists(doc_path):
                document_paths.append(doc_path)
            else:
                print(f"⚠️ Document not found: {doc_path}")
    
    # Add documents from directory
    if args.documents_dir:
        if os.path.exists(args.documents_dir):
            orchestrator = ConstellationOrchestrator()
            dir_docs = orchestrator.research_engine.load_documents_from_directory(
                args.documents_dir, args.recursive
            )
            document_paths.extend(dir_docs)
            print(f"📚 Found {len(dir_docs)} documents in {args.documents_dir}")
        else:
            print(f"⚠️ Documents directory not found: {args.documents_dir}")
    
    # Create document directories if they don't exist
    for doc_dir in ConstellationConfig.RESEARCH_CONFIG["document_directories"].values():
        os.makedirs(doc_dir, exist_ok=True)
    
    # Create episode context
    context = EpisodeContext(
        topic=args.topic,
        primary_language=Language(args.language),
        secondary_languages=secondary_languages,
        episode_type=EpisodeType(args.type),
        target_duration=args.duration,
        cost_tier=args.cost_tier,
        cultural_focus="startup_ecosystem",  # Default, can be customized
        episode_number=args.episode_number,
        include_intro=not args.no_intro,
        include_outro=not args.no_outro,
        transcript_only=args.transcript_only,
        use_transcript=args.use_transcript,
        reference_material=reference_material,
        preserve_standard_sections=args.preserve_standard_sections  # Add the new parameter
    )
    
    # Generate episode
    orchestrator = ConstellationOrchestrator()
    
    # Add documents to research engine if provided
    if document_paths:
        print(f"🔍 Using {len(document_paths)} custom documents for research")
        result = orchestrator.generate_episode_with_documents(context, document_paths)
    else:
        # Standard generation without documents
        result = orchestrator.generate_episode(context)
    
    print(f"\n🎉 Episode content generated successfully!")
    
    # Save transcript to file
    transcript_file = f"{args.output_dir}/ep{args.episode_number:02d}_{args.topic.replace(' ', '_')}_{args.language}.txt"
    with open(transcript_file, "w", encoding="utf-8") as f:
        f.write(result.transcript)
    
    print(f"📝 Transcript saved to: {transcript_file}")
    
    # Save secondary language transcripts if any
    for transformation in result.transformations:
        secondary_lang = transformation.target_language.value
        secondary_transcript = "\n\n".join([
            f"{segment.speaker}: {segment.text}" if segment.speaker != "MUSIC" else segment.text
            for segment in transformation.transformed_content
        ])
        
        secondary_file = f"{args.output_dir}/ep{args.episode_number:02d}_{args.topic.replace(' ', '_')}_{secondary_lang}.txt"
        with open(secondary_file, "w", encoding="utf-8") as f:
            f.write(secondary_transcript)
        
        print(f"📝 {secondary_lang.capitalize()} transcript saved to: {secondary_file}")
    
    # Print audio information if generated
    if not args.transcript_only and result.audio_file:
        print(f"📁 Audio file: {result.audio_file}")
        print(f"💰 Estimated cost: ${result.metadata.get('cost_breakdown', {}).get('total', 0):.2f}")
        print(f"⏱️ Duration estimate: {result.metadata.get('duration_estimate', 0) / 60:.1f} minutes")
    elif args.transcript_only:
        print(f"💡 Running in transcript-only mode - no audio was generated")
        print(f"⏱️ Estimated duration if recorded: {result.metadata.get('duration_estimate', 0) / 60:.1f} minutes")
    
    # Print episode statistics
    if "validation" in result.metadata:
        validation = result.metadata["validation"]
        stats = validation["stats"]
        
        print(f"\n📊 Episode Statistics:")
        print(f"   - Total segments: {stats['total_segments']}")
        print(f"   - Spoken segments: {stats['spoken_segments']}")
        print(f"   - Total words: {stats['total_words']}")
        print(f"   - Average words per segment: {stats['avg_words_per_segment']:.1f}")
        print(f"   - Estimated duration: {stats['estimated_duration_minutes']:.1f} minutes")
        
        if validation["warnings"]:
            print(f"\n⚠️ Validation Warnings:")
            for warning in validation["warnings"]:
                print(f"   - {warning}")
    
    # Print research information if available
    if result.research:
        print(f"\n📚 Research Information:")
        print(f"   - Topic: {result.research.topic}")
        print(f"   - Key Points: {len(result.research.key_points)}")
        print(f"   - Citations: {len(result.research.citations)}")
        
        # Save research summary to file
        research_file = f"{args.output_dir}/ep{args.episode_number:02d}_{args.topic.replace(' ', '_')}_{args.language}_research.md"
        with open(research_file, "w", encoding="utf-8") as f:
            f.write(result.research.to_markdown())
        
        print(f"📝 Research summary saved to: {research_file}")
        
        # Print GitHub resources if available
        if "github_resources" in result.metadata and result.metadata["github_resources"]:
            github = result.metadata["github_resources"]
            print(f"\n📦 GitHub Resources:")
            print(f"   - Citation Path: {github['citation_path']}")
            print(f"   - Resource Path: {github['resource_path']}")
    
    # Print podcast title
    if "podcast_title" in result.metadata:
        print(f"\n🎙️ Podcast Title: {result.metadata['podcast_title']}")

if __name__ == "__main__":
    main()
