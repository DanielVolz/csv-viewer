"""Tests for OpenSearch statistics functions."""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock


class TestStatsIndex:
    """Test statistics index creation."""

    @patch('utils.opensearch.OpenSearchConfig.client', new_callable=PropertyMock)
    def test_create_stats_index_creates_when_missing(self, mock_client_prop):
        """Test that create_stats_index creates index when it doesn't exist."""
        from utils.opensearch import opensearch_config

        mock_client = MagicMock()
        mock_client_prop.return_value = mock_client
        mock_client.indices.exists.return_value = False
        mock_client.indices.create.return_value = {'acknowledged': True}

        result = opensearch_config.create_stats_index()

        assert result is True
        mock_client.indices.create.assert_called_once()

    @patch('utils.opensearch.OpenSearchConfig.client', new_callable=PropertyMock)
    def test_create_stats_index_skips_when_exists(self, mock_client_prop):
        """Test that create_stats_index skips creation if index exists."""
        from utils.opensearch import opensearch_config

        mock_client = MagicMock()
        mock_client_prop.return_value = mock_client
        mock_client.indices.exists.return_value = True

        result = opensearch_config.create_stats_index()

        assert result is True
        mock_client.indices.create.assert_not_called()


class TestStatsSnapshot:
    """Test statistics snapshot operations."""

    @patch('utils.opensearch.OpenSearchConfig.client', new_callable=PropertyMock)
    def test_index_stats_snapshot_indexes_document(self, mock_client_prop):
        """Test that index_stats_snapshot indexes a document."""
        from utils.opensearch import opensearch_config

        mock_client = MagicMock()
        mock_client_prop.return_value = mock_client
        mock_client.indices.exists.return_value = True
        mock_client.index.return_value = {'result': 'created'}

        metrics = {'totalPhones': 1000, 'phonesWithKEM': 200}
        result = opensearch_config.index_stats_snapshot(
            file='netspeed.csv',
            date='2025-10-09',
            metrics=metrics
        )

        assert result is True
        mock_client.index.assert_called_once()

    @patch('utils.opensearch.OpenSearchConfig.client', new_callable=PropertyMock)
    def test_get_stats_snapshot_returns_data(self, mock_client_prop):
        """Test that get_stats_snapshot retrieves snapshot data."""
        from utils.opensearch import opensearch_config

        mock_client = MagicMock()
        mock_client_prop.return_value = mock_client
        mock_client.get.return_value = {
            'found': True,
            '_source': {'totalPhones': 1500, 'date': '2025-10-09'}
        }

        snapshot = opensearch_config.get_stats_snapshot(
            file='netspeed.csv',
            date='2025-10-09'
        )

        assert snapshot is not None
        assert snapshot['totalPhones'] == 1500
