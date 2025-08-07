# 🤖 CodeRAG - Intelligent Code Analysis System

Complete RAG (Retrieval-Augmented Generation) system for code analysis using Ollama, with GitLab MR review integration, incremental indexing, and comprehensive debugging capabilities. Fully containerized with multiple vector database backends.

## 🚀 Features

### 🎯 Core Capabilities
- **🔍 Intelligent Code Search** - Semantic search through your codebase
- **💬 Natural Language Queries** - Ask questions about your code in plain English
- **📁 Project Management** - Index and manage multiple projects
- **🔄 Incremental Updates** - Fast updates for changed files only
- **🌐 Web Interface** - Beautiful, responsive web UI
- **⚡ CLI Tools** - Powerful command-line interface

### 🔧 GitLab Integration
- **📋 MR Review Automation** - Automated merge request reviews
- **🎨 Review Templates** - Customizable review templates
- **⚙️ CI/CD Integration** - GitLab pipeline integration
- **📊 Batch Processing** - Review multiple MRs efficiently
- **🔍 Debug Logging** - Comprehensive debug and tracing capabilities

### 🗄️ Vector Database Backends
- **ChromaDB** - Fast local storage (default)
- **OpenSearch** - Scalable enterprise solution

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Install Docker and Docker Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install and start Ollama on host
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &

# Download required models
ollama pull nomic-embed-text
ollama pull qwen2.5-coder
```

### 2. Quick Setup

```bash
# Clone repository
git clone <repo>
cd RAG4code

# Initial setup
make setup

# Place projects in folder
cp -r /path/to/your/projects ./projects/

# Start system
make run
```

### 3. Access Interfaces

- **Web Interface**: http://localhost:8080
- **API Documentation**: http://localhost:8080/health
- **Logs**: `make logs`
- **Shell**: `make shell`

## 🌐 Web Interface

### 💬 Questions Tab
- Ask natural language questions about your code
- Filter by specific projects
- Adjustable context size
- Real-time processing feedback

### 📁 Index Tab
- Index new projects
- Full project analysis
- Progress tracking
- Error reporting

### 🔄 Update Tab *(NEW)*
- **Incremental updates** - Only process changed files
- **Force update option** - Reprocess all files if needed
- **Change detection** - Smart file modification tracking
- **Detailed statistics** - See exactly what changed

### 📊 Statistics Tab
- Index statistics and metrics
- File type distribution
- Function and class counts
- Storage usage information

### 📂 Projects Tab
- List available projects
- Manage project indexing
- View project status

## 🔄 Incremental Updates

### Why Incremental Updates?
- **⚡ Faster** - Only processes changed files
- **🔧 Efficient** - Saves time on large projects
- **🎯 Smart** - Automatic change detection using file timestamps
- **📊 Transparent** - Clear reporting of what changed

### Usage Examples

#### CLI
```bash
# Incremental update
python code_rag_docker.py update --project myproject

# Force update all files
python code_rag_docker.py update --project myproject --force

# JSON output
python code_rag_docker.py update --project myproject --output json
```

#### Web Interface
1. Go to "🔄 Update" tab
2. Select your project
3. Check "Force update" if needed
4. Click "🔄 Update"

#### API
```bash
curl -X POST http://localhost:8080/api/update \
  -H "Content-Type: application/json" \
  -d '{"project": "myproject", "force_update": false}'
```

## 🔧 GitLab MR Review Integration

### Overview
Automated GitLab merge request reviews using CodeRAG semantic search and AI analysis.

### Features
- **🎨 Review Templates** - Customizable review patterns
- **📊 Batch Processing** - Review multiple MRs efficiently  
- **⚙️ CI/CD Integration** - GitLab pipeline integration
- **🔍 Debug Logging** - Comprehensive tracing and debugging
- **📋 Smart Analysis** - Context-aware code review

### Quick Start

#### 1. Setup GitLab Token
```bash
export GITLAB_TOKEN="your-gitlab-token"
export GITLAB_URL="https://gitlab.example.com"
```

#### 2. Index Your Project
```bash
# First, index your project in CodeRAG
python code_rag_docker.py index --project myproject
```

#### 3. Review a Merge Request
```bash
python gitlab_review.py review \
  --project-id 123 \
  --mr-id 456 \
  --coderag-project myproject
```

#### 4. Advanced Usage with Debug Logging
```bash
# With comprehensive debug logging
python gitlab_review.py review \
  --project-id 123 \
  --mr-id 456 \
  --coderag-project myproject \
  --verbose \
  --debug-file debug.log
```

### Configuration Files

#### Review Templates
Create custom review templates in `gitlab_integration/templates/`:

```yaml
# gitlab_integration/templates/security_review.yaml
name: "Security Review"
description: "Security-focused code review"
analysis_prompts:
  - "Check for security vulnerabilities"
  - "Identify potential SQL injection risks"
  - "Review authentication and authorization"
criteria:
  - security: 0.8
  - performance: 0.6
