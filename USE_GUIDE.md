# 🚀 Usage Guide - GitLab MR Review Integration

Complete guide on how to configure and use the GitLab MR review system with your Docker environment.

## 📋 Prerequisites

You already have:
- ✅ CodeRAG running in Docker container
- ✅ Ollama running in Docker container
- ✅ Both containers can communicate with each other

## 🛠️ Initial Setup

### 1. Environment Configuration

Create a `.env` file in the project directory:

```bash
# GitLab Configuration
GITLAB_URL=https://your.gitlab.instance
GITLAB_TOKEN=your-access-token

# Ollama Configuration (container URL)
OLLAMA_HOST=http://ollama-container:11434

# CodeRAG Configuration (container URL)
RAG_API_URL=http://coderag-container:8000
```

### 2. GitLab Token

To obtain the token:
1. Go to GitLab → Settings → Access Tokens
2. Create a token with scopes: `api`, `read_repository`
3. Copy the token to the `.env` file

### 3. Dependencies Installation

```bash
pip install -r requirements_gitlab.txt
```

## 🏗️ Communication Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  gitlab_review  │    │   CodeRAG       │    │     Ollama      │
│     (local)     │───▶│   Container     │    │   Container     │
│                 │    │   :8000         │    │   :11434        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                      │
         │                        │                      │
         ▼                        ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     GitLab      │    │  Semantic       │    │  LLM Review     │
│      API        │    │   Search        │    │  Generation     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🎯 How to Use

### 1. Individual MR Review

```bash
# Basic review
python gitlab_review.py --mr https://gitlab.com/group/project/-/merge_requests/123

# Review with specific type
python gitlab_review.py --mr https://gitlab.com/group/project/-/merge_requests/123 --type security

# Automatically post review
python gitlab_review.py --mr https://gitlab.com/group/project/-/merge_requests/123 --post

# Filter RAG context by project
python gitlab_review.py --mr https://gitlab.com/group/project/-/merge_requests/123 --project-filter my-project
```

### 2. Batch Review

```bash
# Review all open MRs in a project
python gitlab_review.py --project group/project --batch

# Review with parallel workers
python gitlab_review.py --project group/project --batch --parallel-workers 3

# Export results
python gitlab_review.py --project group/project --batch --export-results results.json

# Filter by author or labels
python gitlab_review.py --project group/project --batch --author-filter username --label-filter enhancement
```

### 3. List MRs

```bash
# List open MRs
python gitlab_review.py --project group/project --list

# List in JSON format
python gitlab_review.py --project group/project --list --output json
```

## ⚙️ Advanced Configuration

### 1. Configuration File (Optional)

Create `.gitlab-review.yml`:

```yaml
# GitLab configuration
gitlab:
  url: "https://your.gitlab.instance"
  
# RAG configuration
rag:
  ollama_host: "http://ollama-container:11434"
  api_url: "http://coderag-container:8000"
  chat_model: "qwen2.5-coder"
  max_context_chunks: 5

# Review configuration
review:
  default_type: "general"
  max_tokens: 1024
  
# CI/CD configuration
ci:
  enabled: true
  auto_post: false
  review_type: "general"
  skip_on_labels:
    - "skip-review"
    - "wip"
```

### 2. CI/CD Integration

For GitLab CI, add to `.gitlab-ci.yml`:

```yaml
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
    CI_REVIEW_ENABLED: "true"
    CI_AUTO_POST: "true"
    OLLAMA_HOST: "http://ollama-container:11434"
    RAG_API_URL: "http://coderag-container:8000"
```

## 🔄 Workflow Process

### 1. **MR Analysis**
```python
# The system does:
1. Connects to GitLab via API
2. Fetches MR data (title, description, diffs)
3. Analyzes changes (files, lines, complexity)
```

### 2. **CodeRAG Context Search**
```python
# For each significant change:
1. Generates intelligent queries based on code
2. Queries CodeRAG container via HTTP
3. Receives relevant semantic context
```

### 3. **Review Generation**
```python
# With Ollama:
1. Builds prompt with analysis + RAG context
2. Sends to Ollama container via HTTP
3. Receives intelligent review generated by LLM
```

### 4. **Formatting and Posting**
```python
# Final result:
1. Formats review for GitLab Markdown
2. Optionally posts as comment on MR
3. Returns complete analysis
```

## 📊 Example Output

