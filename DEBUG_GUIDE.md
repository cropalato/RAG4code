# 🔍 Debug Guide - GitLab MR Review Integration

Comprehensive guide for debugging and tracing the GitLab MR review system.

## 🎯 Debug Features Overview

The system includes comprehensive debug logging to trace:
- **GitLab API calls** and responses
- **RAG system queries** and results
- **Ollama LLM interactions** and generated content
- **MR analysis** process and findings
- **Review generation** steps and timing
- **Error details** with full stack traces

## 🛠️ Debug Options

### 1. Verbose Mode (`--verbose` or `-v`)

Enables detailed console output and debug logging:

```bash
# Basic verbose mode
python gitlab_review.py --mr <URL> --verbose

# Verbose batch processing
python gitlab_review.py --project group/project --batch --verbose

# Verbose CI mode
python gitlab_review.py --ci-mode --verbose
```

**What you'll see:**
- 🔍 Detailed step-by-step process information
- 📊 Performance metrics and timing
- 🧠 RAG query details and results
- 🤖 Ollama request/response information
- 🔧 Configuration and connection details

### 2. Debug File Logging (`--debug-file`)

Saves detailed logs to a specific file:

```bash
# Save debug logs to custom file
python gitlab_review.py --mr <URL> --debug-file my_review_debug.log

# Combine with verbose for both console and file logging
python gitlab_review.py --mr <URL> --verbose --debug-file detailed_trace.log
```

**Debug file contains:**
- Timestamps for all operations
- Full request/response data
- Error stack traces
- Performance metrics
- RAG context details

### 3. Environment Variable Logging

Set environment variables for persistent debug settings:

```bash
# Enable debug level logging
export LOG_LEVEL=DEBUG

# Run with environment debug
python gitlab_review.py --mr <URL>
```

## 📊 Debug Output Examples

### 1. Verbose Console Output

```
🔍 Debug mode enabled - detailed logging active
🔧 Starting component initialization...
🔍 GitLab URL: https://gitlab.com
🔍 GitLab Token: ***
✅ GitLab client initialized
🧠 Initializing CodeRAG system...
🔍 RAG configuration: {
  "ollama_host": "http://localhost:11434",
  "api_url": "http://localhost:8000"
}
✅ CodeRAG system initialized
🔍 Starting review of MR: https://gitlab.com/group/project/-/merge_requests/123
🔍 Review parameters - Type: general, Post: false, Project filter: None
📥 Fetching MR data from GitLab...
🔍 MR data received - Title: Add new authentication feature
🔍 MR author: developer
🔍 Changes data received - Files changed: 8
🧠 Starting RAG context generation...
🔍 Found 3 new functions for RAG queries
🔍 Executing RAG query 1/5: functions similar to authenticate in python
🔍 RAG query returned 2 results
🔍 First result from: src/auth/helpers.py
🤖 Starting LLM call to Ollama...
🔍 Prompt length: 2847 characters
🔍 Ollama response received in 12.45 seconds
🔍 Generated text length: 1024 characters
✅ LLM call completed successfully
```

### 2. Debug File Content

```
2025-08-04 10:30:15 - gitlab_review - INFO - [gitlab_review.py:175] - 🔍 Starting review of MR: https://gitlab.com/group/project/-/merge_requests/123
2025-08-04 10:30:15 - gitlab_review - DEBUG - [gitlab_review.py:177] - 🔍 Review parameters - Type: general, Post: false, Project filter: None
2025-08-04 10:30:16 - gitlab_integration.gitlab_client - DEBUG - [gitlab_client.py:89] - Making API request: GET /projects/group%2Fproject/merge_requests/123
2025-08-04 10:30:16 - gitlab_integration.mr_analyzer - DEBUG - [mr_analyzer.py:468] - 🔍 Executing RAG query 1/5: functions similar to authenticate in python
2025-08-04 10:30:18 - gitlab_integration.review_generator - DEBUG - [review_generator.py:275] - 🔍 Ollama host: http://localhost:11434
2025-08-04 10:30:18 - gitlab_integration.review_generator - DEBUG - [review_generator.py:276] - 🔍 Prompt preview (first 200 chars): You are an expert code reviewer analyzing a GitLab merge request. Please provide a comprehensive review based on the following analysis...
```

## 🔍 What Gets Logged

### 1. GitLab API Interactions

```bash
# Debug shows:
🔗 Parsing MR URL...
📥 Fetching MR data from GitLab...
🔍 MR data received - Title: Add new feature
🔍 MR author: developer
🔍 MR state: opened
📥 Fetching MR changes from GitLab...
🔍 Changes data received - Files changed: 5
🔍 File 1: src/main.py
🔍 File 2: tests/test_main.py
```

### 2. RAG System Queries

```bash
# Debug shows:
🧠 Starting RAG context generation...
🔍 Found 3 new functions for RAG queries
🔍 Added function query: functions similar to authenticate in python
🔍 Generated 5 RAG queries, executing first 10...
🔍 Executing RAG query 1/5: functions similar to authenticate in python
🔍 RAG query returned 2 results
🔍 First result from: src/auth/helpers.py
🔍 RAG context generation complete. Found 3 relevant contexts
```

### 3. Ollama LLM Interactions

```bash
# Debug shows:
🤖 Starting LLM call to Ollama...
🔍 Prompt length: 2847 characters
🔍 Ollama host: http://localhost:11434
🔍 Request options: {
  "temperature": 0.1,
  "top_p": 0.9,
  "max_tokens": 1024
}
🔍 Sending request to Ollama...
🔍 Ollama response received in 12.45 seconds
🔍 Response status code: 200
🔍 Generated text length: 1024 characters
🔍 Tokens evaluated: 2847
🔍 Evaluation duration: 11.23 seconds
✅ LLM call completed successfully
```

