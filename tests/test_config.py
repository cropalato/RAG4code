#!/usr/bin/env python3
"""
Tests for configuration management.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, mock_open
import yaml
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitlab_integration.config import (
    GitLabConfig, RAGConfig, ReviewConfig, AppConfig, 
    ConfigManager, get_config_manager, get_config
)


class TestConfigClasses:
    """Test configuration data classes."""
    
    def test_gitlab_config_defaults(self):
        """Test GitLab config defaults."""
        config = GitLabConfig()
        assert config.url == "https://gitlab.com"
        assert config.token == ""
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.verify_ssl is True
    
    def test_rag_config_defaults(self):
        """Test RAG config defaults."""
        config = RAGConfig()
        assert config.ollama_host == "http://host.docker.internal:11434"
        assert config.embedding_model == "nomic-embed-text"
        assert config.chat_model == "qwen2.5-coder"
        assert config.max_context_chunks == 5
        assert config.temperature == 0.1
        assert config.top_p == 0.9
    
    def test_review_config_defaults(self):
        """Test review config defaults."""
        config = ReviewConfig()
        assert config.default_type == "general"
        assert config.max_line_length == 120
        assert config.auto_post is False
        assert config.include_line_comments is True
        assert config.max_suggestions == 10
    
    def test_app_config_composition(self):
        """Test app config composition."""
        config = AppConfig(
            gitlab=GitLabConfig(token="test-token"),
            rag=RAGConfig(temperature=0.2),
            review=ReviewConfig(auto_post=True),
            log_level="DEBUG"
        )
        
        assert config.gitlab.token == "test-token"
        assert config.rag.temperature == 0.2
        assert config.review.auto_post is True
        assert config.log_level == "DEBUG"
    
    def test_app_config_to_dict(self):
        """Test config serialization to dict."""
        config = AppConfig(
            gitlab=GitLabConfig(token="test"),
            rag=RAGConfig(),
            review=ReviewConfig()
        )
        
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert 'gitlab' in config_dict
        assert 'rag' in config_dict
        assert 'review' in config_dict
        assert config_dict['gitlab']['token'] == "test"
    
    def test_app_config_from_dict(self):
        """Test config deserialization from dict."""
        config_dict = {
            'gitlab': {'token': 'test-token', 'url': 'https://example.com'},
            'rag': {'temperature': 0.3},
            'review': {'auto_post': True},
            'log_level': 'WARNING'
        }
        
        config = AppConfig.from_dict(config_dict)
        
        assert config.gitlab.token == 'test-token'
        assert config.gitlab.url == 'https://example.com'
        assert config.rag.temperature == 0.3
        assert config.review.auto_post is True
        assert config.log_level == 'WARNING'


class TestConfigManager:
    """Test configuration manager."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / 'gitlab-review'
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_manager = ConfigManager(self.config_dir)
    
    def teardown_method(self):
        """Cleanup test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_config_manager_initialization(self):
        """Test config manager initialization."""
        assert self.config_manager.config_dir == self.config_dir
        assert self.config_manager.config_file == self.config_dir / 'config.yaml'
        assert self.config_manager.env_file == self.config_dir / '.env'
        assert isinstance(self.config_manager.config, AppConfig)
    
    def test_load_config_from_yaml(self):
        """Test loading config from YAML file."""
        # Create test config file
        config_data = {
            'gitlab': {
                'url': 'https://test.gitlab.com',
                'token': 'test-token-yaml'
            },
            'rag': {
                'temperature': 0.5
            },
            'log_level': 'DEBUG'
        }
        
        with open(self.config_manager.config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Reload config
        config_manager = ConfigManager(self.config_dir)
        
        assert config_manager.config.gitlab.url == 'https://test.gitlab.com'
        assert config_manager.config.gitlab.token == 'test-token-yaml'
        assert config_manager.config.rag.temperature == 0.5
        assert config_manager.config.log_level == 'DEBUG'
    
    def test_load_config_from_env_file(self):
        """Test loading config from .env file."""
        # Create test .env file
        env_content = """
GITLAB_URL=https://env.gitlab.com
GITLAB_TOKEN=test-token-env
TEMPERATURE=0.7
LOG_LEVEL=INFO
"""
        
        with open(self.config_manager.env_file, 'w') as f:
            f.write(env_content)
        
        # Reload config
        config_manager = ConfigManager(self.config_dir)
        
        assert config_manager.config.gitlab.url == 'https://env.gitlab.com'
        assert config_manager.config.gitlab.token == 'test-token-env'
        assert config_manager.config.rag.temperature == 0.7
        assert config_manager.config.log_level == 'INFO'
    
    @patch.dict(os.environ, {
        'GITLAB_URL': 'https://env-var.gitlab.com',
        'GITLAB_TOKEN': 'test-token-env-var',
        'TEMPERATURE': '0.9',
        'AUTO_POST': 'true'
    })
    def test_load_config_from_env_vars(self):
        """Test loading config from environment variables."""
        config_manager = ConfigManager(self.config_dir)
        
        assert config_manager.config.gitlab.url == 'https://env-var.gitlab.com'
        assert config_manager.config.gitlab.token == 'test-token-env-var'
        assert config_manager.config.rag.temperature == 0.9
        assert config_manager.config.review.auto_post is True
    
    def test_config_precedence(self):
        """Test configuration precedence (env vars > .env file > yaml file)."""
        # Create YAML config
        yaml_config = {
            'gitlab': {'token': 'yaml-token', 'url': 'https://yaml.com'},
            'rag': {'temperature': 0.1}
        }
        with open(self.config_manager.config_file, 'w') as f:
            yaml.dump(yaml_config, f)
        
        # Create .env file
        env_content = """
