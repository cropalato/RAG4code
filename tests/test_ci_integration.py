#!/usr/bin/env python3
"""
Tests for CI Integration.
"""

import pytest
import os
from unittest.mock import Mock, patch, mock_open
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitlab_integration.ci_integration import GitLabCIIntegration, CIConfig


class TestCIConfig:
    """Test cases for CIConfig dataclass."""
    
    def test_ci_config_defaults(self):
        """Test CIConfig with default values."""
        config = CIConfig()
        
        assert config.enabled is True
        assert config.review_type == "general"
        assert config.auto_post is False
        assert config.trigger_on_draft is False
        assert config.trigger_on_wip is False
        assert config.required_approvals == 0
        assert config.review_on_labels == []
        assert config.skip_on_labels == ["skip-review", "no-review"]
        assert config.parallel_workers == 1
        assert config.timeout_minutes == 30
    
    def test_ci_config_custom_values(self):
        """Test CIConfig with custom values."""
        config = CIConfig(
            enabled=False,
            review_type="security",
            auto_post=True,
            trigger_on_draft=True,
            required_approvals=2,
            review_on_labels=["needs-review"],
            skip_on_labels=["wip"],
            parallel_workers=3,
            timeout_minutes=60
        )
        
        assert config.enabled is False
        assert config.review_type == "security"
        assert config.auto_post is True
        assert config.trigger_on_draft is True
        assert config.required_approvals == 2
        assert config.review_on_labels == ["needs-review"]
        assert config.skip_on_labels == ["wip"]
        assert config.parallel_workers == 3
        assert config.timeout_minutes == 60


class TestGitLabCIIntegration:
    """Test cases for GitLab CI Integration."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.mock_gitlab_client = Mock()
        self.mock_mr_analyzer = Mock()
        self.mock_review_generator = Mock()
        
        # Clear environment variables
        self.original_env = os.environ.copy()
        for key in os.environ.keys():
            if key.startswith(('CI_', 'GITLAB_CI', 'GITHUB_', 'JENKINS_')):
                del os.environ[key]
    
    def teardown_method(self):
        """Cleanup after tests."""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    @patch("pathlib.Path.exists", return_value=False)
    def test_initialization_no_config_file(self, mock_exists):
        """Test initialization without config file."""
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer, 
            self.mock_review_generator
        )
        
        assert integration.gitlab_client == self.mock_gitlab_client
        assert integration.mr_analyzer == self.mock_mr_analyzer
        assert integration.review_generator == self.mock_review_generator
        assert isinstance(integration.config, CIConfig)
        assert integration.ci_env["is_ci"] is False
    
    @patch("builtins.open", new_callable=mock_open, read_data="""
ci:
  enabled: true
  review_type: "security"
  auto_post: true
