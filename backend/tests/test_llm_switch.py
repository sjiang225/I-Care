"""Switching LLM providers (e.g. OpenAI -> Gemini's OpenAI-compatible endpoint).

Run from backend/: .venv/bin/python -m unittest discover -s tests -v
No network: the OpenAI client is replaced with a recorder.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.config import get_settings
from app.kb import retrieve
from app.kb.store import LocalVectorStore, Record
from app.llm.base import Message
from app.llm.openai_provider import OpenAIProvider


class RecordingCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return iter([])
        message = SimpleNamespace(content="ok", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], model=kwargs["model"],
                               model_dump=lambda: {})


def provider_with_recorder(reasoning_effort: str) -> tuple[OpenAIProvider, RecordingCompletions]:
    provider = OpenAIProvider(api_key="k", base_url="https://example.test/v1", chat_model="m",
                              embed_model="e", reasoning_effort=reasoning_effort)
    completions = RecordingCompletions()
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return provider, completions


class ReasoningEffortTest(unittest.TestCase):
    def test_sent_for_chat_and_stream_when_configured(self):
        provider, completions = provider_with_recorder("none")
        provider.chat([Message(role="user", content="hi")])
        list(provider.stream_chat([Message(role="user", content="hi")]))
        self.assertEqual([c.get("reasoning_effort") for c in completions.calls], ["none", "none"])

    def test_omitted_by_default_for_plain_openai_models(self):
        provider, completions = provider_with_recorder("")
        provider.chat([Message(role="user", content="hi")])
        list(provider.stream_chat([Message(role="user", content="hi")]))
        self.assertTrue(all("reasoning_effort" not in c for c in completions.calls))


class KnowledgeBaseModelGuardTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "kb.sqlite3")
        store = LocalVectorStore(self.path)
        store.add([Record(id="d:0", text="t", metadata={}, embedding=[1.0, 0.0])])
        store.set_meta("embed_model", "gemini-embedding-001")

    def tearDown(self):
        for fn in (get_settings, retrieve._store):
            fn.cache_clear()
        self.dir.cleanup()

    def open_with(self, embed_model: str):
        env = {"LLM_PROVIDER": "openai", "KB_DB_PATH": self.path, "OPENAI_EMBED_MODEL": embed_model}
        with patch.dict(os.environ, env):
            for fn in (get_settings, retrieve._store):
                fn.cache_clear()
            return retrieve._store()

    def test_matching_model_opens(self):
        self.assertEqual(self.open_with("gemini-embedding-001").count(), 1)

    def test_mismatched_model_fails_loudly(self):
        with self.assertRaisesRegex(RuntimeError, "embedded with 'gemini-embedding-001'"):
            self.open_with("text-embedding-3-small")


if __name__ == "__main__":
    unittest.main()
