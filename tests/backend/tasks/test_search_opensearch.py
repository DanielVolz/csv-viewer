"""Tests for search_opensearch task."""
import pytest
from unittest.mock import patch, MagicMock


class TestSearchOpenSearch:
    """Test the search_opensearch function."""

    @patch('tasks.tasks.opensearch_config')
    def test_search_returns_results(self, mock_os_config):
        """Test that search returns results."""
        from tasks.tasks import search_opensearch

        # Mock opensearch_config.search to return headers and documents
        mock_os_config.search.return_value = (
            ['Name', 'IP Address'],
            [
                {'Name': 'Phone1', 'IP Address': '10.0.0.1'},
                {'Name': 'Phone2', 'IP Address': '10.0.0.2'}
            ]
        )

        result = search_opensearch(query='10.0.0', include_historical=False)

        assert result['status'] == 'success'
        assert len(result['data']) == 2

    @patch('tasks.tasks.opensearch_config')
    def test_search_handles_no_results(self, mock_os_config):
        """Test search with no results."""
        from tasks.tasks import search_opensearch

        # Return empty list
        mock_os_config.search.return_value = (['Name', 'IP Address'], [])

        result = search_opensearch(query='nonexistent', include_historical=False)

        assert result['status'] == 'success'
        assert len(result['data']) == 0

    @patch('tasks.tasks.opensearch_config')
    def test_search_includes_historical_when_requested(self, mock_os_config):
        """Test search with historical indices."""
        from tasks.tasks import search_opensearch

        mock_os_config.search.return_value = (
            ['Name'],
            [{'Name': f'Phone{i}'} for i in range(5)]
        )

        result = search_opensearch(query='test', include_historical=True)

        assert result['status'] == 'success'
        assert len(result['data']) == 5
        # Verify include_historical was passed
        mock_os_config.search.assert_called_once()
        call_kwargs = mock_os_config.search.call_args.kwargs
        assert call_kwargs.get('include_historical') is True