### 4. Analysis Results

```bash
# Debug shows:
🔍 Analysis complete - Complexity: 65/100
🔍 Files analyzed: 5
🔍 Lines added: 142
🔍 Lines removed: 23
🔍 RAG context entries found: 3
🔍 Review generated successfully
🔍 Review type used: python
🔍 Risk assessment: MEDIUM_RISK
🔍 Review summary length: 456 characters
```

## 🚨 Troubleshooting with Debug Logs

### 1. GitLab Connection Issues

**Symptoms:**
```
❌ Failed to initialize components: Invalid token
```

**Debug with:**
```bash
python gitlab_review.py --mr <URL> --verbose
```

**Look for:**
```
🔍 GitLab URL: https://gitlab.com
🔍 GitLab Token: ***
❌ GitLab connection failed: 401 Unauthorized
```

### 2. RAG System Issues

**Symptoms:**
```
🔍 No results for query: functions similar to authenticate in python
```

**Debug with:**
```bash
python gitlab_review.py --mr <URL> --verbose --debug-file rag_debug.log
```

**Look for:**
```
🔍 RAG query failed for 'functions similar to authenticate in python': Connection refused
🔍 RAG system doesn't have expected search methods
```

### 3. Ollama Connection Issues

**Symptoms:**
```
LLM call failed: Connection refused
```

**Debug with:**
```bash
python gitlab_review.py --mr <URL> --verbose
```

**Look for:**
```
🔍 Ollama host: http://localhost:11434
🔍 Sending request to Ollama...
❌ Connection refused to http://localhost:11434/api/generate
```

### 4. Performance Issues

**Symptoms:**
- Reviews taking too long
- High memory usage

**Debug with:**
```bash
python gitlab_review.py --mr <URL> --verbose --debug-file performance.log
```

**Look for:**
```
🔍 Prompt truncated from 8000 to 4000 characters
🔍 Ollama response received in 45.67 seconds
⚠️ Skipping large file: src/large_file.py (5242880 bytes)
🔥 Filtered 15 files for performance (large files or too many files)
```

## 📈 Performance Monitoring

Debug logs include performance metrics:

```bash
# Timing information
🔍 Ollama response received in 12.45 seconds
🔍 Evaluation duration: 11.23 seconds
⏱️ Processing time: 25.30 seconds

# Resource usage
🔍 Prompt length: 2847 characters
🔍 Generated text length: 1024 characters
🔍 Tokens evaluated: 2847

# Optimization indicators
🔍 Prompt truncated from 8000 to 4000 characters
⚠️ Skipping large file: large_data.json (10485760 bytes)
🔥 Filtered 20 files for performance
```

## 🔧 Debug Configuration

### Environment Variables

```bash
# Set debug level
export LOG_LEVEL=DEBUG

# Custom Ollama host for debugging
export OLLAMA_HOST=http://debug-ollama:11434

# Custom RAG API for debugging  
export RAG_API_URL=http://debug-rag:8000
```

### Debug-Specific Usage

```bash
# Full debug session
python gitlab_review.py \
  --mr https://gitlab.com/group/project/-/merge_requests/123 \
  --verbose \
  --debug-file full_trace_$(date +%Y%m%d_%H%M%S).log \
  --type general

# CI debug mode
CI_REVIEW_ENABLED=true \
LOG_LEVEL=DEBUG \
python gitlab_review.py --ci-mode --verbose

# Batch processing debug
python gitlab_review.py \
  --project group/project \
  --batch \
  --parallel-workers 1 \
  --verbose \
  --debug-file batch_debug.log
```

## 📁 Debug Files Management

Debug files are automatically created with timestamps:

```bash
# Auto-generated debug files
gitlab_review_debug_20250804_103015.log
test_cli_debug.log
batch_debug.log

# Check debug file size
ls -lh *debug*.log

# View recent debug logs
tail -f gitlab_review_debug_*.log

# Search for specific issues
grep -i "error\|failed\|exception" debug.log
grep "RAG query" debug.log
grep "Ollama" debug.log
```

## 🎯 Best Practices for Debug Sessions

### 1. Structured Debugging

```bash
# Start with basic verbose
python gitlab_review.py --mr <URL> --verbose

# If issues found, add debug file
python gitlab_review.py --mr <URL> --verbose --debug-file issue_debug.log

# For deep investigation, check specific components
grep "RAG\|Ollama\|GitLab" issue_debug.log
```

### 2. Performance Debugging

```bash
# Monitor timing
python gitlab_review.py --mr <URL> --verbose | grep -E "seconds|time"

# Check for optimization triggers
python gitlab_review.py --mr <URL> --verbose | grep -E "truncated|skipping|filtered"
```

### 3. Component Isolation

```bash
# Test GitLab connection only
python -c "from gitlab_integration import GitLabClient; client = GitLabClient('https://gitlab.com', 'token')"

# Test Ollama connection only
curl http://localhost:11434/api/tags

# Test RAG connection only
curl http://localhost:8000/health
```

## 📞 Support Information

When reporting issues, include:

1. **Command used:**
   ```bash
   python gitlab_review.py --mr <URL> --verbose --debug-file issue.log
   ```

2. **Debug log file** (sanitize sensitive information)

3. **Environment details:**
   ```bash
   echo "Python: $(python --version)"
   echo "OS: $(uname -a)"
   echo "GitLab URL: $GITLAB_URL"
   echo "Ollama Host: $OLLAMA_HOST"
   ```

4. **Error symptoms** and expected behavior

With these debug tools, you can trace every step of the GitLab MR review process and quickly identify issues! 🚀