# Performance Optimization Guide

Comprehensive guide for optimizing GitLab MR Review Integration performance.

## 📊 Performance Benchmarks

### Current Performance Metrics
- **Single MR Review**: 15-45 seconds (typical)
- **Batch Processing**: 5-15 MRs/minute
- **Large MR (100+ files)**: 60-120 seconds
- **Memory Usage**: 256-512MB peak
- **Concurrent Processing**: 3-5 workers optimal

### Target Performance Goals
- **Single MR**: < 30 seconds (95th percentile)
- **Batch Processing**: > 10 MRs/minute
- **Memory Efficiency**: < 1GB total usage
- **Error Rate**: < 2% under normal conditions

## 🚀 Optimization Strategies

### 1. Parallel Processing

#### Batch Processing Optimization
```python
from gitlab_integration.batch_processor import BatchProcessor

# Optimal configuration for most scenarios
processor = BatchProcessor(gitlab_client, mr_analyzer, review_generator)

summary = processor.process_project_mrs(
    project_path="group/project",
    parallel_workers=3,          # Optimal worker count
    delay_between_reviews=0.5,   # Reduced delay for faster throughput
    max_reviews=20               # Batch size optimization
)
```

#### Worker Count Guidelines
- **Small MRs (< 10 files)**: 3-5 workers
- **Medium MRs (10-50 files)**: 2-3 workers  
- **Large MRs (50+ files)**: 1-2 workers
- **Memory constrained**: Reduce workers