```

#### CI/CD Integration
Add to your `.gitlab-ci.yml`:

```yaml
code_review:
  stage: review
  script:
    - python gitlab_review.py review --project-id $CI_PROJECT_ID --mr-id $CI_MERGE_REQUEST_IID
  only:
    - merge_requests
```

### Debug and Tracing

#### Comprehensive Debug Logging
```bash
# Enable verbose logging with file output
python gitlab_review.py review \
  --project-id 123 \
  --mr-id 456 \
  --coderag-project myproject \
  --verbose \
  --debug-file gitlab_debug.log
```

#### What Gets Logged
- **🔍 RAG Query Details** - Exact queries sent to CodeRAG
- **📊 RAG Results** - Code chunks and relevance scores
- **🤖 LLM Communication** - Full prompts and responses to/from Ollama
- **⏱️ Performance Metrics** - Timing and token usage
- **🔄 Process Flow** - Step-by-step execution trace

#### Debug Output Example
```
🔍 RAG Query: "analyze authentication logic in user_controller.py"
📊 Found 5 relevant chunks:
   - user_controller.py:45-67 (score: 0.89)
   - auth_service.py:23-45 (score: 0.85)
🤖 LLM Request: 2,450 tokens sent to qwen2.5-coder
⏱️ Processing time: 3.2s
✅ Review completed: 1,200 tokens generated
```

## 🗄️ Vector Database Backends

### ChromaDB (Default)
- **Usage**: Local storage, great for development
- **Advantages**: Simple setup, fast performance
- **Configuration**: `VECTOR_DB_TYPE=chroma`

### OpenSearch
- **Usage**: Remote cluster, enterprise-grade
- **Advantages**: Scalable, hybrid search, production-ready
- **Configuration**: `VECTOR_DB_TYPE=opensearch`

## 📁 Project Structure

```
RAG4code/
├── 🐳 Docker & Deployment
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── entrypoint.sh
│   └── requirements.txt
├── 🤖 Core RAG System
│   ├── code_rag_docker.py       # ChromaDB backend
│   ├── code_rag_opensearch.py   # OpenSearch backend
│   ├── code_rag.py              # Unified interface
│   └── interactive_docker.py    # Interactive mode
├── 🌐 Web Interface
│   └── web_api.py               # Flask web API + UI
├── 🔧 GitLab Integration
│   ├── gitlab_review.py         # Main review script
│   ├── gitlab_integration/
│   │   ├── gitlab_client.py     # GitLab API client
│   │   ├── mr_analyzer.py       # MR analysis logic
│   │   ├── review_generator.py  # AI review generation
│   │   └── templates/           # Review templates
├── 📚 Documentation
│   ├── README.md               # This file
│   ├── USE_GUIDE.md           # Detailed usage guide
│   ├── DEBUG_GUIDE.md         # Debug and troubleshooting
│   └── docs/                  # Additional documentation
├── 🧪 Testing
│   ├── tests/                 # Test suite
│   ├── test_debug_simple.py   # Debug testing
│   └── test_incremental_web.py # Incremental update tests
├── 📊 Project Data
│   └── projects/              # Your code projects (volume)
└── ⚙️ Configuration
    ├── .env.example
    ├── Makefile
    └── requirements_gitlab.txt
```

## 🐳 Usage Modes

### 1. Web Interface (Recommended)

```bash
make run
# Access: http://localhost:8080
```

**Features:**
- 💬 Ask questions about your code
- 📁 Index projects via dropdown  
- 🔄 Incremental updates with progress tracking
- 📊 Real-time statistics
- 📂 Project management

### 2. Command Line Interface

```bash
# Index project
make index PROJECT=myproject

# Incremental update
python code_rag_docker.py update --project myproject

# Ask questions
make ask QUESTION="How does authentication work?"

# View statistics
make stats

# List projects
make projects
```

### 3. Interactive Mode

```bash
# ChromaDB (default)
make interactive

# OpenSearch
VECTOR_DB_TYPE=opensearch make interactive
```

### 4. GitLab MR Reviews

```bash
# Simple review
python gitlab_review.py review --project-id 123 --mr-id 456

# With debugging
python gitlab_review.py review \
  --project-id 123 --mr-id 456 \
  --verbose --debug-file review.log

# Batch review
python gitlab_review.py batch-review \
  --project-id 123 \
  --mr-states opened,ready_for_review
```

## ⚙️ Configuration

### Environment Variables

#### General Configuration
| Variable             | Default                              | Description                     |
| -------------------- | ----------------------------------- | ----------------------------- |
| `VECTOR_DB_TYPE`     | `chroma`                            | Backend: `chroma` or `opensearch` |
| `OLLAMA_HOST`        | `http://host.docker.internal:11434` | Ollama server URL             |
| `EMBEDDING_MODEL`    | `nomic-embed-text`                  | Model for embeddings          |
| `CHAT_MODEL`         | `qwen2.5-coder`                     | Model for chat/responses      |
| `CHUNK_SIZE`         | `1500`                              | Code chunk size               |
| `MAX_CONTEXT_CHUNKS` | `5`                                 | Context chunks for responses  |

