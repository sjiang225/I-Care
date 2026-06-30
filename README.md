# I-Care

An Intelligence Care (I-Care) program for dementia caregivers — a GPT-based,
multi-agent web companion (PWA) delivering evidence-based education and emotional
support from Rutgers Health's Care2Caregivers materials.

See [DESIGN.md](DESIGN.md) for the full architecture and roadmap.

> ©2026 Rutgers, The State University of New Jersey, All rights reserved.
> Do not copy or reproduce without permission.

---

## What's built so far (M0 — scaffold)

- **Backend** (`backend/`): FastAPI with a streaming `/api/chat` endpoint and an
  LLM provider abstraction. Runs with a built-in **mock** provider, so it works
  with **no API key**. Switch to GPT (or a self-hosted small model later) via
  config only — no code change.
- **Frontend** (`frontend/`): Next.js PWA, mobile-first chat UI with voice input
  + read-aloud (Web Speech API), large-font / high-contrast layout for older
  caregivers, and the required Rutgers copyright + medical disclaimer footer.

Not yet built: RAG knowledge base, the Coordinator/Education/Emotion agents,
emotion tracking, usability-test instrumentation (M1–M5 in DESIGN.md).

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
