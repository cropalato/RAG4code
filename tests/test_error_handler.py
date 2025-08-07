#!/usr/bin/env python3
"""
Tests for Error Handler.
"""

import pytest
import time
import requests
from unittest.mock import Mock, patch
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitlab_integration.error_handler import (
    ErrorContext, RetryConfig, CircuitBreaker, ResilientHTTPSession,
    ErrorRecoveryManager, GracefulDegradation, error_recovery, graceful_degradation
)


class TestErrorContext:
    """Test cases for ErrorContext dataclass."""
    
    def test_error_context_creation(self):
        """Test ErrorContext creation."""
        context = ErrorContext(
            operation="test_operation",
            component="test_component",
            timestamp="2023-01-01T00:00:00",
            attempt=1,
            max_attempts=3,
            error_type="ConnectionError",
            error_message="Connection failed"
        )
        
        assert context.operation == "test_operation"
        assert context.component == "test_component"
        assert context.timestamp == "2023-01-01T00:00:00"
        assert context.attempt == 1
        assert context.max_attempts == 3
        assert context.error_type == "ConnectionError"
        assert context.error_message == "Connection failed"
        assert context.recovery_action is None
    
    def test_error_context_auto_timestamp(self):
        """Test ErrorContext with auto-generated timestamp."""
        context = ErrorContext(
            operation="test",
            component="test",
            timestamp="",
            attempt=1,
            max_attempts=1,
            error_type="Error",
            error_message="Test"
        )
        
        # Should have auto-generated timestamp
        assert context.timestamp
        assert "T" in context.timestamp  # ISO format


class TestRetryConfig:
    """Test cases for RetryConfig dataclass."""
    
    def test_retry_config_defaults(self):
        """Test RetryConfig with default values."""
        config = RetryConfig()
        
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert requests.exceptions.ConnectionError in config.retry_on_exceptions
        assert 429 in config.retry_on_status_codes
    
    def test_calculate_delay_no_jitter(self):
        """Test delay calculation without jitter."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, max_delay=10.0, jitter=False)
        
        assert config.calculate_delay(1) == 1.0  # 1.0 * 2^0
        assert config.calculate_delay(2) == 2.0  # 1.0 * 2^1
        assert config.calculate_delay(3) == 4.0  # 1.0 * 2^2
        assert config.calculate_delay(5) == 10.0  # Capped at max_delay
    
    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with jitter."""
        config = RetryConfig(base_delay=2.0, exponential_base=2.0, jitter=True)
        
        delay1 = config.calculate_delay(2)  # Should be around 2.0 * 2^1 = 4.0, with jitter
        delay2 = config.calculate_delay(2)  # Should be different due to jitter
        
        # Both should be between 2.0 and 4.0 (50-100% of calculated delay)
        assert 2.0 <= delay1 <= 4.0
        assert 2.0 <= delay2 <= 4.0


class TestCircuitBreaker:
    """Test cases for CircuitBreaker."""
    
    def test_circuit_breaker_initialization(self):
        """Test CircuitBreaker initialization."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        
        assert breaker.failure_threshold == 3
        assert breaker.recovery_timeout == 30.0
        assert breaker.failure_count == 0
        assert breaker.state == "CLOSED"
        assert breaker.last_failure_time is None
    
    def test_circuit_breaker_success(self):
        """Test circuit breaker with successful calls."""
        breaker = CircuitBreaker(failure_threshold=2)
        
        @breaker
        def test_function():
            return "success"
        
        result = test_function()
        assert result == "success"
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0
    
    def test_circuit_breaker_failure_and_open(self):
        """Test circuit breaker opening after failures."""
        breaker = CircuitBreaker(failure_threshold=2, expected_exception=ValueError)
        
        @breaker
        def failing_function():
            raise ValueError("Test error")
        
        # First failure
        with pytest.raises(ValueError):
            failing_function()
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 1
        
        # Second failure - should open circuit
        with pytest.raises(ValueError):
            failing_function()
        assert breaker.state == "OPEN"
        assert breaker.failure_count == 2
        
        # Third call should fail immediately due to open circuit
        with pytest.raises(Exception, match="Circuit breaker OPEN"):
            failing_function()
    
    def test_circuit_breaker_half_open_and_recovery(self):
        """Test circuit breaker half-open state and recovery."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1, expected_exception=ValueError)
        
        @breaker
        def test_function(should_fail=True):
            if should_fail:
                raise ValueError("Test error")
            return "success"
        
        # Trigger failure to open circuit
        with pytest.raises(ValueError):
            test_function()
        assert breaker.state == "OPEN"
        
        # Wait for recovery timeout
        time.sleep(0.2)
        
        # Next call should succeed and close circuit
        result = test_function(should_fail=False)
        assert result == "success"
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0


