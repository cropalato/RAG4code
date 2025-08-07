# GitLab Integration API Reference

Complete API reference for the GitLab MR Review Integration system.

## Table of Contents
- [GitLab Client](#gitlab-client)
- [MR Analyzer](#mr-analyzer)
- [Review Generator](#review-generator)
- [Batch Processor](#batch-processor)
- [CI Integration](#ci-integration)
- [Error Handling](#error-handling)
- [Configuration](#configuration)

## GitLab Client

### Class: `GitLabClient`

GitLab API client for merge request operations.

#### Constructor

```python
GitLabClient(gitlab_url: str, token: Optional[str] = None)
```

**Parameters:**
- `gitlab_url` (str): GitLab instance URL
- `token` (Optional[str]): GitLab access token (can be set via environment)

**Raises:**
- `ValueError`: If token is not provided
- `ConnectionError`: If connection to GitLab fails

#### Methods

##### `get_project(project_path: str) -> Dict[str, Any]`

Retrieve project information.

**Parameters:**
- `project_path` (str): Project path in format "group/project"

**Returns:**
- `Dict[str, Any]`: Project data from GitLab API

**Example:**
```python
client = GitLabClient("https://gitlab.com", "token")
project = client.get_project("group/project")
print(project["name"])
```

##### `get_merge_request(project_path: str, mr_iid: int) -> Dict[str, Any]`

Retrieve merge request information.

**Parameters:**
- `project_path` (str): Project path in format "group/project"
- `mr_iid` (int): Merge request internal ID

**Returns:**
- `Dict[str, Any]`: MR data from GitLab API

##### `get_mr_changes(project_path: str, mr_iid: int) -> Dict[str, Any]`

Retrieve merge request changes and diffs.

**Parameters:**
- `project_path` (str): Project path
- `mr_iid` (int): Merge request internal ID

**Returns:**
- `Dict[str, Any]`: Changes data with file diffs

##### `post_mr_note(project_path: str, mr_iid: int, note_body: str) -> Dict[str, Any]`

Post a note/comment to a merge request.

**Parameters:**
- `project_path` (str): Project path
- `mr_iid` (int): Merge request internal ID
- `note_body` (str): Comment content (supports GitLab Markdown)

**Returns:**
- `Dict[str, Any]`: Created note data

##### `parse_mr_url(mr_url: str) -> Tuple[str, int]`

Parse GitLab MR URL to extract project path and MR ID.

**Parameters:**
- `mr_url` (str): GitLab merge request URL

**Returns:**
- `Tuple[str, int]`: (project_path, mr_iid)

**Raises:**
- `ValueError`: If URL format is invalid

##### `get_project_merge_requests(project_path: str, state: str = "opened", per_page: int = 20) -> List[Dict[str, Any]]`

List merge requests for a project.

**Parameters:**
- `project_path` (str): Project path
- `state` (str): MR state filter ("opened", "closed", "merged", "all")
- `per_page` (int): Number of results per page

**Returns:**
- `List[Dict[str, Any]]`: List of MR data

## MR Analyzer

### Class: `MRAnalyzer`

Analyzes merge request changes and generates context using RAG.

#### Constructor

```python
MRAnalyzer(rag_system: Optional[Any] = None, project_filter: Optional[str] = None)
```

**Parameters:**
- `rag_system` (Optional[Any]): CodeRAG system instance
- `project_filter` (Optional[str]): Filter RAG queries by project

#### Methods

##### `analyze_mr_changes(mr_data: Dict[str, Any], changes_data: Dict[str, Any]) -> Dict[str, Any]`

Perform comprehensive analysis of MR changes.

**Parameters:**
- `mr_data` (Dict[str, Any]): MR metadata from GitLab
- `changes_data` (Dict[str, Any]): Changes and diffs from GitLab

**Returns:**
- `Dict[str, Any]`: Analysis results with structure:
  ```python
  {
      "mr_info": {...},           # MR metadata
      "impact_analysis": {...},   # Impact and complexity analysis
      "file_changes": [...],      # Detailed file change analysis
      "code_changes": {...},      # Code structure changes
      "review_context": [...]     # RAG context for review
  }
  ```

##### `analyze_file_changes(changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]`

Analyze individual file changes.

**Parameters:**
- `changes` (List[Dict[str, Any]]): File changes from GitLab

**Returns:**
- `List[Dict[str, Any]]`: Detailed file analysis

##### `calculate_complexity_score(file_changes: List[Dict[str, Any]], code_changes: Dict[str, Any]) -> int`

Calculate MR complexity score (0-100).

**Parameters:**
- `file_changes` (List[Dict[str, Any]]): File change analysis
- `code_changes` (Dict[str, Any]): Code structure changes

**Returns:**
- `int`: Complexity score from 0 (simple) to 100 (complex)

## Review Generator

### Class: `ReviewGenerator`

Generates intelligent code reviews using LLM and templates.

#### Constructor

```python
ReviewGenerator(rag_system: Optional[Any] = None, ollama_host: Optional[str] = None)
```

**Parameters:**
- `rag_system` (Optional[Any]): CodeRAG system instance
- `ollama_host` (Optional[str]): Ollama server URL (default: "http://host.docker.internal:11434")

#### Methods

##### `generate_review(analysis: Dict[str, Any], review_type: str = "general", auto_detect_language: bool = True) -> Dict[str, Any]`

Generate comprehensive code review.

**Parameters:**
- `analysis` (Dict[str, Any]): MR analysis from MRAnalyzer
- `review_type` (str): Review type ("general", "security", "performance", "python", "javascript")
- `auto_detect_language` (bool): Auto-detect primary language for specialized templates

**Returns:**
- `Dict[str, Any]`: Generated review with structure:
  ```python
  {
      "summary": str,              # Review summary
      "detailed_comments": str,    # Detailed analysis
      "recommendations": str,      # Actionable recommendations
      "line_comments": [...],      # Line-specific comments
      "overall_assessment": str,   # Risk assessment
      "metadata": {...}            # Review metadata
  }
  ```

##### `format_for_gitlab(review: Dict[str, Any]) -> str`

Format review for GitLab posting.

**Parameters:**
- `review` (Dict[str, Any]): Generated review data

**Returns:**
- `str`: GitLab Markdown formatted review

#### Available Review Types

- **general**: Comprehensive code quality review
- **security**: Security-focused analysis with OWASP framework
- **performance**: Performance and optimization review
- **python**: Python-specific best practices
- **javascript**: JavaScript/TypeScript specialized review

## Batch Processor

### Class: `BatchProcessor`

Processes multiple merge requests with parallel support and analytics.

#### Constructor

```python
BatchProcessor(gitlab_client: GitLabClient, mr_analyzer: MRAnalyzer, review_generator: ReviewGenerator)
```

#### Methods

##### `process_project_mrs(project_path: str, review_type: str = "general", mr_state: str = "opened", max_reviews: int = 10, post_reviews: bool = False, parallel_workers: int = 3, delay_between_reviews: float = 1.0, filters: Optional[Dict[str, Any]] = None) -> BatchSummary`

Process multiple MRs for a project.

**Parameters:**
- `project_path` (str): GitLab project path
- `review_type` (str): Type of review to generate
- `mr_state` (str): MR state filter
- `max_reviews` (int): Maximum number of MRs to process
- `post_reviews` (bool): Whether to post reviews to GitLab
- `parallel_workers` (int): Number of parallel processing threads
- `delay_between_reviews` (float): Delay between reviews (seconds)
- `filters` (Optional[Dict[str, Any]]): Additional filters

**Filters Structure:**
```python
filters = {
    "author": str,           # Filter by author username
    "labels": List[str],     # Filter by labels
    "keywords": List[str],   # Filter by title/description keywords
    "created_after": str     # Filter by creation date (ISO format)
}
```

**Returns:**
- `BatchSummary`: Processing summary with statistics

##### `set_progress_callback(callback: Callable[[int, int, str], None])`

Set progress callback for tracking batch processing.

**Parameters:**
- `callback` (Callable): Function that receives (current, total, message)

##### `export_results(output_path: str, format: str = "json")`

Export batch results to file.

**Parameters:**
- `output_path` (str): Output file path
- `format` (str): Export format ("json" or "csv")

##### `get_analytics() -> Dict[str, Any]`

Get detailed analytics from batch processing.

**Returns:**
- `Dict[str, Any]`: Analytics data with performance, quality, and success metrics

### DataClasses

#### `BatchResult`

Result of processing a single MR.

```python
@dataclass
class BatchResult:
    mr_iid: int
    project_path: str
    success: bool
    processing_time: float
    review_type: str
    complexity_score: int = 0
    risk_assessment: str = ""
    error: Optional[str] = None
    review_posted: bool = False
    file_count: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    timestamp: str = ""
```

#### `BatchSummary`

Summary of batch processing session.

```python
@dataclass
class BatchSummary:
    total_mrs: int
    successful_reviews: int
    failed_reviews: int
    total_processing_time: float
    average_processing_time: float
    reviews_posted: int
    start_time: str
    end_time: str
    project_path: str
    review_type: str
    errors: List[str]
    
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
```

## CI Integration

### Class: `GitLabCIIntegration`

GitLab CI/CD integration for automated reviews.

#### Constructor

```python
GitLabCIIntegration(gitlab_client: GitLabClient, mr_analyzer: MRAnalyzer, review_generator: ReviewGenerator)
```

#### Methods

##### `run_ci_review() -> Dict[str, Any]`

Run automated review in CI environment.

**Returns:**
- `Dict[str, Any]`: Review results and CI metadata

**Example Response:**
```python
{
    "success": bool,
    "skipped": bool,
    "reason": str,               # If skipped
    "mr_info": {...},
    "analysis": {...},
    "review": {...},
    "ci_env": {...}
}
```

##### `should_run_review(mr_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]`

Determine if review should run based on CI configuration.

**Parameters:**
- `mr_data` (Optional[Dict[str, Any]]): MR data (fetched if not provided)

**Returns:**
- `Tuple[bool, str]`: (should_run, reason)

##### `generate_ci_config_template() -> str`

Generate GitLab CI configuration template.

**Returns:**
- `str`: YAML configuration for `.gitlab-ci.yml`

##### `generate_project_config_template() -> str`

Generate project configuration template.

**Returns:**
- `str`: YAML configuration for `.gitlab-review.yml`

### Configuration: `CIConfig`

CI/CD configuration dataclass.

```python
@dataclass
class CIConfig:
    enabled: bool = True
    review_type: str = "general"
    auto_post: bool = False
    trigger_on_draft: bool = False
    trigger_on_wip: bool = False
    required_approvals: int = 0
    review_on_labels: List[str] = None
    skip_on_labels: List[str] = None
    parallel_workers: int = 1
    timeout_minutes: int = 30
```

### Environment Variables

CI/CD environment variables for configuration:

- `CI_REVIEW_ENABLED`: Enable/disable CI reviews
- `CI_REVIEW_TYPE`: Review type ("general", "security", "performance")
- `CI_AUTO_POST`: Auto-post reviews to GitLab
- `CI_TRIGGER_ON_DRAFT`: Review draft MRs
- `CI_TRIGGER_ON_WIP`: Review work-in-progress MRs
- `CI_REQUIRED_APPROVALS`: Minimum approvals before review
- `CI_REVIEW_ON_LABELS`: Comma-separated required labels
- `CI_SKIP_ON_LABELS`: Comma-separated skip labels
- `CI_PARALLEL_WORKERS`: Number of parallel workers
- `CI_TIMEOUT_MINUTES`: Review timeout in minutes

## Error Handling

### Classes

#### `ErrorContext`

Error context information for tracking.

```python
@dataclass
class ErrorContext:
    operation: str
    component: str
    timestamp: str
    attempt: int
    max_attempts: int
    error_type: str
    error_message: str
    recovery_action: Optional[str] = None
```

#### `RetryConfig`

Configuration for retry behavior.

```python
@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_exceptions: tuple = (...)
    retry_on_status_codes: tuple = (429, 500, 502, 503, 504)
```

#### `CircuitBreaker`

Circuit breaker pattern for failing services.

```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        """Initialize circuit breaker."""
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator for protecting functions."""
```

#### `ResilientHTTPSession`

HTTP session with built-in resilience features.

```python
class ResilientHTTPSession:
    def __init__(self, retry_config: Optional[RetryConfig] = None):
        """Initialize resilient session."""
    
    def request_with_resilience(self, service_name: str, method: str, url: str, **kwargs) -> requests.Response:
        """Make HTTP request with resilience features."""
```

#### `ErrorRecoveryManager`

Manages error recovery strategies and fallback mechanisms.

```python
class ErrorRecoveryManager:
    def register_recovery_strategy(self, error_type: str, strategy: Callable):
        """Register recovery strategy for specific error type."""
    
    def register_fallback_handler(self, operation: str, handler: Callable):
        """Register fallback handler for operation."""
    
    def handle_error(self, error: Exception, operation: str, component: str, **context) -> Any:
        """Handle error with recovery strategies and fallbacks."""
```

#### `GracefulDegradation`

Manages graceful degradation of features during failures.

```python
class GracefulDegradation:
    def register_feature(self, feature_name: str, health_check: Callable, degraded_handler: Optional[Callable] = None):
        """Register a feature with health check and optional degraded mode."""
    
    def use_feature(self, feature_name: str, operation: Callable, *args, **kwargs):
        """Use feature with graceful degradation."""
```

### Decorators

#### `@retry_with_backoff`

Decorator for retrying operations with exponential backoff.

```python
@retry_with_backoff(config: Optional[RetryConfig] = None)
def my_function():
    """Function that might fail and should be retried."""
    pass
```

### Global Instances

```python
from gitlab_integration.error_handler import error_recovery, graceful_degradation

# Global error recovery manager
error_recovery.register_recovery_strategy("ConnectionError", my_recovery_function)

# Global graceful degradation manager
graceful_degradation.register_feature("my_feature", health_check, degraded_handler)
```

## Configuration

### Settings Module

Configuration management for the GitLab integration.

```python
from gitlab_integration.config.settings import GitLabSettings, RAGSettings, ReviewSettings

# Load settings
gitlab_settings = GitLabSettings.from_env()
rag_settings = RAGSettings.from_env()
review_settings = ReviewSettings.from_env()
```

### Environment Variables

#### GitLab Configuration
- `GITLAB_URL`: GitLab instance URL
- `GITLAB_TOKEN`: GitLab access token
- `GITLAB_API_VERSION`: API version (default: "v4")

#### RAG Configuration
- `OLLAMA_HOST`: Ollama server URL
- `RAG_CHAT_MODEL`: Chat model name
- `RAG_EMBEDDING_MODEL`: Embedding model name
- `RAG_MAX_CONTEXT_CHUNKS`: Maximum context chunks

#### Review Configuration
- `REVIEW_TEMPLATES_DIR`: Custom templates directory
- `REVIEW_DEFAULT_TYPE`: Default review type
- `REVIEW_MAX_TOKENS`: Maximum LLM tokens

### Configuration Files

#### `.gitlab-review.yml`

Project-specific configuration file:

```yaml
ci:
  enabled: true
  review_type: "general"
  auto_post: true
  trigger_on_draft: false
  skip_on_labels:
    - "skip-review"
    - "wip"

gitlab:
  url: "https://gitlab.com"

rag:
  ollama_host: "http://localhost:11434"
  chat_model: "qwen2.5-coder"
  embedding_model: "nomic-embed-text"
  max_context_chunks: 5

review:
  templates_dir: "gitlab_integration/templates"
  custom_templates: {}

notifications:
  slack_webhook: ""
  email_recipients: []

quality:
  max_complexity_score: 75
  required_test_coverage: 80
  block_on_security_issues: true
```

## Error Codes

### GitLab API Errors
- `401`: Authentication failed
- `403`: Insufficient permissions
- `404`: Resource not found
- `429`: Rate limit exceeded
- `500`: Server error

### Application Errors
- `CONFIG_ERROR`: Configuration invalid
- `CONNECTION_ERROR`: Network connection failed
- `ANALYSIS_ERROR`: MR analysis failed
- `REVIEW_ERROR`: Review generation failed
- `POST_ERROR`: Review posting failed

## Rate Limiting

### GitLab API Limits
- **Authenticated requests**: 2000/minute
- **Unauthenticated requests**: 20/minute
- **CI/CD pipelines**: Higher limits available

### Rate Limiting Handling
- Automatic retry with exponential backoff
- Rate limit header monitoring
- Graceful degradation when limits exceeded

## Performance Guidelines

### Optimization Tips
1. **Use parallel processing** for batch operations
2. **Configure appropriate timeouts** based on MR size
3. **Implement caching** for repeated operations
4. **Monitor memory usage** with large MRs

### Resource Usage
- **Memory**: ~100MB base + ~1MB per file analyzed
- **CPU**: Moderate usage during LLM generation
- **Network**: ~1MB per MR (varies with diff size)

### Scaling Recommendations
- **Single instance**: Up to 50 MRs/hour
- **Multiple workers**: Linear scaling with worker count
- **Large deployments**: Consider load balancing

---

For more detailed examples and usage patterns, see the main documentation and examples directory.