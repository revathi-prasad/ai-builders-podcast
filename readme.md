# AI Builders Podcast System

A comprehensive podcast generation system that creates multilingual, culturally-adapted AI host conversations with a focus on real building over theory.

Spotify Links to the Podcast: 
1. **English:** https://open.spotify.com/show/5EL3E8QlPYtp5R7Nm351Tv?si=a21157be054e49f1
2. **Hindi:** https://open.spotify.com/show/1pPhCIW4pbH9xQXtAvhPSD?si=8ac098fafcd54d37
3. **Tamil:** https://open.spotify.com/show/52q6VK5e7Yocu9J6O2wWHP?si=1fa2bd1cc743405c

## Core Features

- **Multilingual Content**: Generate content in English, Hindi, and Tamil with cultural adaptation (not just translation)
- **Research Integration**: Web research and citation support to create well-informed content
- **Cultural Adaptation**: Region-specific examples, analogies, and perspectives
- **AI Personality Engine**: Distinct AI host personalities maintained across episodes
- **Audio Production Pipeline**: Voice synthesis with ElevenLabs, batch processing, and music integration
- **Intelligent Caching**: Reduce costs by caching API responses and audio files

## System Architecture

The system follows a modular design with the following components:

1. **Configuration (config.py)**
   - Centralized system settings and language-specific configurations

2. **Data Models (models.py)**
   - Structured data types for episodes, research, and transformations

3. **Intelligent Cache (cache.py)**
   - SQLite-based caching system for API responses and audio files

4. **Research Engine (research_engine.py)**
   - Web search integration and research synthesis

5. **Personality Engine (personality_engine.py)**
   - Culturally-adapted AI host personality and conversation generation

6. **Transformation Engine (transformation.py)**
   - Content adaptation between languages with cultural context

7. **Audio Pipeline (audio_pipeline.py)**
   - Voice synthesis and audio processing

8. **Main Orchestrator (orchestrator.py)**
   - Coordinates all components for episode generation

9. **Command-line Interface (main.py)**
   - User-friendly command-line interface for podcast generation

## Getting Started

### Prerequisites

- Python 3.8+
- [Claude API Key](https://www.anthropic.com/)
- [ElevenLabs API Key](https://elevenlabs.io/)
- `pydub` (for audio processing)
- `anthropic` Python SDK

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ai-builders-podcast.git
   cd ai-builders-podcast
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Update API keys in `config.py`:
   ```python
   CLAUDE_API_KEY = "your_claude_api_key"
   ELEVENLABS_API_KEY = "your_elevenlabs_api_key"
   ```

4. Create the required directories:
   ```bash
   mkdir -p episodes audio-files assets/intros assets/outros
   ```

### Usage

Generate a basic episode:
```bash
python main.py --topic "Future-Proofing Your Career with AI" --language english --type conversation --episode-number 1
```

Generate a Hindi episode:
```bash
python main.py --topic "AI Skills for 2025" --language hindi --type build --episode-number 2
```

Generate Tamil episode with secondary languages:
```bash
python main.py --topic "AI in Healthcare" --language tamil --type conversation --episode-number 3 --secondary-languages english hindi
```

Generate transcript only (no audio):
```bash
python main.py --topic "AI Ethics" --language english --type conversation --episode-number 4 --transcript-only
```

### Using Custom Documents for Research

```bash
# Use specific documents
python main.py --topic "AI in Agriculture" --language english --documents docs/ai_agriculture_report.pdf docs/india_agritech.txt

# Use all documents in a directory
python main.py --topic "Future of Remote Work" --language hindi --documents-dir documents/research

# Search recursively in subdirectories
python main.py --topic "Healthcare AI" --language tamil --documents-dir documents --recursive
```

### Command-line Options

```
usage: main.py [-h] --topic TOPIC [--language {english,hindi,tamil}] [--type {introduction,build,conversation,interview,summary}]
               [--cost-tier {economy,standard,premium}] [--duration DURATION] [--episode-number EPISODE_NUMBER] [--no-intro]
               [--no-outro] [--transcript-only] [--use-transcript USE_TRANSCRIPT] [--reference-material REFERENCE_MATERIAL]
               [--secondary-languages {english,hindi,tamil} [{english,hindi,tamil} ...]] [--output-dir OUTPUT_DIR]

AI Builders Podcast System

options:
  -h, --help            show this help message and exit
  --topic TOPIC         Episode topic
  --language {english,hindi,tamil}
                        Primary language for the episode
  --type {introduction,build,conversation,interview,summary}
                        Episode type
  --cost-tier {economy,standard,premium}
                        Cost tier for generation
  --duration DURATION   Target duration in minutes
  --episode-number EPISODE_NUMBER
                        Episode number
  --no-intro            Skip standard intro
  --no-outro            Skip standard outro
  --transcript-only     Generate only transcript without audio
  --use-transcript USE_TRANSCRIPT
                        Use a pre-defined transcript file instead of generating new content
  --reference-material REFERENCE_MATERIAL
                        Path to reference material for content enrichment
  --documents DOCUMENTS [DOCUMENTS ...]
                        Paths to custom documents for research
  --documents-dir DOCUMENTS_DIR
                        Directory containing documents for research
  --recursive           Recursively search for documents in subdirectories
  --secondary-languages {english,hindi,tamil} [{english,hindi,tamil} ...]
                        Secondary languages for transformation
  --output-dir OUTPUT_DIR
                        Output directory for episodes
```

## Podcast Titles by Language

- **English**: "Future Proof with AI"
- **Hindi**: "नई तकनीक, नए अवसर" (New Technology, New Opportunities)
- **Tamil**: "புதிய மனிதருடன் ஆழ்நோக்கம்" (Deep Dive with the New Human)

## Customization

### Adding New Languages

1. Update the `Language` enum in `config.py`
2. Add voice configurations in `VOICE_LIBRARY`
3. Add transformation guidelines in `TRANSFORMATION_GUIDELINES`
4. Add regional examples in `REGIONAL_EXAMPLES`
5. Add standard intros and outros in `STANDARD_INTROS` and `STANDARD_OUTROS`
6. Add cultural contexts in `CULTURAL_CONTEXTS`

### Adding New Episode Types

1. Update the `EpisodeType` enum in `config.py`
2. Add episode length configuration in `EPISODE_LENGTH`
3. Add episode planning method in `CulturalPersonalityEngine`
4. Add episode generation method in `ConstellationOrchestrator`

## Research and Citation Support

The system includes a research engine that:

1. Gathers information from web searches (simulated in the current version)
2. Synthesizes findings into a structured research result
3. Creates citations in various formats (APA, MLA)
4. Generates GitHub resources for research references

## License

This project is licensed under the MIT License - see the LICENSE file for details.