class TestResilientHTTPSession:
    """Test cases for ResilientHTTPSession."""
    
    def test_session_initialization(self):
        """Test session initialization."""
        session = ResilientHTTPSession()
        
        assert session.retry_config is not None
        assert session.session is not None
        assert session.circuit_breakers == {}
    
    def test_get_circuit_breaker(self):
        """Test circuit breaker creation and retrieval."""
        session = ResilientHTTPSession()
        
        breaker1 = session.get_circuit_breaker("service1")
        breaker2 = session.get_circuit_breaker("service1")  # Same service
        breaker3 = session.get_circuit_breaker("service2")  # Different service
        
        assert breaker1 is breaker2  # Same instance
        assert breaker1 is not breaker3  # Different instances
        assert len(session.circuit_breakers) == 2
    
    @patch('requests.Session.request')
    def test_request_with_resilience_success(self, mock_request):
        """Test successful resilient request."""
        session = ResilientHTTPSession()
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        result = session.request_with_resilience("test_service", "GET", "http://test.com")
        
        assert result == mock_response
        mock_request.assert_called_once()
    
    @patch('requests.Session.request')
    def test_request_with_resilience_failure(self, mock_request):
        """Test resilient request with failure."""
        session = ResilientHTTPSession()
        
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Server error")
        mock_request.return_value = mock_response
        
        with pytest.raises(requests.exceptions.HTTPError):
            session.request_with_resilience("test_service", "GET", "http://test.com")


