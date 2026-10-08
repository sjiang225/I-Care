"""English instruments transcribed from the three user-supplied PDFs.

Question wording, recall periods and response values are preserved. PHQ/GAD
functional difficulty is not scored. PSS-10 has no diagnostic cutoffs. Sources,
version decisions and application-authored follow-up copy are documented in
docs/self-assessment.md. No model is used to administer or score these forms.
"""
from __future__ import annotations

FREQUENCY = ["Not at all", "Several days", "More than half the days", "Nearly every day"]
DIFFICULTY = ["Not difficult at all", "Somewhat difficult", "Very difficult", "Extremely difficult"]
FUNCTION_QUESTION = (
    "If you checked off any problems, how difficult have these problems made it for you "
    "to do your work, take care of things at home, or get along with other people?"
)

INSTRUMENTS = {
    "phq9": {
        "id": "phq9", "version": "phq9-en-2005-icare-1",
        "name": "PHQ-9", "title": "PHQ-9 (Depression)",
        "description": "Reflect on symptoms of depression over the last two weeks.",
        "recall": "Over the last 2 weeks",
        "instructions": "Over the last 2 weeks, how often have you been bothered by any of the following problems?",
        "questions": [
            "Little interest or pleasure in doing things",
            "Feeling down, depressed, or hopeless",
            "Trouble falling or staying asleep, or sleeping too much",
            "Feeling tired or having little energy",
            "Poor appetite or overeating",
            "Feeling bad about yourself — or that you are a failure or have let yourself or your family down",
            "Trouble concentrating on things, such as reading the newspaper or watching television",
            "Moving or speaking so slowly that other people could have noticed. Or the opposite — being so fidgety or restless that you have been moving around a lot more than usual",
            "Thoughts that you would be better off dead, or of hurting yourself",
        ],
        "options": FREQUENCY, "max_score": 27,
        "difficulty_question": FUNCTION_QUESTION, "difficulty_options": DIFFICULTY,
        "safety_item_index": 8,
        "source_pdf": "/assessments/phq-9.pdf",
        "source_url": "https://aims.uw.edu/resource/phq-9-depression-scale/",
        "attribution": "PHQ-9 © Pfizer Inc. PRIME-MD is a trademark of Pfizer Inc. Source: supplied PHQ-9 questionnaire and scoring card (2005).",
    },
    "gad7": {
        "id": "gad7", "version": "gad7-en-provided-icare-1",
        "name": "GAD-7", "title": "GAD-7 (Anxiety)",
        "description": "Reflect on symptoms of anxiety over the last two weeks.",
        "recall": "Over the last 2 weeks",
        "instructions": "Over the last 2 weeks, how often have you been bothered by the following problems?",
        "questions": [
            "Feeling nervous, anxious, or on edge",
            "Not being able to stop or control worrying",
            "Worrying too much about different things",
            "Trouble relaxing",
            "Being so restless that it is hard to sit still",
            "Becoming easily annoyed or irritable",
            "Feeling afraid as if something awful might happen",
        ],
        "options": FREQUENCY, "max_score": 21,
        "difficulty_question": FUNCTION_QUESTION,
        "difficulty_options": ["Not at all", *DIFFICULTY[1:]],
        "safety_item_index": None,
        "source_pdf": "/assessments/gad-7.pdf",
        "source_url": "https://www.phqscreeners.com/",
        "attribution": "GAD-7: Robert L. Spitzer, Kurt Kroenke, Janet B. W. Williams and Bernd Löwe. Source: supplied Generalized Anxiety Disorder 7-Item Scale.",
    },
    "pss10": {
        "id": "pss10", "version": "pss10-en-1994-icare-2",
        "name": "PSS-10", "title": "PSS-10 (Stress)",
        "description": "Reflect on how stressful life has felt over the last month.",
        "recall": "In the last month",
        "instructions": "The questions in this scale ask you about your feelings and thoughts during the last month. In each case, indicate how often you felt or thought a certain way.",
        "questions": [
            "In the last month, how often have you been upset because of something that happened unexpectedly?",
            "In the last month, how often have you felt that you were unable to control the important things in your life?",
            "In the last month, how often have you felt nervous and ‘stressed’?",
            "In the last month, how often have you felt confident about your ability to handle your personal problems?",
            "In the last month, how often have you felt that things were going your way?",
            "In the last month, how often have you found that you could not cope with all the things that you had to do?",
            "In the last month, how often have you been able to control irritations in your life?",
            "In the last month, how often have you felt that you were on top of things?",
            "In the last month, how often have you been angered because of things that were outside of your control?",
            "In the last month, how often have you felt difficulties were piling up so high that you could not overcome them?",
        ],
        "options": ["Never", "Almost Never", "Sometimes", "Fairly Often", "Very Often"],
        "max_score": 40, "difficulty_question": None, "difficulty_options": [],
        "safety_item_index": None,
        "source_pdf": "/assessments/pss-10.pdf",
        "source_url": "https://www.cmu.edu/dietrich/psychology/stress-immunity-disease-lab/scales/index.html",
        "attribution": "Perceived Stress Scale by Sheldon Cohen. Copyright © 1994. All rights reserved. Source: supplied English PSS-10, hosted by Mind Garden.",
    },
}


