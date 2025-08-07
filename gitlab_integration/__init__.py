"""
GitLab Integration Package for CodeRAG

Provides GitLab merge request analysis and review generation
using the CodeRAG system.
"""

__version__ = "1.0.0"
__author__ = "CodeRAG Team"

from .gitlab_client import GitLabClient
from .mr_analyzer import MRAnalyzer
from .review_generator import ReviewGenerator

__all__ = [
    "GitLabClient",
    "MRAnalyzer",
    "ReviewGenerator"
]