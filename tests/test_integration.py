#!/usr/bin/env python3
"""
Integration tests for GitLab MR Review system.

These tests validate the end-to-end workflow and integration between components.
"""

import pytest
import responses
import os
import tempfile
import json
from unittest.mock import patch, Mock, MagicMock
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitlab_integration import GitLabClient, MRAnalyzer, ReviewGenerator
from gitlab_integration.batch_processor import BatchProcessor
from gitlab_integration.ci_integration import GitLabCIIntegration
from gitlab_review import GitLabReviewCLI


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Integration tests for complete MR review workflow."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.gitlab_url = "https://gitlab.example.com"
        self.token = "test-token-123"
        self.project_path = "group/test-project"
        self.mr_iid = 123
        
        # Mock user response for GitLab client
        self.mock_user_response = {
            "id": 1,
            "username": "testuser",
            "name": "Test User"
        }
        
        # Mock MR data
        self.mock_mr_data = {
            "iid": self.mr_iid,
            "title": "Add new feature",
            "description": "This MR adds a new feature to the application",
            "state": "opened",
            "author": {"username": "developer", "name": "Dev User"},
            "source_branch": "feature/new-feature",
            "target_branch": "main",
            "labels": [{"name": "enhancement"}],
            "upvotes": 1,
            "draft": False,
            "work_in_progress": False
        }
        
        # Mock changes data
        self.mock_changes_data = {
            "changes": [
                {
                    "old_path": "src/main.py",
                    "new_path": "src/main.py",
                    "diff": "@@ -1,5 +1,10 @@\n def main():\n     print('Hello')\n+    print('New feature')\n+    return True\n"
                },
                {
                    "old_path": "tests/test_main.py",
                    "new_path": "tests/test_main.py",
                    "diff": "@@ -1,3 +1,8 @@\n def test_main():\n     assert True\n+\n+def test_new_feature():\n+    assert main() is True\n"
                }
            ]
        }
        
        # Mock RAG system
        self.mock_rag_system = Mock()
        self.mock_rag_system.query_codebase.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "file_path": "src/related.py",
                            "content": "def related_function(): pass",
                            "functions": ["related_function"]
                        }
                    }
                ]
            }
        }
    
    @responses.activate
    def test_complete_mr_review_workflow(self):
        """Test complete MR review workflow from URL to posted review."""
        # Setup GitLab API responses
        self._setup_gitlab_responses()
        
        # Setup Ollama response
        responses.add(
            responses.POST,
            "http://host.docker.internal:11434/api/generate",
            json={
                "response": """
                **Summary**
                This MR adds a new feature with proper test coverage. The implementation looks clean and follows good practices.
                
                **Detailed Comments**
                - Good addition of the new feature functionality
                - Appropriate test coverage has been added
                - Code style is consistent with the existing codebase
                
                **Recommendations**
                - Consider adding documentation for the new feature
                - Verify performance impact of the new functionality
                """
            },
            status=200
        )
        
        # Initialize components
        gitlab_client = GitLabClient(self.gitlab_url, self.token)
        mr_analyzer = MRAnalyzer(self.mock_rag_system)
        review_generator = ReviewGenerator(self.mock_rag_system)
        
        # Create CLI and perform review
        cli = GitLabReviewCLI()
        cli.gitlab_client = gitlab_client
        cli.rag_system = self.mock_rag_system
        cli.mr_analyzer = mr_analyzer
        cli.review_generator = review_generator
        
        mr_url = f"{self.gitlab_url}/{self.project_path}/-/merge_requests/{self.mr_iid}"
        
        # Execute review
        result = cli.review_mr_from_url(mr_url, review_type="general", post_review=True)
        
        # Verify results
        assert result["success"] is True
        assert result["mr_iid"] == self.mr_iid
        assert result["project_path"] == self.project_path
        assert result["posted"] is True
        
        # Verify analysis was performed
        analysis = result["analysis"]
        assert "mr_info" in analysis
        assert "impact_analysis" in analysis
        assert "file_changes" in analysis
        assert analysis["mr_info"]["iid"] == self.mr_iid
        
        # Verify review was generated
        review = result["review"]
        assert "summary" in review
        assert "detailed_comments" in review
        assert "recommendations" in review
        assert "overall_assessment" in review
        assert review["metadata"]["review_type"] == "python"  # Auto-detected
        
        # Verify RAG system was queried
        self.mock_rag_system.query_codebase.assert_called()
    
    @responses.activate
    def test_batch_processing_workflow(self):
        """Test batch processing of multiple MRs."""
        # Setup GitLab API responses for multiple MRs
        self._setup_gitlab_responses()
        
        # Mock project MRs list
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/projects/{self.project_path.replace('/', '%2F')}/merge_requests",
            json=[
                self.mock_mr_data,
                {
                    "iid": 124,
                    "title": "Fix bug",
                    "state": "opened",
                    "author": {"username": "developer2"},
                    "labels": [{"name": "bugfix"}]
                }
            ],
            status=200
        )
        
        # Mock changes for second MR
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/projects/{self.project_path.replace('/', '%2F')}/merge_requests/124/changes",
            json=self.mock_changes_data,
            status=200
        )
        
        # Setup Ollama responses
        responses.add(
            responses.POST,
            "http://host.docker.internal:11434/api/generate",
            json={"response": "**Summary**\nGood changes overall."},
            status=200
        )
        
        # Initialize components
        gitlab_client = GitLabClient(self.gitlab_url, self.token)
        mr_analyzer = MRAnalyzer(self.mock_rag_system)
        review_generator = ReviewGenerator(self.mock_rag_system)
        batch_processor = BatchProcessor(gitlab_client, mr_analyzer, review_generator)
        
        # Execute batch processing
        summary = batch_processor.process_project_mrs(
            project_path=self.project_path,
            max_reviews=2,
            parallel_workers=1
        )
        
        # Verify results
        assert summary.total_mrs == 2
        assert summary.successful_reviews == 2
        assert summary.failed_reviews == 0
        assert summary.project_path == self.project_path
        assert summary.success_rate() == 100.0
        
        # Verify results were stored
        assert len(batch_processor.results) == 2
        assert all(r.success for r in batch_processor.results)
    
    @responses.activate 
    def test_ci_integration_workflow(self):
        """Test CI integration workflow."""
        # Setup environment variables for GitLab CI
        original_env = os.environ.copy()
        os.environ.update({
            "GITLAB_CI": "true",
            "CI_MERGE_REQUEST_IID": str(self.mr_iid),
            "CI_PROJECT_PATH": self.project_path,
            "CI_PIPELINE_ID": "12345",
            "CI_JOB_ID": "67890"
        })
        
        try:
            # Setup GitLab API responses
            self._setup_gitlab_responses()
            
            # Setup Ollama response
            responses.add(
                responses.POST,
                "http://host.docker.internal:11434/api/generate",
                json={"response": "**Summary**\nAutomated CI review looks good."},
                status=200
            )
            
            # Initialize components
            gitlab_client = GitLabClient(self.gitlab_url, self.token)
            mr_analyzer = MRAnalyzer(self.mock_rag_system)
            review_generator = ReviewGenerator(self.mock_rag_system)
            ci_integration = GitLabCIIntegration(gitlab_client, mr_analyzer, review_generator)
            
            # Enable auto-posting for CI
            ci_integration.config.auto_post = True
            
            # Execute CI review
            result = ci_integration.run_ci_review()
            
            # Verify results
            assert result["success"] is True
            assert result["skipped"] is False
            assert result["mr_info"]["iid"] == self.mr_iid
            assert result["review"]["posted"] is True
            assert result["ci_env"]["platform"] == "gitlab"
            
        finally:
            # Restore environment
            os.environ.clear()
            os.environ.update(original_env)
    
    @responses.activate
    def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        # Setup GitLab client connection
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/user",
            json=self.mock_user_response,
            status=200
        )
        
        # Mock MR data response
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/projects/{self.project_path.replace('/', '%2F')}/merge_requests/{self.mr_iid}",
            json=self.mock_mr_data,
            status=200
        )
        
        # Mock initial failed changes request
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/projects/{self.project_path.replace('/', '%2F')}/merge_requests/{self.mr_iid}/changes",
            status=500
        )
        
        # Mock successful retry
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/projects/{self.project_path.replace('/', '%2F')}/merge_requests/{self.mr_iid}/changes",
            json=self.mock_changes_data,
            status=200
        )
        
        # Setup Ollama response
        responses.add(
            responses.POST,
            "http://host.docker.internal:11434/api/generate",
            json={"response": "**Summary**\nReview after retry."},
            status=200
        )
        
        # Initialize components with retry
        gitlab_client = GitLabClient(self.gitlab_url, self.token)
        mr_analyzer = MRAnalyzer(self.mock_rag_system)
        review_generator = ReviewGenerator(self.mock_rag_system)
        
        # Use resilient HTTP session for GitLab client
        from gitlab_integration.error_handler import ResilientHTTPSession, RetryConfig
        retry_config = RetryConfig(max_attempts=2, base_delay=0.1)
        resilient_session = ResilientHTTPSession(retry_config)
        
        # Patch the session to use resilient one
        with patch.object(gitlab_client, 'session', resilient_session.session):
            # This should succeed after retry
            result = gitlab_client.get_mr_changes(self.project_path, self.mr_iid)
            assert "changes" in result
    
    def test_configuration_loading_and_validation(self):
        """Test configuration loading and validation."""
        # Create temporary config file
        config_data = {
            "ci": {
                "enabled": True,
                "review_type": "security",
                "auto_post": False,
                "trigger_on_draft": True
            },
            "gitlab": {
                "url": "https://gitlab.example.com"
            },
            "rag": {
                "ollama_host": "http://localhost:11434",
                "chat_model": "qwen2.5-coder"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            # Test config loading
            with patch("pathlib.Path.exists", return_value=True):
                with patch("builtins.open", open(config_path, 'r')):
                    ci_integration = GitLabCIIntegration(None, None, None)
                    
                    # Verify config was loaded
                    assert ci_integration.config.enabled is True
                    assert ci_integration.config.review_type == "security"
                    assert ci_integration.config.auto_post is False
                    assert ci_integration.config.trigger_on_draft is True
        
        finally:
            # Cleanup
            os.unlink(config_path)
    
    @responses.activate
    def test_template_auto_detection(self):
        """Test automatic template detection based on file types."""
        # Setup GitLab API responses
        self._setup_gitlab_responses()
        
        # Mock changes with JavaScript files
        js_changes = {
            "changes": [
                {
                    "old_path": "src/app.js",
                    "new_path": "src/app.js", 
                    "diff": "@@ -1,3 +1,5 @@\n function hello() {\n   console.log('hello');\n+  return true;\n }\n"
                }
            ]
        }
        
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/projects/{self.project_path.replace('/', '%2F')}/merge_requests/{self.mr_iid}/changes",
            json=js_changes,
            status=200
        )
        
        # Setup Ollama response
        responses.add(
            responses.POST,
            "http://host.docker.internal:11434/api/generate",
            json={"response": "**Summary**\nJavaScript review completed."},
            status=200
        )
        
        # Initialize components
        gitlab_client = GitLabClient(self.gitlab_url, self.token)
        mr_analyzer = MRAnalyzer(self.mock_rag_system)
        review_generator = ReviewGenerator(self.mock_rag_system)
        
        # Get MR data and changes
        mr_data = gitlab_client.get_merge_request(self.project_path, self.mr_iid)
        changes_data = gitlab_client.get_mr_changes(self.project_path, self.mr_iid)
        
        # Analyze changes
        analysis = mr_analyzer.analyze_mr_changes(mr_data, changes_data)
        
        # Generate review with auto-detection
        review = review_generator.generate_review(analysis, "general", auto_detect_language=True)
        
        # Verify JavaScript template was used
        assert review["metadata"]["review_type"] == "javascript"
    
    def _setup_gitlab_responses(self):
        """Setup common GitLab API responses."""
        # User response for connection validation
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/user",
            json=self.mock_user_response,
            status=200
        )
        
        # MR data response
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/projects/{self.project_path.replace('/', '%2F')}/merge_requests/{self.mr_iid}",
            json=self.mock_mr_data,
            status=200
        )
        
        # MR changes response
        responses.add(
            responses.GET,
            f"{self.gitlab_url}/api/v4/projects/{self.project_path.replace('/', '%2F')}/merge_requests/{self.mr_iid}/changes",
            json=self.mock_changes_data,
            status=200
        )
        
        # Note posting response
        responses.add(
            responses.POST,
            f"{self.gitlab_url}/api/v4/projects/{self.project_path.replace('/', '%2F')}/merge_requests/{self.mr_iid}/notes",
            json={"id": 789, "body": "Review comment"},
            status=201
        )