def pss_reference(score: int, *, historical: bool = False) -> dict:
    """PI-requested reference groups, not validated diagnostic cutoffs."""
    bands = [
        {"min": 0, "max": 13, "label": "Low perceived stress"},
        {"min": 14, "max": 26, "label": "Moderate perceived stress"},
        {"min": 27, "max": 40, "label": "High perceived stress"},
    ]
    selected = next(b for b in bands if b["min"] <= score <= b["max"])
    return {
        "band": selected["label"], "bands": bands,
        "interpretation": (
            f"Your score falls within the {selected['label'].lower()} range "
            f"({selected['min']}–{selected['max']}) for the last month. "
            "These categories are for general guidance, not a diagnosis. "
            "The PSS-10 has no official diagnostic cutoffs."
        ),
        "source_url": "https://recallify.ai/perceived-stress-scale/",
        "applied_to_saved_result": historical,
    }


def with_pss_reference(result: dict) -> dict:
    """Enrich legacy responses without changing their stored result snapshots."""
    if result["instrument_id"] == "pss10" and "pss_reference" not in result:
        return {**result, "pss_reference": pss_reference(result["score"], historical=True)}
    return result


def score_assessment(instrument_id: str, answers: list[int], difficulty: int | None) -> dict:
    """Validate a complete form and return a deterministic, non-diagnostic result."""
    instrument = INSTRUMENTS[instrument_id]
    if len(answers) != len(instrument["questions"]):
        raise ValueError("Please answer every question before submitting.")
    if any(type(a) is not int or not 0 <= a < len(instrument["options"]) for a in answers):
        raise ValueError("One or more answers are outside the response scale.")
    if difficulty is not None and (type(difficulty) is not int or not 0 <= difficulty <= 3):
        raise ValueError("Please select a valid response to the daily-life question.")
    if instrument_id == "pss10" and difficulty is not None:
        raise ValueError("PSS-10 does not have a daily-life difficulty question.")
    if instrument["difficulty_question"] and any(answers) and difficulty is None:
        raise ValueError("Please answer the question about the impact on daily life.")

    safety_followup = instrument_id == "phq9" and answers[8] > 0
    if instrument_id == "pss10":
        # Source uses 1-based item numbers 4, 5, 7, 8.
        total = sum(4 - a if i in (3, 4, 6, 7) else a for i, a in enumerate(answers))
        reference = pss_reference(total)
        band = reference["band"]
        interpretation = reference["interpretation"]
        steps = [
            "Consider which demands feel hardest to manage and one practical source of help, such as sharing a caregiving task.",
            "If stress is affecting your daily life or you are concerned, discuss how you are feeling with a qualified healthcare professional.",
        ]
    else:
        total = sum(answers)
        bands = [(0, "Minimal"), (5, "Mild"), (10, "Moderate")]
        bands += [(15, "Moderately severe"), (20, "Severe")] if instrument_id == "phq9" else [(15, "Severe")]
        level = next(label for lower, label in reversed(bands) if total >= lower)
        symptom = "depressive" if instrument_id == "phq9" else "anxiety"
        band = f"{level} {symptom} symptoms"
        interpretation = (
            f"Your responses fall in the {level.lower()} range for {symptom} symptoms "
            "on this questionnaire. This is a screening result, not a diagnosis. "
            "A qualified healthcare professional can help you understand it in the context of your life."
        )
        if safety_followup:
            steps = ["Please contact a qualified healthcare professional promptly to discuss your response to question 9, regardless of your total score."]
        elif total >= 15:
            steps = ["Please reach out to a qualified healthcare professional soon to discuss these symptoms and the support available to you."]
        elif total >= 10 or (difficulty is not None and difficulty >= 2):
            steps = ["Arrange an appointment with a qualified healthcare professional to discuss your symptoms and their impact on daily life."]
        else:
            steps = ["If these feelings continue, affect daily life, or concern you, consider discussing them with a qualified healthcare professional. You can seek support at any score."]
        steps.append("Consider sharing how you are feeling with someone you trust or contacting a caregiver support service.")

    return {
        **({"pss_reference": reference} if instrument_id == "pss10" else {}),
        "instrument_id": instrument_id, "instrument_version": instrument["version"],
        "title": instrument["title"], "score": total, "max_score": instrument["max_score"],
        "band": band, "interpretation": interpretation, "next_steps": steps,
        "safety_followup": safety_followup,
        "difficulty": instrument["difficulty_options"][difficulty] if difficulty is not None else None,
        "source_pdf": instrument["source_pdf"], "source_url": instrument["source_url"],
        "attribution": instrument["attribution"],
    }
