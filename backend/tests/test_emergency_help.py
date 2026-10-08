"""Regression coverage for R09 emergency help in chat.

Run from backend/: .venv/bin/python -m unittest discover -s tests -v
Rule-based only; no model is called.
"""
from __future__ import annotations

import unittest

from app.agents.safety import check_safety
from app.agents.style import safety_instruction

MEETING_TEXT = ("If you ever feel in danger or fear for the safety of the person you are supporting, "
                "call **911**. Emergency workers can assist you and help you in a crisis.")


class CaregiverSafetyTest(unittest.TestCase):
    def test_danger_to_caregiver_or_person_supported_triggers_meeting_text(self):
        for text in [
            "My husband hit me last night when I tried to help him bathe.",
            "I'm scared of him when he gets angry.",
            "She threatened me with a kitchen knife and I don't feel safe.",
            "I fear for her safety when she tries to leave at night.",
            "Dad has a gun in the house and I'm afraid of him.",
        ]:
            with self.subTest(text=text):
                result = check_safety(text)
                self.assertEqual(result.category, "caregiver_safety")
                self.assertIn(MEETING_TEXT, result.message)

    def test_everyday_questions_and_feelings_do_not_trigger(self):
        for text in [
            "It really hurt me when she forgot my name.",
            "How do I handle aggression during bathing?",
            "Is my mom in danger of falling at night?",
            "He pushed the plate away and refused to eat.",
            "Where can I find adult day care in Bergen County?",
        ]:
            with self.subTest(text=text):
                self.assertFalse(check_safety(text).triggered)

    def test_existing_categories_keep_priority(self):
        self.assertEqual(check_safety("He hit me and now he is not breathing").category, "medical_emergency")
        self.assertEqual(check_safety("I'm scared of him and I want to die").category, "self_harm")

    def test_replies_after_a_notice_lead_with_safety_steps(self):
        self.assertEqual(safety_instruction({}), "")
        rule = safety_instruction({"safety": "caregiver_safety"})
        self.assertIn("overrides any rule below", rule)
        self.assertIn("Do not thank, praise or describe feelings", rule)


if __name__ == "__main__":
    unittest.main()
