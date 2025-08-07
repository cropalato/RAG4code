#!/usr/bin/env python3
"""
Phase 1 validation script for GitLab integration.

Tests core functionality without external dependencies.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all core modules can be imported."""
    print("🔍 Testing imports...")
    
    try:
        from gitlab_integration import GitLabClient, MRAnalyzer, ReviewGenerator
        print("✅ GitLab integration imports successful")
    except ImportError as e:
        print(f"❌ GitLab integration import failed: {e}")
        return False
    
    try:
        from gitlab_integration.config import get_config, ConfigManager
        print("✅ Configuration imports successful")
    except ImportError as e:
        print(f"❌ Configuration import failed: {e}")
        return False
    
    return True

def test_gitlab_client():
    """Test GitLab client basic functionality."""
    print("\n🔍 Testing GitLab client...")
    
    try:
        from gitlab_integration.gitlab_client import GitLabClient
        
        # Test URL parsing (no network required)
        client = GitLabClient.__new__(GitLabClient)  # Create without __init__
        client.gitlab_url = "https://gitlab.com/"
        
        # Test URL parsing
        project_path, mr_iid = client.parse_mr_url("https://gitlab.com/group/project/-/merge_requests/123")
        assert project_path == "group/project"
        assert mr_iid == 123
        print("✅ URL parsing works correctly")
        
        return True
    except Exception as e:
        print(f"❌ GitLab client test failed: {e}")
        return False

def test_mr_analyzer():
    """Test MR analyzer basic functionality."""
    print("\n🔍 Testing MR analyzer...")
    
    try:
        from gitlab_integration.mr_analyzer import MRAnalyzer
        
        analyzer = MRAnalyzer(None)  # No RAG system
        
        # Test language detection
        assert analyzer._detect_language("test.py") == "python"
        assert analyzer._detect_language("test.js") == "javascript"
        assert analyzer._detect_language("test.unknown") == "unknown"
        print("✅ Language detection works correctly")
        
        # Test function extraction
        functions = analyzer._extract_functions_from_line("def test_function(param):", "python")
        assert "test_function" in functions
        print("✅ Function extraction works correctly")
        
        return True
    except Exception as e:
        print(f"❌ MR analyzer test failed: {e}")
        return False

def test_review_generator():
    """Test review generator basic functionality."""
    print("\n🔍 Testing review generator...")
    
    try:
        from gitlab_integration.review_generator import ReviewGenerator
        
        generator = ReviewGenerator(None)  # No RAG system
        
        # Test template loading
        assert 'general' in generator.templates
        assert 'security' in generator.templates
        assert 'performance' in generator.templates
        print("✅ Template loading works correctly")
        
        return True
    except Exception as e:
        print(f"❌ Review generator test failed: {e}")
        return False

def test_configuration():
    """Test configuration management."""
    print("\n🔍 Testing configuration...")
    
    try:
        from gitlab_integration.config import GitLabConfig, RAGConfig, ReviewConfig, AppConfig
        
        # Test config creation
        gitlab_config = GitLabConfig(token="test-token")
        rag_config = RAGConfig(temperature=0.5)
        review_config = ReviewConfig(auto_post=True)
        
        app_config = AppConfig(
            gitlab=gitlab_config,
            rag=rag_config,
            review=review_config
        )
        
        # Test serialization
        config_dict = app_config.to_dict()
        assert config_dict['gitlab']['token'] == "test-token"
        assert config_dict['rag']['temperature'] == 0.5
        assert config_dict['review']['auto_post'] is True
        print("✅ Configuration creation and serialization works correctly")
        
        # Test deserialization
        restored_config = AppConfig.from_dict(config_dict)
        assert restored_config.gitlab.token == "test-token"
        print("✅ Configuration deserialization works correctly")
        
        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_file_structure():
    """Test that all required files exist."""
    print("\n🔍 Testing file structure...")
    
    required_files = [
        "gitlab_integration/__init__.py",
        "gitlab_integration/gitlab_client.py",
        "gitlab_integration/mr_analyzer.py", 
        "gitlab_integration/review_generator.py",
        "gitlab_integration/config/__init__.py",
        "gitlab_integration/config/settings.py",
        "gitlab_review.py",
        "requirements_gitlab.txt",
        "TODO_GITLAB_MR_REVIEW.md",
        "examples/sample_config.yaml",
        "examples/sample_review.md"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    else:
        print("✅ All required files exist")
        return True

def main():
    """Run all validation tests."""
    print("🚀 GitLab Integration Phase 1 Validation")
    print("=" * 50)
    
    tests = [
        test_file_structure,
        test_imports,
        test_gitlab_client,
        test_mr_analyzer,
        test_review_generator,
        test_configuration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Validation Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 Phase 1 validation successful! Ready for testing with real GitLab instance.")
        print("\n📋 Next steps:")
        print("1. Install dependencies: pip install -r requirements_gitlab.txt")
        print("2. Set up GitLab token: export GITLAB_TOKEN=your_token")
        print("3. Test with real MR: python gitlab_review.py --mr https://gitlab.com/...")
    else:
        print("⚠️ Some tests failed. Please review the output above.")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())