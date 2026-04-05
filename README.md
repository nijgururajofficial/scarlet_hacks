# Day 1 Brain

> Onboarding copilot that turns company docs into a personalized knowledge brief for new hires.

*"Drop your company docs. Select your role. Get everything you need to know — before you even ask."*

## Features

### Knowledge Transfer Agent
- Triggered on role selection
- Proactively reads all documents
- Generates role-specific briefs with no query needed
- Outputs: must-knows, tools checklist, key contacts, 30-day roadmap

### Knowledge Search Agent
- Answers free-form questions by searching the vector knowledge base (RAG)
- Provides role-aware answers with source documents and freshness tags

## Tech Stack

| Layer | Tool |
|---|---|
| UI | Streamlit |
| PDF Parsing | PyMuPDF |
| Vector Store | FAISS (in-memory) |
| AI | OpenAI API |
| Language | Python 3.11+ |

## Prerequisites

- Python 3.11+
- OpenAI API key

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd scarlet_hacks
   ```

2. Set up environment variables:
   Create a `.env` file in the `backend/` folder:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

3. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. Install frontend dependencies:
   ```bash
   cd ../frontend
   pip install -r requirements.txt
   ```

## Running the Application

You'll need two terminal windows:

**Terminal 1 - Start the backend server:**
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Start the frontend:**
```bash
cd frontend
streamlit run app.py
```

## Usage

1. Open your browser to the Streamlit URL (usually http://localhost:8501)
2. Upload company documents (PDF, MD, TXT formats supported)
3. Select your role (Software Engineer)
4. Use the Briefing Agent for comprehensive onboarding information
5. Use the Conversational Agent for specific questions

## Project Structure

```
scarlet_hacks/
├── backend/
│   ├── main.py              # FastAPI server
│   ├── agents.py            # AI agents (transfer & search)
│   ├── ingest.py            # Document parsing & embedding
│   ├── prompts.py           # System prompts per role
│   ├── requirements.txt
│   └── demo_docs/           # Pre-loaded example documents
│       ├── api_docs.md
│       ├── engineering_handbook.md
│       ├── system_architecture.md
│       └── transcripts/
│           └── transcript_sprint_planning.md
├── frontend/
│   ├── app.py               # Streamlit UI
│   ├── api_client.py        # Backend API client
│   └── requirements.txt
└── README.md
```

## API Endpoints

- `GET /health` - Health check
- `POST /ingest` - Upload and process documents
- `POST /brief` - Generate knowledge brief
- `POST /search` - Search knowledge base

## Development

The backend automatically loads demo documents from `demo_docs/` on startup. Additional documents can be uploaded through the UI.
