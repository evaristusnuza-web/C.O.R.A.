# Friday — Personal Assistant

Friday is a local-first personal assistant built around `friday_jarvis2-main`. It runs as a browser app and does **not** need LiveKit. ElevenLabs provides voice transcription and spoken replies; an OpenAI-compatible model provides the assistant's reasoning and chat responses.

## What it can do

- Chat with an OpenAI-compatible language model.
- Record a voice message and transcribe it with ElevenLabs Scribe when configured; supported browsers have a speech-recognition fallback.
- Read replies aloud with ElevenLabs when configured; browser speech synthesis is the fallback.
- Keep conversation history and explicit personal memories in a local SQLite database.
- Look up current weather and search the web.
- Prepare email drafts. **Friday never sends a web-app email without your separate review and confirmation.** Gmail sending is optional.
- Optionally connect an n8n MCP SSE endpoint to expose extra tools, such as Spotify workflows.

Chat history and memories are stored locally, but prompts go to the model provider you configure. Voice recordings are sent to ElevenLabs for transcription and response text is sent to ElevenLabs when spoken replies are enabled. Weather, web search, email, and MCP tools also contact their configured services. Use a local OpenAI-compatible model if you do not want chat requests to go to a hosted model provider.

## Run the app

Use Python 3.11 or newer.

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

python -m pip install -r friday_jarvis2-main/requirements.txt
cp friday_jarvis2-main/.env.example friday_jarvis2-main/.env
```

Edit `friday_jarvis2-main/.env` and set:

- `OPENAI_API_KEY` for the model that powers Friday's chat. The default is `gpt-4o-mini`; change `OPENAI_MODEL` if your provider uses a different model.
- `ELEVENLABS_API_KEY` for ElevenLabs voice transcription and synthesis.
- `ELEVENLABS_VOICE_ID` for the voice Friday should use when reading replies aloud. Find the ID for a voice in your ElevenLabs account.

`OPENAI_BASE_URL` is optional for an OpenAI-compatible local model server. Keep `.env` private and never commit it.

Start Friday from the project folder:

```bash
cd friday_jarvis2-main
uvicorn web_app:app --host 127.0.0.1 --port 8000
```

Then open <http://127.0.0.1:8000>. Enable spoken replies with the **Voice off** control. Use the microphone button to record and transcribe a message; allow microphone access when prompted. The browser app calls ElevenLabs through the server, so the ElevenLabs key is never sent to the browser. The app creates `friday_jarvis2-main/data/friday.sqlite3` automatically; that database is ignored by Git and contains local chat history, memories, and email drafts.

## Optional integrations

### Gmail

Set `GMAIL_USER` and `GMAIL_APP_PASSWORD` in `.env` to send a reviewed draft. For Gmail, use a Google App Password rather than your normal account password. Friday first prepares a draft; review the recipient, subject, and body in the app, then explicitly choose **Review & send**.

### n8n / MCP

Set `N8N_MCP_SERVER_URL` to an MCP **SSE** endpoint in `.env`; if required, also set `N8N_MCP_SERVER_TOKEN`. The web app discovers tools when it starts. The Spotify instructions only apply if the MCP server actually exposes corresponding Spotify tools. Email-related MCP tools are hidden from the web app so they cannot bypass its review-before-send flow. If the optional server is offline, Friday still starts with its built-in tools.

## Privacy and safety

- The app has no sign-in system and is intended for one trusted user on a private machine.
- Keep it bound to `127.0.0.1`; do not expose it to the public internet or an untrusted network without adding authentication and HTTPS.
- API keys are read by the server and are not returned to the browser.
- Chat history and memories are local; chat prompts go to your configured model provider. Microphone recordings and text sent for spoken replies go to ElevenLabs.
- Web-app email is sent only after you review and confirm the draft.

## Legacy LiveKit files

`friday_jarvis2-main/agent.py`, `mcp_client/agent_tools.py`, and `friday_jarvis-main/` are the original LiveKit prototypes, retained as historical references. They are not part of the browser app and are not needed to run Friday. The current app uses ElevenLabs for voice and the core `requirements.txt` does not install LiveKit.

## Tests

```bash
cd friday_jarvis2-main
python -m unittest discover -s tests -v
```

## Project layout

- `friday_jarvis2-main/web_app.py` — app API, model/tool orchestration, SQLite storage, and ElevenLabs endpoints.
- `friday_jarvis2-main/static/` — browser interface, microphone recording, and audio playback.
- `friday_jarvis2-main/mcp_client/server.py` — optional MCP SSE transport; the Stdio class is a placeholder.
- `friday_jarvis2-main/agent.py` — legacy LiveKit prototype, not used by the app.
- `friday_jarvis-main/` — original first-version snapshot.

Please review the project-specific license in `friday_jarvis2-main/LICENSE` before redistribution or commercial use.