""")
    @patch("pathlib.Path.exists", return_value=True)
    def test_initialization_with_config_file(self, mock_exists, mock_file):
        """Test initialization with config file."""
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        assert integration.config.enabled is True
        assert integration.config.review_type == "security"
        assert integration.config.auto_post is True
    
    def test_load_env_config(self):
        """Test loading configuration from environment variables."""
        # Set environment variables
        os.environ.update({
            "CI_REVIEW_ENABLED": "false",
            "CI_REVIEW_TYPE": "performance",
            "CI_AUTO_POST": "true",
            "CI_TRIGGER_ON_DRAFT": "true",
            "CI_REQUIRED_APPROVALS": "2",
            "CI_REVIEW_ON_LABELS": "review,security",
            "CI_SKIP_ON_LABELS": "wip,skip",
            "CI_PARALLEL_WORKERS": "4",
            "CI_TIMEOUT_MINUTES": "45"
        })
        
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        env_config = integration._load_env_config()
        
        assert env_config["enabled"] is False
        assert env_config["review_type"] == "performance"
        assert env_config["auto_post"] is True
        assert env_config["trigger_on_draft"] is True
        assert env_config["required_approvals"] == 2
        assert env_config["review_on_labels"] == ["review", "security"]
        assert env_config["skip_on_labels"] == ["wip", "skip"]
        assert env_config["parallel_workers"] == 4
        assert env_config["timeout_minutes"] == 45
    
    def test_detect_gitlab_ci_environment(self):
        """Test GitLab CI environment detection."""
        os.environ.update({
            "GITLAB_CI": "true",
            "CI_PIPELINE_ID": "12345",
            "CI_JOB_ID": "67890",
            "CI_COMMIT_SHA": "abc123",
            "CI_COMMIT_REF_NAME": "feature-branch",
            "CI_MERGE_REQUEST_IID": "456",
            "CI_PROJECT_PATH": "group/project",
            "CI_PROJECT_ID": "789",
            "CI_MERGE_REQUEST_TARGET_BRANCH_NAME": "main",
            "CI_MERGE_REQUEST_SOURCE_BRANCH_NAME": "feature"
        })
        
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        ci_env = integration.ci_env
        
        assert ci_env["is_ci"] is True
        assert ci_env["platform"] == "gitlab"
        assert ci_env["pipeline_id"] == "12345"
        assert ci_env["job_id"] == "67890"
        assert ci_env["commit_sha"] == "abc123"
        assert ci_env["branch"] == "feature-branch"
        assert ci_env["mr_iid"] == "456"
        assert ci_env["project_path"] == "group/project"
        assert ci_env["project_id"] == "789"
        assert ci_env["target_branch"] == "main"
        assert ci_env["source_branch"] == "feature"
    
    def test_detect_github_actions_environment(self):
        """Test GitHub Actions environment detection."""
        os.environ.update({
            "GITHUB_ACTIONS": "true",
            "GITHUB_SHA": "def456",
            "GITHUB_REF_NAME": "main",
            "GITHUB_REPOSITORY": "owner/repo"
        })
        
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        ci_env = integration.ci_env
        
        assert ci_env["is_ci"] is True
        assert ci_env["platform"] == "github"
        assert ci_env["commit_sha"] == "def456"
        assert ci_env["branch"] == "main"
        assert ci_env["project_path"] == "owner/repo"
    
    def test_detect_jenkins_environment(self):
        """Test Jenkins environment detection."""
        os.environ.update({
            "JENKINS_URL": "https://jenkins.example.com",
            "BUILD_NUMBER": "123",
            "GIT_COMMIT": "ghi789",
            "GIT_BRANCH": "origin/develop"
        })
        
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        ci_env = integration.ci_env
        
        assert ci_env["is_ci"] is True
        assert ci_env["platform"] == "jenkins"
        assert ci_env["job_id"] == "123"
        assert ci_env["commit_sha"] == "ghi789"
        assert ci_env["branch"] == "origin/develop"
    
    def test_should_run_review_disabled(self):
        """Test should_run_review when reviews are disabled."""
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        integration.config.enabled = False
        
        should_run, reason = integration.should_run_review()
        
        assert should_run is False
        assert "disabled" in reason
    
    def test_should_run_review_not_ci(self):
        """Test should_run_review when not in CI environment."""
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        should_run, reason = integration.should_run_review()
        
        assert should_run is False
        assert "Not running in CI" in reason
    
    def test_should_run_review_draft_mr_trigger_disabled(self):
        """Test should_run_review with draft MR when trigger is disabled."""
        os.environ["GITLAB_CI"] = "true"
        
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        integration.config.trigger_on_draft = False
        
        mr_data = {
            "draft": True,
            "work_in_progress": False,
            "labels": []
        }
        
        should_run, reason = integration.should_run_review(mr_data)
        
        assert should_run is False
        assert "draft" in reason
    
    def test_should_run_review_wip_mr_trigger_disabled(self):
        """Test should_run_review with WIP MR when trigger is disabled."""
        os.environ["GITLAB_CI"] = "true"
        
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        integration.config.trigger_on_wip = False
        
        mr_data = {
            "draft": False,
            "work_in_progress": True,
            "labels": []
        }
        
        should_run, reason = integration.should_run_review(mr_data)
        
        assert should_run is False
        assert "WIP" in reason
    
    def test_should_run_review_skip_label(self):
        """Test should_run_review with skip label."""
        os.environ["GITLAB_CI"] = "true"
        
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        mr_data = {
            "draft": False,
            "work_in_progress": False,
            "labels": [{"name": "skip-review"}]
        }
        
        should_run, reason = integration.should_run_review(mr_data)
        
        assert should_run is False
        assert "skip-review" in reason
    
    def test_should_run_review_required_labels_missing(self):
        """Test should_run_review with missing required labels."""
        os.environ["GITLAB_CI"] = "true"
        
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        integration.config.review_on_labels = ["needs-review"]
        
        mr_data = {
            "draft": False,
            "work_in_progress": False,
            "labels": [{"name": "enhancement"}]
        }
        
        should_run, reason = integration.should_run_review(mr_data)
        
        assert should_run is False
        assert "missing required labels" in reason
    
    def test_should_run_review_insufficient_approvals(self):
        """Test should_run_review with insufficient approvals."""
        os.environ["GITLAB_CI"] = "true"
        
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        integration.config.required_approvals = 2
        
        mr_data = {
            "draft": False,
            "work_in_progress": False,
            "labels": [],
            "upvotes": 1
        }
        
        should_run, reason = integration.should_run_review(mr_data)
        
        assert should_run is False
        assert "1 more approvals" in reason
    
    def test_should_run_review_success(self):
        """Test should_run_review when all conditions are met."""
        os.environ["GITLAB_CI"] = "true"
        
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        mr_data = {
            "draft": False,
            "work_in_progress": False,
            "labels": [],
            "upvotes": 0
        }
        
        should_run, reason = integration.should_run_review(mr_data)
        
        assert should_run is True
        assert "All conditions met" in reason
    
    def test_run_ci_review_not_ci_environment(self):
        """Test run_ci_review when not in CI environment."""
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        with pytest.raises(RuntimeError, match="Not running in CI"):
            integration.run_ci_review()
    
    def test_run_ci_review_missing_env_vars(self):
        """Test run_ci_review with missing environment variables."""
        os.environ["GITLAB_CI"] = "true"
        # Don't set MR_IID or PROJECT_PATH
        
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        with pytest.raises(RuntimeError, match="Missing required CI environment"):
            integration.run_ci_review()
    
    def test_run_ci_review_skipped(self):
        """Test run_ci_review when review should be skipped."""
        os.environ.update({
            "GITLAB_CI": "true",
            "CI_MERGE_REQUEST_IID": "123",
            "CI_PROJECT_PATH": "group/project",
            "CI_PIPELINE_ID": "456",
            "CI_JOB_ID": "789"
        })
        
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        # Mock MR data that should be skipped
        mr_data = {
            "iid": 123,
            "title": "Test MR",
            "state": "opened",
            "draft": True,
            "work_in_progress": False,
            "labels": []
        }
        
        self.mock_gitlab_client.get_merge_request.return_value = mr_data
        
        result = integration.run_ci_review()
        
        assert result["skipped"] is True
        assert "draft" in result["reason"]
        assert result["mr_info"]["iid"] == 123
    
    def test_run_ci_review_success_no_posting(self):
        """Test successful CI review without posting."""
        os.environ.update({
            "GITLAB_CI": "true",
            "CI_MERGE_REQUEST_IID": "123",
            "CI_PROJECT_PATH": "group/project",
            "CI_PIPELINE_ID": "456",
            "CI_JOB_ID": "789"
        })
        
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        integration.config.auto_post = False
        
        # Mock data
        mr_data = {
            "iid": 123,
            "title": "Test MR",
            "state": "opened",
            "author": {"username": "testuser"},
            "source_branch": "feature",
            "target_branch": "main",
            "draft": False,
            "work_in_progress": False,
            "labels": []
        }
        
        changes_data = {"changes": []}
        
        analysis = {
            "impact_analysis": {
                "complexity_score": 45,
                "files_count": 3,
                "lines_added": 20,
                "lines_removed": 5,
                "risk_factors": ["new_dependencies"]
            }
        }
        
        review = {
            "summary": "Test review",
            "overall_assessment": "MEDIUM_RISK"
        }
        
        # Setup mocks
        self.mock_gitlab_client.get_merge_request.return_value = mr_data
        self.mock_gitlab_client.get_mr_changes.return_value = changes_data
        self.mock_mr_analyzer.analyze_mr_changes.return_value = analysis
        self.mock_review_generator.generate_review.return_value = review
        
        result = integration.run_ci_review()
        
        assert result["success"] is True
        assert result["skipped"] is False
        assert result["mr_info"]["iid"] == 123
        assert result["analysis"]["complexity_score"] == 45
        assert result["review"]["type"] == "general"
        assert result["review"]["posted"] is False
    
    def test_run_ci_review_success_with_posting(self):
        """Test successful CI review with posting."""
        os.environ.update({
            "GITLAB_CI": "true",
            "CI_MERGE_REQUEST_IID": "123",
            "CI_PROJECT_PATH": "group/project",
            "CI_PIPELINE_ID": "456",
            "CI_JOB_ID": "789"
        })
        
        integration = GitLabCIIntegration(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        integration.config.auto_post = True
        
        # Mock data (same as above)
        mr_data = {
            "iid": 123,
            "title": "Test MR",
            "state": "opened",
            "author": {"username": "testuser"},
            "source_branch": "feature", 
            "target_branch": "main",
            "draft": False,
            "work_in_progress": False,
            "labels": []
        }
        
        changes_data = {"changes": []}
        analysis = {
            "impact_analysis": {
                "complexity_score": 45,
                "files_count": 3,
                "lines_added": 20,
                "lines_removed": 5,
                "risk_factors": []
            }
        }
        review = {"summary": "Test review", "overall_assessment": "MEDIUM_RISK"}
        
        # Setup mocks
        self.mock_gitlab_client.get_merge_request.return_value = mr_data
        self.mock_gitlab_client.get_mr_changes.return_value = changes_data
        self.mock_mr_analyzer.analyze_mr_changes.return_value = analysis
        self.mock_review_generator.generate_review.return_value = review
        self.mock_review_generator.format_for_gitlab.return_value = "Formatted review"
        self.mock_gitlab_client.post_mr_note.return_value = {"id": 987}
        
        result = integration.run_ci_review()
        
        assert result["success"] is True
        assert result["review"]["posted"] is True
        assert result["review"]["note_id"] == 987
        
        # Verify posting was called
        self.mock_gitlab_client.post_mr_note.assert_called_once()
        
        # Check that CI metadata was added to comment
        call_args = self.mock_gitlab_client.post_mr_note.call_args[0]
        comment = call_args[2]  # Third argument is the comment
        assert "Pipeline #456" in comment
        assert "Job #789" in comment
    
    def test_generate_ci_config_template(self):
        """Test CI config template generation."""
        integration = GitLabCIIntegration(None, None, None)
        
        template = integration.generate_ci_config_template()
        
        assert "automated-review:" in template
        assert "python gitlab_review.py --ci-mode" in template
        assert "CI_REVIEW_ENABLED:" in template
        assert "security-review:" in template
        assert "performance-review:" in template
    
    def test_generate_project_config_template(self):
        """Test project config template generation."""
        integration = GitLabCIIntegration(None, None, None)
        
        template = integration.generate_project_config_template()
        
        assert "ci:" in template
        assert "enabled: true" in template
        assert "review_type:" in template
        assert "skip_on_labels:" in template
        assert "gitlab:" in template
        assert "rag:" in template


if __name__ == '__main__':
    pytest.main([__file__])