#### GitLab Integration
| Variable             | Default                              | Description                     |
| -------------------- | ----------------------------------- | ----------------------------- |
| `GITLAB_TOKEN`       | -                                   | GitLab personal access token  |
| `GITLAB_URL`         | `https://gitlab.com`                | GitLab instance URL           |
| `CODERAG_HOST`       | `http://localhost:8080`             | CodeRAG API endpoint          |

#### ChromaDB Specific
| Variable             | Default                              | Description                     |
| -------------------- | ----------------------------------- | ----------------------------- |
| `COLLECTION_NAME`    | `code_project`                      | ChromaDB collection name      |
| `CHROMA_DB_PATH`     | `/chroma_db`                        | ChromaDB storage path         |

#### OpenSearch Specific
| Variable                 | Default              | Description                         |
| ------------------------ | ------------------- | --------------------------------- |
| `OPENSEARCH_INDEX`       | `code-rag-index`    | OpenSearch index name             |
| `OPENSEARCH_HOST`        | `localhost`         | OpenSearch cluster host           |
| `OPENSEARCH_PORT`        | `9200`              | OpenSearch cluster port           |
| `OPENSEARCH_USER`        | `admin`             | Authentication username           |
| `OPENSEARCH_PASSWORD`    | `admin`             | Authentication password           |

## 🧪 Testing

### Automated Test Suite
```bash
# Run all tests
python -m pytest tests/ -v

# Test incremental updates
python test_incremental_web.py

# Test GitLab integration
python test_debug_simple.py
```

### Manual Testing
```bash
# Test web API
curl http://localhost:8080/health

# Test incremental update
python code_rag_docker.py update --project test-project --output json

# Test GitLab review (with debug)
python gitlab_review.py review --project-id 123 --mr-id 456 --verbose
```

## 🚨 Troubleshooting

### Common Issues

#### "Cannot connect to Ollama"
```bash
# Check if Ollama is running
ollama serve

# Verify models are downloaded
ollama list

# Test connection
curl http://localhost:11434/api/tags
```

#### "No changes detected in incremental update"
```bash
# Check file modification times
ls -la projects/myproject/

# Force update to reprocess all files
python code_rag_docker.py update --project myproject --force
```

#### "GitLab authentication failed"
```bash
# Verify token
echo $GITLAB_TOKEN

# Test GitLab API access
curl -H "Authorization: Bearer $GITLAB_TOKEN" $GITLAB_URL/api/v4/user
```

#### "Debug logs not showing"
```bash
# Enable verbose mode with file output
python gitlab_review.py review \
  --project-id 123 --mr-id 456 \
  --verbose \
  --debug-file debug.log

# Check log file
tail -f debug.log
```

### Performance Optimization

#### For Large Projects
```bash
# Increase timeouts
export REQUEST_TIMEOUT=300

# Larger chunk size
export CHUNK_SIZE=2000

# More context
export MAX_CONTEXT_CHUNKS=10
```

#### For Limited Resources
```bash
# Smaller chunks
export CHUNK_SIZE=800

# Less context
export MAX_CONTEXT_CHUNKS=3

# Specific file patterns
export FILE_PATTERNS="*.py,*.js"
```

## 📊 API Reference

### Core RAG API
- `GET /health` - System health check
- `POST /api/ask` - Ask questions about code
- `POST /api/index` - Index a project
- `POST /api/update` - Incremental project update *(NEW)*
- `GET /api/stats` - Index statistics
- `GET /api/projects` - List projects

### GitLab Integration API
- Review single MR: `gitlab_review.py review`
- Batch review: `gitlab_review.py batch-review`  
- CI/CD integration: See `.gitlab-ci.yml` examples

## 🔐 Security

- ✅ **Non-root execution** - Containers run as non-root user
- ✅ **Read-only project volumes** - Source code mounted read-only
- ✅ **Isolated data storage** - Persistent data in dedicated volumes
- ✅ **Token-based authentication** - Secure GitLab API access
- ✅ **Health checks** - Automated container health monitoring

## 🆕 Recent Updates

### Version 2.1.0
- **🔄 Incremental Updates** - Smart file change detection and processing
- **🌐 Enhanced Web UI** - New Update tab with progress tracking
- **🔍 Comprehensive Debug Logging** - Full RAG and LLM tracing
- **📊 Detailed Statistics** - Enhanced metrics and reporting
- **🧪 Improved Testing** - Comprehensive test suite and validation

### Version 2.0.0
- **🔧 GitLab MR Review Integration** - Complete automated review system
- **🎨 Review Templates** - Customizable review patterns
- **⚙️ CI/CD Integration** - GitLab pipeline support
- **📋 Batch Processing** - Multiple MR review capabilities

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

MIT License - see LICENSE for details.

## 🙏 Acknowledgments

- **Ollama** - Local LLM inference
- **ChromaDB** - Vector database
- **OpenSearch** - Enterprise search
- **GitLab** - DevOps platform
- **Flask** - Web framework