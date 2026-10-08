"""Catalogue coverage and per-answer citation persistence, using synthetic data."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.agents.education import Source, build_context_and_sources
from app.db import Database
from app.kb.sources import SourceDoc, load_sources
from app.tools.resources import pick_videos
from app.main import app


class LibraryTests(unittest.TestCase):
    def test_public_catalogue_matches_entire_manifest_without_database_or_model(self):
        with TestClient(app) as client, \
             patch("app.db.get_db", side_effect=AssertionError("No database needed")), \
             patch("app.llm.factory.get_llm", side_effect=AssertionError("No model needed")):
            response = client.get("/api/library")
        self.assertEqual(response.status_code, 200)
        catalogue = response.json()
        expected = load_sources()
        self.assertEqual(len(catalogue["documents"]), len(expected))
        self.assertEqual(len({d["id"] for d in catalogue["documents"]}), len(expected))
        self.assertEqual(catalogue["documents"], [
            {"id": d.id, "title": d.title, "category": d.category, "url": d.url_en}
            for d in expected
        ])
        video_manifest = json.loads((Path(__file__).parents[1] / "app/tools/data/videos.json").read_text())["videos"]
        self.assertEqual(catalogue["videos"], [{
            "id": v["youtube_id"], "title": v["title"], "category": v["category"],
            "language": v["language"], "url": v["url"],
        } for v in video_manifest])
        self.assertEqual(len({v["id"] for v in catalogue["videos"]}), len(video_manifest))
        self.assertEqual({c["id"] for c in catalogue["categories"]},
                         {d.category for d in expected} | {v["category"] for v in video_manifest})

    def test_new_categories_and_unavailable_urls_are_not_silently_omitted(self):
        sources = [SourceDoc("new", "New guide", "new_topic", None, None),
                   SourceDoc("unsafe", "Unsafe link", "new_topic", "javascript:alert(1)", None)]
        with patch("app.api.library.load_sources", return_value=sources), \
             patch("app.api.library.load_videos", return_value=[]), TestClient(app) as client:
            catalogue = client.get("/api/library").json()
        self.assertEqual(len(catalogue["documents"]), 2)
        self.assertEqual([d["url"] for d in catalogue["documents"]], [None, None])
        self.assertEqual(catalogue["categories"], [{"id": "new_topic", "label": "New Topic"}])

    def test_video_only_topics_all_languages_and_unavailable_links_stay_in_catalogue(self):
        videos = [{"youtube_id": str(i), "title": f"Video {i}", "category": "video_only",
                   "language": language, "url": url}
                  for i, (language, url) in enumerate([
                      ("en", "https://example.test/one"), ("en", "https://example.test/two"),
                      ("en", "https://example.test/three"), ("es", "https://example.test/spanish"),
                      ("ru", "https://example.test/russian"), ("en", "javascript:alert(1)"),
                      ("en", "https://[invalid"),
                  ])]
        with patch("app.api.library.load_sources", return_value=[]), \
             patch("app.api.library.load_videos", return_value=videos), TestClient(app) as client:
            response = client.get("/api/library")
        self.assertEqual(response.status_code, 200)
        catalogue = response.json()
        self.assertEqual(len(catalogue["videos"]), 7)
        self.assertEqual([v["url"] for v in catalogue["videos"]][-2:], [None, None])
        self.assertEqual({v["language"] for v in catalogue["videos"]}, {"en", "es", "ru"})
        self.assertEqual(catalogue["categories"], [{"id": "video_only", "label": "Video Only"}])

    def test_library_expansion_preserves_chat_video_selection(self):
        videos = [{"title": f"Video {i}", "url": f"https://example.test/{i}",
                   "category": category, "language": language}
                  for i, (category, language) in enumerate([
                      ("sleep", "es"), ("sleep", "en"), ("sleep", "en"),
                      ("sleep", "en"), ("nutrition", "en"),
                  ])]
        with patch("app.tools.resources.load_videos", return_value=videos):
            self.assertEqual(pick_videos("sleep"), [
                {"title": "Video 1", "url": "https://example.test/1"},
                {"title": "Video 2", "url": "https://example.test/2"},
            ])
            self.assertEqual(pick_videos("sleep", language="es"), [
                {"title": "Video 0", "url": "https://example.test/0"},
            ])


class CitationHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="icare-citations-")
        self.addCleanup(self.temp.cleanup)
        self.db = Database(str(Path(self.temp.name) / "app.sqlite3"))
        self.addCleanup(self.db._conn.close)
        for target in ("app.api.chat.get_db", "app.api.history.get_db", "app.api.deps.get_db"):
            self.enterContext(patch(target, return_value=self.db))
        self.client = self.enterContext(TestClient(app))
        self.users = []
        for name in ("alice", "bob"):
            user = self.db.create_user(name + "@example.test", "unused", "unused", name)
            self.db.create_token(user.id, "test-" + name)
            self.users.append(user)
        self.headers = {"Authorization": "Bearer test-alice"}

    def test_stream_sources_survive_history_and_remain_specific_to_each_answer(self):
        conversation = self.db.create_conversation(self.users[0].id, "Synthetic")
        expected = []
        for title in ("Sleep guide", "Care options guide"):
            source = Source(1, title, "sleep", "https://example.test/" + title.split()[0] + ".pdf")
            expected.append([asdict(source)])
            stream = [("sources", [source]), ("delta", f"Synthetic answer [1] about {title}.")]
            with patch("app.api.chat._coordinator.stream", return_value=iter(stream)):
                response = self.client.post("/api/chat", headers=self.headers, json={
                    "messages": [{"role": "user", "content": "Synthetic question"}],
                    "conversation_id": conversation,
                })
            self.assertEqual(response.status_code, 200)
            self.assertIn('event: done', response.text)
            self.assertIn(json.dumps(asdict(source)), response.text)
        history = self.client.get("/api/history", headers=self.headers).json()
        answers = [m for m in history["latest_messages"] if m["role"] == "assistant"]
        self.assertEqual([m["sources"] for m in answers], expected)
        self.assertEqual(self.client.get("/api/history", headers={"Authorization": "Bearer test-bob"}).json()["latest_messages"], [])
        self.assertEqual(self.client.get("/api/history").status_code, 401)

    def test_guests_do_not_persist_and_foreign_conversation_ids_are_rejected(self):
        with patch("app.api.chat._coordinator.stream", return_value=iter([("delta", "Guest [1]")])):
            self.assertEqual(self.client.post("/api/chat", json={"messages": [{"role": "user", "content": "Question"}]}).status_code, 200)
        self.assertEqual(self.db._conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 0)
        other_id = self.db.create_conversation(self.users[1].id)
        for conversation in (other_id, 99999):
            response = self.client.post("/api/chat", headers=self.headers, json={
                "conversation_id": conversation, "messages": [{"role": "user", "content": "Question"}],
            })
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.db.conversation_messages(other_id), [])

    def test_multiple_chunks_of_one_document_keep_one_citation_number(self):
        hits = [SimpleNamespace(text=f"Chunk {i}", metadata={"doc_id": doc, "title": doc,
                    "url": f"https://example.test/{doc}.pdf"})
                for i, doc in enumerate(("sleep", "care", "sleep"))]
        context, sources = build_context_and_sources(hits)
        self.assertEqual([s.n for s in sources], [1, 2])
        self.assertEqual(context, "[1] Chunk 0\n\n[2] Chunk 1\n\n[1] Chunk 2")

    def test_legacy_database_migration_preserves_text_without_inventing_sources(self):
        path = str(Path(self.temp.name) / "legacy.sqlite3")
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, conversation_id INTEGER, user_id INTEGER, role TEXT, content TEXT, created_at REAL)")
            conn.execute("INSERT INTO messages VALUES (1, 1, 1, 'assistant', 'Original answer [1]', 123)")
        for _ in range(2):
            db = Database(path)
            try:
                row = db.conversation_messages(1)[0]
                self.assertEqual((row.content, row.ts, row.sources), ("Original answer [1]", 123, []))
            finally:
                db._conn.close()


if __name__ == "__main__":
    unittest.main()
