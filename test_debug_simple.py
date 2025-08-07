#!/usr/bin/env python3
"""
Simple test script to demonstrate debug logging functionality without dependencies.
"""

import sys
from pathlib import Path
import logging
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import only the logging setup function
def setup_logging(verbose: bool = False, debug_file: str = None):
    """Setup comprehensive logging for debugging."""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    simple_formatter = logging.Formatter('%(levelname)s: %(message)s')
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(simple_formatter if not verbose else detailed_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler for debug logs
    if debug_file or verbose:
        debug_file = debug_file or f"gitlab_review_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(debug_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
        
        if verbose:
            print(f"🔍 Debug logging enabled. Logs saved to: {debug_file}")
    
    return root_logger

def test_debug_logging():
    """Test the debug logging functionality."""
    
    print("🧪 Testing Debug Logging Functionality")
    print("=" * 50)
    
    # Test 1: Basic logging without debug
    print("\n1. Testing basic logging (INFO level):")
    logger = setup_logging(verbose=False)
    logger.info("This is an info message")
    logger.debug("This debug message should NOT appear")
    logger.warning("This is a warning message")
    
    # Test 2: Verbose logging
    print("\n2. Testing verbose logging (DEBUG level):")
    logger = setup_logging(verbose=True, debug_file="test_debug.log")
    logger.info("🔍 This is an info message with debug enabled")
    logger.debug("🔍 This debug message SHOULD appear")
    logger.warning("🔍 This is a warning message")
    
    # Test 3: Custom debug file
    print("\n3. Testing custom debug file:")
    logger = setup_logging(verbose=False, debug_file="custom_debug.log")
    logger.info("📝 Writing to custom debug file")
    logger.debug("📝 Debug message in custom file")
    
    # Test 4: Simulate GitLab review process logging
    print("\n4. Simulating GitLab review process:")
    logger = setup_logging(verbose=True, debug_file="review_simulation.log")
    
    # Simulate the review process
    logger.info("🚀 GitLab Review CLI initialized")
    logger.debug("🔍 Debug mode enabled - detailed logging active")
    logger.info("🔧 Starting component initialization...")
    logger.debug("🔍 GitLab URL: https://gitlab.example.com")
    logger.debug("🔍 GitLab Token: ***")
    logger.info("✅ GitLab client initialized")
    logger.info("🧠 Initializing CodeRAG system...")
    logger.debug("🔍 RAG configuration: {\"ollama_host\": \"http://localhost:11434\"}")
    logger.info("✅ CodeRAG system initialized")
    logger.info("🔍 Starting review of MR: https://gitlab.example.com/group/project/-/merge_requests/123")
    logger.debug("🔍 Review parameters - Type: general, Post: false")
    logger.debug("📥 Fetching MR data from GitLab...")
    logger.debug("🔍 MR data received - Title: Add new feature")
    logger.debug("🔍 Changes data received - Files changed: 3")
    logger.debug("🧠 Starting RAG context generation...")
    logger.debug("🔍 Found 2 new functions for RAG queries")
    logger.debug("🔍 Executing RAG query 1/2: functions similar to authenticate in python")
    logger.debug("🔍 RAG query returned 1 results")
    logger.debug("🤖 Starting LLM call to Ollama...")
    logger.debug("🔍 Prompt length: 1234 characters")
    logger.debug("🔍 Ollama response received in 8.45 seconds")
    logger.debug("🔍 Generated text length: 512 characters")
    logger.debug("✅ LLM call completed successfully")
    logger.info("🎉 Review generation completed successfully")
    
    print("\n5. Checking created debug files:")
    debug_files = ["test_debug.log", "custom_debug.log", "review_simulation.log"]
    
    for log_file in debug_files:
        if Path(log_file).exists():
            size = Path(log_file).stat().st_size
            print(f"✅ {log_file} - Size: {size} bytes")
            
            # Show a few lines from the file
            with open(log_file, 'r') as f:
                lines = f.readlines()
                if lines:
                    print(f"   📝 Sample content: {lines[0].strip()}")
        else:
            print(f"❌ {log_file} - Not found")
    
    print("\n6. Debug Usage Examples:")
    print("   Basic usage:")
    print("   python gitlab_review.py --mr <URL> --verbose")
    print("")
    print("   With custom debug file:")
    print("   python gitlab_review.py --mr <URL> --debug-file my_debug.log")
    print("")
    print("   Full debug (console + file):")
    print("   python gitlab_review.py --mr <URL> --verbose --debug-file detailed.log")
    
    print("\n✅ Debug logging test completed successfully!")
    print("\n📋 Debug Features Summary:")
    print("   🔍 Verbose console output with --verbose flag")
    print("   📝 Custom debug file with --debug-file option")
    print("   🎯 Detailed tracing of GitLab API calls")
    print("   🧠 RAG system query logging")
    print("   🤖 Ollama LLM interaction logs")
    print("   ⏱️ Performance timing information")
    print("   🚨 Error details with stack traces")

if __name__ == "__main__":
    test_debug_logging()