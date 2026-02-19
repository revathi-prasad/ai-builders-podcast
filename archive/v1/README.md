# AI Podcast Generator — v1 (Archived)

This directory contains the original v1 CLI pipeline, superseded by the v2 LangGraph multi-agent system in `src/`.

## Known Limitations

- **Mock web search**: `research_engine.py` lines 420-463 return hardcoded fake results from `example.com` instead of calling a real search API.
- **Stub PDF/DOCX reading**: `research_engine.py` lines 229-238 have incomplete document reading. The v2 system has a working `PDFProcessor` at `src/tools/pdf_processor.py`.
- **Hardcoded API keys**: `config.py` (not tracked in git) stores keys as class attributes. The v2 system uses `.env` files.
- **Single LLM provider**: Only supports Claude via direct `anthropic.Anthropic()`. The v2 system supports 6 providers via `src/llm/`.

## Usage (if needed)

```bash
cd archive/v1
pip install -r requirements_v1.txt
python main.py --topic "Your Topic" --language english --duration 20
```

Note: Requires `config.py` with valid API keys (not included in repo).
