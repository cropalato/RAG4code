#!/usr/bin/env python3
"""
Tests for MR analyzer.
"""

import pytest
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitlab_integration.mr_analyzer import MRAnalyzer


class TestMRAnalyzer:
    """Test cases for MR analyzer."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.mock_rag_system = Mock()
        self.analyzer = MRAnalyzer(self.mock_rag_system)
        
        # Sample MR data
        self.sample_mr_data = {
            "iid": 123,
            "title": "Add user authentication",
            "description": "Implements JWT-based authentication",
            "author": {"username": "testuser"},
            "source_branch": "feature/auth",
            "target_branch": "main",
            "state": "opened",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-02T00:00:00Z",
            "labels": [{"name": "enhancement"}, {"name": "security"}]
        }
        
        # Sample changes data
        self.sample_changes_data = {
            "changes": [
                {
                    "old_path": "auth.py",
                    "new_path": "auth.py",
                    "new_file": False,
                    "deleted_file": False,
                    "diff": """@@ -1,3 +1,8 @@
 import bcrypt
 
-def hash_password(password):
+def hash_password(password: str) -> str:
+    \"\"\"Hash password using bcrypt.\"\"\"
+    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
+
+def verify_password(password: str, hashed: str) -> bool:
+    \"\"\"Verify password against hash.\"\"\"
     return bcrypt.checkpw(password.encode(), hashed.encode())"""
                }
            ]
        }
    
    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        analyzer = MRAnalyzer()
        assert analyzer.rag_system is None
        assert '.py' in analyzer.code_extensions
        assert 'python' in analyzer.function_patterns
    
    def test_analyze_mr_changes_basic(self):
        """Test basic MR analysis."""
        analysis = self.analyzer.analyze_mr_changes(
            self.sample_mr_data, 
            self.sample_changes_data
        )
        
        # Check basic structure
        assert 'mr_info' in analysis
        assert 'file_changes' in analysis
        assert 'code_changes' in analysis
        assert 'impact_analysis' in analysis
        
        # Check MR info extraction
        mr_info = analysis['mr_info']
        assert mr_info['iid'] == 123
        assert mr_info['title'] == "Add user authentication"
        assert mr_info['author'] == "testuser"
        assert mr_info['source_branch'] == "feature/auth"
        assert mr_info['target_branch'] == "main"
        assert "enhancement" in mr_info['labels']
        assert "security" in mr_info['labels']
    
    def test_analyze_file_change(self):
        """Test file change analysis."""
        change = self.sample_changes_data['changes'][0]
        file_analysis = self.analyzer._analyze_file_change(change)
        
        assert file_analysis['file_path'] == "auth.py"
        assert file_analysis['change_type'] == "modified"
        assert file_analysis['file_extension'] == ".py"
        assert file_analysis['language'] == "python"
        assert file_analysis['is_code_file'] is True
        assert file_analysis['lines_added'] > 0
        assert len(file_analysis['modified_lines']) > 0
    
    def test_determine_change_type(self):
        """Test change type determination."""
        # New file
        new_file_change = {"new_file": True}
        assert self.analyzer._determine_change_type(new_file_change) == "added"
        
        # Deleted file
        deleted_file_change = {"deleted_file": True}
        assert self.analyzer._determine_change_type(deleted_file_change) == "deleted"
        
        # Renamed file
        renamed_file_change = {"renamed_file": True}
        assert self.analyzer._determine_change_type(renamed_file_change) == "renamed"
        
        # Modified file
        modified_file_change = {}
        assert self.analyzer._determine_change_type(modified_file_change) == "modified"
    
    def test_detect_language(self):
        """Test programming language detection."""
        test_cases = [
            ("file.py", "python"),
            ("script.js", "javascript"),
            ("app.ts", "typescript"),
            ("Component.jsx", "javascript"),
            ("Service.java", "java"),
            ("main.go", "go"),
            ("lib.rs", "rust"),
            ("unknown.xyz", "unknown"),
            ("", "unknown")
        ]
        
        for file_path, expected_language in test_cases:
            result = self.analyzer._detect_language(file_path)
            assert result == expected_language
    
    def test_parse_diff(self):
        """Test diff parsing."""
        file_analysis = {
            'lines_added': 0,
            'lines_removed': 0,
            'modified_lines': [],
            'context_lines': []
        }
        
        diff_content = """@@ -1,3 +1,5 @@
 import bcrypt
 
