"""Scoring and privacy checks using temporary, synthetic records only."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.assessments.instruments import INSTRUMENTS, score_assessment
from app.config import get_settings
from app.db import Database, get_db
from app.main import app


class ScoringTests(unittest.TestCase):
    def test_every_phq_and_gad_total_and_boundary(self):
        for instrument, count, expected_bands in (
            ("phq9", 9, ["Minimal"] * 5 + ["Mild"] * 5 + ["Moderate"] * 5
             + ["Moderately severe"] * 5 + ["Severe"] * 8),
            ("gad7", 7, ["Minimal"] * 5 + ["Mild"] * 5 + ["Moderate"] * 5 + ["Severe"] * 7),
        ):
            for total, expected in enumerate(expected_bands):
                with self.subTest(instrument=instrument, total=total):
                    answers = [min(3, max(0, total - 3 * i)) for i in range(count)]
                    result = score_assessment(instrument, answers, 0)
                    self.assertEqual(result["score"], total)
                    self.assertTrue(result["band"].startswith(expected + " "))
                    # The extra daily-life response must not add to the total.
                    self.assertEqual(score_assessment(instrument, answers, 3)["score"], total)

    def test_pss_reverse_scoring(self):
        cases = [
            ([0] * 10, 16), ([4] * 10, 24), ([2] * 10, 20),
            ([0, 0, 0, 4, 4, 0, 4, 4, 0, 0], 0),
            ([4, 4, 4, 0, 0, 4, 0, 0, 4, 4], 40),
        ]
        for answers, score in cases:
            with self.subTest(answers=answers):
                result = score_assessment("pss10", answers, None)
                self.assertEqual(result["score"], score)
                self.assertFalse(result["safety_followup"])
        for index in range(10):
            answers = [0] * 10
            answers[index] = 1
            self.assertEqual(score_assessment("pss10", answers, None)["score"],
                             15 if index in (3, 4, 6, 7) else 17)

    def test_every_pss_total_and_reference_boundary(self):
        expected = ["Low"] * 14 + ["Moderate"] * 13 + ["High"] * 14
        for total, level in enumerate(expected):
            with self.subTest(total=total):
                scored_items = [min(4, max(0, total - 4 * i)) for i in range(10)]
                answers = [4 - a if i in (3, 4, 6, 7) else a for i, a in enumerate(scored_items)]
                result = score_assessment("pss10", answers, None)
                self.assertEqual(result["score"], total)
                self.assertEqual(result["band"], level + " perceived stress")
                reference = result["pss_reference"]
                self.assertEqual(reference["band"], result["band"])
                self.assertFalse(reference["applied_to_saved_result"])
                self.assertIn("not a diagnosis", result["interpretation"])
                self.assertEqual(len([b for b in reference["bands"] if b["min"] <= total <= b["max"]]), 1)

    def test_question_nine_followup_is_independent_of_total(self):
        result = score_assessment("phq9", [0] * 8 + [1], 0)
        self.assertEqual(result["score"], 1)
        self.assertTrue(result["safety_followup"])
        self.assertIn("regardless of your total score", result["next_steps"][0])
        self.assertFalse(score_assessment("phq9", [3] * 8 + [0], 3)["safety_followup"])
        self.assertFalse(score_assessment("gad7", [3] * 7, 3)["safety_followup"])


class AssessmentApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="icare-assessment-test-")
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {"LLM_PROVIDER": "mock",
                                     "APP_DB_PATH": self.tmp.name + "/app.sqlite3"})
        env.start()
        self.addCleanup(env.stop)
        get_settings.cache_clear()
        get_db.cache_clear()
        self.db = get_db()
        self.addCleanup(self.close_db)
        self.client = self.enterContext(TestClient(app))
        self.accounts = []
        for name in ("alice", "bob"):
            user = self.db.create_user(name + "@example.test", "unused", "unused", name)
            self.db.create_token(user.id, "synthetic-" + name)
            self.accounts.append({"Authorization": "Bearer synthetic-" + name})

    def close_db(self):
        self.db._conn.close()
        get_db.cache_clear()
        get_settings.cache_clear()

    def submission(self, instrument="phq9", **changes):
        return {"instrument_id": instrument,
                "instrument_version": INSTRUMENTS[instrument]["version"],
                "answers": [0] * len(INSTRUMENTS[instrument]["questions"]),
                "difficulty": None, "submission_id": str(uuid4()), "save": False, **changes}

    def count(self):
        return self.db._conn.execute("SELECT COUNT(*) FROM self_assessments").fetchone()[0]

    def test_catalogue_and_guest_results_do_not_persist_or_use_a_model(self):
        instruments = self.client.get("/api/assessments/instruments").json()["instruments"]
        self.assertEqual([len(i["questions"]) for i in instruments], [9, 7, 10])
        # Raise if the assessment path tries to instantiate any language model.
        with patch("app.llm.factory.get_llm", side_effect=AssertionError("No model allowed")):
            for instrument, expected in (("phq9", 0), ("gad7", 0), ("pss10", 16)):
                response = self.client.post("/api/assessments", json=self.submission(instrument))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertEqual(response.json()["score"], expected)
                self.assertFalse(response.json()["saved"])
                self.assertIsNone(response.json()["id"])
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.client.get("/api/assessments/history").status_code, 401)

    def test_saved_answers_versions_and_user_isolation_survive_reopen(self):
        first = self.submission(answers=[0] * 8 + [1], difficulty=2, save=True)
        saved = self.client.post("/api/assessments", json=first, headers=self.accounts[0]).json()
        self.assertTrue(saved["saved"])
        self.assertEqual(saved["score"], 1)
        second = self.submission("pss10", answers=[4] * 10, save=True)
        other = self.client.post("/api/assessments", json=second, headers=self.accounts[1]).json()
        self.assertEqual(other["score"], 24)
        # Guessing a user/session ID does not change the authenticated owner.
        for account, expected in zip(self.accounts, [saved, other]):
            response = self.client.get("/api/assessments/history?user_id=999&session_id=other",
                                       headers=account)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(response.json()["results"], [expected])
        row = self.db._conn.execute(
            "SELECT instrument_version, answers, difficulty FROM self_assessments WHERE id = ?",
            (saved["id"],),
        ).fetchone()
        self.assertEqual(row, (first["instrument_version"], json.dumps(first["answers"]), 2))
        reopened = Database(self.tmp.name + "/app.sqlite3")
        try:
            self.assertEqual(reopened.assessment_history(1), [saved])
        finally:
            reopened._conn.close()
        self.assertEqual(self.db._conn.execute("SELECT COUNT(*) FROM wellbeing_logs").fetchone()[0], 0)

    def test_legacy_pss_history_adds_reference_without_overwriting_snapshot(self):
        original = score_assessment("pss10", [2] * 10, None)
        original.pop("pss_reference")
        original.update(instrument_version="pss10-en-1994-icare-1", band=None,
                        interpretation="Original score-only interpretation.")
        saved = self.db.save_assessment(1, str(uuid4()), [2] * 10, None, original)
        before = self.db._conn.execute("SELECT result FROM self_assessments WHERE id = ?", (saved["id"],)).fetchone()
        item = self.client.get("/api/assessments/history", headers=self.accounts[0]).json()["results"][0]
        self.assertIsNone(item["band"])
        self.assertEqual(item["interpretation"], original["interpretation"])
        self.assertEqual(item["pss_reference"]["band"], "Moderate perceived stress")
        self.assertTrue(item["pss_reference"]["applied_to_saved_result"])
        self.assertEqual(self.db._conn.execute("SELECT result FROM self_assessments WHERE id = ?", (saved["id"],)).fetchone(), before)
        self.assertEqual(self.client.get("/api/assessments/history", headers=self.accounts[1]).json()["results"], [])

    def test_repeat_submission_is_idempotent_and_cannot_overwrite_answers(self):
        body = self.submission(save=True)
        first = self.client.post("/api/assessments", json=body, headers=self.accounts[0])
        retry = self.client.post("/api/assessments", json=body, headers=self.accounts[0])
        self.assertEqual(first.status_code, 200)
        self.assertEqual(retry.json(), first.json())
        self.assertEqual(self.count(), 1)
        changed = {**body, "answers": [1] * 9, "difficulty": 0}
        self.assertEqual(self.client.post("/api/assessments", json=changed,
                                          headers=self.accounts[0]).status_code, 409)
        self.assertEqual(self.count(), 1)
        # Different accounts may safely use the same submission UUID.
        self.assertEqual(self.client.post("/api/assessments", json=changed,
                                          headers=self.accounts[1]).status_code, 200)
        self.assertEqual(self.count(), 2)

    def test_authentication_is_required_to_save_and_never_silently_falls_back(self):
        self.db.create_token(1, "expired-synthetic", ttl_days=-1)
        self.assertEqual(self.client.post("/api/assessments", json=self.submission(save=True)).status_code, 401)
        for token in ("invalid", "expired-synthetic", ""):
            headers = {"Authorization": "Bearer " + token}
            for save in (True, False):
                self.assertEqual(self.client.post("/api/assessments", headers=headers,
                                                  json=self.submission(save=save)).status_code, 401)
            self.assertEqual(self.client.get("/api/assessments/history", headers=headers).status_code, 401)
        # The save flag is an explicit choice, even when authenticated.
        self.assertFalse(self.client.post("/api/assessments", json=self.submission(),
                                          headers=self.accounts[0]).json()["saved"])
        self.assertEqual(self.count(), 0)

    def test_incomplete_or_forged_submissions_are_rejected(self):
        invalid = [
            {"answers": [0] * n} for n in (0, 7, 8, 10, 11)
        ] + [
            {"answers": [0] * 8 + [value]} for value in (-1, 4, True, 1.0, "1", None)
        ] + [
            {"answers": [1] * 9, "difficulty": None},
            {"difficulty": True}, {"difficulty": 4}, {"difficulty": -1},
            {"score": 0}, {"user_id": 2}, {"session_id": "other"},
            {"instrument_id": "unknown"}, {"submission_id": "invalid"}, {"save": "true"},
        ]
        for changes in invalid:
            with self.subTest(changes=changes):
                response = self.client.post("/api/assessments", headers=self.accounts[0],
                                            json={**self.submission(save=True), **changes})
                self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.post("/api/assessments", json=self.submission(
            "pss10", difficulty=0)).status_code, 422)
        self.assertEqual(self.client.post("/api/assessments", json=self.submission(
            instrument_version="outdated")).status_code, 409)
        self.assertEqual(self.count(), 0)


if __name__ == "__main__":
    unittest.main()
