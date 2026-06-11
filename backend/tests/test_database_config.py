from pathlib import Path

from app.db.database import _normalize_database_url


def test_relative_sqlite_url_resolves_under_backend_dir() -> None:
    backend_dir = Path(__file__).resolve().parents[1]

    assert _normalize_database_url("sqlite:///./skill_agent_loop.db") == (
        f"sqlite:///{backend_dir / 'skill_agent_loop.db'}"
    )


def test_absolute_and_memory_sqlite_urls_are_preserved() -> None:
    assert _normalize_database_url("sqlite:////tmp/example.db") == "sqlite:////tmp/example.db"
    assert _normalize_database_url("sqlite:///:memory:") == "sqlite:///:memory:"
