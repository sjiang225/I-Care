# I-Care

An Intelligence Care (I-Care) program for dementia caregivers — a GPT-based,
multi-agent web companion (PWA) delivering evidence-based education and emotional
support from Rutgers Health's Care2Caregivers materials.

See [DESIGN.md](DESIGN.md) for the full architecture and roadmap.

> ©2026 Rutgers, The State University of New Jersey, All rights reserved.
> Do not copy or reproduce without permission.

---

## Current features

- **Backend** (`backend/`): FastAPI with a streaming `/api/chat` endpoint and an
  LLM provider abstraction. Runs with a built-in **mock** provider, so it works
  with **no API key**. Switch to GPT (or a self-hosted small model later) via
  config only — no code change.
- **Frontend** (`frontend/`): Next.js PWA, mobile-first chat UI with voice input
  + read-aloud (Web Speech API), large-font / high-contrast layout for older
  caregivers, and the required Rutgers copyright + medical disclaimer footer.
- **Caregiver support**: Care2Caregivers knowledge retrieval and citations,
  coordinated education/emotional-support/peer-companion agents, safety notices,
  and NJ resources and related videos.
- **Accounts**: optional registration/sign-in and restoration of the latest
  saved conversation; guests can chat without an account.
- **Home and navigation**: persistent, labeled Home / Chat / Library / Self-assessment
  navigation; a dedicated homepage with a clear start/continue action, topic
  suggestions and an illustrated first-use guide. Switching pages preserves the
  conversation, draft and unfinished questionnaire in the open page. See
  [R01 implementation notes](docs/home-navigation.md).
- **How to use I-Care**: a voluntary four-step picture guide available from Home
  and the labeled Help button on every page, plus two-step tutorials for Library
  and Self-assessment. Closing Help returns to the current page with work intact.
  See [R03 implementation notes](docs/illustrated-help-guide.md).
- **Educational resources**: browse 25 English PDF guides and 12 videos across
  11 topics, filter All / Guides / Videos and search titles, topics or languages
  without asking a question. Videos are labeled English, Spanish or Russian and
  open on YouTube. Inline citation numbers open the matching source for that answer;
  new saved answers retain sources when restored. See [R02 / R10 notes](docs/guide-library-and-citations.md).
- **Self-assessment**: voluntary PHQ-9, GAD-7 and PSS-10 questionnaires with
  deterministic scoring, non-diagnostic explanations and support links.
  Guest results are not stored; signed-in submissions are saved separately
  from chat and visible only to their owner. See [implementation notes](docs/self-assessment.md).

**September 2026 upgrade, step 1:** automatic stress/emotion scoring, its chart,
and history-based feedback have been retired. Emotional support remains
available. Legacy records are retained in the database but are no longer read,
written, or exposed by the application; `/api/wellbeing` returns `410 Gone`.
Voluntary questionnaire-based self-assessment has now been added using the
team's supplied instruments. See [step 1 implementation notes](docs/upgrade-step-1.md)
and [self-assessment details](docs/self-assessment.md).

---

## Run locally

Two terminals.

### 1. Backend (http://localhost:8000)

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env            # defaults to LLM_PROVIDER=mock (no key needed)
./.venv/bin/uvicorn app.main:app --reload
```

### 2. Frontend (http://localhost:3000)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. On a phone, use Safari/Chrome → "Add to Home Screen"
to install it like an app.

## Regression checks

The backend tests use temporary synthetic data and a deterministic local model;
they do not use the existing application database or make model API calls.

```bash
cd backend
./.venv/bin/python -m unittest discover -s tests -v
```

For frontend checks, run `npm test`, `npx tsc --noEmit --incremental false` and `npm run build`
from `frontend/`.

---

## Switch from mock to real GPT

In `backend/.env`:

```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-4o-mini
```

### Later: switch to a self-hosted small model

Serve your model behind an OpenAI-compatible API (vLLM / Ollama / TGI), then just
point the base URL at it — no code change:

```
LLM_PROVIDER=openai
OPENAI_BASE_URL=http://your-server:8000/v1
OPENAI_CHAT_MODEL=your-model-name
```