```
============================================================
🎉 MERGE REQUEST REVIEW COMPLETE
============================================================
📋 MR #123: Add new authentication feature
👤 Author: developer
🌿 feature/auth → main

────────────────────────────────────────
📊 ANALYSIS METRICS
────────────────────────────────────────
⏱️  Processing time: 25.30 seconds
🟡 Complexity score: 65/100
📁 Files changed: 8
📈 Lines: +142 / -23
🟡 Risk level: Medium Risk
📤 Review posted to GitLab (Note ID: 789)

────────────────────────────────────────
📝 REVIEW SUMMARY
────────────────────────────────────────
  This MR introduces a comprehensive authentication system with proper
  security practices. The implementation follows good patterns and includes
  appropriate error handling.

────────────────────────────────────────
💡 RECOMMENDATIONS
────────────────────────────────────────
  • Add unit tests for the authentication middleware
  • Consider rate limiting for login attempts
  • Validate input sanitization in auth endpoints
```

## 🚨 Troubleshooting

### Common Issues:

1. **Ollama connection error:**
```bash
# Check if container is running
docker ps | grep ollama

# Test connectivity
curl http://ollama-container:11434/api/tags
```

2. **CodeRAG connection error:**
```bash
# Check if container is running
docker ps | grep coderag

# Test API
curl http://coderag-container:8000/health
```

3. **Invalid GitLab token:**
```bash
# Test the token
curl -H "Authorization: Bearer your-token" https://your.gitlab.instance/api/v4/user
```

4. **Debug mode:**
```bash
# Run with verbose for debugging
python gitlab_review.py --mr URL --verbose
```

## 🔧 Configuration Examples

### Docker Compose Integration

If using docker-compose, you can add the review system:

```yaml
version: '3.8'
services:
  coderag:
    # Your existing CodeRAG service
    ports:
      - "8000:8000"
    networks:
      - review-network

  ollama:
    # Your existing Ollama service
    ports:
      - "11434:11434"
    networks:
      - review-network

  gitlab-review:
    build: .
    environment:
      - GITLAB_URL=https://your.gitlab.instance
      - GITLAB_TOKEN=${GITLAB_TOKEN}
      - OLLAMA_HOST=http://ollama:11434
      - RAG_API_URL=http://coderag:8000
    networks:
      - review-network
    depends_on:
      - coderag
      - ollama

networks:
  review-network:
    driver: bridge
```

### Environment Variables Reference

```bash
# Required
GITLAB_URL=https://your.gitlab.instance
GITLAB_TOKEN=your-access-token

# Container URLs
OLLAMA_HOST=http://ollama-container:11434
RAG_API_URL=http://coderag-container:8000

# Optional configurations
RAG_CHAT_MODEL=qwen2.5-coder
RAG_MAX_CONTEXT_CHUNKS=5
REVIEW_DEFAULT_TYPE=general
REVIEW_MAX_TOKENS=1024

# CI/CD specific
CI_REVIEW_ENABLED=true
CI_AUTO_POST=false
CI_REVIEW_TYPE=general
CI_PARALLEL_WORKERS=3
```

## 📈 Performance Tuning

### For Large Projects:

```bash
# Limit file processing for performance
python gitlab_review.py --mr URL --max-files 50

# Use parallel processing for batch reviews
python gitlab_review.py --project group/project --batch --parallel-workers 3 --delay 0.5

# Filter large files automatically (built-in optimization)
# Files > 5MB are automatically skipped
```

### Memory Optimization:

The system automatically:
- Limits file size processing (5MB max per file)
- Filters binary files
- Processes large MRs in chunks
- Uses memory-efficient diff parsing

## 🎯 Next Steps

1. **Initial test:**
```bash
python gitlab_review.py --mr https://your-gitlab.com/project/mr/1
```

2. **Configure CI/CD** for automated reviews

3. **Customize review templates** according to your team needs

4. **Configure project filters** in RAG for better context

5. **Set up monitoring** for production usage

## 📝 Quick Start Checklist

- [ ] Install dependencies: `pip install -r requirements_gitlab.txt`
- [ ] Create `.env` file with GitLab token and container URLs
- [ ] Test Ollama connectivity: `curl http://ollama-container:11434/api/tags`
- [ ] Test CodeRAG connectivity: `curl http://coderag-container:8000/health`
- [ ] Run first review: `python gitlab_review.py --mr YOUR_MR_URL`
- [ ] Configure CI/CD pipeline (optional)
- [ ] Set up project-specific configuration (optional)

The system is ready for production use! 🚀

## 🆘 Support

For issues or questions:
1. Check the troubleshooting section above
2. Run with `--verbose` flag for detailed logging
3. Verify container connectivity and GitLab token
4. Check the complete documentation in `docs/` directory

## 🔗 Related Documentation

- [API Reference](docs/API_REFERENCE.md) - Complete API documentation
- [Performance Optimization](docs/PERFORMANCE_OPTIMIZATION.md) - Performance tuning guide
- [Main Documentation](docs/README_GITLAB_INTEGRATION.md) - Comprehensive feature overview