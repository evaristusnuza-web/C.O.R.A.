# Friday Personal Assistant

This directory contains the current browser app. It uses an OpenAI-compatible model for chat and ElevenLabs for voice transcription and spoken replies; **LiveKit is not used by the app**.

For setup, API configuration, privacy notes, and optional integrations, see the [repository README](../README.md).

Quick start:

```bash
python -m pip install -r requirements.txt
cp .env.example .env
# Set OPENAI_API_KEY, ELEVENLABS_API_KEY, and ELEVENLABS_VOICE_ID in .env.
uvicorn web_app:app --host 127.0.0.1 --port 8000
```

The legacy `agent.py` file is retained as a reference and is not required to run the app.

## Licenses

- Proprietary portions: See [`LICENSE`](LICENSE) for personal/educational-use terms and restrictions.
- The `mcp_client` folder includes portions licensed under the MIT License; see [`thirdparty/LICENSE-LIVEKIT`](thirdparty/LICENSE-LIVEKIT).
