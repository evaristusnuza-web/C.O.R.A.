# Friday Personal Assistant

The repository now has **one active Friday project** in the `friday/` directory. It combines the useful assistant capabilities from both earlier folders into one browser app: an OpenAI-compatible model for chat and reasoning, ElevenLabs for voice transcription and spoken replies, SQLite memory/history, weather and web search, reviewed email drafts, and optional n8n/MCP tools. LiveKit is not used by the active app.

## Run Friday

Use Python 3.11 or newer. From the repository root:

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

python -m pip install -r friday/requirements.txt
cp friday/.env.example friday/.env
```

Edit `friday/.env` and set:

- `OPENAI_API_KEY` for the model that powers chat. The default is `gpt-4o-mini`; update `OPENAI_MODEL` for your provider/model.
- `ELEVENLABS_API_KEY` for voice transcription and synthesis.
- `ELEVENLABS_VOICE_ID` for Friday's spoken replies.

Then run from the repository root:

```bash
python -m friday
```

Open <http://127.0.0.1:8000>. Or run with Uvicorn directly:

```bash
uvicorn friday.web_app:app --host 127.0.0.1 --port 8000
```

Friday records microphone audio and sends it to ElevenLabs Scribe when configured; spoken replies use ElevenLabs when configured. Browser speech features are fallbacks. Chat prompts go to your configured model provider. The local SQLite database is created at `friday/data/friday.sqlite3` and is ignored by Git.

## Optional integrations

- **Gmail:** set `GMAIL_USER` and `GMAIL_APP_PASSWORD` to send a draft. Friday will not send from the browser app until you review the recipient, subject, and body and confirm in the UI. Use a Google App Password, not your normal password.
- **n8n/MCP:** set `N8N_MCP_SERVER_URL` to an MCP SSE endpoint, and `N8N_MCP_SERVER_TOKEN` if required. Friday loads remote tools at startup. Email-related MCP tools are hidden so they cannot bypass the draft-confirmation flow.
- **OpenAI-compatible local model:** set `OPENAI_BASE_URL` and the corresponding API key value in `.env`.

## Privacy and safety

- The app has no sign-in and is intended for one trusted user on a private machine. Keep it bound to `127.0.0.1`; do not expose it publicly without authentication and HTTPS.
- API keys remain server-side and are not sent to the browser.
- Chat history and memories are local, but prompts are sent to the model provider. Voice recordings and text-to-speech requests go to ElevenLabs.
- Email is sent only after a user reviews and confirms its draft.

## Tests

From the repository root:

```bash
python -m unittest discover -s friday/tests -v
```

## Project layout

- `friday/` — the single active assistant app.
- `friday/static/` — browser interface, microphone recording, and audio playback.
- `friday/mcp_client/` — MCP SSE transport used by the active app.
- `friday/legacy/first_version/` — original first LiveKit prototype, retained for reference.
- `friday/legacy/livekit_worker/` — previous LiveKit worker and adapters, retained for reference only.
- `friday/LICENSE` and `friday/thirdparty/` — project and third-party license files.

The older source has been consolidated under `friday/legacy/`; use `friday/` for all normal setup and development. Review `friday/LICENSE` before redistribution or commercial use.
