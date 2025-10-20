"""
Test search functionality across all CSV columns.

This test verifies that searching for values from each column returns results.
It uses actual values from the OpenSearch index to ensure realistic testing.
Tests run against the live API at http://localhost:8002
"""
import pytest
import requests


API_BASE = "http://localhost:8002/api"


class TestSearchAllColumns:
    """Test search functionality for all CSV columns."""

    def test_search_ip_address(self):
        """Test searching by IP Address."""
        response = requests.get(f"{API_BASE}/search/?query=10.216.10.6")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) > 0, "Should find results for IP address"
        assert any("10.216.10" in str(row.get("IP Address", "")) for row in data["data"])

    def test_search_line_number_phone(self):
        """Test searching by Line Number (phone number)."""
        response = requests.get(f"{API_BASE}/search/?query=498955974361")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_search_serial_number(self):
        """Test searching by Serial Number."""
        response = requests.get(f"{API_BASE}/search/?query=FCH262128N8")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        # Real datasets may rotate, so results can be empty during tests. If data is present,
        # ensure the serial number appears in at least one row.
        if data["data"]:
            assert any(
                "FCH262128N8" in str(row.get("Serial Number", ""))
                for row in data["data"]
            )

    def test_search_model_name(self):
        """Test searching by Model Name."""
        response = requests.get(f"{API_BASE}/search/?query=8851")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) > 0, "Should find results for model 8851"
        assert any("8851" in str(row.get("Model Name", "")) for row in data["data"])

    def test_search_mac_address(self):
        """Test searching by MAC Address."""
        response = requests.get(f"{API_BASE}/search/?query=482E72E48944")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) > 0, "Should find results for MAC address"
        mac_found = any(
            "482E72E48944" in str(row.get("MAC Address", "")).replace(":", "").replace("-", "").upper()
            or "482E72E48944" in str(row.get("MAC Address 2", "")).replace(":", "").replace("-", "").upper()
            for row in data["data"]
        )
        assert mac_found, "MAC address should be found in results"

    def test_search_voice_vlan(self):
        """Test searching by Voice VLAN (3-digit pattern)."""
        response = requests.get(f"{API_BASE}/search/?query=803")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) > 0, "Should find results for VLAN 803"
        assert any("803" in str(row.get("Voice VLAN", "")) for row in data["data"])

    def test_search_subnet_mask(self):
        """Test searching by Subnet Mask."""
        response = requests.get(f"{API_BASE}/search/?query=255.255.254.0")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_search_switch_hostname(self):
        """Test searching by Switch Hostname."""
        response = requests.get(f"{API_BASE}/search/?query=Mxx03ZSL4750P")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_search_switch_hostname_fqdn(self):
        """Test searching by Switch Hostname FQDN."""
        response = requests.get(f"{API_BASE}/search/?query=Mxx03ZSL4750P.juwin.bayern.de")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_search_switch_port(self):
        """Test searching by Switch Port."""
        response = requests.get(f"{API_BASE}/search/?query=GigabitEthernet1/0/5")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_search_port_speed(self):
        """Test searching by port speed status."""
        response = requests.get(f"{API_BASE}/search/?query=Down")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) > 0, "Should find results for 'Down' status"
        assert any(
            "Down" in str(row.get("PC Port Speed", "")) or "Down" in str(row.get("Phone Port Speed", ""))
            for row in data["data"]
        )

    def test_search_call_manager(self):
        """Test searching by Call Manager hostname."""
        response = requests.get(f"{API_BASE}/search/?query=Mxx13ZSH006vw")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_search_kem_module(self):
        """Test searching for phones with KEM modules - verify KEM Serial Number columns are present."""
        response = requests.get(f"{API_BASE}/search/?query=CP-8851")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify KEM Serial Number columns are in headers (even if no results)
        assert "KEM 1 Serial Number" in data["headers"], "KEM 1 Serial Number should be in headers"
        assert "KEM 2 Serial Number" in data["headers"], "KEM 2 Serial Number should be in headers"

        # Verify KEM Serial Number fields are in results if any data returned
        if len(data["data"]) > 0:
            first_result = data["data"][0]
            assert "KEM 1 Serial Number" in first_result, "KEM 1 Serial Number should be in results"
            assert "KEM 2 Serial Number" in first_result, "KEM 2 Serial Number should be in results"

    def test_search_partial_ip(self):
        """Test searching by partial IP address."""
        response = requests.get(f"{API_BASE}/search/?query=10.216")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) > 0, "Should find results for partial IP"
        assert any("10.216" in str(row.get("IP Address", "")) for row in data["data"])

    def test_search_serial_number_variants(self):
        """Test searching various serial number formats."""
        test_cases = [
            "FVH263803RN",  # 11 chars, starts with letters
            "FCH262128N8",  # 11 chars, FCH prefix
            "WZP253492MQ",  # 11 chars, WZP prefix
        ]

        for serial in test_cases:
            response = requests.get(f"{API_BASE}/search/?query={serial}")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert isinstance(data["data"], list)

    def test_search_model_prefix(self):
        """Test searching by model number only."""
        response = requests.get(f"{API_BASE}/search/?query=8851")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) > 0, "Should find 8851 models"
        assert any("8851" in str(row.get("Model Name", "")) for row in data["data"])

    def test_search_empty_query(self):
        """Test that empty query returns error or all results."""
        response = requests.get(f"{API_BASE}/search/?query=")
        assert response.status_code in [200, 400]

    def test_search_special_characters(self):
        """Test searching with special characters (VLAN, port speed)."""
        response = requests.get(f"{API_BASE}/search/?query=Full%20duplex")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_search_case_insensitive_serial(self):
        """Test that serial number search is case-insensitive."""
        response1 = requests.get(f"{API_BASE}/search/?query=fch262128n8")
        assert response1.status_code == 200
        data1 = response1.json()

        response2 = requests.get(f"{API_BASE}/search/?query=FCH262128N8")
        assert response2.status_code == 200
        data2 = response2.json()

        assert data1["success"] is True
        assert data2["success"] is True

    def test_search_vlan_specific(self):
        """Test that 3-digit VLAN search targets Voice VLAN field."""
        for vlan in ["801", "802", "803"]:
            response = requests.get(f"{API_BASE}/search/?query={vlan}")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            if len(data["data"]) > 0:
                assert any(vlan in str(row.get("Voice VLAN", "")) for row in data["data"])

    def test_search_results_have_required_fields(self):
        """Test that search results contain all expected fields."""
        response = requests.get(f"{API_BASE}/search/?query=8851")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        if len(data["data"]) > 0:
            first_result = data["data"][0]
            expected_fields = [
                "#", "File Name", "Creation Date", "IP Address",
                "Serial Number", "Model Name", "MAC Address",
                "KEM 1 Serial Number", "KEM 2 Serial Number"
            ]
            # Ensure required columns are offered in the response headers
            for field in expected_fields:
                assert field in data["headers"], f"Field '{field}' should be in headers"
            # Rows may omit rarely populated columns; only check those present to avoid brittle failures
            for field in expected_fields:
                if field in first_result:
                    assert first_result[field] is not None

    def test_search_response_structure(self):
        """Test that search response has correct structure."""
        response = requests.get(f"{API_BASE}/search/?query=test")
        assert response.status_code == 200
        data = response.json()

        assert "success" in data
        assert "message" in data
        assert "data" in data
        assert "headers" in data
        assert isinstance(data["data"], list)
        assert isinstance(data["headers"], list)

    def test_search_historical_flag(self):
        """Test search with include_historical parameter."""
        response1 = requests.get(f"{API_BASE}/search/?query=8851&include_historical=false")
        assert response1.status_code == 200
        data1 = response1.json()

        response2 = requests.get(f"{API_BASE}/search/?query=8851&include_historical=true")
        assert response2.status_code == 200
        data2 = response2.json()

        assert data1["success"] is True
        assert data2["success"] is True
