#!/usr/bin/env python3
"""
Configuration management for GitLab integration.

Handles environment variables, config files, and default settings.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class GitLabConfig:
    """GitLab configuration settings."""
    url: str = "https://gitlab.com"
    token: str = ""
    timeout: int = 30
    max_retries: int = 3
    verify_ssl: bool = True


@dataclass
class RAGConfig:
    """RAG system configuration."""
    ollama_host: str = "http://host.docker.internal:11434"
    embedding_model: str = "nomic-embed-text"
    chat_model: str = "qwen2.5-coder"
    max_context_chunks: int = 5
    temperature: float = 0.1
    top_p: float = 0.9


@dataclass
class ReviewConfig:
    """Review generation configuration."""
    default_type: str = "general"
    max_line_length: int = 120
    auto_post: bool = False
    include_line_comments: bool = True
    max_suggestions: int = 10


@dataclass
class AppConfig:
    """Complete application configuration."""
    gitlab: GitLabConfig
    rag: RAGConfig
    review: ReviewConfig
    log_level: str = "INFO"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """Create config from dictionary."""
        return cls(
            gitlab=GitLabConfig(**data.get('gitlab', {})),
            rag=RAGConfig(**data.get('rag', {})),
            review=ReviewConfig(**data.get('review', {})),
            log_level=data.get('log_level', 'INFO')
        )


class ConfigManager:
    """Manages configuration loading and saving."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_dir: Directory for config files (default: ~/.config/gitlab-review)
        """
        if config_dir is None:
            config_dir = Path.home() / '.config' / 'gitlab-review'
        
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / 'config.yaml'
        self.env_file = self.config_dir / '.env'
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load configuration
        self.config = self._load_config()
    
    def _load_config(self) -> AppConfig:
        """Load configuration from all sources."""
        # Start with defaults
        config_data = {}
        
        # Load from config file
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    file_config = yaml.safe_load(f) or {}
                config_data.update(file_config)
                logger.info(f"📄 Loaded config from {self.config_file}")
            except Exception as e:
                logger.warning(f"Failed to load config file: {e}")
        
        # Load from .env file
        if self.env_file.exists():
            try:
                env_config = self._load_env_file()
                config_data = self._merge_env_config(config_data, env_config)
                logger.info(f"📄 Loaded .env from {self.env_file}")
            except Exception as e:
                logger.warning(f"Failed to load .env file: {e}")
        
        # Override with environment variables
        env_config = self._load_env_vars()
        config_data = self._merge_env_config(config_data, env_config)
        
        return AppConfig.from_dict(config_data)
    
    def _load_env_file(self) -> Dict[str, str]:
        """Load environment variables from .env file."""
        env_vars = {}
        
        with open(self.env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip().strip('"\'')
        
        return env_vars
    
    def _load_env_vars(self) -> Dict[str, str]:
        """Load relevant environment variables."""
        env_vars = {}
        
        # GitLab environment variables
        gitlab_vars = [
            'GITLAB_URL', 'GITLAB_TOKEN', 'GITLAB_TIMEOUT',
            'GITLAB_MAX_RETRIES', 'GITLAB_VERIFY_SSL'
        ]
        
        # RAG environment variables
        rag_vars = [
            'OLLAMA_HOST', 'EMBEDDING_MODEL', 'CHAT_MODEL',
            'MAX_CONTEXT_CHUNKS', 'TEMPERATURE', 'TOP_P'
        ]
        
        # Review environment variables
        review_vars = [
            'DEFAULT_REVIEW_TYPE', 'MAX_LINE_LENGTH', 'AUTO_POST',
            'INCLUDE_LINE_COMMENTS', 'MAX_SUGGESTIONS'
        ]
        
        # General variables
        general_vars = ['LOG_LEVEL']
        
        all_vars = gitlab_vars + rag_vars + review_vars + general_vars
        
        for var in all_vars:
            value = os.getenv(var)
            if value is not None:
                env_vars[var] = value
        
        return env_vars
    
    def _merge_env_config(self, config_data: Dict[str, Any], env_vars: Dict[str, str]) -> Dict[str, Any]:
        """Merge environment variables into config data."""
        # Ensure nested dictionaries exist
        if 'gitlab' not in config_data:
            config_data['gitlab'] = {}
        if 'rag' not in config_data:
            config_data['rag'] = {}
        if 'review' not in config_data:
            config_data['review'] = {}
        
        # Map environment variables to config structure
        env_mapping = {
            # GitLab config
            'GITLAB_URL': ('gitlab', 'url'),
            'GITLAB_TOKEN': ('gitlab', 'token'),
            'GITLAB_TIMEOUT': ('gitlab', 'timeout', int),
            'GITLAB_MAX_RETRIES': ('gitlab', 'max_retries', int),
            'GITLAB_VERIFY_SSL': ('gitlab', 'verify_ssl', self._str_to_bool),
            
            # RAG config
            'OLLAMA_HOST': ('rag', 'ollama_host'),
            'EMBEDDING_MODEL': ('rag', 'embedding_model'),
            'CHAT_MODEL': ('rag', 'chat_model'),
            'MAX_CONTEXT_CHUNKS': ('rag', 'max_context_chunks', int),
            'TEMPERATURE': ('rag', 'temperature', float),
            'TOP_P': ('rag', 'top_p', float),
            
            # Review config
            'DEFAULT_REVIEW_TYPE': ('review', 'default_type'),
            'MAX_LINE_LENGTH': ('review', 'max_line_length', int),
            'AUTO_POST': ('review', 'auto_post', self._str_to_bool),
            'INCLUDE_LINE_COMMENTS': ('review', 'include_line_comments', self._str_to_bool),
            'MAX_SUGGESTIONS': ('review', 'max_suggestions', int),
            
            # General config
            'LOG_LEVEL': ('log_level',),
        }
        
        for env_var, mapping in env_mapping.items():
            if env_var in env_vars:
                value = env_vars[env_var]
                
                # Apply type conversion if specified
                if len(mapping) > 2:
                    converter = mapping[2]
                    try:
                        value = converter(value)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to convert {env_var}={value}: {e}")
                        continue
                
                # Set value in config
                if len(mapping) == 2:
                    section, key = mapping
                    config_data[section][key] = value
                else:
                    key = mapping[0]
                    config_data[key] = value
        
        return config_data
    
    def _str_to_bool(self, value: str) -> bool:
        """Convert string to boolean."""
        return value.lower() in ('true', '1', 'yes', 'on')
    
    def save_config(self, config: Optional[AppConfig] = None) -> None:
        """Save configuration to file."""
        if config is None:
            config = self.config
        
        try:
            with open(self.config_file, 'w') as f:
                yaml.dump(config.to_dict(), f, default_flow_style=False, indent=2)
            logger.info(f"✅ Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"❌ Failed to save config: {e}")
            raise
    
    def create_sample_config(self) -> None:
        """Create sample configuration file."""
        sample_config = AppConfig(
            gitlab=GitLabConfig(
                url="https://gitlab.com",
                token="your-gitlab-token-here",
                timeout=30,
                max_retries=3,
                verify_ssl=True
            ),
            rag=RAGConfig(
                ollama_host="http://localhost:11434",
                embedding_model="nomic-embed-text",
                chat_model="qwen2.5-coder",
                max_context_chunks=5,
                temperature=0.1,
                top_p=0.9
            ),
            review=ReviewConfig(
                default_type="general",
                max_line_length=120,
                auto_post=False,
                include_line_comments=True,
                max_suggestions=10
            ),
            log_level="INFO"
        )
        
        sample_file = self.config_dir / 'config.yaml.sample'
        with open(sample_file, 'w') as f:
            yaml.dump(sample_config.to_dict(), f, default_flow_style=False, indent=2)
        
        logger.info(f"📄 Sample config created at {sample_file}")
    
    def create_sample_env(self) -> None:
        """Create sample .env file."""
        sample_env = """# GitLab Configuration
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=your-gitlab-token-here
GITLAB_TIMEOUT=30
GITLAB_MAX_RETRIES=3
GITLAB_VERIFY_SSL=true

