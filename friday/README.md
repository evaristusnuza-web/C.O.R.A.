# Friday

This is the one active Friday assistant app. It uses ElevenLabs for voice and an OpenAI-compatible model for chat; it does not require LiveKit.

For the full install guide, configuration, integrations, privacy notes, and tests, see the [repository README](../README.md).

Quick start from the repository root:

```bash
python -m pip install -r friday/requirements.txt
cp friday/.env.example friday/.env
# Set OPENAI_API_KEY, ELEVENLABS_API_KEY, and ELEVENLABS_VOICE_ID in friday/.env.
python -m friday
```

The previous implementations are archived in `legacy/` for reference and are not part of the active app.
