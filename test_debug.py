#!/usr/bin/env python3
"""
Test script to demonstrate debug logging functionality.
"""

import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from gitlab_review import GitLabReviewCLI, setup_logging

def test_debug_logging():
    """Test the debug logging functionality."""
    
    print("🧪 Testing Debug Logging Functionality")
    print("=" * 50)
    
    # Test verbose logging
    print("\n1. Testing verbose logging:")
    logger = setup_logging(verbose=True, debug_file="test_debug.log")
    
    logger.info("This is an info message")
    logger.debug("This is a debug message")
    logger.warning("This is a warning message")
    
    # Test CLI initialization
    print("\n2. Testing CLI initialization with debug:")
    try:
        cli = GitLabReviewCLI(verbose=True, debug_file="test_cli_debug.log")
        print("✅ CLI initialized successfully with debug logging")
    except Exception as e:
        print(f"❌ CLI initialization failed: {e}")
    
    print("\n3. Debug log files created:")
    for log_file in ["test_debug.log", "test_cli_debug.log"]:
        if Path(log_file).exists():
            print(f"✅ {log_file} - Size: {Path(log_file).stat().st_size} bytes")
        else:
            print(f"❌ {log_file} - Not found")
    
    print("\n4. Usage example:")
    print("To use debug logging with GitLab review:")
    print("python gitlab_review.py --mr <URL> --verbose")
    print("python gitlab_review.py --mr <URL> --debug-file my_debug.log")
    print("python gitlab_review.py --mr <URL> --verbose --debug-file detailed_debug.log")
    
    print("\n✅ Debug logging test completed!")

if __name__ == "__main__":
    test_debug_logging()