class TestErrorRecoveryManager:
    """Test cases for ErrorRecoveryManager."""
    
    def test_initialization(self):
        """Test manager initialization."""
        manager = ErrorRecoveryManager()
        
        assert manager.error_history == []
        assert manager.recovery_strategies == {}
        assert manager.fallback_handlers == {}
    
    def test_register_recovery_strategy(self):
        """Test recovery strategy registration."""
        manager = ErrorRecoveryManager()
        
        def test_strategy(error, context, **kwargs):
            return "recovered"
        
        manager.register_recovery_strategy("ConnectionError", test_strategy)
        
        assert "ConnectionError" in manager.recovery_strategies
        assert manager.recovery_strategies["ConnectionError"] == test_strategy
    
    def test_register_fallback_handler(self):
        """Test fallback handler registration."""
        manager = ErrorRecoveryManager()
        
        def test_fallback(error, context, **kwargs):
            return "fallback_result"
        
        manager.register_fallback_handler("test_operation", test_fallback)
        
        assert "test_operation" in manager.fallback_handlers
        assert manager.fallback_handlers["test_operation"] == test_fallback
    
    def test_handle_error_with_recovery_strategy(self):
        """Test error handling with successful recovery strategy."""
        manager = ErrorRecoveryManager()
        
        def recovery_strategy(error, context, **kwargs):
            return "recovered_value"
        
        manager.register_recovery_strategy("ValueError", recovery_strategy)
        
        error = ValueError("Test error")
        result = manager.handle_error(error, "test_operation", "test_component")
        
        assert result == "recovered_value"
        assert len(manager.error_history) == 1
        assert manager.error_history[0].recovery_action == "recovery_strategy_succeeded"
    
    def test_handle_error_with_fallback(self):
        """Test error handling with fallback when recovery fails."""
        manager = ErrorRecoveryManager()
        
        def failing_recovery(error, context, **kwargs):
            raise Exception("Recovery failed")
        
        def fallback_handler(error, context, **kwargs):
            return "fallback_value"
        
        manager.register_recovery_strategy("ValueError", failing_recovery)
        manager.register_fallback_handler("test_operation", fallback_handler)
        
        error = ValueError("Test error")
        result = manager.handle_error(error, "test_operation", "test_component")
        
        assert result == "fallback_value"
        assert manager.error_history[0].recovery_action == "fallback_succeeded"
    
    def test_handle_error_no_recovery(self):
        """Test error handling when no recovery is available."""
        manager = ErrorRecoveryManager()
        
        error = ValueError("Test error")
        
        with pytest.raises(ValueError):
            manager.handle_error(error, "test_operation", "test_component")
        
        assert len(manager.error_history) == 1
        assert manager.error_history[0].recovery_action == "no_recovery_available"
    
    def test_get_error_statistics(self):
        """Test error statistics generation."""
        manager = ErrorRecoveryManager()
        
        # Add some error history
        error1 = ValueError("Error 1")
        error2 = ConnectionError("Error 2")
        
        try:
            manager.handle_error(error1, "op1", "comp1")
        except:
            pass
        
        try:
            manager.handle_error(error2, "op2", "comp2")
        except:
            pass
        
        stats = manager.get_error_statistics()
        
        assert stats["total_errors"] == 2
        assert "ValueError" in stats["error_types"]
        assert "ConnectionError" in stats["error_types"]
        assert "comp1" in stats["affected_components"]
        assert "comp2" in stats["affected_components"]
        assert "op1" in stats["affected_operations"]
        assert "op2" in stats["affected_operations"]
    
    def test_cleanup_old_errors(self):
        """Test cleanup of old error records."""
        manager = ErrorRecoveryManager()
        
        # Create old error context
        old_time = (datetime.now() - timedelta(hours=25)).isoformat()
        old_context = ErrorContext(
            operation="old_op",
            component="old_comp",
            timestamp=old_time,
            attempt=1,
            max_attempts=1,
            error_type="Error",
            error_message="Old error"
        )
        
        # Create recent error context
        recent_time = datetime.now().isoformat()
        recent_context = ErrorContext(
            operation="recent_op",
            component="recent_comp", 
            timestamp=recent_time,
            attempt=1,
            max_attempts=1,
            error_type="Error",
            error_message="Recent error"
        )
        
        manager.error_history = [old_context, recent_context]
        
        manager.cleanup_old_errors(max_age_hours=24)
        
        # Only recent error should remain
        assert len(manager.error_history) == 1
        assert manager.error_history[0].operation == "recent_op"


