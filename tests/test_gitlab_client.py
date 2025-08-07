#!/usr/bin/env python3
"""
Tests for GitLab API client.
"""

import pytest
import responses
import json
from unittest.mock import patch, Mock
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitlab_integration.gitlab_client import GitLabClient


class TestGitLabClient:
    """Test cases for GitLab API client."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.gitlab_url = "https://gitlab.example.com"
        self.token = "test-token-123"
        
        # Mock user info response for connection validation
        self.mock_user_response = {
            "id": 1,
            "username": "testuser",
            "name": "Test User",
            "email": "test@example.com"
        }
    
    @responses.activate
    def test_client_initialization_success(self):
        """Test successful client initialization."""
        # Mock the user API call for connection validation
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/user",
            json=self.mock_user_response,
            status=200
        )
        
        client = GitLabClient(self.gitlab_url, self.token)
        
        assert client.gitlab_url == f"{self.gitlab_url}/"
        assert client.token == self.token
        assert client.api_url == f"{self.gitlab_url}/api/v4/"
    
    @responses.activate
    def test_client_initialization_connection_failure(self):
        """Test client initialization with connection failure."""
        # Mock failed connection
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/user",
            status=401
        )
        
        with pytest.raises(ConnectionError):
            GitLabClient(self.gitlab_url, self.token)
    
    def test_client_initialization_no_token(self):
        """Test client initialization without token."""
        with pytest.raises(ValueError, match="GitLab token is required"):
            GitLabClient(self.gitlab_url, None)
    
    @responses.activate
    def test_get_project_success(self):
        """Test successful project retrieval."""
        # Setup client
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/user",
            json=self.mock_user_response,
            status=200
        )
        
        client = GitLabClient(self.gitlab_url, self.token)
        
        # Mock project response
        project_data = {
            "id": 123,
            "name": "test-project",
            "path_with_namespace": "group/test-project",
            "web_url": f"{self.gitlab_url}/group/test-project"
        }
        
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/projects/group%2Ftest-project",
            json=project_data,
            status=200
        )
        
        result = client.get_project("group/test-project")
        assert result["name"] == "test-project"
        assert result["id"] == 123
    
    @responses.activate
    def test_get_merge_request_success(self):
        """Test successful MR retrieval."""
        # Setup client
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/user",
            json=self.mock_user_response,
            status=200
        )
        
        client = GitLabClient(self.gitlab_url, self.token)
        
        # Mock MR response
        mr_data = {
            "iid": 123,
            "title": "Test MR",
            "description": "Test description",
            "state": "opened",
            "author": {"username": "testuser"},
            "source_branch": "feature",
            "target_branch": "main"
        }
        
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/projects/group%2Ftest-project/merge_requests/123",
            json=mr_data,
            status=200
        )
        
        result = client.get_merge_request("group/test-project", 123)
        assert result["iid"] == 123
        assert result["title"] == "Test MR"
        assert result["state"] == "opened"
    
    @responses.activate
    def test_get_mr_changes_success(self):
        """Test successful MR changes retrieval."""
        # Setup client
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/user",
            json=self.mock_user_response,
            status=200
        )
        
        client = GitLabClient(self.gitlab_url, self.token)
        
        # Mock changes response
        changes_data = {
            "changes": [
                {
                    "old_path": "file1.py",
                    "new_path": "file1.py",
                    "diff": "@@ -1,3 +1,3 @@\n print('hello')\n-print('old')\n+print('new')\n"
                }
            ]
        }
        
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/projects/group%2Ftest-project/merge_requests/123/changes",
            json=changes_data,
            status=200
        )
        
        result = client.get_mr_changes("group/test-project", 123)
        assert len(result["changes"]) == 1
        assert result["changes"][0]["new_path"] == "file1.py"
    
    @responses.activate
    def test_post_mr_note_success(self):
        """Test successful MR note posting."""
        # Setup client
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/user",
            json=self.mock_user_response,
            status=200
        )
        
        client = GitLabClient(self.gitlab_url, self.token)
        
        # Mock note response
        note_data = {
            "id": 456,
            "body": "Test review comment",
            "author": {"username": "testuser"},
            "created_at": "2023-01-01T00:00:00Z"
        }
        
        responses.add(
            responses.POST,
            f"{self.gitlab_url}/api/v4/projects/group%2Ftest-project/merge_requests/123/notes",
            json=note_data,
            status=201
        )
        
        result = client.post_mr_note("group/test-project", 123, "Test review comment")
        assert result["id"] == 456
        assert result["body"] == "Test review comment"
    
    def test_parse_mr_url_success(self):
        """Test successful MR URL parsing."""
        # Mock connection validation
        with patch.object(GitLabClient, '_validate_connection', return_value=True):
            client = GitLabClient(self.gitlab_url, self.token)
        
        test_cases = [
            (
                "https://gitlab.com/group/project/-/merge_requests/123",
                ("group/project", 123)
            ),
            (
                "https://gitlab.example.com/namespace/subgroup/project/-/merge_requests/456",
                ("namespace/subgroup/project", 456)
            )
        ]
        
        for url, expected in test_cases:
            result = client.parse_mr_url(url)
            assert result == expected
    
    def test_parse_mr_url_invalid(self):
        """Test MR URL parsing with invalid URLs."""
        # Mock connection validation
        with patch.object(GitLabClient, '_validate_connection', return_value=True):
            client = GitLabClient(self.gitlab_url, self.token)
        
        invalid_urls = [
            "https://gitlab.com/group/project",
            "https://gitlab.com/group/project/-/issues/123",
            "invalid-url",
            ""
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValueError):
                client.parse_mr_url(url)
    
    @responses.activate
    def test_get_mr_from_url_success(self):
        """Test successful MR retrieval from URL."""
        # Setup client
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/user",
            json=self.mock_user_response,
            status=200
        )
        
        client = GitLabClient(self.gitlab_url, self.token)
        
        # Mock MR response
        mr_data = {
            "iid": 123,
            "title": "Test MR",
            "state": "opened"
        }
        
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/projects/group%2Fproject/merge_requests/123",
            json=mr_data,
            status=200
        )
        
        url = f"{self.gitlab_url}/group/project/-/merge_requests/123"
        result = client.get_mr_from_url(url)
        
        assert result["iid"] == 123
        assert result["title"] == "Test MR"
        assert "_gitlab_client_meta" in result
        assert result["_gitlab_client_meta"]["project_path"] == "group/project"
        assert result["_gitlab_client_meta"]["mr_iid"] == 123
        assert result["_gitlab_client_meta"]["original_url"] == url
    
    @responses.activate 
    def test_get_project_merge_requests_success(self):
        """Test successful project MRs listing."""
        # Setup client
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/user",
            json=self.mock_user_response,
            status=200
        )
        
        client = GitLabClient(self.gitlab_url, self.token)
        
        # Mock MRs response
        mrs_data = [
            {
                "iid": 1,
                "title": "MR 1",
                "state": "opened"
            },
            {
                "iid": 2,
                "title": "MR 2", 
                "state": "opened"
            }
        ]
        
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/projects/group%2Fproject/merge_requests",
            json=mrs_data,
            status=200
        )
        
        result = client.get_project_merge_requests("group/project")
        assert len(result) == 2
        assert result[0]["iid"] == 1
        assert result[1]["iid"] == 2
    
    @responses.activate
    def test_api_request_error_handling(self):
        """Test API error handling."""
        # Setup client
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/user",
            json=self.mock_user_response,
            status=200
        )
        
        client = GitLabClient(self.gitlab_url, self.token)
        
        # Mock error response
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/projects/nonexistent",
            status=404
        )
        
        with pytest.raises(Exception):
            client.get_project("nonexistent")


if __name__ == '__main__':
    pytest.main([__file__])