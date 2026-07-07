from pathlib import Path

from fastapi.responses import FileResponse, RedirectResponse
from starlette.staticfiles import StaticFiles

from app.main import app


ROOT_DIR = Path(__file__).resolve().parents[1]
ENTERPRISE_DIST = ROOT_DIR / "frontend-enterprise" / "dist"
SPA_INDEX_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


def spa_index_response(index_path: Path) -> FileResponse:
    return FileResponse(index_path, headers=SPA_INDEX_HEADERS)

app.mount(
    "/assets",
    StaticFiles(directory=ENTERPRISE_DIST / "assets", check_dir=False),
    name="assets",
)
app.mount(
    "/enterprise/assets",
    StaticFiles(directory=ENTERPRISE_DIST / "assets", check_dir=False),
    name="enterprise-assets",
)
app.mount(
    "/chat/assets",
    StaticFiles(directory=ENTERPRISE_DIST / "assets", check_dir=False),
    name="chat-assets",
)


@app.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/chat/")


@app.get("/enterprise", include_in_schema=False)
@app.get("/enterprise/{path:path}", include_in_schema=False)
def enterprise_app(path: str = "") -> FileResponse:
    return spa_index_response(ENTERPRISE_DIST / "index.html")


@app.get("/login", include_in_schema=False)
@app.get("/chat", include_in_schema=False)
@app.get("/chat/{path:path}", include_in_schema=False)
def chat_app(path: str = "") -> FileResponse:
    return spa_index_response(ENTERPRISE_DIST / "index.html")
