# AI Podcast Generator

> A multi-agent system for generating culturally-adapted podcasts from multi-modal inputs
> **Status:** v2 pipeline implemented, research experiments in progress

## Overview

Transforms documents, audio, video, URLs, and topics into podcast scripts and audio using a LangGraph multi-agent pipeline with Knowledge Graph memory, two-layer verification, and reinforcement learning capabilities.

### Architecture

```
Input → Router → Gatherer → Generator → Verifier → Synthesizer → Audio
                    ↕              ↕           ↕
              Knowledge Graph   KG Facts    FM Monitors
```

- **Router**: Classifies inputs and routes to appropriate processors
- **Gatherer**: Extracts content, populates Knowledge Graph with facts and provenance
- **Generator**: Produces podcast scripts using KG-retrieved facts and persona system
- **Verifier**: Two-layer quality assurance (FM monitors + quality checkers + LLM fact checking)
- **Synthesizer**: Audio synthesis via VibeVoice, ElevenLabs, or gTTS fallback chain

## Quick Start

```bash
# Clone and install
git clone https://github.com/revathi-prasad/ai-builders-podcast.git
cd ai-builders-podcast
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy env template and add your API keys
cp .env.example .env
# Edit .env with your keys (at minimum: one LLM provider key)

# Generate a podcast
python -m src --topic "Introduction to Machine Learning" --duration 5 --verbose

# With specific options
python -m src --topic "AI Safety" --language hindi --format conversation --audience beginner
```

### Running Tests

```bash
pytest tests/ -v --tb=short
```

### API Server

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
# Health check: http://localhost:8000/health
# API docs: http://localhost:8000/docs
```

## Project Structure

```
src/
├── agents/
│   ├── graph.py              # Central LangGraph workflow (router→gatherer→generator→verifier→synthesizer)
│   ├── generator.py          # Script generation with persona system
│   ├── router.py             # Input classification and routing
│   └── synthesizer.py        # Audio synthesis (VibeVoice/ElevenLabs/gTTS)
├── api/
│   ├── main.py               # FastAPI server with SQLite persistence
│   ├── database.py           # SQLite persistence layer
│   └── runner.py             # Background job runner with real progress tracking
├── graph/
│   ├── manager.py            # Knowledge Graph CRUD (Kuzu)
│   └── schema.py             # KG schema (Topic, Fact, Source, Segment entities)
├── llm/
│   ├── factory.py            # Multi-provider LLM factory
│   ├── config.py             # Provider definitions (Anthropic, Groq, Together, Fireworks, Ollama, OpenAI)
│   └── providers/            # Provider implementations
├── rl/
│   ├── reward_model.py       # Engagement + quality reward models
│   └── trainer.py            # DPO/GRPO/SFT trainers (TRL-based with fallback)
├── tools/
│   ├── web_search.py         # Serper/Tavily web search
│   ├── pdf_processor.py      # PDF text extraction
│   ├── url_processor.py      # URL content fetching
│   └── audio_processor.py    # Audio transcription
├── verification/
│   ├── fm_monitors.py        # MAST failure mode monitors (Layer 1)
│   └── quality_checkers.py   # Quality checkers + LLM fact checker (Layer 2)
├── cli.py                    # CLI entry point
└── __main__.py               # python -m src support

tests/                        # pytest suite (8 test files)
frontend/                     # React + TypeScript web UI
archive/v1/                   # Archived v1 pipeline code
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Agent Framework | LangGraph (StateGraph) |
| Knowledge Graph | Kuzu (embedded, MIT license) |
| LLM | Multi-provider: Anthropic, Groq, Together, Fireworks, Ollama, OpenAI |
| TTS | VibeVoice → ElevenLabs → gTTS (fallback chain) |
| RL Training | TRL (DPO, GRPO, SFT) with LoRA/PEFT |
| API | FastAPI + SQLite (aiosqlite) |
| Frontend | React + TypeScript + Tailwind |
| Web Search | Serper (primary), Tavily (fallback) |

## Research Focus

This project is a research testbed for:

1. **Multi-Agent Coordination** — Handoff protocols, information preservation across agent boundaries
2. **RL for Creative Content** — FM-augmented rewards, credit assignment, engagement-based reward models
3. **Cultural Adaptation** — Beyond translation: persona-based cultural context for Hindi, Tamil, English
4. **Verification Systems** — Two-layer quality assurance combining heuristic monitors with LLM fact checking

See [docs/RESEARCH_ROADMAP.md](docs/RESEARCH_ROADMAP.md) for open research directions (17 research questions with code pointers).

## Datasets

Training datasets (DPO preference pairs, evaluation data, engagement feedback) will be published on HuggingFace at **[TBD]**.

## Supported Languages

- English
- Hindi (हिंदी)
- Tamil (தமிழ்)

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE_v2.md](docs/ARCHITECTURE_v2.md) | Full system architecture, components, tech stack |
| [RESEARCH_ROADMAP.md](docs/RESEARCH_ROADMAP.md) | Open research directions with code pointers |

## Related Work

- [AgentFlow](https://arxiv.org/abs/2510.05592) — In-the-Flow RL for multi-agent systems
- [MAST](https://arxiv.org/abs/2503.13657) — Multi-agent failure taxonomy
- [Graphiti](https://github.com/getzep/graphiti) — Temporal knowledge graphs for agents
- [DPO](https://arxiv.org/abs/2305.18290) — Direct Preference Optimization
- [GRPO](https://arxiv.org/abs/2402.03300) — Group Relative Policy Optimization

## License

MIT License — see LICENSE file for details.

## Author

Revathi Prasad — [GitHub](https://github.com/revathi-prasad)
