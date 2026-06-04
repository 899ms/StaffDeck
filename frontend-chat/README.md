# Chat Client

```bash
npm install
npm run dev
```

Environment:

- `VITE_API_BASE_URL`, default `http://127.0.0.1:8000`
- `VITE_TENANT_ID`, default `tenant_demo`
- `VITE_USER_ID`, default `user_demo`
- `VITE_SHOW_DEBUG=true` to show session state in the chat window

From the repository root, prefer `scripts/dev_up.sh` so the backend CORS and
frontend API base stay consistent.
