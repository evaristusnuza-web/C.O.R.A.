import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from friday import web_app


class FridayWebAppTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "FRIDAY_DB_PATH": os.path.join(self.tempdir.name, "test.sqlite3"),
                "OPENAI_API_KEY": "",
                "GMAIL_USER": "",
                "GMAIL_APP_PASSWORD": "",
                "ELEVENLABS_API_KEY": "",
                "ELEVENLABS_VOICE_ID": "",
                "N8N_MCP_SERVER_URL": "",
            },
            clear=False,
        )
        self.env.start()
        self.client_context = TestClient(web_app.app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.env.stop()
        self.tempdir.cleanup()

    def new_conversation(self):
        response = self.client.post("/api/conversations", json={})
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_health_and_static_app(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertFalse(health.json()["model_configured"])
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Friday", page.text)

    def test_conversations_and_local_memories(self):
        conversation_id = self.new_conversation()
        memory = self.client.post("/api/memories", json={"memory": "I prefer concise answers."})
        self.assertEqual(memory.status_code, 201)
        self.assertEqual(memory.json()["content"], "I prefer concise answers.")

        saved = self.client.get("/api/memories")
        self.assertEqual(len(saved.json()), 1)
        removed = self.client.delete(f"/api/memories/{memory.json()['id']}")
        self.assertEqual(removed.status_code, 204)

        conversation = self.client.get(f"/api/conversations/{conversation_id}")
        self.assertEqual(conversation.status_code, 200)
        self.assertEqual(conversation.json()["messages"], [])

    def test_chat_reports_missing_model_key_without_saving_prompt(self):
        conversation_id = self.new_conversation()
        response = self.client.post(
            "/api/chat",
            json={"conversation_id": conversation_id, "message": "Hello Friday"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENAI_API_KEY", response.json()["detail"])
        conversation = self.client.get(f"/api/conversations/{conversation_id}")
        self.assertEqual(conversation.json()["messages"], [])

    def test_email_requires_confirmation_and_records_delivery(self):
        conversation_id = self.new_conversation()
        draft = web_app._create_email_draft(
            conversation_id,
            "boss@example.com",
            None,
            "A short update",
            "Hello, here is the update.",
        )
        with patch.dict(os.environ, {"GMAIL_USER": "sender@example.com", "GMAIL_APP_PASSWORD": "test-password"}):
            unconfirmed = self.client.post(
                f"/api/drafts/{draft['id']}/send", json={"confirm": False}
            )
            self.assertEqual(unconfirmed.status_code, 400)
            with patch.object(web_app, "_send_email_sync") as send_email:
                sent = self.client.post(
                    f"/api/drafts/{draft['id']}/send", json={"confirm": True}
                )
            self.assertEqual(sent.status_code, 200)
            self.assertEqual(sent.json()["status"], "sent")
            send_email.assert_called_once()
        self.assertEqual(web_app._get_draft(draft["id"])["status"], "sent")

    def test_chat_runs_model_tool_calls_and_persists_memory(self):
        conversation_id = self.new_conversation()

        tool_call = SimpleNamespace(
            id="call_memory_1",
            function=SimpleNamespace(
                name="remember_fact",
                arguments=json.dumps({"fact": "I prefer practical suggestions."}),
            ),
            model_dump=lambda exclude_none=True: {
                "id": "call_memory_1",
                "type": "function",
                "function": {
                    "name": "remember_fact",
                    "arguments": json.dumps({"fact": "I prefer practical suggestions."}),
                },
            },
        )
        tool_reply = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[tool_call]))]
        )
        final_reply = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="I'll keep that in mind.", tool_calls=None))]
        )

        class FakeCompletions:
            def __init__(self):
                self.replies = [tool_reply, final_reply]
                self.calls = 0

            async def create(self, **kwargs):
                self.calls += 1
                return self.replies.pop(0)

        completions = FakeCompletions()
        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        with patch.object(web_app, "_get_openai_client", return_value=fake_client):
            response = self.client.post(
                "/api/chat",
                json={"conversation_id": conversation_id, "message": "Remember that I prefer practical suggestions."},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["assistant_message"]["content"], "I'll keep that in mind.")
        self.assertEqual(completions.calls, 2)
        self.assertEqual(web_app._list_memories()[0]["content"], "I prefer practical suggestions.")
        messages = self.client.get(f"/api/conversations/{conversation_id}").json()["messages"]
        self.assertEqual([message["role"] for message in messages], ["user", "assistant"])

    def test_elevenlabs_endpoints_require_configuration(self):
        speech = self.client.post("/api/speech", json={"text": "Hello there."})
        self.assertEqual(speech.status_code, 503)
        self.assertIn("ELEVENLABS_API_KEY", speech.json()["detail"])

        transcription = self.client.post(
            "/api/transcribe",
            files={"file": ("sample.webm", b"audio bytes", "audio/webm")},
        )
        self.assertEqual(transcription.status_code, 503)
        self.assertIn("ELEVENLABS_API_KEY", transcription.json()["detail"])

    def test_elevenlabs_speech_and_transcription_proxy(self):
        class FakeAsyncClient:
            def __init__(self, response):
                self.fake_response = response
                self.request = None

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def post(self, *args, **kwargs):
                self.request = (args, kwargs)
                return self.fake_response

        with patch.dict(
            os.environ,
            {
                "ELEVENLABS_API_KEY": "test-elevenlabs-key",
                "ELEVENLABS_VOICE_ID": "test-voice-id",
            },
        ):
            speech_client = FakeAsyncClient(
                SimpleNamespace(is_error=False, content=b"fake-mp3", headers={"content-type": "audio/mpeg"})
            )
            with patch.object(web_app.httpx, "AsyncClient", return_value=speech_client):
                speech = self.client.post("/api/speech", json={"text": "Hello there."})
            self.assertEqual(speech.status_code, 200)
            self.assertEqual(speech.content, b"fake-mp3")
            self.assertEqual(speech.headers["content-type"], "audio/mpeg")
            self.assertIn("xi-api-key", speech_client.request[1]["headers"])

            transcription_client = FakeAsyncClient(
                SimpleNamespace(is_error=False, json=lambda: {"text": "Hello Friday."})
            )
            with patch.object(web_app.httpx, "AsyncClient", return_value=transcription_client):
                transcription = self.client.post(
                    "/api/transcribe",
                    files={"file": ("recording.webm", b"fake-audio", "audio/webm")},
                )
            self.assertEqual(transcription.status_code, 200)
            self.assertEqual(transcription.json()["text"], "Hello Friday.")
            self.assertEqual(transcription_client.request[1]["data"]["model_id"], "scribe_v2")

    def test_invalid_email_address_is_rejected(self):
        conversation_id = self.new_conversation()
        with self.assertRaises(ValueError):
            web_app._create_email_draft(
                conversation_id, "not-an-email", None, "Subject", "Body"
            )


if __name__ == "__main__":
    unittest.main()
