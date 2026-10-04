import pytest
import pytest_asyncio
import sys
from pathlib import Path
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
from app.ratelimit import limiter


@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Isolate the in-memory rate limiter between tests."""
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def clean_database():
    """Start (and finish) every test with a pristine database.

    Manual live runs against the dev database can leave rows behind;
    without this, order-dependent tests (e.g. empty-history assertions)
    fail depending on what ran before pytest.
    """
    from app.db.session import SessionLocal
    from app.db.models import Evidence, Feedback, Scan

    def wipe():
        db = SessionLocal()
        try:
            db.query(Evidence).delete()
            db.query(Feedback).delete()
            db.query(Scan).delete()
            db.commit()
        finally:
            db.close()

    wipe()
    yield
    wipe()