-def hash_password(password):
+def hash_password(password: str) -> str:
+    \"\"\"Hash password using bcrypt.\"\"\"
     return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()"""
        
        self.analyzer._parse_diff(diff_content, file_analysis)
        
        assert file_analysis['lines_added'] == 2  # Two + lines
        assert file_analysis['lines_removed'] == 1  # One - line
        assert len(file_analysis['modified_lines']) == 3  # 2 added + 1 removed
        assert len(file_analysis['context_lines']) > 0  # Context lines present
    
    def test_extract_functions_from_line(self):
        """Test function extraction from code lines."""
        test_cases = [
            ("def hash_password(password: str) -> str:", "python", ["hash_password"]),
            ("function validateUser(user) {", "javascript", ["validateUser"]),
            ("const processData = (data) => {", "javascript", ["processData"]),
            ("public void saveUser(User user) {", "java", []),  # More complex pattern
            ("// This is a comment", "python", [])
        ]
        
        for line, language, expected in test_cases:
            result = self.analyzer._extract_functions_from_line(line, language)
            assert result == expected
    
    def test_extract_classes_from_line(self):
        """Test class extraction from code lines."""
        test_cases = [
            ("class UserAuth:", "python", ["UserAuth"]),
            ("class UserService extends BaseService {", "javascript", ["UserService"]),
            ("public class AuthenticationManager {", "java", ["AuthenticationManager"]),
            ("interface UserRepository {", "typescript", ["UserRepository"]),
            ("# This is a comment", "python", [])
        ]
        
        for line, language, expected in test_cases:
            result = self.analyzer._extract_classes_from_line(line, language)
            assert result == expected
    
    def test_calculate_complexity_score(self):
        """Test complexity score calculation."""
        # Create a sample analysis
        analysis = {
            'impact_analysis': {
                'files_count': 5,
                'lines_added': 100,
                'lines_removed': 50
            },
            'code_changes': {
                'new_functions': ['func1', 'func2'],
                'new_classes': ['Class1']
            },
            'file_changes': [
                {'language': 'python'},
                {'language': 'javascript'},
                {'language': 'python'}  # Duplicate to test diversity
            ]
        }
        
        score = self.analyzer._calculate_complexity_score(analysis)
        
        assert isinstance(score, int)
        assert 0 <= score <= 100
        assert score > 0  # Should have some complexity
    
    def test_identify_risk_factors(self):
        """Test risk factor identification."""
        # High-risk analysis
        high_risk_analysis = {
            'impact_analysis': {
                'files_count': 25,  # > 20
                'lines_added': 600,  # > 500
                'lines_removed': 100,
                'complexity_score': 80  # > 75
            },
            'code_changes': {
                'new_functions': ['f' + str(i) for i in range(15)],  # > 10
                'new_classes': []
            },
            'file_changes': [
                {'file_path': 'security/auth.py'},
                {'file_path': 'config/database.yml'},
                {'file_path': 'migrations/001_add_users.sql'}
            ]
        }
        
        risks = self.analyzer._identify_risk_factors(high_risk_analysis)
        
        assert len(risks) > 0
        assert any("Large number of files" in risk for risk in risks)
        assert any("Large number of lines" in risk for risk in risks)
        assert any("High complexity score" in risk for risk in risks)
        assert any("Many new code elements" in risk for risk in risks)
        assert any("Critical file modified" in risk for risk in risks)
    
    def test_generate_rag_context(self):
        """Test RAG context generation."""
        # Setup mock RAG system
        self.mock_rag_system.search_code.return_value = {
            'hits': [
                {
                    '_source': {
                        'file_path': 'related_auth.py',
                        'content': 'def authenticate_user(username, password):',
                        'functions': ['authenticate_user']
                    }
                }
            ]
        }
        
        analysis = {
            'code_changes': {
                'new_functions': [
                    {
                        'name': 'hash_password',
                        'language': 'python',
                        'file_path': 'auth.py'
                    }
                ]
            },
            'file_changes': [
                {
                    'file_path': 'auth.py',
                    'is_code_file': True,
                    'language': 'python'
                }
            ]
        }
        
        context = self.analyzer._generate_rag_context(analysis)
        
        assert len(context) > 0
        assert self.mock_rag_system.search_code.called
        
        # Check context structure
        for ctx in context:
            assert 'query' in ctx
            assert 'type' in ctx
            assert 'element' in ctx
            assert 'rag_results' in ctx
    
    def test_generate_analysis_summary(self):
        """Test analysis summary generation."""
        analysis = self.analyzer.analyze_mr_changes(
            self.sample_mr_data,
            self.sample_changes_data
        )
        
        summary = self.analyzer.generate_analysis_summary(analysis)
        
        assert isinstance(summary, str)
        assert "MR Analysis Summary" in summary
        assert "Add user authentication" in summary
        assert "testuser" in summary
        assert "feature/auth" in summary
        assert "main" in summary
    
    def test_analyze_mr_changes_with_rag_system(self):
        """Test full MR analysis with RAG system."""
        # Mock RAG system responses
        self.mock_rag_system.search_code.return_value = {
            'hits': [
                {
                    '_source': {
                        'file_path': 'auth_helper.py',
                        'content': 'def validate_password_strength(password):',
                        'functions': ['validate_password_strength']
                    }
                }
            ]
        }
        
        analysis = self.analyzer.analyze_mr_changes(
            self.sample_mr_data,
            self.sample_changes_data
        )
        
        # Check that RAG context was generated
        assert 'review_context' in analysis
        assert len(analysis['review_context']) > 0
        
        # Verify RAG system was called
        assert self.mock_rag_system.search_code.called
    
    def test_analyze_mr_changes_without_rag_system(self):
        """Test MR analysis without RAG system."""
        analyzer_no_rag = MRAnalyzer(None)
        
        analysis = analyzer_no_rag.analyze_mr_changes(
            self.sample_mr_data,
            self.sample_changes_data
        )
        
        # Should still work but without RAG context
        assert 'review_context' in analysis
        assert analysis['review_context'] == []


if __name__ == '__main__':
    pytest.main([__file__])