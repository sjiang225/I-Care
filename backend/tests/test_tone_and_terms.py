"""Regression coverage for R06 (supportive tone) and R07 (neutral wording).

Run from backend/: .venv/bin/python -m unittest discover -s tests -v
Checks the instructions every caregiver-facing agent receives; no model is called.
Response quality itself is checked with scripts/eval_tone.py.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.agents import coordinator, education, emotion, peer
from app.agents.safety import check_safety
from app.agents.style import CARE_RECIPIENT_TERMS, CAREGIVER_VOICE

PROMPTS = {
    "education": education.EDUCATION_SYSTEM.format(context="", tone=""),
    "emotion": emotion.EMOTION_SYSTEM.format(context=""),
    "peer": peer.PEER_SYSTEM.format(context=""),
}


class ToneAndTermsTest(unittest.TestCase):
    def test_every_agent_prompt_carries_shared_rules(self):
        for name, prompt in PROMPTS.items():
            with self.subTest(agent=name):
                self.assertIn(CAREGIVER_VOICE.strip(), prompt)
                self.assertIn(CARE_RECIPIENT_TERMS.strip(), prompt)

    def test_emotion_agent_no_longer_leads_with_generic_empathy(self):
        self.assertNotIn("Lead with genuine empathy", emotion.EMOTION_SYSTEM)
        self.assertIn("thanking them for sharing", emotion.EMOTION_SYSTEM)

    def test_education_tone_reflects_stated_feelings_only(self):
        self.assertNotIn("sounds emotionally stressed", education._EMOTION_TONE)
        self.assertIn("only the feelings they stated", education._EMOTION_TONE)

    def test_router_requires_feelings_in_the_caregivers_own_words(self):
        description = coordinator.ROUTE_SPEC.parameters["properties"]["needs_emotion"]["description"]
        self.assertIn("OWN feelings", description)
        self.assertIn("NOT enough", description)

    def test_missing_person_notice_uses_neutral_wording(self):
        result = check_safety("My wife wandered off and I can't find her")
        self.assertEqual(result.category, "missing_person")
        self.assertIn("the person you care for", result.message)
        self.assertNotIn("loved one", result.message.lower())

    def test_app_text_does_not_say_loved_one(self):
        # style.py names the phrase only to forbid it; source titles live in JSON data.
        app_dir = Path(__file__).resolve().parents[1] / "app"
        for path in app_dir.rglob("*.py"):
            if path.name == "style.py":
                continue
            with self.subTest(file=str(path.relative_to(app_dir))):
                self.assertIsNone(re.search(r"loved ones?", path.read_text(), re.I))


if __name__ == "__main__":
    unittest.main()