@pytest.mark.integration
class TestPerformanceAndScalability:
    """Performance and scalability tests."""
    
    def test_large_mr_handling(self):
        """Test handling of large MRs with many files."""
        # Create mock data for large MR
        large_changes = {
            "changes": [
                {
                    "old_path": f"src/file_{i}.py",
                    "new_path": f"src/file_{i}.py",
                    "diff": f"@@ -1,1 +1,2 @@\n # File {i}\n+print('hello {i}')\n"
                }
                for i in range(50)  # 50 files
            ]
        }
        
        mock_rag_system = Mock()
        mock_rag_system.query_codebase.return_value = {"hits": {"hits": []}}
        
        # Initialize analyzer
        mr_analyzer = MRAnalyzer(mock_rag_system)
        
        # Mock MR data
        mr_data = {
            "iid": 123,
            "title": "Large MR",
            "author": {"username": "dev"},
            "source_branch": "feature",
            "target_branch": "main",
            "description": "Large changes"
        }
        
        # Analyze large MR
        import time
        start_time = time.time()
        
        analysis = mr_analyzer.analyze_mr_changes(mr_data, large_changes)
        
        processing_time = time.time() - start_time
        
        # Verify analysis completed
        assert analysis["impact_analysis"]["files_count"] == 50
        assert processing_time < 10.0  # Should complete within 10 seconds
    
    def test_concurrent_processing(self):
        """Test concurrent processing capabilities."""
        from concurrent.futures import ThreadPoolExecutor
        import time
        
        def mock_process_mr(mr_id):
            # Simulate processing time
            time.sleep(0.1)
            return {"mr_id": mr_id, "success": True}
        
        # Test processing multiple MRs concurrently
        mr_ids = list(range(10))
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(mock_process_mr, mr_ids))
        
        processing_time = time.time() - start_time
        
        # Verify all processed successfully
        assert len(results) == 10
        assert all(r["success"] for r in results)
        
        # Should be faster than sequential processing
        assert processing_time < 1.0  # Should complete much faster than 1 second