# RAG System Configuration
OLLAMA_HOST=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
CHAT_MODEL=qwen2.5-coder
MAX_CONTEXT_CHUNKS=5
TEMPERATURE=0.1
TOP_P=0.9

# Review Configuration
DEFAULT_REVIEW_TYPE=general
MAX_LINE_LENGTH=120
AUTO_POST=false
INCLUDE_LINE_COMMENTS=true
MAX_SUGGESTIONS=10

# General Configuration
LOG_LEVEL=INFO
"""
        
        sample_env_file = self.config_dir / '.env.sample'
        with open(sample_env_file, 'w') as f:
            f.write(sample_env)
        
        logger.info(f"📄 Sample .env created at {sample_env_file}")
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        # Validate GitLab config
        if not self.config.gitlab.token:
            issues.append("GitLab token is required")
        
        if not self.config.gitlab.url:
            issues.append("GitLab URL is required")
        
        # Validate RAG config
        if not self.config.rag.ollama_host:
            issues.append("Ollama host is required")
        
        if self.config.rag.temperature < 0 or self.config.rag.temperature > 1:
            issues.append("Temperature must be between 0 and 1")
        
        if self.config.rag.top_p < 0 or self.config.rag.top_p > 1:
            issues.append("Top_p must be between 0 and 1")
        
        # Validate review config
        valid_types = ['general', 'security', 'performance']
        if self.config.review.default_type not in valid_types:
            issues.append(f"Default review type must be one of: {valid_types}")
        
        return issues
    
    def get_config(self) -> AppConfig:
        """Get current configuration."""
        return self.config
    
    def update_config(self, **kwargs) -> None:
        """Update configuration with new values."""
        config_dict = self.config.to_dict()
        
        # Update nested values
        for key, value in kwargs.items():
            if '.' in key:
                section, field = key.split('.', 1)
                if section in config_dict:
                    config_dict[section][field] = value
            else:
                config_dict[key] = value
        
        self.config = AppConfig.from_dict(config_dict)
    
    def print_config(self) -> None:
        """Print current configuration (masking sensitive values)."""
        config_dict = self.config.to_dict()
        
        # Mask sensitive values
        if 'gitlab' in config_dict and 'token' in config_dict['gitlab']:
            token = config_dict['gitlab']['token']
            if token:
                config_dict['gitlab']['token'] = token[:8] + '...' + token[-4:] if len(token) > 12 else '***'
        
        print("📋 Current Configuration:")
        print(yaml.dump(config_dict, default_flow_style=False, indent=2))


# Global config manager instance
_config_manager = None


def get_config_manager() -> ConfigManager:
    """Get global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> AppConfig:
    """Get current application configuration."""
    return get_config_manager().get_config()