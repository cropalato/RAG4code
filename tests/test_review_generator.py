#!/usr/bin/env python3
"""
Tests for Review Generator.
"""

import pytest
import responses
import json
from unittest.mock import patch, Mock, mock_open
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitlab_integration.review_generator import ReviewGenerator


class TestReviewGenerator:
    """Test cases for Review Generator."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.mock_analysis = {
            "mr_info": {
                "iid": 123,
                "title": "Test MR",
                "author": "testuser",
                "source_branch": "feature",
                "target_branch": "main",
                "description": "Test description",
                "labels": ["enhancement"]
            },
            "impact_analysis": {
                "complexity_score": 45,
                "files_count": 3,
                "lines_added": 50,
                "lines_removed": 10,
                "risk_factors": ["new_dependencies"]
            },
            "code_changes": {
                "new_functions": [
                    {
                        "name": "test_function",
                        "file_path": "test.py",
                        "line_number": 10
                    }
                ],
                "new_classes": []
            },
            "file_changes": [
                {
                    "file_path": "test.py",
                    "change_type": "modified",
                    "language": "python",
                    "is_code_file": True,
                    "lines_added": 30,
                    "lines_removed": 5,
                    "modified_lines": [
                        {
                            "line_number": 15,
                            "type": "added",
                            "content": "print('hello world')"
                        }
                    ]
                }
            ],
            "review_context": [
                {
                    "query": "test query",
                    "type": "function_context",
                    "rag_results": [
                        {
                            "_source": {
                                "file_path": "related.py",
                                "functions": ["related_function"],
                                "content": "def related_function(): pass"
                            }
                        }
                    ]
                }
            ]
        }
    
    def test_initialization_default(self):
        """Test reviewer initialization with defaults."""
        generator = ReviewGenerator()
        
        assert generator.ollama_host == "http://host.docker.internal:11434"
        assert generator.rag_system is None
        assert "general" in generator.templates
        assert "security" in generator.templates
        assert "performance" in generator.templates
    
    def test_initialization_with_params(self):
        """Test reviewer initialization with parameters."""
        mock_rag = Mock()
        ollama_host = "http://localhost:11434"
        
        generator = ReviewGenerator(mock_rag, ollama_host)
        
        assert generator.rag_system == mock_rag
        assert generator.ollama_host == ollama_host
    
    @patch("builtins.open", new_callable=mock_open, read_data="Custom template: {mr_summary}")
    def test_load_template_from_file(self, mock_file):
        """Test loading template from file."""
        generator = ReviewGenerator()
        
        # Mock the path exists check
        with patch("pathlib.Path.exists", return_value=True):
            template = generator._load_template("custom")
        
        assert "Custom template:" in template
    
    def test_load_template_fallback(self):
        """Test template fallback when file doesn't exist."""
        generator = ReviewGenerator()
        
        # Mock the path exists check to return False
        with patch("pathlib.Path.exists", return_value=False):
            template = generator._load_template("general")
        
        assert "You are an expert code reviewer" in template
    
    def test_detect_primary_language_python(self):
        """Test language detection for Python."""
        generator = ReviewGenerator()
        
        result = generator._detect_primary_language(self.mock_analysis)
        assert result == "python"
    
    def test_detect_primary_language_javascript(self):
        """Test language detection for JavaScript."""
        generator = ReviewGenerator()
        
        # Modify analysis for JavaScript
        analysis = self.mock_analysis.copy()
        analysis["file_changes"][0]["language"] = "javascript"
        
        result = generator._detect_primary_language(analysis)
        assert result == "javascript"
    
    def test_detect_primary_language_unknown(self):
        """Test language detection with unknown language."""
        generator = ReviewGenerator()
        
        # Modify analysis for unknown language
        analysis = self.mock_analysis.copy()
        analysis["file_changes"][0]["language"] = "unknown"
        
        result = generator._detect_primary_language(analysis)
        assert result is None
    
    def test_format_mr_summary(self):
        """Test MR summary formatting."""
        generator = ReviewGenerator()
        
        summary = generator._format_mr_summary(self.mock_analysis["mr_info"])
        
        assert "Test MR" in summary
        assert "testuser" in summary
        assert "feature → main" in summary
        assert "enhancement" in summary
    
    def test_format_analysis_summary(self):
        """Test analysis summary formatting."""
        generator = ReviewGenerator()
        
        summary = generator._format_analysis_summary(self.mock_analysis)
        
        assert "Files Changed: 3" in summary
        assert "Lines: +50 / -10" in summary
        assert "Complexity Score: 45/100" in summary
        assert "test.py" in summary
    
    def test_format_rag_context(self):
        """Test RAG context formatting."""
        generator = ReviewGenerator()
        
        context = generator._format_rag_context(self.mock_analysis["review_context"])
        
        assert "test query" in context
        assert "function_context" in context
        assert "related.py" in context
        assert "related_function" in context
    
    def test_format_rag_context_empty(self):
        """Test RAG context formatting with empty context."""
        generator = ReviewGenerator()
        
        context = generator._format_rag_context([])
        
        assert "No related code context found" in context
    
    @responses.activate
    def test_call_llm_success(self):
        """Test successful LLM call."""
        generator = ReviewGenerator()
        
        # Mock Ollama response
        responses.add(
            responses.POST,
            f"{generator.ollama_host}/api/generate",
            json={"response": "Test review response"},
            status=200
        )
        
        result = generator._call_llm("Test prompt")
        assert result == "Test review response"
    
    @responses.activate
    def test_call_llm_failure(self):
        """Test LLM call failure."""
        generator = ReviewGenerator()
        
        # Mock failed response
        responses.add(
            responses.POST,
            f"{generator.ollama_host}/api/generate",
            status=500
        )
        
        with pytest.raises(Exception):
            generator._call_llm("Test prompt")
    
    def test_extract_sections(self):
        """Test section extraction from LLM response."""
        generator = ReviewGenerator()
        
        response = """
        **Summary**
        This is the summary section.
        
        **Detailed Comments**
        These are detailed comments.
        
        **Recommendations**
        These are recommendations.
        """
        
        sections = generator._extract_sections(response)
        
        assert "summary" in sections
        assert "detailed_comments" in sections
        assert "recommendations" in sections
        assert "This is the summary section." in sections["summary"]
    
    def test_assess_mr_risk_high(self):
        """Test high risk assessment."""
        generator = ReviewGenerator()
        
        # High complexity score
        analysis = self.mock_analysis.copy()
        analysis["impact_analysis"]["complexity_score"] = 80
        
        risk = generator._assess_mr_risk(analysis)
        assert risk == "HIGH_RISK"
    
    def test_assess_mr_risk_medium(self):
        """Test medium risk assessment."""
        generator = ReviewGenerator()
        
        # Medium complexity score
        analysis = self.mock_analysis.copy()
        analysis["impact_analysis"]["complexity_score"] = 60
        
        risk = generator._assess_mr_risk(analysis)
        assert risk == "MEDIUM_RISK"
    
    def test_assess_mr_risk_low(self):
        """Test low risk assessment."""
        generator = ReviewGenerator()
        
        # Low complexity score and no risk factors
        analysis = self.mock_analysis.copy()
        analysis["impact_analysis"]["complexity_score"] = 30
        analysis["impact_analysis"]["risk_factors"] = []
        
        risk = generator._assess_mr_risk(analysis)
        assert risk == "LOW_RISK"
    
    def test_generate_line_comments(self):
        """Test line comment generation."""
        generator = ReviewGenerator()
        
        comments = generator._generate_line_comments(self.mock_analysis, "LLM response")
        
        # Should generate comment for new function
        assert len(comments) == 1
        assert comments[0]["file_path"] == "test.py"
        assert comments[0]["line_number"] == 10
        assert "test_function" in comments[0]["comment"]
    
    def test_generate_fallback_review(self):
        """Test fallback review generation."""
        generator = ReviewGenerator()
        
        review = generator._generate_fallback_review(self.mock_analysis, "general")
        
        assert "MR #123" in review["summary"]
        assert "3 files" in review["summary"]
        assert review["metadata"]["fallback"] is True
        assert review["overall_assessment"] == "MEDIUM_RISK"
    
    @responses.activate
    def test_generate_review_success(self):
        """Test successful review generation."""
        generator = ReviewGenerator()
        
        # Mock LLM response
        responses.add(
            responses.POST,
            f"{generator.ollama_host}/api/generate",
            json={
                "response": """
                **Summary**
                Good code changes overall.
                
                **Detailed Comments**
                The implementation looks solid.
                
                **Recommendations**
                Consider adding more tests.
                """
            },
            status=200
        )
        
        with patch.object(generator, '_get_timestamp', return_value="2023-01-01T00:00:00"):
            review = generator.generate_review(self.mock_analysis, "general")
        
        assert review["metadata"]["review_type"] == "python"  # Auto-detected
        assert review["metadata"]["mr_iid"] == 123
        assert review["overall_assessment"] == "MEDIUM_RISK"
        assert "Good code changes overall" in review["summary"]
    
    @responses.activate
    def test_generate_review_llm_failure(self):
        """Test review generation with LLM failure."""
        generator = ReviewGenerator()
        
        # Mock failed LLM response
        responses.add(
            responses.POST,
            f"{generator.ollama_host}/api/generate",
            status=500
        )
        
        review = generator.generate_review(self.mock_analysis, "general")
        
        # Should return fallback review
        assert review["metadata"]["fallback"] is True
        assert "MR #123" in review["summary"]
    
    def test_format_for_gitlab(self):
        """Test GitLab formatting."""
        generator = ReviewGenerator()
        
        review = {
            "summary": "Test summary",
            "detailed_comments": "Test details",
            "recommendations": "Test recommendations",
            "overall_assessment": "LOW_RISK",
            "metadata": {
                "mr_iid": 123,
                "review_type": "general"
            }
        }
        
        gitlab_text = generator.format_for_gitlab(review)
        
        assert "🤖 Automated Code Review ✅" in gitlab_text
        assert "Test summary" in gitlab_text
        assert "Test details" in gitlab_text
        assert "Test recommendations" in gitlab_text
        assert "CodeRAG GitLab Integration" in gitlab_text
    
    def test_format_for_gitlab_high_risk(self):
        """Test GitLab formatting for high risk."""
        generator = ReviewGenerator()
        
        review = {
            "summary": "Test summary",
            "detailed_comments": "Test details", 
            "recommendations": "Test recommendations",
            "overall_assessment": "HIGH_RISK",
            "metadata": {
                "mr_iid": 123,
                "review_type": "security"
            }
        }
        
        gitlab_text = generator.format_for_gitlab(review)
        
        assert "🚨" in gitlab_text
        assert "security" in gitlab_text


if __name__ == '__main__':
    pytest.main([__file__])