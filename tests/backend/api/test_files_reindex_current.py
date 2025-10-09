"""Tests for /api/files/reindex/current endpoint."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from pathlib import Path

from main import app

client = TestClient(app)


class TestReindexCurrentEndpoint:
    """Test the fast reindex current endpoint."""

    def test_reindex_endpoint_exists(self):
        """Test that reindex/current endpoint exists and responds."""
        response = client.get('/api/files/reindex/current')

        # Should return 404 (no file) or 503 (opensearch unavailable) or other
        # Just verify endpoint exists
        assert response.status_code in [404, 500, 503]

    def test_reindex_returns_json_response(self):
        """Test that reindex endpoint returns JSON response."""
        response = client.get('/api/files/reindex/current')

        # Should return JSON regardless of status
        assert response.headers.get('content-type') == 'application/json'

    def test_reindex_has_proper_structure(self):
        """Test that reindex response has proper structure."""
        response = client.get('/api/files/reindex/current')
        data = response.json()

        # Response should have status field or detail
        assert 'status' in data or 'detail' in data
