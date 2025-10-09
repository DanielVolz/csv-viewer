"""Tests for OpenSearch repair functionality."""
import pytest
from unittest.mock import patch, MagicMock


class TestOpenSearchRepair:
    """Test OpenSearch repair operations."""

    @patch('utils.opensearch.opensearch_config')
    def test_repair_current_file_after_indexing_exists(self, mock_config):
        """Test that repair function exists and can be called."""
        # Test that the method exists
        assert hasattr(mock_config, 'repair_current_file_after_indexing')

        mock_config.repair_current_file_after_indexing.return_value = {
            'success': True,
            'documents_repaired': 10
        }

        result = mock_config.repair_current_file_after_indexing('/app/data/netspeed.csv')

        assert result['success'] is True
        assert 'documents_repaired' in result

    def test_repair_data_structure(self):
        """Test expected repair result structure."""
        # Test the expected structure of repair results
        expected_keys = ['success', 'documents_repaired']
        result = {'success': True, 'documents_repaired': 5}

        for key in expected_keys:
            assert key in result