#### Concurrent Processing Example
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def parallel_mr_processing(mr_list):
    """Process multiple MRs concurrently."""
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        tasks = []
        
        for mr in mr_list:
            task = asyncio.get_event_loop().run_in_executor(
                executor, 
                process_single_mr, 
                mr
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return results
```

### 2. Memory Management

#### Efficient Data Handling
```python
class OptimizedMRAnalyzer:
    """Memory-optimized MR analyzer."""
    
    def __init__(self, rag_system, max_file_size_mb=10):
        self.rag_system = rag_system
        self.max_file_size = max_file_size_mb * 1024 * 1024
    
    def analyze_mr_changes(self, mr_data, changes_data):
        """Analyze with memory optimization."""
        
        # Filter large files to prevent memory issues
        filtered_changes = []
        for change in changes_data.get("changes", []):
            diff_size = len(change.get("diff", ""))
            if diff_size < self.max_file_size:
                filtered_changes.append(change)
            else:
                # Log skipped large files
                logger.warning(f"Skipping large file: {change.get('new_path')}")
        
        # Process in chunks for large change sets
        if len(filtered_changes) > 50:
            return self._process_in_chunks(mr_data, filtered_changes)
        else:
            return self._process_all(mr_data, filtered_changes)
```

#### Memory Monitoring
```python
import psutil
import gc

def monitor_memory_usage():
    """Monitor and log memory usage."""
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    
    if memory_mb > 512:  # Alert if using > 512MB
        logger.warning(f"High memory usage: {memory_mb:.1f}MB")
        gc.collect()  # Force garbage collection
    
    return memory_mb
```

### 3. Network Optimization

#### Connection Pooling
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class OptimizedGitLabClient(GitLabClient):
    """GitLab client with connection pooling."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_session_pool()
    
    def _setup_session_pool(self):
        """Configure session with connection pooling."""
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        # Configure adapter with pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,     # Connection pool size
            pool_maxsize=20,        # Max connections per pool
            pool_block=False        # Don't block on pool exhaustion
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
```

#### Request Batching
```python
def batch_api_requests(requests_list, batch_size=5):
    """Batch API requests to reduce overhead."""
    
    results = []
    for i in range(0, len(requests_list), batch_size):
        batch = requests_list[i:i + batch_size]
        
        # Process batch concurrently
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            batch_results = list(executor.map(make_api_request, batch))
        
        results.extend(batch_results)
        
        # Rate limiting compliance
        time.sleep(0.1)
    
    return results
```

### 4. Caching Strategies

#### RAG Query Caching
```python
from functools import lru_cache
import hashlib

class CachedRAGSystem:
    """RAG system with query caching."""
    
    def __init__(self, rag_system, cache_size=1000):
        self.rag_system = rag_system
        self.cache_size = cache_size
    
    @lru_cache(maxsize=1000)
    def cached_query(self, query_hash: str, query: str, project_filter: str = None):
        """Cached RAG query with hash-based key."""
        return self.rag_system.query_codebase(
            query=query,
            project_filter=project_filter
        )
    
    def query_codebase(self, query: str, project_filter: str = None):
        """Query with automatic caching."""
        # Create cache key
        cache_key = f"{query}:{project_filter or 'all'}"
        query_hash = hashlib.md5(cache_key.encode()).hexdigest()
        
        return self.cached_query(query_hash, query, project_filter)
```

#### Template Caching
```python
class CachedReviewGenerator(ReviewGenerator):
    """Review generator with template caching."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._template_cache = {}
    
    def _load_template(self, template_name: str) -> str:
        """Load template with caching."""
        if template_name not in self._template_cache:
            self._template_cache[template_name] = super()._load_template(template_name)
        
        return self._template_cache[template_name]
```

### 5. Algorithm Optimization

#### Efficient Diff Processing
```python
def optimized_diff_analysis(diff_content: str) -> Dict[str, Any]:
    """Optimized diff processing algorithm."""
    
    if not diff_content:
        return {"lines_added": 0, "lines_removed": 0, "modified_lines": []}
    
    lines_added = 0
    lines_removed = 0
    modified_lines = []
    
    # Process line by line efficiently
    for line_number, line in enumerate(diff_content.split('\n'), 1):
        if line.startswith('+') and not line.startswith('+++'):
            lines_added += 1
            if len(line) > 100:  # Only track long lines
                modified_lines.append({
                    "line_number": line_number,
                    "type": "added",
                    "content": line[1:100] + "..." if len(line) > 100 else line[1:]
                })
        elif line.startswith('-') and not line.startswith('---'):
            lines_removed += 1
    
    return {
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "modified_lines": modified_lines
    }
```

#### Smart Context Selection
```python
def smart_context_selection(rag_results: List[Dict], max_contexts: int = 3) -> List[Dict]:
    """Intelligently select most relevant contexts."""
    
    if len(rag_results) <= max_contexts:
        return rag_results
    
    # Score contexts by relevance
    scored_contexts = []
    for context in rag_results:
        score = calculate_context_relevance(context)
        scored_contexts.append((score, context))
    
    # Return top scoring contexts
    scored_contexts.sort(key=lambda x: x[0], reverse=True)
    return [context for score, context in scored_contexts[:max_contexts]]

def calculate_context_relevance(context: Dict) -> float:
    """Calculate context relevance score."""
    score = 0.0
    
    # Function matches boost score
    if context.get("functions"):
        score += 0.3
    
    # Recent changes boost score
    if "recent" in context.get("metadata", {}):
        score += 0.2
    
    # File type relevance
    file_path = context.get("file_path", "")
    if file_path.endswith((".py", ".js", ".ts")):
        score += 0.1
    
    return score
```

## ⚡ Configuration Tuning

### 1. Ollama/LLM Optimization

#### Model Configuration
```python
# Optimized Ollama settings
OLLAMA_CONFIG = {
    "model": "qwen2.5-coder:7b",  # Smaller model for speed
    "options": {
        "temperature": 0.1,        # Lower for consistency
        "top_p": 0.9,             # Focused sampling
        "max_tokens": 1024,       # Reduced for speed
        "num_predict": 1024,      # Match max_tokens
        "num_ctx": 4096,          # Context window
        "repeat_penalty": 1.1,    # Prevent repetition
        "stop": ["```", "\n\n\n"] # Early stopping
    }
}
```

#### Request Optimization
```python
def optimized_llm_call(prompt: str, max_retries: int = 2) -> str:
    """Optimized LLM call with timeout and retries."""
    
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": "qwen2.5-coder:7b",
                    "prompt": prompt[:4000],  # Truncate long prompts
                    "stream": False,
                    "options": OLLAMA_CONFIG["options"]
                },
                timeout=60  # Reduced timeout
            )
            
            response.raise_for_status()
            return response.json().get("response", "")
            
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                logger.warning(f"LLM timeout, retrying ({attempt + 1}/{max_retries})")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
```

### 2. Database/Storage Optimization

#### Elasticsearch/OpenSearch Tuning
```python
# Optimized search settings
SEARCH_CONFIG = {
    "index_settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,    # Reduce for development
        "refresh_interval": "30s",   # Less frequent refresh
        "max_result_window": 1000    # Limit result size
    },
    "search_params": {
        "size": 5,                   # Limit results
        "timeout": "10s",           # Search timeout
        "_source_excludes": ["content_full"]  # Exclude large fields
    }
}
```

### 3. Environment-Specific Tuning

#### Development Environment
```yaml
# .gitlab-review.yml for development
ci:
  enabled: true
  parallel_workers: 1      # Single worker for debugging
  timeout_minutes: 10      # Shorter timeout

