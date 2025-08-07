#!/usr/bin/env python3
"""
Tests for Batch Processor.
"""

import pytest
import time
from unittest.mock import Mock, patch, call
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitlab_integration.batch_processor import BatchProcessor, BatchResult, BatchSummary


class TestBatchResult:
    """Test cases for BatchResult dataclass."""
    
    def test_batch_result_creation(self):
        """Test BatchResult creation."""
        result = BatchResult(
            mr_iid=123,
            project_path="group/project",
            success=True,
            processing_time=1.5,
            review_type="general",
            complexity_score=45,
            risk_assessment="MEDIUM_RISK"
        )
        
        assert result.mr_iid == 123
        assert result.project_path == "group/project"
        assert result.success is True
        assert result.processing_time == 1.5
        assert result.review_type == "general"
        assert result.complexity_score == 45
        assert result.risk_assessment == "MEDIUM_RISK"
        assert result.timestamp  # Should be auto-generated
    
    def test_batch_result_defaults(self):
        """Test BatchResult with default values."""
        result = BatchResult(
            mr_iid=123,
            project_path="group/project",
            success=True,
            processing_time=1.0,
            review_type="general"
        )
        
        assert result.complexity_score == 0
        assert result.risk_assessment == ""
        assert result.error is None
        assert result.review_posted is False


class TestBatchSummary:
    """Test cases for BatchSummary dataclass."""
    
    def test_batch_summary_success_rate(self):
        """Test success rate calculation."""
        summary = BatchSummary(
            total_mrs=10,
            successful_reviews=8,
            failed_reviews=2,
            total_processing_time=50.0,
            average_processing_time=5.0,
            reviews_posted=6,
            start_time="2023-01-01T00:00:00",
            end_time="2023-01-01T01:00:00",
            project_path="group/project",
            review_type="general",
            errors=[]
        )
        
        assert summary.success_rate() == 80.0
    
    def test_batch_summary_success_rate_zero_mrs(self):
        """Test success rate with zero MRs."""
        summary = BatchSummary(
            total_mrs=0,
            successful_reviews=0,
            failed_reviews=0,
            total_processing_time=0.0,
            average_processing_time=0.0,
            reviews_posted=0,
            start_time="2023-01-01T00:00:00",
            end_time="2023-01-01T00:00:00",
            project_path="group/project",
            review_type="general",
            errors=[]
        )
        
        assert summary.success_rate() == 0.0


