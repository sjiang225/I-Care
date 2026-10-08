"""Regression coverage for retiring inferred wellbeing, using synthetic data only.

Run from backend/: .venv/bin/python -m unittest discover -s tests -v
No network, real model, or existing application database is used.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import Database, get_db
from app.kb.retrieve import _store
from app.kb.store import Record
from app.llm.base import ChatResult, ToolCall
from app.llm.factory import get_llm
from app.llm.mock_provider import MockProvider
from app.main import app
from app.tools.base import registry


class RecordingProvider(MockProvider):
    """Drive each real agent path deterministically and capture its model input."""

    def __init__(self):
        super().__init__()
        self.route = {"needs_education": True}
        self.tool_requests = []
        self.prompts = []

    def chat(self, messages, **kwargs):
        self.tool_requests.extend(t.name for t in kwargs.get("tools", []))
        if kwargs.get("tool_choice", {}).get("function", {}).get("name") == "route":
            return ChatResult(
                content="", model="test",
                tool_calls=[ToolCall("test-route", "route", self.route.copy())],
            )
        return super().chat(messages, **kwargs)

    def stream_chat(self, messages, **kwargs):
        self.prompts.append(messages)
        yield "Synthetic support response."


def events(response):
    parsed = []
    for block in response.text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        parsed.append((fields["event"], json.loads(fields["data"])))
    return parsed


class WellbeingRetirementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="icare-retirement-test-")
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {
            "LLM_PROVIDER": "mock",
            "APP_DB_PATH": self.tmp.name + "/app.sqlite3",
            "KB_DB_PATH": self.tmp.name + "/kb.sqlite3",
        })
        env.start()
        self.addCleanup(env.stop)
        for fn in (get_settings, get_db, get_llm, _store):
            fn.cache_clear()
        self.provider = RecordingProvider()
        provider_patch = patch("app.llm.factory.MockProvider", return_value=self.provider)
        provider_patch.start()
        self.addCleanup(provider_patch.stop)
        self.db = get_db()
        self.kb = _store()
        self.addCleanup(self.close_databases)
        self.kb.add([Record(
            id="sleep:0", text="Synthetic sleep reference.",
            metadata={"doc_id": "sleep", "title": "Sleep reference",
                      "category": "sleep", "url": "https://example.test/sleep.pdf"},
            embedding=self.provider.embed(["Synthetic sleep reference."])[0],
        )])
        self.client = self.enterContext(TestClient(app))
        account = self.client.post("/api/auth/register", json={
            "email": "review@example.test", "password": "synthetic-password",
        }).json()
        self.headers = {"Authorization": "Bearer " + account["token"]}
        self.owner = f"u:{account['user']['id']}"
        # Represent an existing installation with high-stress inferred records.
        for owner in (self.owner, "legacy-guest"):
            self.db._conn.executemany(
                "INSERT INTO wellbeing_logs (session_id, ts, stress_level, emotions, note)"
                " VALUES (?, ?, ?, ?, ?)",
                [(owner, i, score, '["synthetic-emotion"]', "private-legacy-note")
                 for i, score in enumerate((4, 5, 5))],
            )
        self.db._conn.commit()
        self.original_records = self.records()
        self.queries = []
        self.db._conn.set_trace_callback(self.queries.append)

    def close_databases(self):
        self.db._conn.close()
        self.kb._conn.close()
        for fn in (get_settings, get_db, get_llm, _store):
            fn.cache_clear()

    def records(self):
        return self.db._conn.execute("SELECT * FROM wellbeing_logs ORDER BY id").fetchall()

    def chat(self, text, *, session_id="legacy-guest", headers=None):
        response = self.client.post("/api/chat", headers=headers, json={
            "session_id": session_id,
            "messages": [{"role": "user", "content": text}],
        })
        self.assertEqual(response.status_code, 200)
        result = events(response)
        self.assertIn(("done", {}), result)
        self.assertNotIn("error", [kind for kind, _ in result])
        self.assertTrue(any(kind == "delta" and payload["text"] for kind, payload in result))
        return result

    def test_chat_paths_support_users_without_reading_or_writing_old_scores(self):
        cases = [
            ("education", "How can I help with sleep?", {"needs_education": True}, ["education"]),
            ("resources", "Find care in Bergen County", {
                "needs_resources": True, "county": "Bergen",
            }, ["education"]),
            ("emotion", "I feel overwhelmed", {"needs_emotion": True}, ["emotion"]),
            ("peer", "I feel alone", {"needs_peer": True}, ["peer"]),
            ("mixed", "I am exhausted. How can I help with sleep?", {
                "needs_emotion": True, "needs_education": True,
            }, ["emotion", "education"]),
            ("crisis", "I want to die", {"needs_emotion": True}, ["emotion"]),
        ]
        for headers in (None, self.headers):
            for name, text, route, plan in cases:
                with self.subTest(path=name, authenticated=headers is not None):
                    self.provider.route = route
                    self.provider.tool_requests.clear()
                    self.queries.clear()
                    result = self.chat(text, headers=headers)
                    self.assertIn(("signal", {"plan": plan}), result)
                    self.assertFalse(any("wellbeing" in payload for kind, payload in result if kind == "signal"))
                    self.assertNotIn("log_wellbeing", self.provider.tool_requests)
                    self.assertFalse(any("wellbeing_logs" in q.lower() for q in self.queries))
                    self.assertFalse(any("self_assessments" in q.lower() for q in self.queries))
                    self.assertEqual(self.records(), self.original_records)
                    if name in ("education", "resources", "mixed"):
                        self.assertTrue(any(kind == "sources" and payload["sources"] for kind, payload in result))
                    if name == "resources":
                        resources = next(payload for kind, payload in result if kind == "resources")
                        self.assertTrue(resources["helplines"])
                        self.assertTrue(resources["facilities"])
                    if name == "peer":
                        self.assertIn(("signal", {"agent": "peer"}), result)
                    if name == "crisis":
                        self.assertIn(("signal", {"safety": "self_harm"}), result)
                        self.assertIn("988", "".join(payload["text"] for kind, payload in result if kind == "delta"))
        history = self.client.get("/api/history", headers=self.headers).json()
        self.assertEqual([m["role"] for m in history["latest_messages"]], ["user", "assistant"])

    def test_old_stress_does_not_change_prompts_or_recommendations(self):
        for route in ({"needs_education": True}, {"needs_emotion": True}, {"needs_peer": True}):
            with self.subTest(route=route):
                self.provider.route = route
                self.provider.prompts.clear()
                old = self.chat("How can you help?", session_id="legacy-guest")
                old_prompts = self.provider.prompts.copy()
                self.provider.prompts.clear()
                new = self.chat("How can you help?", session_id="new-guest")
                self.assertEqual(old, new)
                self.assertEqual(old_prompts, self.provider.prompts)

    def test_retired_endpoint_never_exposes_legacy_data(self):
        for headers in (None, self.headers, {"Authorization": "Bearer invalid"}):
            for session_id in (self.owner, "legacy-guest", "default"):
                with self.subTest(headers=bool(headers), session_id=session_id):
                    self.queries.clear()
                    response = self.client.get("/api/wellbeing", headers=headers,
                                               params={"session_id": session_id})
                    self.assertEqual(response.status_code, 410)
                    self.assertEqual(response.headers["cache-control"], "no-store")
                    self.assertEqual(set(response.json()), {"detail"})
                    self.assertNotIn("private-legacy-note", response.text)
                    self.assertFalse(any("wellbeing_logs" in q.lower() for q in self.queries))

    def test_legacy_records_survive_database_initialization(self):
        reopened = Database(self.tmp.name + "/app.sqlite3")
        try:
            records = reopened._conn.execute("SELECT * FROM wellbeing_logs ORDER BY id").fetchall()
            self.assertEqual(records, self.original_records)
        finally:
            reopened._conn.close()

    def test_retired_tool_cannot_write_records(self):
        result = registry.dispatch(ToolCall("old-call", "log_wellbeing", {
            "stress_level": 5, "emotions": ["synthetic"],
        }), self.owner)
        self.assertIn("error", result)
        self.assertEqual(self.records(), self.original_records)


if __name__ == "__main__":
    unittest.main()
