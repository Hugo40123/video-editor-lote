"""Shared test fixtures and configuration.

v2.8 — Provides test database, mock settings, sample paths.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Ensure project root is on sys.path for imports
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from app.models import Base


@pytest.fixture(scope="function")
def test_db() -> Generator[Session, None, None]:
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def sample_video_path() -> Path:
    return Path("/tmp/test_video.mp4")


@pytest.fixture
def sample_image_path() -> Path:
    return Path("/tmp/test_bg.jpg")


@pytest.fixture
def sample_logo_path() -> Path:
    return Path("/tmp/test_logo.png")


@pytest.fixture
def sample_output_dir(tmp_path: Path) -> Path:
    d = tmp_path / "output"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture
def sample_settings() -> dict[str, str]:
    return {
        "instagram_user_id": "test_ig_user",
        "instagram_access_token": "test_ig_token_eabcd1234",
        "ai_gemini_key": "test_gemini_key_xyz789",
        "ai_gemini_model": "gemini-2.0-flash",
        "ml_affiliate_id": "ML_TEST_123",
        "shopee_affiliate_id": "SHOPEE_TEST_456",
        "shopee_sub_id": "instagram",
    }


@pytest.fixture
def suppress_db() -> Generator[None, None, None]:
    """Monkey-patch database to use in-memory SQLite for all tests.

    Patches both app.database and app.repository because repository.py
    imports get_session at module load time (local reference).

    Usage: add 'suppress_db' as a parameter to any test that uses repository functions.
    """
    import app.database as db_module
    import app.repository as repo_module

    # Save originals
    db_orig_session = db_module.get_session
    db_orig_engine = db_module.get_engine
    repo_orig_session = repo_module.get_session

    # Create in-memory engine + tables
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine)

    def mock_get_session() -> Session:
        return TestSession()

    def mock_get_engine():
        return test_engine

    # Apply patches to both modules
    db_module.get_session = mock_get_session
    db_module.get_engine = mock_get_engine
    repo_module.get_session = mock_get_session

    try:
        yield
    finally:
        # Restore originals
        db_module.get_session = db_orig_session
        db_module.get_engine = db_orig_engine
        repo_module.get_session = repo_orig_session