class TestGracefulDegradation:
    """Test cases for GracefulDegradation."""
    
    def test_initialization(self):
        """Test graceful degradation initialization."""
        degradation = GracefulDegradation()
        
        assert degradation.feature_status == {}
        assert degradation.degradation_modes == {}
    
    def test_register_feature(self):
        """Test feature registration."""
        degradation = GracefulDegradation()
        
        def health_check():
            return True
        
        def degraded_handler():
            return "degraded_result"
        
        degradation.register_feature("test_feature", health_check, degraded_handler)
        
        assert "test_feature" in degradation.feature_status
        feature = degradation.feature_status["test_feature"]
        assert feature["healthy"] is True
        assert feature["health_check"] == health_check
        assert feature["degraded_handler"] == degraded_handler
        assert feature["failure_count"] == 0
    
    def test_check_feature_health_success(self):
        """Test successful health check."""
        degradation = GracefulDegradation()
        
        def health_check():
            return True
        
        degradation.register_feature("test_feature", health_check)
        
        is_healthy = degradation.check_feature_health("test_feature")
        
        assert is_healthy is True
        assert degradation.feature_status["test_feature"]["healthy"] is True
        assert degradation.feature_status["test_feature"]["failure_count"] == 0
    
    def test_check_feature_health_failure(self):
        """Test failed health check."""
        degradation = GracefulDegradation()
        
        def health_check():
            return False
        
        degradation.register_feature("test_feature", health_check)
        
        is_healthy = degradation.check_feature_health("test_feature")
        
        assert is_healthy is False
        assert degradation.feature_status["test_feature"]["healthy"] is False
        assert degradation.feature_status["test_feature"]["failure_count"] == 1
    
    def test_check_feature_health_exception(self):
        """Test health check with exception."""
        degradation = GracefulDegradation()
        
        def health_check():
            raise Exception("Health check failed")
        
        degradation.register_feature("test_feature", health_check)
        
        is_healthy = degradation.check_feature_health("test_feature")
        
        assert is_healthy is False
        assert degradation.feature_status["test_feature"]["healthy"] is False
        assert degradation.feature_status["test_feature"]["failure_count"] == 1
    
    def test_use_feature_healthy(self):
        """Test using feature when healthy."""
        degradation = GracefulDegradation()
        
        def health_check():
            return True
        
        def normal_operation():
            return "normal_result"
        
        degradation.register_feature("test_feature", health_check)
        
        result = degradation.use_feature("test_feature", normal_operation)
        
        assert result == "normal_result"
    
    def test_use_feature_degraded(self):
        """Test using feature in degraded mode."""
        degradation = GracefulDegradation()
        
        def health_check():
            return False
        
        def normal_operation():
            return "normal_result"
        
        def degraded_handler():
            return "degraded_result"
        
        degradation.register_feature("test_feature", health_check, degraded_handler)
        
        result = degradation.use_feature("test_feature", normal_operation)
        
        assert result == "degraded_result"
    
    def test_use_feature_unavailable(self):
        """Test using feature when unavailable and no degraded mode."""
        degradation = GracefulDegradation()
        
        def health_check():
            return False
        
        def normal_operation():
            return "normal_result"
        
        degradation.register_feature("test_feature", health_check)
        
        with pytest.raises(Exception, match="unavailable and has no degraded mode"):
            degradation.use_feature("test_feature", normal_operation)
    
    def test_get_system_health(self):
        """Test system health reporting."""
        degradation = GracefulDegradation()
        
        # Register multiple features
        degradation.register_feature("feature1", lambda: True)
        degradation.register_feature("feature2", lambda: False)
        degradation.register_feature("feature3", lambda: True)
        
        # Check health for all features
        degradation.check_feature_health("feature1")
        degradation.check_feature_health("feature2")
        degradation.check_feature_health("feature3")
        
        health = degradation.get_system_health()
        
        assert health["overall_health"] == 2/3  # 2 out of 3 healthy
        assert health["healthy_features"] == 2
        assert health["total_features"] == 3
        assert "feature1" in health["feature_status"]
        assert health["feature_status"]["feature1"]["healthy"] is True
        assert health["feature_status"]["feature2"]["healthy"] is False


class TestGlobalInstances:
    """Test cases for global instances."""
    
    def test_global_error_recovery_instance(self):
        """Test global error recovery manager instance."""
        assert error_recovery is not None
        assert isinstance(error_recovery, ErrorRecoveryManager)
    
    def test_global_graceful_degradation_instance(self):
        """Test global graceful degradation instance."""
        assert graceful_degradation is not None
        assert isinstance(graceful_degradation, GracefulDegradation)


class TestRetryDecorator:
    """Test cases for retry decorator."""
    
    def test_retry_decorator_success(self):
        """Test retry decorator with successful function."""
        from gitlab_integration.error_handler import retry_with_backoff
        
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_attempts=3))
        def test_function():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = test_function()
        
        assert result == "success"
        assert call_count == 1
    
    def test_retry_decorator_eventual_success(self):
        """Test retry decorator with eventual success."""
        from gitlab_integration.error_handler import retry_with_backoff
        
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_attempts=3, base_delay=0.01))
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests.exceptions.ConnectionError("Connection failed")
            return "success"
        
        result = test_function()
        
        assert result == "success"
        assert call_count == 3
    
    def test_retry_decorator_max_attempts_reached(self):
        """Test retry decorator when max attempts are reached."""
        from gitlab_integration.error_handler import retry_with_backoff
        
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_attempts=2, base_delay=0.01))
        def test_function():
            nonlocal call_count
            call_count += 1
            raise requests.exceptions.ConnectionError("Connection failed")
        
        with pytest.raises(requests.exceptions.ConnectionError):
            test_function()
        
        assert call_count == 2
    
    def test_retry_decorator_unexpected_exception(self):
        """Test retry decorator with unexpected exception."""
        from gitlab_integration.error_handler import retry_with_backoff
        
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_attempts=3))
        def test_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Unexpected error")  # Not in retry_on_exceptions
        
        with pytest.raises(ValueError):
            test_function()
        
        assert call_count == 1  # Should not retry


if __name__ == '__main__':
    pytest.main([__file__])