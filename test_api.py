"""
Test suite for Log Monitoring Service API
"""

import pytest
import os
from pathlib import Path
from fastapi.testclient import TestClient
from app import app, BASE_LOG_DIR

# Create test client
client = TestClient(app)


class TestLogMonitoringAPI:
    """Test cases for the Log Monitoring Service API"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        # Ensure log directory exists
        BASE_LOG_DIR.mkdir(parents=True, exist_ok=True)
        yield
        # Cleanup can be added here if needed

    def test_root_endpoint(self):
        """Test the root endpoint returns API information"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert data["service"] == "Log Monitoring Service"
        assert "endpoints" in data

    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_list_logs_root(self):
        """Test listing log files in root directory"""
        response = client.get("/logs/list")
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert "total_files" in data

        # Check if our test files are listed
        filenames = [f["filename"] for f in data["files"]]
        assert "log1.txt" in filenames
        assert "log2.txt" in filenames
        assert "apache/log3.txt" in filenames

    def test_list_logs_subdirectory(self):
        """Test listing log files in subdirectory"""
        response = client.get("/logs/list?directory=apache")
        assert response.status_code == 200
        data = response.json()
        assert "files" in data

        filenames = [f["filename"] for f in data["files"]]
        # The filename includes the relative path from var/log
        assert any("log3.txt" in f for f in filenames)

    def test_get_logs_basic(self):
        """Test basic log fetching"""
        response = client.get("/logs?filename=log1.txt&entries=5")
        assert response.status_code == 200
        data = response.json()

        assert data["filename"] == "log1.txt"
        assert data["returned_lines"] <= 5
        assert isinstance(data["entries"], list)
        assert not data["filtered"]

        # Check that entries are in reverse order (newest first)
        if len(data["entries"]) > 0:
            # The last entry should contain "shutdown" based on our test data
            assert "shutdown" in data["entries"][0].lower()

    def test_get_logs_with_filter(self):
        """Test log fetching with keyword filter"""
        response = client.get("/logs?filename=log1.txt&entries=10&keyword=ERROR")
        assert response.status_code == 200
        data = response.json()

        assert data["filtered"] == True
        # All returned entries should contain "ERROR"
        for entry in data["entries"]:
            assert "ERROR" in entry.upper()

    def test_get_logs_nested_file(self):
        """Test fetching logs from nested directory"""
        response = client.get("/logs?filename=apache/log3.txt&entries=5")
        assert response.status_code == 200
        data = response.json()

        assert data["filename"] == "apache/log3.txt"
        assert data["returned_lines"] <= 5

        # Check that we got apache logs
        if len(data["entries"]) > 0:
            assert "apache" in data["entries"][0].lower()

    def test_get_logs_nonexistent_file(self):
        """Test error handling for non-existent file"""
        response = client.get("/logs?filename=nonexistent.txt")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_logs_invalid_filename(self):
        """Test security: prevent directory traversal"""
        response = client.get("/logs?filename=../../../etc/passwd")
        assert response.status_code == 400
        data = response.json()
        assert "invalid" in data["detail"].lower()

    def test_get_logs_invalid_entries_param(self):
        """Test validation of entries parameter"""
        # Test with too many entries
        response = client.get("/logs?filename=log1.txt&entries=20000")
        assert response.status_code == 422  # Validation error

        # Test with negative entries
        response = client.get("/logs?filename=log1.txt&entries=-1")
        assert response.status_code == 422

    def test_stream_logs_endpoint(self):
        """Test the streaming endpoint for large files"""
        response = client.get("/logs/stream?filename=log2.txt&entries=3")
        assert response.status_code == 200

        # Parse the streamed JSON
        import json
        data = json.loads(response.text)
        assert "entries" in data
        assert isinstance(data["entries"], list)
        assert len(data["entries"]) <= 3

    def test_case_insensitive_filter(self):
        """Test that keyword filtering is case-insensitive"""
        response1 = client.get("/logs?filename=log1.txt&entries=10&keyword=error")
        response2 = client.get("/logs?filename=log1.txt&entries=10&keyword=ERROR")

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Both should return the same number of entries
        assert len(data1["entries"]) == len(data2["entries"])

    def test_empty_log_file(self):
        """Test handling of empty log files"""
        # Create an empty log file
        empty_file = BASE_LOG_DIR / "empty.txt"
        empty_file.touch()

        response = client.get("/logs?filename=empty.txt")
        assert response.status_code == 200
        data = response.json()
        assert data["returned_lines"] == 0
        assert data["entries"] == []

        # Clean up
        empty_file.unlink()

    def test_large_entries_request(self):
        """Test fetching many entries"""
        response = client.get("/logs?filename=log1.txt&entries=1000")
        assert response.status_code == 200
        data = response.json()

        # Should return all available lines (we have 20 in log1.txt)
        assert data["returned_lines"] <= 1000
        assert len(data["entries"]) > 0


class TestPerformance:
    """Performance tests for large file handling"""

    @pytest.fixture
    def large_log_file(self, tmp_path):
        """Create a large test log file"""
        large_file = BASE_LOG_DIR / "large_test.txt"

        # Generate a 10MB file with sample log entries
        with open(large_file, 'w') as f:
            for i in range(100000):
                f.write(f"2024-11-30 12:00:{i:02d} INFO Test log entry number {i}\n")

        yield large_file

        # Cleanup
        large_file.unlink()

    def test_large_file_performance(self, large_log_file):
        """Test that large files are handled efficiently"""
        import time

        start_time = time.time()
        response = client.get(f"/logs?filename={large_log_file.name}&entries=100")
        end_time = time.time()

        assert response.status_code == 200
        data = response.json()
        assert data["returned_lines"] == 100

        # Should complete in reasonable time (< 2 seconds for 10MB file)
        assert (end_time - start_time) < 2.0

    def test_large_file_with_filter(self, large_log_file):
        """Test filtering on large files"""
        response = client.get(f"/logs?filename={large_log_file.name}&entries=50&keyword=99999")

        assert response.status_code == 200
        data = response.json()

        # Should find the entry with "99999"
        assert data["returned_lines"] >= 1
        for entry in data["entries"]:
            assert "99999" in entry


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
