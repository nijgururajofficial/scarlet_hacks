# Day 1 Brain — Project Plan
> Onboarding copilot that turns company docs into a personalized knowledge brief for new hires.

---

## The Pitch
*"Drop your company docs. Select your role. Get everything you need to know — before you even ask."*

---

## Two Agents

### Agent 1 — Knowledge Transfer Agent
Triggered on role selection. Proactively reads all docs and generates a role-specific brief with no query needed.

**Outputs:** must-knows, tools checklist, key contacts, 30-day roadmap

### Agent 2 — Knowledge Search Agent
Answers free-form questions by searching the vector knowledge base (RAG). Same question, different answer per role.

**Outputs:** role-aware answer + source doc + freshness tag

---

## Tech Stack

| Layer | Tool |
|---|---|
| UI | Streamlit |
| PDF parsing | PyMuPDF |
| Vector store | FAISS (in-memory) |
| AI | OpenAI API (gpt-5.3) |
| Language | Python 3.11+ |

---

## File Structure

```
app.py          ← Streamlit UI + routing
agents.py       ← Agent 1 (transfer) + Agent 2 (search)
ingest.py       ← PDF parse → chunk → embed → FAISS
prompts.py      ← System prompts per role
demo_docs/      ← 6 pre-loaded company docs
requirements.txt
```

---

## Features

### P0 — Must have
- [ ] PDF + text ingestion into FAISS vector store
- [ ] Role selector (Junior Engineer / PM / Marketing / HR)
- [ ] Agent 2: chat interface with RAG retrieval + role-aware answers
- [ ] Source doc tag on every response

### P1 — Core wow
- [ ] Agent 1: auto-generates knowledge brief on role selection
- [ ] 30-day roadmap output (Week 1 / Week 2 / Week 3–4)
- [ ] Structured JSON output rendered as Streamlit cards

### P2 — If time allows
- [ ] Contradiction flag when two docs disagree
- [ ] "Who to ask" fallback using doc author metadata

---

## 12-Hour Timeline

| Hours | Task |
|---|---|
| 0–3h | `ingest.py` — PDF parse, chunk, embed, FAISS. `prompts.py` — role system prompts |
| 3–6h | `app.py` shell + Agent 2 end-to-end (query → FAISS → OpenAI → stream) |
| 6–9h | Agent 1 — structured brief prompt, JSON parse, Streamlit card layout |
| 9–11h | Load demo docs, test all 3 demo scenarios, UI polish |
| 11–12h | Dry run demo × 3, fix edge cases, prep 3 slides |

---

## Demo Docs (write by hour 9)

| File | Contents |
|---|---|
| `employee_handbook.pdf` | Leave, expenses, HR contacts, benefits |
| `engineering_wiki.md` | Dev setup, deploy steps, DB access, git conventions |
| `security_policy.pdf` | Access by role, escalation paths |
| `org_chart.md` | Team leads, Slack handles, who owns what |
| `product_roadmap.pdf` | Sprint goals, PM↔eng process, release flow |
| `brand_guidelines.pdf` | Tone, approved tools, campaign approval |

---

## 90-Second Demo Script

1. **Hook (10s)** — "It's your first day. 12 tabs open. You don't know who to ask. Day 1 Brain fixes that."
2. **Upload docs (10s)** — Drop 6 files. "Any company. Any docs. No integration needed."
3. **Select role → brief appears (20s)** — Click "Junior Engineer." Brief auto-generates. "No query. It already knows what a new engineer needs."
4. **Same question, two roles (25s)** — Ask "How do I get DB access?" as Engineer → terminal steps. Switch to Marketing → "You don't have access. Contact Lead Dev."
5. **Close (15s)** — "Glean costs $20k/year and takes 3 months to set up. This runs on your existing docs in 60 seconds."

---

## Team Split

| Person | Owns |
|---|---|
| A | `ingest.py`, `agents.py`, OpenAI API, RAG pipeline |
| B | `app.py`, Streamlit UI, chat interface, brief cards |
| C | Demo docs, prompt engineering, pitch slides, QA |

---

## Key Prompt Design Note

Both agents share the same knowledge base but use different system prompts:

- **Agent 1:** *"You are proactively briefing a new [ROLE]. Synthesize everything they need — they haven't asked anything yet."*
- **Agent 2:** *"You are answering a specific question for a [ROLE]. Only tell them what is relevant and accessible to their role."*

This framing difference is what makes the role-switching demo beat work.