@pytest.mark.integration
class TestDataConsistency:
    """Data consistency and integrity tests."""
    
    def test_analysis_data_consistency(self):
        """Test consistency of analysis data across components."""
        mock_rag_system = Mock()
        mock_rag_system.query_codebase.return_value = {"hits": {"hits": []}}
        
        # Initialize components
        mr_analyzer = MRAnalyzer(mock_rag_system)
        review_generator = ReviewGenerator(mock_rag_system)
        
        # Mock data
        mr_data = {
            "iid": 123,
            "title": "Test MR",
            "author": {"username": "dev"},
            "source_branch": "feature",
            "target_branch": "main",
            "description": "Test"
        }
        
        changes_data = {
            "changes": [
                {
                    "old_path": "test.py",
                    "new_path": "test.py",
                    "diff": "@@ -1,1 +1,2 @@\n print('test')\n+print('new')\n"
                }
            ]
        }
        
        # Analyze changes
        analysis = mr_analyzer.analyze_mr_changes(mr_data, changes_data)
        
        # Verify data consistency
        assert analysis["mr_info"]["iid"] == mr_data["iid"]
        assert analysis["mr_info"]["title"] == mr_data["title"]
        assert len(analysis["file_changes"]) == len(changes_data["changes"])
        
        # Verify impact analysis consistency
        impact = analysis["impact_analysis"]
        assert impact["files_count"] == len(changes_data["changes"])
        assert impact["lines_added"] >= 0
        assert impact["lines_removed"] >= 0
        assert 0 <= impact["complexity_score"] <= 100


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'integration'])