rag:
  max_context_chunks: 3    # Fewer chunks for speed
  
review:
  max_tokens: 512          # Shorter reviews
```

#### Production Environment
```yaml
# .gitlab-review.yml for production
ci:
  enabled: true
  parallel_workers: 3      # Multiple workers
  timeout_minutes: 30      # Longer timeout

rag:
  max_context_chunks: 5    # More context for quality

review:
  max_tokens: 2048         # Detailed reviews
```

## 📈 Monitoring and Profiling

### 1. Performance Monitoring

#### Metrics Collection
```python
import time
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class PerformanceMetrics:
    """Performance metrics for monitoring."""
    operation: str
    duration: float
    memory_usage: float
    success: bool
    timestamp: str

class PerformanceMonitor:
    """Monitor performance metrics."""
    
    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
    
    def measure_operation(self, operation_name: str):
        """Decorator for measuring operation performance."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                start_memory = monitor_memory_usage()
                
                try:
                    result = func(*args, **kwargs)
                    success = True
                except Exception as e:
                    success = False
                    raise
                finally:
                    duration = time.time() - start_time
                    end_memory = monitor_memory_usage()
                    
                    metric = PerformanceMetrics(
                        operation=operation_name,
                        duration=duration,
                        memory_usage=end_memory - start_memory,
                        success=success,
                        timestamp=datetime.now().isoformat()
                    )
                    
                    self.metrics.append(metric)
                    self._log_metric(metric)
                
                return result
            return wrapper
        return decorator
    
    def _log_metric(self, metric: PerformanceMetrics):
        """Log performance metric."""
        if metric.duration > 30:  # Slow operation
            logger.warning(f"Slow operation: {metric.operation} took {metric.duration:.2f}s")
        
        if metric.memory_usage > 100:  # High memory usage
            logger.warning(f"High memory usage: {metric.operation} used {metric.memory_usage:.1f}MB")
```

#### Usage Example
```python
monitor = PerformanceMonitor()

@monitor.measure_operation("mr_review")
def review_mr(mr_url: str) -> Dict[str, Any]:
    """Review MR with performance monitoring."""
    # ... review logic ...
    return result
```

### 2. Profiling Tools

#### Python Profiler Integration
```python
import cProfile
import pstats
from contextlib import contextmanager

@contextmanager
def profile_operation(operation_name: str):
    """Context manager for profiling operations."""
    profiler = cProfile.Profile()
    profiler.enable()
    
    try:
        yield
    finally:
        profiler.disable()
        
        # Save profile stats
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        
        # Log top 10 time-consuming functions
        logger.info(f"Profile for {operation_name}:")
        stats.print_stats(10)

# Usage
with profile_operation("batch_processing"):
    batch_processor.process_project_mrs(...)
```

## 🔍 Troubleshooting Performance Issues

### Common Performance Problems

#### 1. Slow LLM Response
**Symptoms:**
- Reviews taking > 60 seconds
- Timeout errors in logs

**Solutions:**
```python
# Reduce model size
OLLAMA_CONFIG["model"] = "qwen2.5-coder:1.5b"  # Smaller model

# Optimize prompt length
def truncate_prompt(prompt: str, max_length: int = 3000) -> str:
    if len(prompt) <= max_length:
        return prompt
    return prompt[:max_length] + "\n\n[... truncated for performance ...]"

# Add request timeout
response = requests.post(url, json=data, timeout=30)
```

#### 2. High Memory Usage
**Symptoms:**
- Memory usage > 1GB
- Out of memory errors

**Solutions:**
```python
# Process files in chunks
def process_large_mr_in_chunks(changes: List[Dict], chunk_size: int = 10):
    results = []
    for i in range(0, len(changes), chunk_size):
        chunk = changes[i:i + chunk_size]
        chunk_result = process_chunk(chunk)
        results.extend(chunk_result)
        
        # Clear memory between chunks
        gc.collect()
    
    return results

# Limit file processing
MAX_FILES_PER_MR = 50
MAX_DIFF_SIZE_MB = 5

def filter_large_changes(changes: List[Dict]) -> List[Dict]:
    filtered = []
    for change in changes[:MAX_FILES_PER_MR]:
        diff_size = len(change.get("diff", ""))
        if diff_size < MAX_DIFF_SIZE_MB * 1024 * 1024:
            filtered.append(change)
    return filtered
```

#### 3. Slow GitLab API Calls
**Symptoms:**
- API timeouts
- Rate limit errors

**Solutions:**
```python
# Implement exponential backoff
def api_call_with_backoff(func, *args, **kwargs):
    for attempt in range(3):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Rate limited
                wait_time = 2 ** attempt
                logger.warning(f"Rate limited, waiting {wait_time}s")
                time.sleep(wait_time)
            else:
                raise
    raise Exception("Max retries exceeded")

# Use connection pooling
session = requests.Session()
adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20)
session.mount("https://", adapter)
```

### Performance Testing

#### Load Testing Script
```python
import concurrent.futures
import time
from typing import List

def performance_test_batch_processing():
    """Performance test for batch processing."""
    
    # Test configuration
    test_mrs = ["project/mr1", "project/mr2", "project/mr3"] * 10
    workers = [1, 2, 3, 5]
    
    results = {}
    
    for worker_count in workers:
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(mock_mr_review, mr) for mr in test_mrs]
            completed = list(concurrent.futures.as_completed(futures))
        
        duration = time.time() - start_time
        throughput = len(test_mrs) / duration
        
        results[worker_count] = {
            "duration": duration,
            "throughput": throughput,
            "mrs_per_minute": throughput * 60
        }
        
        print(f"Workers: {worker_count}, Duration: {duration:.2f}s, "
              f"Throughput: {throughput:.2f} MRs/s")
    
    return results

def mock_mr_review(mr_id: str) -> Dict[str, Any]:
    """Mock MR review for testing."""
    time.sleep(2)  # Simulate processing time
    return {"mr_id": mr_id, "success": True}
```

## 📋 Performance Checklist

### Pre-deployment Checklist
- [ ] **Memory limits configured** (< 1GB total)
- [ ] **Worker count optimized** for target load
- [ ] **Timeouts configured** appropriately
- [ ] **Connection pooling enabled**
- [ ] **Caching implemented** for expensive operations
- [ ] **Large file filtering** in place
- [ ] **Error handling with retries** configured
- [ ] **Monitoring and alerting** set up

### Production Monitoring
- [ ] **Response time metrics** tracked
- [ ] **Memory usage** monitored
- [ ] **Error rates** below 2%
- [ ] **Throughput** meeting targets
- [ ] **Resource utilization** optimized
- [ ] **Cache hit rates** above 80%
- [ ] **API rate limits** respected

### Regular Optimization Tasks
- [ ] **Review performance metrics** weekly
- [ ] **Update model configurations** based on usage
- [ ] **Cleanup old cache entries**
- [ ] **Optimize database queries**
- [ ] **Profile critical operations** monthly
- [ ] **Update dependencies** for performance improvements

---

## 🎯 Performance Goals Summary

| Metric | Current | Target | Optimized |
|--------|---------|--------|-----------|
| Single MR Review | 15-45s | < 30s | 15-25s |
| Batch Processing | 5-15/min | > 10/min | 15-20/min |
| Memory Usage | 256-512MB | < 1GB | 200-400MB |
| Error Rate | < 5% | < 2% | < 1% |
| Cache Hit Rate | N/A | > 80% | > 90% |

Following these optimization guidelines will ensure your GitLab MR Review Integration performs efficiently at scale while maintaining high quality reviews.