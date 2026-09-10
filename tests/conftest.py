"""
Pytest configuration and global fixtures for DEMOSCENE test suite.
Ensures test database tables and schema are automatically initialized on clean checkouts.
"""
import pytest
from app.core.config import settings
from app.core import database as db


@pytest.fixture(autouse=True, scope="session")
def setup_test_database(tmp_path_factory):
    """Initialize an isolated test database with complete schema and seed."""
    tmp_dir = tmp_path_factory.mktemp("demoscene_test_data")
    test_db_path = str(tmp_dir / "test_demopals.db")

    # Point settings to test DB for the duration of the test session
    orig_db_path = settings.DB_PATH
    settings.DB_PATH = test_db_path

    # Initialize schema and seed data into test database
    db.init_db(test_db_path)

    yield test_db_path

    # Restore original setting
    settings.DB_PATH = orig_db_path


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Clear in-memory auth rate limits between tests so test suites do not exhaust IP quotas."""
    from app.main import _auth_rate_limits
    _auth_rate_limits.clear()
    yield
    _auth_rate_limits.clear()

