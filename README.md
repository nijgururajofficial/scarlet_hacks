# Day1 Brain

Day1 Brain is an onboarding assistant that ingests internal docs, builds a lightweight knowledge base, generates a proactive onboarding brief, and answers follow-up questions with grounded sources.

## What It Does

- Uploads `.pdf`, `.md`, and `.txt` documents to the backend
- Builds an in-memory FAISS knowledge base from the uploaded files
- Generates a structured onboarding brief with must-knows, tools, contacts, and a roadmap
- Answers free-form questions using retrieval-augmented generation
- Shows cited sources and freshness metadata in the chat response details

## Current App Setup

- The backend is a FastAPI app in `backend`
- The frontend is a Next.js app in `frontend`
- The frontend currently sends a fixed backend role of `junior engineer`

## Tech Stack

| Layer | Tool |
|---|---|
| Frontend | Next.js + React |
| Backend | FastAPI |
| PDF Parsing | PyMuPDF |
| Vector Store | FAISS (in-memory) |
| AI | OpenAI API |
| Language | Python 3.11+ and Node.js |

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm
- OpenAI API key

## Installation

### 1. Set the backend environment

Create `backend/.env` with:

```env
OPENAI_API_KEY=your_api_key_here
```

### 2. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Install frontend dependencies

```bash
cd ../frontend
npm install
```

## Running the App

Run the backend and frontend in separate terminals.

### Terminal 1: backend

```bash
cd backend
python .\main.py
```

You can also run:

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 2: frontend

```bash
cd frontend
npm run dev
```

## Local URLs

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend: [http://localhost:8000](http://localhost:8000)
- Backend health check: [http://localhost:8000/health](http://localhost:8000/health)

## How To Use

1. Start the backend
2. Start the frontend
3. Open `http://localhost:3000`
4. Upload company documents from the sidebar
5. Open the brief page to generate onboarding context
6. Open the analysis page to ask questions against the loaded documents

## Project Structure

```text
Scarlet Hacks/
├── backend/
│   ├── main.py
│   ├── agents.py
│   ├── ingest.py
│   ├── prompts.py
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── app/
│   │   ├── layout.js
│   │   ├── page.js
│   │   ├── globals.css
│   │   └── analysis/
│   │       └── page.js
│   ├── components/
│   │   └── portal_app.jsx
│   ├── package.json
│   └── package-lock.json
└── README.md
```

## API Endpoints

- `GET /health` returns backend readiness and document counts
- `POST /ingest` uploads documents and rebuilds the knowledge base
- `POST /brief` generates the onboarding brief
- `POST /search` answers a question using the current knowledge base

## Notes

- The backend may preload documents from a repo-level `demo_docs` folder if it exists
- Uploaded documents are stored in a temporary runtime directory and used to rebuild the in-memory index
- The current frontend has replaced the older Streamlit UI, but the old Python frontend files still remain in `frontend`
