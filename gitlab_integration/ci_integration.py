#!/usr/bin/env python3
"""
GitLab CI/CD Integration for Automated MR Reviews

Provides integration hooks for GitLab CI/CD pipelines to automatically
review merge requests as part of the development workflow.
"""

import os
import json
import logging
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class CIConfig:
    """CI/CD configuration for automated reviews."""
    enabled: bool = True
    review_type: str = 'general'
    auto_post: bool = False
    trigger_on_draft: bool = False
    trigger_on_wip: bool = False
    required_approvals: int = 0
    review_on_labels: List[str] = None
    skip_on_labels: List[str] = None
    parallel_workers: int = 1
    timeout_minutes: int = 30
    
    def __post_init__(self):
        if self.review_on_labels is None:
            self.review_on_labels = []
        if self.skip_on_labels is None:
            self.skip_on_labels = ['skip-review', 'no-review']


class GitLabCIIntegration:
    """GitLab CI/CD integration for automated MR reviews."""
    
    def __init__(self, gitlab_client, mr_analyzer, review_generator):
        """
        Initialize CI integration.
        
        Args:
            gitlab_client: GitLab API client
            mr_analyzer: MR analyzer instance
            review_generator: Review generator instance
        """
        self.gitlab_client = gitlab_client
        self.mr_analyzer = mr_analyzer
        self.review_generator = review_generator
        
        # Load CI configuration
        self.config = self._load_ci_config()
        
        # CI environment detection
        self.ci_env = self._detect_ci_environment()
        
        logger.info(f"🔧 GitLab CI integration initialized")
        logger.info(f"📋 Config: {self.config.review_type} reviews, auto-post: {self.config.auto_post}")
    
    def _load_ci_config(self) -> CIConfig:
        """Load CI configuration from various sources."""
        config_data = {}
        
        # Try to load from .gitlab-review.yml
        config_file = Path('.gitlab-review.yml')
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    file_config = yaml.safe_load(f) or {}
                config_data.update(file_config.get('ci', {}))
                logger.info(f"📄 Loaded CI config from {config_file}")
            except Exception as e:
                logger.warning(f"Failed to load CI config file: {e}")
        
        # Override with environment variables
        env_config = self._load_env_config()
        config_data.update(env_config)
        
        return CIConfig(**config_data)
    
    def _load_env_config(self) -> Dict[str, Any]:
        """Load CI configuration from environment variables."""
        env_config = {}
        
        env_mapping = {
            'CI_REVIEW_ENABLED': ('enabled', lambda x: x.lower() == 'true'),
            'CI_REVIEW_TYPE': ('review_type', str),
            'CI_AUTO_POST': ('auto_post', lambda x: x.lower() == 'true'),
            'CI_TRIGGER_ON_DRAFT': ('trigger_on_draft', lambda x: x.lower() == 'true'),
            'CI_TRIGGER_ON_WIP': ('trigger_on_wip', lambda x: x.lower() == 'true'),
            'CI_REQUIRED_APPROVALS': ('required_approvals', int),
            'CI_REVIEW_ON_LABELS': ('review_on_labels', lambda x: x.split(',')),
            'CI_SKIP_ON_LABELS': ('skip_on_labels', lambda x: x.split(',')),
            'CI_PARALLEL_WORKERS': ('parallel_workers', int),
            'CI_TIMEOUT_MINUTES': ('timeout_minutes', int),
        }
        
        for env_var, (config_key, converter) in env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    env_config[config_key] = converter(value)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid value for {env_var}: {value} ({e})")
        
        return env_config
    
    def _detect_ci_environment(self) -> Dict[str, Any]:
        """Detect CI environment and extract relevant information."""
        ci_env = {
            'is_ci': False,
            'platform': 'unknown',
            'pipeline_id': None,
            'job_id': None,
            'commit_sha': None,
            'branch': None,
            'mr_iid': None,
            'project_path': None
        }
        
        # GitLab CI detection
        if os.getenv('GITLAB_CI'):
            ci_env.update({
                'is_ci': True,
                'platform': 'gitlab',
                'pipeline_id': os.getenv('CI_PIPELINE_ID'),
                'job_id': os.getenv('CI_JOB_ID'),
                'commit_sha': os.getenv('CI_COMMIT_SHA'),
                'branch': os.getenv('CI_COMMIT_REF_NAME'),
                'mr_iid': os.getenv('CI_MERGE_REQUEST_IID'),
                'project_path': os.getenv('CI_PROJECT_PATH'),
                'project_id': os.getenv('CI_PROJECT_ID'),
                'target_branch': os.getenv('CI_MERGE_REQUEST_TARGET_BRANCH_NAME'),
                'source_branch': os.getenv('CI_MERGE_REQUEST_SOURCE_BRANCH_NAME')
            })
            logger.info("🔍 Detected GitLab CI environment")
        
        # GitHub Actions detection
        elif os.getenv('GITHUB_ACTIONS'):
            ci_env.update({
                'is_ci': True,
                'platform': 'github',
                'commit_sha': os.getenv('GITHUB_SHA'),
                'branch': os.getenv('GITHUB_REF_NAME'),
                'project_path': os.getenv('GITHUB_REPOSITORY')
            })
            logger.info("🔍 Detected GitHub Actions environment")
        
        # Jenkins detection
        elif os.getenv('JENKINS_URL'):
            ci_env.update({
                'is_ci': True,
                'platform': 'jenkins',
                'job_id': os.getenv('BUILD_NUMBER'),
                'commit_sha': os.getenv('GIT_COMMIT'),
                'branch': os.getenv('GIT_BRANCH')
            })
            logger.info("🔍 Detected Jenkins environment")
        
        return ci_env
    
    def should_run_review(self, mr_data: Optional[Dict[str, Any]] = None) -> tuple[bool, str]:
        """
        Determine if review should run based on CI configuration and MR state.
        
        Args:
            mr_data: MR data from GitLab API (optional, will fetch if not provided)
            
        Returns:
            Tuple of (should_run, reason)
        """
        if not self.config.enabled:
            return False, "CI reviews disabled in configuration"
        
        if not self.ci_env['is_ci']:
            return False, "Not running in CI environment"
        
        # Get MR data if not provided
        if mr_data is None and self.ci_env['mr_iid'] and self.ci_env['project_path']:
            try:
                mr_data = self.gitlab_client.get_merge_request(
                    self.ci_env['project_path'], 
                    int(self.ci_env['mr_iid'])
                )
            except Exception as e:
                return False, f"Failed to fetch MR data: {e}"
        
        if not mr_data:
            return False, "No MR data available"
        
        # Check if MR is draft/WIP
        is_draft = mr_data.get('draft', False) or mr_data.get('work_in_progress', False)
        if is_draft and not self.config.trigger_on_draft:
            return False, "MR is draft and trigger_on_draft is disabled"
        
        if mr_data.get('work_in_progress', False) and not self.config.trigger_on_wip:
            return False, "MR is WIP and trigger_on_wip is disabled"
        
        # Check labels
        mr_labels = set(label.get('name', '') for label in mr_data.get('labels', []))
        
        # Skip if has skip labels
        if mr_labels.intersection(set(self.config.skip_on_labels)):
            skip_label = mr_labels.intersection(set(self.config.skip_on_labels)).pop()
            return False, f"MR has skip label: {skip_label}"
        
        # Check if requires specific labels
        if self.config.review_on_labels:
            if not mr_labels.intersection(set(self.config.review_on_labels)):
                return False, f"MR missing required labels: {self.config.review_on_labels}"
        
        # Check approval requirements
        if self.config.required_approvals > 0:
            approvals = mr_data.get('upvotes', 0)
            if approvals < self.config.required_approvals:
                return False, f"MR needs {self.config.required_approvals - approvals} more approvals"
        
        return True, "All conditions met for CI review"
    
    def run_ci_review(self) -> Dict[str, Any]:
        """
        Run automated review in CI environment.
        
        Returns:
            Review results and CI metadata
        """
        logger.info("🚀 Starting automated CI review")
        
        # Validate CI environment
        if not self.ci_env['is_ci']:
            raise RuntimeError("Not running in CI environment")
        
        if not self.ci_env['mr_iid'] or not self.ci_env['project_path']:
            raise RuntimeError("Missing required CI environment variables (MR IID or project path)")
        
        # Get MR data
        project_path = self.ci_env['project_path']
        mr_iid = int(self.ci_env['mr_iid'])
        
        mr_data = self.gitlab_client.get_merge_request(project_path, mr_iid)
        
        # Check if review should run
        should_run, reason = self.should_run_review(mr_data)
        if not should_run:
            logger.info(f"⏭️ Skipping review: {reason}")
            return {
                'skipped': True,
                'reason': reason,
                'ci_env': self.ci_env,
                'mr_info': {
                    'iid': mr_iid,
                    'title': mr_data.get('title', ''),
                    'state': mr_data.get('state', '')
                }
            }
        
        logger.info(f"✅ Review conditions met: {reason}")
        
        # Get MR changes
        changes_data = self.gitlab_client.get_mr_changes(project_path, mr_iid)
        
        # Analyze MR
        logger.info("🔬 Analyzing MR changes...")
        analysis = self.mr_analyzer.analyze_mr_changes(mr_data, changes_data)
        
        # Generate review
        logger.info(f"🤖 Generating {self.config.review_type} review...")
        review = self.review_generator.generate_review(analysis, self.config.review_type)
        
        # Post review if enabled
        review_posted = False
        note_id = None
        if self.config.auto_post and review.get('summary'):
            try:
                logger.info("📤 Posting review to GitLab...")
                gitlab_comment = self.review_generator.format_for_gitlab(review)
                
                # Add CI metadata to comment
                ci_footer = f"\n\n---\n*🤖 Automated review by GitLab CI Pipeline #{self.ci_env['pipeline_id']} • Job #{self.ci_env['job_id']}*"
                gitlab_comment += ci_footer
                
                note = self.gitlab_client.post_mr_note(project_path, mr_iid, gitlab_comment)
                note_id = note.get('id')
                review_posted = True
                logger.info(f"✅ Review posted successfully (Note ID: {note_id})")
                
            except Exception as e:
                logger.error(f"❌ Failed to post review: {e}")
        
        # Prepare result
        result = {
            'success': True,
            'skipped': False,
            'mr_info': {
                'iid': mr_iid,
                'title': mr_data.get('title', ''),
                'state': mr_data.get('state', ''),
                'author': mr_data.get('author', {}).get('username', ''),
                'source_branch': mr_data.get('source_branch', ''),
                'target_branch': mr_data.get('target_branch', '')
            },
            'analysis': {
                'complexity_score': analysis['impact_analysis']['complexity_score'],
                'files_changed': analysis['impact_analysis']['files_count'],
                'lines_added': analysis['impact_analysis']['lines_added'],
                'lines_removed': analysis['impact_analysis']['lines_removed'],
                'risk_factors': analysis['impact_analysis']['risk_factors']
            },
            'review': {
                'type': self.config.review_type,
                'risk_assessment': review.get('overall_assessment', 'UNKNOWN'),
                'posted': review_posted,
                'note_id': note_id
            },
            'ci_env': self.ci_env,
            'config': asdict(self.config)
        }
        
        logger.info("🎉 CI review completed successfully")
        return result
    
    def generate_ci_config_template(self) -> str:
        """Generate GitLab CI configuration template."""
        template = """# GitLab CI/CD Configuration for Automated MR Reviews
# Add this to your .gitlab-ci.yml file

stages:
  - review

automated-review:
  stage: review
  image: python:3.11-slim
  before_script:
    - pip install -r requirements_gitlab.txt
  script:
    - python gitlab_review.py --ci-mode
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  variables:
    # Review configuration
    CI_REVIEW_ENABLED: "true"
    CI_REVIEW_TYPE: "general"  # general, security, performance
    CI_AUTO_POST: "true"       # Post reviews automatically
    CI_TRIGGER_ON_DRAFT: "false"  # Review draft MRs
    CI_PARALLEL_WORKERS: "1"   # Number of parallel workers
    CI_TIMEOUT_MINUTES: "30"   # Timeout for review process
    
    # Label-based triggers (optional)
    # CI_REVIEW_ON_LABELS: "needs-review,security-review"
    # CI_SKIP_ON_LABELS: "skip-review,wip"
  artifacts:
    reports:
      junit: review-results.xml
    paths:
      - review-results.json
    expire_in: 1 week
  timeout: 30 minutes
  retry:
    max: 2
    when:
      - runner_system_failure
      - stuck_or_timeout_failure

# Optional: Security-focused review job
security-review:
  extends: automated-review
  variables:
    CI_REVIEW_TYPE: "security"
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes:
        - "**/*.py"
        - "**/*.js"
        - "**/*.ts"
        - "**/requirements*.txt"
        - "**/package*.json"
  only:
    variables:
      - $CI_MERGE_REQUEST_LABELS =~ /security/

# Optional: Performance review for specific changes
performance-review:
  extends: automated-review
  variables:
    CI_REVIEW_TYPE: "performance"
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes:
        - "**/*.py"
        - "**/*.sql"
        - "**/api/**/*"
  only:
    variables:
      - $CI_MERGE_REQUEST_LABELS =~ /performance/
"""
        return template
    
    def generate_project_config_template(self) -> str:
        """Generate project-specific configuration template."""
        template = """# .gitlab-review.yml - Project Configuration for GitLab MR Reviews

ci:
  enabled: true
  review_type: "general"  # general, security, performance, python, javascript
  auto_post: true         # Automatically post reviews to MRs
  trigger_on_draft: false # Review draft MRs
  trigger_on_wip: false   # Review work-in-progress MRs
  required_approvals: 0   # Minimum approvals before review
  parallel_workers: 1     # Number of parallel workers
  timeout_minutes: 30     # Maximum time for review process
  
  # Label-based control
  review_on_labels: []    # Only review MRs with these labels
  skip_on_labels:         # Skip review for MRs with these labels
    - "skip-review"
    - "no-review"
    - "wip"
    - "draft"

# GitLab integration settings
gitlab:
  url: "https://gitlab.com"
  # Token should be set via CI_GITLAB_TOKEN environment variable
  
# RAG system settings (if using CodeRAG integration)
rag:
  ollama_host: "http://localhost:11434"
  chat_model: "qwen2.5-coder"
  embedding_model: "nomic-embed-text"
  max_context_chunks: 5

# Review templates customization
review:
  templates_dir: "gitlab_integration/templates"
  custom_templates: {}  # Override default templates
  
# Notification settings
notifications:
  slack_webhook: ""     # Slack webhook for notifications
  email_recipients: []  # Email addresses for notifications
  
# Quality gates
quality:
  max_complexity_score: 75    # Fail if complexity exceeds this
  required_test_coverage: 80  # Require minimum test coverage
  block_on_security_issues: true  # Block MR on security findings
"""
        return template


def main():
    """CLI entry point for CI integration."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="GitLab CI/CD Integration for MR Reviews")
    parser.add_argument('--generate-ci-config', action='store_true',
                       help='Generate GitLab CI configuration template')
    parser.add_argument('--generate-project-config', action='store_true',
                       help='Generate project configuration template')
    parser.add_argument('--run-ci-review', action='store_true',
                       help='Run automated review in CI environment')
    parser.add_argument('--check-conditions', action='store_true',
                       help='Check if review conditions are met')
    parser.add_argument('--output', choices=['text', 'json'], default='text',
                       help='Output format')
    
    args = parser.parse_args()
    
    if args.generate_ci_config:
        integration = GitLabCIIntegration(None, None, None)
        print(integration.generate_ci_config_template())
        return
    
    if args.generate_project_config:
        integration = GitLabCIIntegration(None, None, None)
        print(integration.generate_project_config_template())
        return
    
    # For actual CI operations, we'd need to initialize the real components
    if args.run_ci_review or args.check_conditions:
        print("❌ CI operations require full component initialization")
        print("Use: python gitlab_review.py --ci-mode")
        sys.exit(1)


if __name__ == '__main__':
    main()