class TestBatchProcessor:
    """Test cases for Batch Processor."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.mock_gitlab_client = Mock()
        self.mock_mr_analyzer = Mock()
        self.mock_review_generator = Mock()
        
        self.processor = BatchProcessor(
            self.mock_gitlab_client,
            self.mock_mr_analyzer,
            self.mock_review_generator
        )
        
        # Mock MR data
        self.mock_mrs = [
            {
                "iid": 1,
                "title": "MR 1",
                "state": "opened",
                "author": {"username": "user1"},
                "labels": [{"name": "enhancement"}]
            },
            {
                "iid": 2,
                "title": "MR 2",
                "state": "opened",
                "author": {"username": "user2"},
                "labels": [{"name": "bugfix"}]
            }
        ]
        
        # Mock analysis result
        self.mock_analysis = {
            "impact_analysis": {
                "complexity_score": 45,
                "files_count": 3,
                "lines_added": 20,
                "lines_removed": 5
            }
        }
        
        # Mock review result
        self.mock_review = {
            "summary": "Test review",
            "overall_assessment": "MEDIUM_RISK"
        }
    
    def test_initialization(self):
        """Test processor initialization."""
        assert self.processor.gitlab_client == self.mock_gitlab_client
        assert self.processor.mr_analyzer == self.mock_mr_analyzer
        assert self.processor.review_generator == self.mock_review_generator
        assert self.processor.progress_callback is None
        assert self.processor.results == []
    
    def test_set_progress_callback(self):
        """Test setting progress callback."""
        callback = Mock()
        self.processor.set_progress_callback(callback)
        
        assert self.processor.progress_callback == callback
    
    def test_apply_filters_author(self):
        """Test filtering by author."""
        filters = {"author": "user1"}
        
        result = self.processor._apply_filters(self.mock_mrs, filters)
        
        assert len(result) == 1
        assert result[0]["iid"] == 1
    
    def test_apply_filters_labels(self):
        """Test filtering by labels."""
        filters = {"labels": ["enhancement"]}
        
        result = self.processor._apply_filters(self.mock_mrs, filters)
        
        assert len(result) == 1
        assert result[0]["iid"] == 1
    
    def test_apply_filters_keywords(self):
        """Test filtering by keywords."""
        filters = {"keywords": ["MR 2"]}
        
        result = self.processor._apply_filters(self.mock_mrs, filters)
        
        assert len(result) == 1
        assert result[0]["iid"] == 2
    
    def test_apply_filters_multiple(self):
        """Test filtering with multiple criteria."""
        filters = {
            "author": "user1",
            "labels": ["enhancement"]
        }
        
        result = self.processor._apply_filters(self.mock_mrs, filters)
        
        assert len(result) == 1
        assert result[0]["iid"] == 1
    
    def test_process_single_mr_success(self):
        """Test successful single MR processing."""
        mr = self.mock_mrs[0]
        
        # Setup mocks
        self.mock_gitlab_client.get_mr_changes.return_value = {"changes": []}
        self.mock_mr_analyzer.analyze_mr_changes.return_value = self.mock_analysis
        self.mock_review_generator.generate_review.return_value = self.mock_review
        
        result = self.processor._process_single_mr(mr, "general", False)
        
        assert result.success is True
        assert result.mr_iid == 1
        assert result.review_type == "general"
        assert result.complexity_score == 45
        assert result.risk_assessment == "MEDIUM_RISK"
        assert result.review_posted is False
    
    def test_process_single_mr_with_posting(self):
        """Test single MR processing with review posting."""
        mr = self.mock_mrs[0]
        
        # Setup mocks
        self.mock_gitlab_client.get_mr_changes.return_value = {"changes": []}
        self.mock_mr_analyzer.analyze_mr_changes.return_value = self.mock_analysis
        self.mock_review_generator.generate_review.return_value = self.mock_review
        self.mock_review_generator.format_for_gitlab.return_value = "Formatted review"
        self.mock_gitlab_client.post_mr_note.return_value = {"id": 123}
        
        result = self.processor._process_single_mr(mr, "general", True)
        
        assert result.success is True
        assert result.review_posted is True
        
        # Verify posting was called
        self.mock_gitlab_client.post_mr_note.assert_called_once()
    
    def test_process_single_mr_failure(self):
        """Test single MR processing failure."""
        mr = self.mock_mrs[0]
        
        # Setup mock to raise exception
        self.mock_gitlab_client.get_mr_changes.side_effect = Exception("API Error")
        
        result = self.processor._process_single_mr(mr, "general", False)
        
        assert result.success is False
        assert result.error == "API Error"
        assert result.mr_iid == 1
    
    def test_get_mrs_to_process_success(self):
        """Test successful MR retrieval."""
        self.mock_gitlab_client.get_project_merge_requests.return_value = self.mock_mrs
        
        result = self.processor._get_mrs_to_process("group/project", "opened", 5, None)
        
        assert len(result) == 2
        assert result[0]["iid"] == 1
        assert result[1]["iid"] == 2
    
    def test_get_mrs_to_process_with_filters(self):
        """Test MR retrieval with filters."""
        self.mock_gitlab_client.get_project_merge_requests.return_value = self.mock_mrs
        filters = {"author": "user1"}
        
        result = self.processor._get_mrs_to_process("group/project", "opened", 5, filters)
        
        assert len(result) == 1
        assert result[0]["iid"] == 1
    
    def test_get_mrs_to_process_failure(self):
        """Test MR retrieval failure."""
        self.mock_gitlab_client.get_project_merge_requests.side_effect = Exception("API Error")
        
        result = self.processor._get_mrs_to_process("group/project", "opened", 5, None)
        
        assert result == []
    
    def test_update_progress(self):
        """Test progress update."""
        callback = Mock()
        self.processor.set_progress_callback(callback)
        
        self.processor._update_progress(1, 5, "Processing...")
        
        callback.assert_called_once_with(1, 5, "Processing...")
    
    def test_update_progress_no_callback(self):
        """Test progress update without callback."""
        # Should not raise exception
        self.processor._update_progress(1, 5, "Processing...")
    
    def test_process_sequential(self):
        """Test sequential processing."""
        self.processor.results = []
        
        # Setup mocks
        self.mock_gitlab_client.get_mr_changes.return_value = {"changes": []}
        self.mock_mr_analyzer.analyze_mr_changes.return_value = self.mock_analysis
        self.mock_review_generator.generate_review.return_value = self.mock_review
        
        with patch.object(self.processor, '_update_progress') as mock_progress:
            self.processor._process_sequential(self.mock_mrs, "general", False, 0)
        
        assert len(self.processor.results) == 2
        assert all(r.success for r in self.processor.results)
        
        # Check progress calls
        assert mock_progress.call_count >= 2
    
    @patch('time.sleep')
    def test_process_sequential_with_delay(self, mock_sleep):
        """Test sequential processing with delay."""
        self.processor.results = []
        
        # Setup mocks
        self.mock_gitlab_client.get_mr_changes.return_value = {"changes": []}
        self.mock_mr_analyzer.analyze_mr_changes.return_value = self.mock_analysis
        self.mock_review_generator.generate_review.return_value = self.mock_review
        
        self.processor._process_sequential(self.mock_mrs, "general", False, 1.0)
        
        # Should sleep between MRs (but not after the last one)
        mock_sleep.assert_called_once_with(1.0)
    
    def test_create_empty_summary(self):
        """Test empty summary creation."""
        start_time = "2023-01-01T00:00:00"
        
        summary = self.processor._create_empty_summary("group/project", "general", start_time)
        
        assert summary.total_mrs == 0
        assert summary.successful_reviews == 0
        assert summary.failed_reviews == 0
        assert summary.project_path == "group/project"
        assert summary.review_type == "general"
        assert summary.start_time == start_time
    
    @patch('time.time')
    @patch.object(BatchProcessor, '_log_summary')
    def test_process_project_mrs_success(self, mock_log, mock_time):
        """Test successful project MR processing."""
        # Setup time mock
        mock_time.side_effect = [1000.0, 1010.0]  # Start and end times
        
        # Setup mocks
        self.mock_gitlab_client.get_project_merge_requests.return_value = self.mock_mrs
        self.mock_gitlab_client.get_mr_changes.return_value = {"changes": []}
        self.mock_mr_analyzer.analyze_mr_changes.return_value = self.mock_analysis
        self.mock_review_generator.generate_review.return_value = self.mock_review
        
        summary = self.processor.process_project_mrs(
            project_path="group/project",
            review_type="general",
            max_reviews=5,
            parallel_workers=1
        )
        
        assert summary.total_mrs == 2
        assert summary.successful_reviews == 2
        assert summary.failed_reviews == 0
        assert summary.total_processing_time == 10.0
        assert summary.project_path == "group/project"
        assert summary.review_type == "general"
        
        # Verify summary was logged
        mock_log.assert_called_once()
    
    def test_process_project_mrs_no_mrs_found(self):
        """Test processing when no MRs are found."""
        self.mock_gitlab_client.get_project_merge_requests.return_value = []
        
        summary = self.processor.process_project_mrs(
            project_path="group/project",
            review_type="general"
        )
        
        assert summary.total_mrs == 0
        assert summary.successful_reviews == 0
        assert summary.failed_reviews == 0
    
    def test_export_results_json(self):
        """Test JSON export."""
        # Add some results
        self.processor.results = [
            BatchResult(
                mr_iid=1,
                project_path="group/project",
                success=True,
                processing_time=1.0,
                review_type="general"
            )
        ]
        
        with patch("builtins.open", create=True) as mock_open:
            with patch("json.dump") as mock_json_dump:
                with patch("pathlib.Path.mkdir"):
                    self.processor.export_results("/tmp/results.json", "json")
        
        mock_json_dump.assert_called_once()
    
    def test_export_results_csv(self):
        """Test CSV export."""
        # Add some results
        self.processor.results = [
            BatchResult(
                mr_iid=1,
                project_path="group/project",
                success=True,
                processing_time=1.0,
                review_type="general"
            )
        ]
        
        with patch("builtins.open", create=True):
            with patch("csv.DictWriter") as mock_writer_class:
                mock_writer = Mock()
                mock_writer_class.return_value = mock_writer
                with patch("pathlib.Path.mkdir"):
                    self.processor.export_results("/tmp/results.csv", "csv")
        
        mock_writer.writeheader.assert_called_once()
        mock_writer.writerow.assert_called_once()
    
    def test_export_results_no_results(self):
        """Test export with no results."""
        self.processor.results = []
        
        with patch("builtins.open", create=True) as mock_open:
            self.processor.export_results("/tmp/results.json", "json")
        
        # Should not try to open file
        mock_open.assert_not_called()
    
    def test_get_analytics_empty(self):
        """Test analytics with no results."""
        self.processor.results = []
        
        analytics = self.processor.get_analytics()
        
        assert analytics == {}
    
    def test_get_analytics_with_results(self):
        """Test analytics with results."""
        self.processor.results = [
            BatchResult(
                mr_iid=1,
                project_path="group/project",
                success=True,
                processing_time=2.0,
                review_type="general",
                complexity_score=45,
                risk_assessment="MEDIUM_RISK",
                file_count=3,
                lines_added=20,
                lines_removed=5
            ),
            BatchResult(
                mr_iid=2,
                project_path="group/project",
                success=False,
                processing_time=1.0,
                review_type="general",
                error="Connection timeout"
            )
        ]
        
        analytics = self.processor.get_analytics()
        
        assert "performance" in analytics
        assert "quality" in analytics
        assert "success_metrics" in analytics
        
        # Check performance metrics
        perf = analytics["performance"]
        assert perf["total_processing_time"] == 3.0
        assert perf["average_processing_time"] == 1.5
        assert perf["fastest_review"] == 1.0
        assert perf["slowest_review"] == 2.0
        
        # Check quality metrics
        quality = analytics["quality"]
        assert quality["average_complexity_score"] == 45.0
        assert "MEDIUM_RISK" in quality["risk_distribution"]
        
        # Check success metrics
        success = analytics["success_metrics"]
        assert success["success_rate"] == 50.0
        assert "connection_issues" in success["error_categories"]


if __name__ == '__main__':
    pytest.main([__file__])