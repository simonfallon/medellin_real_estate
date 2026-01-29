"""
Tests for dynamic price range functionality in the API endpoint.
"""
import sys
import os
from fastapi.testclient import TestClient

# Add backend to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from backend.main import app
from backend.scrapers.base import ScraperConfig


client = TestClient(app)


def test_scrape_endpoint_without_price_params(monkeypatch):
    """Test that endpoint works without price parameters (uses defaults)."""
    mock_data = []

    async def mock_scrape(config=None):
        # Verify config is None when no prices provided
        assert config is None
        return mock_data

    monkeypatch.setattr("backend.scraper.scrape_all_batch", mock_scrape)

    response = client.post("/api/scrape/batch?source=all&force=true")

    assert response.status_code == 200
    data = response.json()
    assert "new_properties" in data or "cached" in data


def test_scrape_endpoint_with_custom_price_params(monkeypatch):
    """Test that endpoint correctly passes custom price parameters."""
    mock_data = []
    received_config = None

    async def mock_scrape(config=None):
        nonlocal received_config
        received_config = config
        return mock_data

    monkeypatch.setattr("backend.scraper.scrape_all_batch", mock_scrape)

    response = client.post(
        "/api/scrape/batch?source=all&force=true&price_min=2000000&price_max=4000000"
    )

    assert response.status_code == 200
    assert received_config is not None
    assert isinstance(received_config, ScraperConfig)
    assert received_config.price_ranges == [{"min": 2000000, "max": 4000000}]


def test_scrape_endpoint_rejects_negative_prices():
    """Test that endpoint rejects negative price values."""
    response = client.post(
        "/api/scrape/batch?source=all&force=true&price_min=-1000&price_max=3000000"
    )

    assert response.status_code == 400
    data = response.json()
    assert "Prices must be positive" in data["detail"]


def test_scrape_endpoint_rejects_min_greater_than_max():
    """Test that endpoint rejects min >= max."""
    response = client.post(
        "/api/scrape/batch?source=all&force=true&price_min=4000000&price_max=2000000"
    )

    assert response.status_code == 400
    data = response.json()
    assert "Min price must be less than max price" in data["detail"]


def test_scrape_endpoint_rejects_min_equal_to_max():
    """Test that endpoint rejects min == max."""
    response = client.post(
        "/api/scrape/batch?source=all&force=true&price_min=3000000&price_max=3000000"
    )

    assert response.status_code == 400
    data = response.json()
    assert "Min price must be less than max price" in data["detail"]


def test_scrape_endpoint_rejects_excessive_max_price():
    """Test that endpoint rejects max price > 50M."""
    response = client.post(
        "/api/scrape/batch?source=all&force=true&price_min=1000000&price_max=60000000"
    )

    assert response.status_code == 400
    data = response.json()
    assert "exceeds reasonable limit" in data["detail"]


def test_scrape_endpoint_accepts_boundary_max_price(monkeypatch):
    """Test that endpoint accepts max price exactly at 50M."""
    mock_data = []

    async def mock_scrape(_config=None):
        return mock_data

    monkeypatch.setattr("backend.scraper.scrape_all_batch", mock_scrape)

    response = client.post(
        "/api/scrape/batch?source=all&force=true&price_min=1000000&price_max=50000000"
    )

    assert response.status_code == 200


def test_scrape_endpoint_accepts_zero_min_price(monkeypatch):
    """Test that endpoint accepts 0 as min price."""
    mock_data = []
    received_config = None

    async def mock_scrape(config=None):
        nonlocal received_config
        received_config = config
        return mock_data

    monkeypatch.setattr("backend.scraper.scrape_all_batch", mock_scrape)

    response = client.post(
        "/api/scrape/batch?source=all&force=true&price_min=0&price_max=4000000"
    )

    assert response.status_code == 200
    assert received_config.price_ranges == [{"min": 0, "max": 4000000}]


def test_scrape_endpoint_with_only_price_min_provided(monkeypatch):
    """Test that endpoint ignores prices when only min is provided."""
    mock_data = []
    received_config = None

    async def mock_scrape(config=None):
        nonlocal received_config
        received_config = config
        return mock_data

    monkeypatch.setattr("backend.scraper.scrape_all_batch", mock_scrape)

    response = client.post("/api/scrape/batch?source=all&force=true&price_min=2000000")

    assert response.status_code == 200
    # Should be None because only one price param provided
    assert received_config is None


def test_scrape_endpoint_with_only_price_max_provided(monkeypatch):
    """Test that endpoint ignores prices when only max is provided."""
    mock_data = []
    received_config = None

    async def mock_scrape(config=None):
        nonlocal received_config
        received_config = config
        return mock_data

    monkeypatch.setattr("backend.scraper.scrape_all_batch", mock_scrape)

    response = client.post("/api/scrape/batch?source=all&force=true&price_max=4000000")

    assert response.status_code == 200
    # Should be None because only one price param provided
    assert received_config is None


def test_scrape_endpoint_routes_to_specific_scraper(monkeypatch):
    """Test that endpoint correctly routes to specific scrapers with config."""
    mock_data = []
    received_config = None

    async def mock_alberto_scrape(config=None):
        nonlocal received_config
        received_config = config
        return mock_data

    monkeypatch.setattr(
        "backend.scraper.scrape_alberto_alvarez_batch", mock_alberto_scrape
    )

    response = client.post(
        "/api/scrape/batch?source=alberto_alvarez&force=true&price_min=2500000&price_max=3500000"
    )

    assert response.status_code == 200
    assert received_config is not None
    assert received_config.price_ranges == [{"min": 2500000, "max": 3500000}]
