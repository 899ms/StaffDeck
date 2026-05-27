# Skill Agent Loop Service

End-to-end MVP for an enterprise Skill Agent Loop service.

## Projects

- `backend`: FastAPI service with skill runtime, model config, tool execution, chat API, and trace APIs.
- `frontend-enterprise`: React/Vite enterprise console for skills, models, tools, and persona configuration.
- `frontend-chat`: React/Vite user chat client.
- `docs`: API and schema notes.

## Backend Quick Start

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

Set `DEMO_MODEL_API_KEY` in `backend/.env` to seed the demo OpenAI-compatible model config. The key is encrypted before it is stored in the database and is never committed.

## Frontend Quick Start

```bash
cd frontend-enterprise
npm install
npm run dev

cd ../frontend-chat
npm install
npm run dev
```

The apps default to `http://localhost:8000` for the backend.
