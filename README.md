# Pipecat Voice Backend

This is the voice interview service built with Pipecat framework.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your API keys

# Run the server
python bot.py
```

## Environment Variables

```env
# Required
OPENAI_API_KEY=sk-...          # For Whisper STT
MINIMAX_API_KEY=sk-cp-...      # For LLM
PIPER_VOICE_PATH=/path/to/piper/voices

# Optional (Pipecat defaults)
LOG_LEVEL=INFO
```

## Architecture

Uses Pipecat's frame-based pipeline:
1. **VAD** → Voice Activity Detection (built-in)
2. **STT** → OpenAI Whisper for transcription
3. **LLM** → Minimax for response generation
4. **TTS** → Piper for audio output