GITLAB_TOKEN=env-file-token
TEMPERATURE=0.5
"""
        with open(self.config_manager.env_file, 'w') as f:
            f.write(env_content)
        
        # Set environment variable
        with patch.dict(os.environ, {'GITLAB_TOKEN': 'env-var-token'}):
            config_manager = ConfigManager(self.config_dir)
            
            # Environment variable should have highest precedence
            assert config_manager.config.gitlab.token == 'env-var-token'
            # .env file should override YAML
            assert config_manager.config.rag.temperature == 0.5
            # YAML value should be used if not overridden
            assert config_manager.config.gitlab.url == 'https://yaml.com'
    
    def test_save_config(self):
        """Test saving configuration."""
        config = AppConfig(
            gitlab=GitLabConfig(token='saved-token'),
            rag=RAGConfig(temperature=0.8),
            review=ReviewConfig(auto_post=True)
        )
        
        self.config_manager.save_config(config)
        
        # Verify file was created
        assert self.config_manager.config_file.exists()
        
        # Verify content
        with open(self.config_manager.config_file, 'r') as f:
            saved_data = yaml.safe_load(f)
        
        assert saved_data['gitlab']['token'] == 'saved-token'
        assert saved_data['rag']['temperature'] == 0.8
        assert saved_data['review']['auto_post'] is True
    
    def test_create_sample_config(self):
        """Test sample config creation."""
        self.config_manager.create_sample_config()
        
        sample_file = self.config_dir / 'config.yaml.sample'
        assert sample_file.exists()
        
        with open(sample_file, 'r') as f:
            sample_data = yaml.safe_load(f)
        
        assert 'gitlab' in sample_data
        assert 'rag' in sample_data
        assert 'review' in sample_data
    
    def test_create_sample_env(self):
        """Test sample .env creation."""
        self.config_manager.create_sample_env()
        
        sample_file = self.config_dir / '.env.sample'
        assert sample_file.exists()
        
        with open(sample_file, 'r') as f:
            content = f.read()
        
        assert 'GITLAB_URL' in content
        assert 'GITLAB_TOKEN' in content
        assert 'OLLAMA_HOST' in content
    
    def test_validate_config_valid(self):
        """Test config validation with valid config."""
        config = AppConfig(
            gitlab=GitLabConfig(
                url='https://gitlab.com',
                token='valid-token'
            ),
            rag=RAGConfig(
                temperature=0.5,
                top_p=0.8
            ),
            review=ReviewConfig(default_type='general')
        )
        
        self.config_manager.config = config
        issues = self.config_manager.validate_config()
        
        assert len(issues) == 0
    
    def test_validate_config_invalid(self):
        """Test config validation with invalid config."""
        config = AppConfig(
            gitlab=GitLabConfig(url='', token=''),  # Missing required fields
            rag=RAGConfig(temperature=1.5, top_p=2.0),  # Invalid ranges
            review=ReviewConfig(default_type='invalid')  # Invalid type
        )
        
        self.config_manager.config = config
        issues = self.config_manager.validate_config()
        
        assert len(issues) > 0
        assert any('token is required' in issue for issue in issues)
        assert any('URL is required' in issue for issue in issues)
        assert any('Temperature must be between' in issue for issue in issues)
        assert any('Top_p must be between' in issue for issue in issues)
        assert any('Default review type must be' in issue for issue in issues)
    
    def test_update_config(self):
        """Test config updating."""
        original_token = self.config_manager.config.gitlab.token
        
        self.config_manager.update_config(**{
            'gitlab.token': 'updated-token',
            'rag.temperature': 0.6,
            'log_level': 'WARNING'
        })
        
        assert self.config_manager.config.gitlab.token == 'updated-token'
        assert self.config_manager.config.rag.temperature == 0.6
        assert self.config_manager.config.log_level == 'WARNING'
    
    def test_str_to_bool(self):
        """Test string to boolean conversion."""
        test_cases = [
            ('true', True),
            ('True', True),
            ('1', True),
            ('yes', True),
            ('on', True),
            ('false', False),
            ('False', False),
            ('0', False),
            ('no', False),
            ('off', False),
            ('invalid', False)
        ]
        
        for input_str, expected in test_cases:
            result = self.config_manager._str_to_bool(input_str)
            assert result == expected


class TestGlobalConfigFunctions:
    """Test global configuration functions."""
    
    def test_get_config_manager_singleton(self):
        """Test config manager singleton behavior."""
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        
        assert manager1 is manager2
    
    def test_get_config(self):
        """Test get_config function."""
        config = get_config()
        
        assert isinstance(config, AppConfig)
        assert hasattr(config, 'gitlab')
        assert hasattr(config, 'rag')
        assert hasattr(config, 'review')


if __name__ == '__main__':
    pytest.main([__file__])