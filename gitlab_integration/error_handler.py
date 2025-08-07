#!/usr/bin/env python3
"""
Enhanced Error Handling and Resilience for GitLab Integration

Provides comprehensive error handling, retry mechanisms, and graceful degradation
for GitLab MR review operations.
"""

import logging
import time
import functools
from typing import Dict, List, Any, Optional, Callable, Type
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class ErrorContext:
    """Context information for error tracking."""
    operation: str
    component: str
    timestamp: str
    attempt: int
    max_attempts: int
    error_type: str
    error_message: str
    recovery_action: Optional[str] = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_exceptions: tuple = (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.HTTPError
    )
    retry_on_status_codes: tuple = (429, 500, 502, 503, 504)
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt."""
        delay = min(
            self.base_delay * (self.exponential_base ** (attempt - 1)),
            self.max_delay
        )
        
        if self.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)  # 50-100% of calculated delay
        
        return delay


class CircuitBreaker:
    """Circuit breaker pattern for failing services."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0, expected_exception: Type[Exception] = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == 'OPEN':
                if self._should_attempt_reset():
                    self.state = 'HALF_OPEN'
                    logger.info(f"🔄 Circuit breaker half-open for {func.__name__}")
                else:
                    raise Exception(f"Circuit breaker OPEN for {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise e
        
        return wrapper
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful operation."""
        self.failure_count = 0
        if self.state == 'HALF_OPEN':
            self.state = 'CLOSED'
            logger.info("✅ Circuit breaker closed - service recovered")
    
    def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(f"🚨 Circuit breaker opened - service failing")


class ResilientHTTPSession:
    """HTTP session with built-in resilience features."""
    
    def __init__(self, retry_config: Optional[RetryConfig] = None):
        self.retry_config = retry_config or RetryConfig()
        self.session = self._create_session()
        self.circuit_breakers = {}
    
    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry strategy."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.retry_config.max_attempts,
            status_forcelist=self.retry_config.retry_on_status_codes,
            backoff_factor=self.retry_config.base_delay,
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for service."""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker()
        return self.circuit_breakers[service_name]
    
    def request_with_resilience(self, service_name: str, method: str, url: str, **kwargs) -> requests.Response:
        """Make HTTP request with resilience features."""
        circuit_breaker = self.get_circuit_breaker(service_name)
        
        @circuit_breaker
        def make_request():
            response = self.session.request(method, url, **kwargs)
            if response.status_code in self.retry_config.retry_on_status_codes:
                response.raise_for_status()
            return response
        
        return make_request()


def retry_with_backoff(config: Optional[RetryConfig] = None):
    """Decorator for retrying operations with exponential backoff."""
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except config.retry_on_exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_attempts:
                        logger.error(f"❌ {func.__name__} failed after {attempt} attempts: {e}")
                        break
                    
                    delay = config.calculate_delay(attempt)
                    logger.warning(f"⚠️ {func.__name__} attempt {attempt} failed: {e}. Retrying in {delay:.2f}s")
                    time.sleep(delay)
                except Exception as e:
                    # Don't retry on unexpected exceptions
                    logger.error(f"❌ {func.__name__} failed with unexpected error: {e}")
                    raise
            
            raise last_exception
        
        return wrapper
    return decorator


class ErrorRecoveryManager:
    """Manages error recovery strategies and fallback mechanisms."""
    
    def __init__(self):
        self.error_history: List[ErrorContext] = []
        self.recovery_strategies: Dict[str, Callable] = {}
        self.fallback_handlers: Dict[str, Callable] = {}
    
    def register_recovery_strategy(self, error_type: str, strategy: Callable):
        """Register recovery strategy for specific error type."""
        self.recovery_strategies[error_type] = strategy
        logger.info(f"📝 Registered recovery strategy for {error_type}")
    
    def register_fallback_handler(self, operation: str, handler: Callable):
        """Register fallback handler for operation."""
        self.fallback_handlers[operation] = handler
        logger.info(f"📝 Registered fallback handler for {operation}")
    
    def handle_error(self, error: Exception, operation: str, component: str, **context) -> Any:
        """Handle error with recovery strategies and fallbacks."""
        error_type = type(error).__name__
        
        # Record error
        error_context = ErrorContext(
            operation=operation,
            component=component,
            timestamp=datetime.now().isoformat(),
            attempt=context.get('attempt', 1),
            max_attempts=context.get('max_attempts', 1),
            error_type=error_type,
            error_message=str(error)
        )
        
        self.error_history.append(error_context)
        
        # Try recovery strategy
        if error_type in self.recovery_strategies:
            try:
                logger.info(f"🔧 Attempting recovery for {error_type}")
                result = self.recovery_strategies[error_type](error, error_context, **context)
                error_context.recovery_action = "recovery_strategy_succeeded"
                return result
            except Exception as recovery_error:
                logger.warning(f"⚠️ Recovery strategy failed: {recovery_error}")
                error_context.recovery_action = "recovery_strategy_failed"
        
        # Try fallback handler
        if operation in self.fallback_handlers:
            try:
                logger.info(f"🔄 Using fallback for {operation}")
                result = self.fallback_handlers[operation](error, error_context, **context)
                error_context.recovery_action = "fallback_succeeded"
                return result
            except Exception as fallback_error:
                logger.warning(f"⚠️ Fallback handler failed: {fallback_error}")
                error_context.recovery_action = "fallback_failed"
        
        # No recovery possible
        error_context.recovery_action = "no_recovery_available"
        logger.error(f"❌ No recovery available for {operation} error: {error}")
        raise error
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics and trends."""
        if not self.error_history:
            return {}
        
        # Calculate statistics
        total_errors = len(self.error_history)
        error_types = {}
        components = {}
        operations = {}
        recovery_actions = {}
        
        for error in self.error_history:
            error_types[error.error_type] = error_types.get(error.error_type, 0) + 1
            components[error.component] = components.get(error.component, 0) + 1
            operations[error.operation] = operations.get(error.operation, 0) + 1
            
            if error.recovery_action:
                recovery_actions[error.recovery_action] = recovery_actions.get(error.recovery_action, 0) + 1
        
        # Recent errors (last hour)
        recent_cutoff = datetime.now() - timedelta(hours=1)
        recent_errors = [
            error for error in self.error_history
            if datetime.fromisoformat(error.timestamp) > recent_cutoff
        ]
        
        return {
            'total_errors': total_errors,
            'recent_errors': len(recent_errors),
            'error_types': error_types,
            'affected_components': components,
            'affected_operations': operations,
            'recovery_actions': recovery_actions,
            'error_rate_last_hour': len(recent_errors)
        }
    
    def cleanup_old_errors(self, max_age_hours: int = 24):
        """Remove old error records to prevent memory bloat."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        old_count = len(self.error_history)
        self.error_history = [
            error for error in self.error_history
            if datetime.fromisoformat(error.timestamp) > cutoff
        ]
        
        removed = old_count - len(self.error_history)
        if removed > 0:
            logger.info(f"🧹 Cleaned up {removed} old error records")


class GracefulDegradation:
    """Manages graceful degradation of features during failures."""
    
    def __init__(self):
        self.feature_status = {}
        self.degradation_modes = {}
    
    def register_feature(self, feature_name: str, health_check: Callable, degraded_handler: Optional[Callable] = None):
        """Register a feature with health check and optional degraded mode."""
        self.feature_status[feature_name] = {
            'healthy': True,
            'health_check': health_check,
            'degraded_handler': degraded_handler,
            'last_check': None,
            'failure_count': 0
        }
    
    def check_feature_health(self, feature_name: str) -> bool:
        """Check health of a specific feature."""
        if feature_name not in self.feature_status:
            return False
        
        feature = self.feature_status[feature_name]
        
        try:
            is_healthy = feature['health_check']()
            feature['healthy'] = is_healthy
            feature['last_check'] = datetime.now().isoformat()
            
            if is_healthy:
                feature['failure_count'] = 0
            else:
                feature['failure_count'] += 1
            
            return is_healthy
            
        except Exception as e:
            logger.warning(f"Health check failed for {feature_name}: {e}")
            feature['healthy'] = False
            feature['failure_count'] += 1
            feature['last_check'] = datetime.now().isoformat()
            return False
    
    def use_feature(self, feature_name: str, operation: Callable, *args, **kwargs):
        """Use feature with graceful degradation."""
        if feature_name not in self.feature_status:
            raise ValueError(f"Feature {feature_name} not registered")
        
        feature = self.feature_status[feature_name]
        
        # Check if feature is healthy
        if not self.check_feature_health(feature_name):
            if feature['degraded_handler']:
                logger.info(f"🔻 Using degraded mode for {feature_name}")
                return feature['degraded_handler'](*args, **kwargs)
            else:
                raise Exception(f"Feature {feature_name} is unavailable and has no degraded mode")
        
        # Use normal feature
        return operation(*args, **kwargs)
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        total_features = len(self.feature_status)
        healthy_features = sum(1 for f in self.feature_status.values() if f['healthy'])
        
        return {
            'overall_health': healthy_features / total_features if total_features > 0 else 1.0,
            'healthy_features': healthy_features,
            'total_features': total_features,
            'feature_status': {
                name: {
                    'healthy': feature['healthy'],
                    'failure_count': feature['failure_count'],
                    'last_check': feature['last_check']
                }
                for name, feature in self.feature_status.items()
            }
        }


# Global error recovery manager instance
error_recovery = ErrorRecoveryManager()

# Global graceful degradation manager
graceful_degradation = GracefulDegradation()


def setup_default_recovery_strategies():
    """Setup default recovery strategies for common errors."""
    
    def gitlab_connection_recovery(error, context, **kwargs):
        """Recovery strategy for GitLab connection errors."""
        logger.info("🔧 Attempting GitLab connection recovery")
        time.sleep(5)  # Wait before retry
        return None  # Will trigger retry
    
    def ollama_connection_recovery(error, context, **kwargs):
        """Recovery strategy for Ollama connection errors."""
        logger.info("🔧 Attempting Ollama connection recovery")
        time.sleep(2)
        return None
    
    def rate_limit_recovery(error, context, **kwargs):
        """Recovery strategy for rate limiting."""
        logger.info("🔧 Handling rate limit - waiting")
        time.sleep(60)  # Wait for rate limit to reset
        return None
    
    # Register strategies
    error_recovery.register_recovery_strategy('ConnectionError', gitlab_connection_recovery)
    error_recovery.register_recovery_strategy('HTTPError', rate_limit_recovery)
    error_recovery.register_recovery_strategy('Timeout', ollama_connection_recovery)
    
    # Register fallback handlers
    def review_generation_fallback(error, context, **kwargs):
        """Fallback for review generation failures."""
        return {
            'summary': 'Review generation unavailable - manual review required',
            'detailed_comments': '',
            'recommendations': '',
            'line_comments': [],
            'overall_assessment': 'UNKNOWN',
            'metadata': {
                'fallback': True,
                'error': str(error),
                'generated_at': datetime.now().isoformat()
            }
        }
    
    error_recovery.register_fallback_handler('review_generation', review_generation_fallback)


# Initialize default strategies
setup_default_recovery_strategies()