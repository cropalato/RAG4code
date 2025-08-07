#!/usr/bin/env python3
"""
Enhanced Batch Processing for GitLab MR Reviews

Provides advanced batch processing capabilities with progress tracking,
parallel processing, and comprehensive reporting.
"""

import logging
import time
import json
from typing import Dict, List, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import csv

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    """Result of a single MR review in batch processing."""
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
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class BatchSummary:
    """Summary of entire batch processing session."""
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
        if self.total_mrs == 0:
            return 0.0
        return (self.successful_reviews / self.total_mrs) * 100


class BatchProcessor:
    """Enhanced batch processor for GitLab MR reviews."""
    
    def __init__(self, gitlab_client, mr_analyzer, review_generator):
        """
        Initialize batch processor.
        
        Args:
            gitlab_client: GitLab API client
            mr_analyzer: MR analyzer instance
            review_generator: Review generator instance
        """
        self.gitlab_client = gitlab_client
        self.mr_analyzer = mr_analyzer
        self.review_generator = review_generator
        
        # Progress tracking
        self.progress_callback: Optional[Callable] = None
        self.results: List[BatchResult] = []
    
    def set_progress_callback(self, callback: Callable[[int, int, str], None]):
        """
        Set progress callback function.
        
        Args:
            callback: Function that receives (current, total, status_message)
        """
        self.progress_callback = callback
    
    def process_project_mrs(self, 
                           project_path: str,
                           review_type: str = 'general',
                           mr_state: str = 'opened',
                           max_reviews: int = 10,
                           post_reviews: bool = False,
                           parallel_workers: int = 3,
                           delay_between_reviews: float = 1.0,
                           filters: Optional[Dict[str, Any]] = None) -> BatchSummary:
        """
        Process multiple MRs for a project with enhanced capabilities.
        
        Args:
            project_path: GitLab project path
            review_type: Type of review to generate
            mr_state: MR state to filter ('opened', 'merged', 'closed', 'all')
            max_reviews: Maximum number of MRs to review
            post_reviews: Whether to post reviews to GitLab
            parallel_workers: Number of parallel worker threads
            delay_between_reviews: Delay between reviews to respect rate limits
            filters: Additional filters for MR selection
            
        Returns:
            BatchSummary with processing results
        """
        start_time = time.time()
        start_timestamp = datetime.now().isoformat()
        
        logger.info(f"🚀 Starting batch processing for project: {project_path}")
        logger.info(f"📋 Configuration: {review_type} reviews, {mr_state} MRs, max {max_reviews}")
        
        self.results = []
        errors = []
        
        try:
            # Get MRs to process
            mrs = self._get_mrs_to_process(project_path, mr_state, max_reviews, filters)
            total_mrs = len(mrs)
            
            if total_mrs == 0:
                logger.warning(f"No MRs found for project {project_path} with state {mr_state}")
                return self._create_empty_summary(project_path, review_type, start_timestamp)
            
            logger.info(f"📊 Found {total_mrs} MRs to process")
            self._update_progress(0, total_mrs, "Starting batch processing...")
            
            # Process MRs
            if parallel_workers > 1:
                self._process_parallel(mrs, review_type, post_reviews, parallel_workers, delay_between_reviews)
            else:
                self._process_sequential(mrs, review_type, post_reviews, delay_between_reviews)
            
        except Exception as e:
            error_msg = f"Batch processing failed: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        # Calculate summary
        end_time = time.time()
        end_timestamp = datetime.now().isoformat()
        total_processing_time = end_time - start_time
        
        successful_reviews = sum(1 for r in self.results if r.success)
        failed_reviews = len(self.results) - successful_reviews
        reviews_posted = sum(1 for r in self.results if r.review_posted)
        
        avg_processing_time = (
            total_processing_time / len(self.results) if self.results else 0
        )
        
        summary = BatchSummary(
            total_mrs=len(self.results),
            successful_reviews=successful_reviews,
            failed_reviews=failed_reviews,
            total_processing_time=total_processing_time,
            average_processing_time=avg_processing_time,
            reviews_posted=reviews_posted,
            start_time=start_timestamp,
            end_time=end_timestamp,
            project_path=project_path,
            review_type=review_type,
            errors=errors
        )
        
        self._log_summary(summary)
        return summary
    
    def _get_mrs_to_process(self, 
                           project_path: str, 
                           mr_state: str, 
                           max_reviews: int,
                           filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get list of MRs to process with filtering."""
        try:
            # Get MRs from GitLab
            mrs = self.gitlab_client.get_project_merge_requests(
                project_path, 
                state=mr_state,
                per_page=min(max_reviews * 2, 100)  # Get more than needed for filtering
            )
            
            # Apply filters
            if filters:
                mrs = self._apply_filters(mrs, filters)
            
            # Limit to max_reviews
            return mrs[:max_reviews]
            
        except Exception as e:
            logger.error(f"Failed to get MRs for {project_path}: {e}")
            return []
    
    def _apply_filters(self, mrs: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply additional filters to MR list."""
        filtered_mrs = mrs
        
        # Filter by author
        if 'author' in filters:
            author_filter = filters['author'].lower()
            filtered_mrs = [
                mr for mr in filtered_mrs 
                if author_filter in mr.get('author', {}).get('username', '').lower()
            ]
        
        # Filter by labels
        if 'labels' in filters:
            required_labels = set(filters['labels'])
            filtered_mrs = [
                mr for mr in filtered_mrs 
                if required_labels.intersection(set(label['name'] for label in mr.get('labels', [])))
            ]
        
        # Filter by title/description keywords
        if 'keywords' in filters:
            keywords = [kw.lower() for kw in filters['keywords']]
            filtered_mrs = [
                mr for mr in filtered_mrs
                if any(
                    kw in mr.get('title', '').lower() or 
                    kw in mr.get('description', '').lower()
                    for kw in keywords
                )
            ]
        
        # Filter by creation date
        if 'created_after' in filters:
            created_after = filters['created_after']
            filtered_mrs = [
                mr for mr in filtered_mrs
                if mr.get('created_at', '') >= created_after
            ]
        
        return filtered_mrs
    
    def _process_sequential(self, 
                           mrs: List[Dict[str, Any]], 
                           review_type: str, 
                           post_reviews: bool,
                           delay: float):
        """Process MRs sequentially."""
        total_mrs = len(mrs)
        
        for i, mr in enumerate(mrs, 1):
            self._update_progress(i - 1, total_mrs, f"Processing MR #{mr['iid']}")
            
            result = self._process_single_mr(mr, review_type, post_reviews)
            self.results.append(result)
            
            # Add delay between reviews
            if i < total_mrs and delay > 0:
                time.sleep(delay)
        
        self._update_progress(total_mrs, total_mrs, "Batch processing completed")
    
    def _process_parallel(self, 
                         mrs: List[Dict[str, Any]], 
                         review_type: str, 
                         post_reviews: bool,
                         workers: int,
                         delay: float):
        """Process MRs in parallel with limited workers."""
        total_mrs = len(mrs)
        completed = 0
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all jobs
            future_to_mr = {
                executor.submit(self._process_single_mr, mr, review_type, post_reviews): mr
                for mr in mrs
            }
            
            # Process completed jobs
            for future in as_completed(future_to_mr):
                completed += 1
                mr = future_to_mr[future]
                
                try:
                    result = future.result()
                    self.results.append(result)
                    
                    self._update_progress(
                        completed, 
                        total_mrs, 
                        f"Completed MR #{mr['iid']} ({completed}/{total_mrs})"
                    )
                    
                except Exception as e:
                    error_result = BatchResult(
                        mr_iid=mr['iid'],
                        project_path=mr.get('project_path', ''),
                        success=False,
                        processing_time=0.0,
                        review_type=review_type,
                        error=str(e)
                    )
                    self.results.append(error_result)
                    logger.error(f"Failed to process MR #{mr['iid']}: {e}")
                
                # Add delay between completions
                if delay > 0:
                    time.sleep(delay)
        
        self._update_progress(total_mrs, total_mrs, "Parallel processing completed")
    
    def _process_single_mr(self, 
                          mr: Dict[str, Any], 
                          review_type: str, 
                          post_review: bool) -> BatchResult:
        """Process a single MR and return result."""
        start_time = time.time()
        mr_iid = mr['iid']
        project_path = mr.get('project_path', '')
        
        try:
            # Get MR changes
            changes_data = self.gitlab_client.get_mr_changes(project_path, mr_iid)
            
            # Analyze MR
            analysis = self.mr_analyzer.analyze_mr_changes(mr, changes_data)
            
            # Generate review
            review = self.review_generator.generate_review(analysis, review_type)
            
            # Post review if requested
            review_posted = False
            if post_review and review.get('summary'):
                try:
                    gitlab_comment = self.review_generator.format_for_gitlab(review)
                    self.gitlab_client.post_mr_note(project_path, mr_iid, gitlab_comment)
                    review_posted = True
                except Exception as e:
                    logger.warning(f"Failed to post review for MR #{mr_iid}: {e}")
            
            processing_time = time.time() - start_time
            
            return BatchResult(
                mr_iid=mr_iid,
                project_path=project_path,
                success=True,
                processing_time=processing_time,
                review_type=review_type,
                complexity_score=analysis['impact_analysis']['complexity_score'],
                risk_assessment=review.get('overall_assessment', 'UNKNOWN'),
                review_posted=review_posted,
                file_count=analysis['impact_analysis']['files_count'],
                lines_added=analysis['impact_analysis']['lines_added'],
                lines_removed=analysis['impact_analysis']['lines_removed']
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error processing MR #{mr_iid}: {e}")
            
            return BatchResult(
                mr_iid=mr_iid,
                project_path=project_path,
                success=False,
                processing_time=processing_time,
                review_type=review_type,
                error=str(e)
            )
    
    def _update_progress(self, current: int, total: int, message: str):
        """Update progress if callback is set."""
        if self.progress_callback:
            self.progress_callback(current, total, message)
    
    def _create_empty_summary(self, project_path: str, review_type: str, start_time: str) -> BatchSummary:
        """Create empty summary for when no MRs are found."""
        return BatchSummary(
            total_mrs=0,
            successful_reviews=0,
            failed_reviews=0,
            total_processing_time=0.0,
            average_processing_time=0.0,
            reviews_posted=0,
            start_time=start_time,
            end_time=datetime.now().isoformat(),
            project_path=project_path,
            review_type=review_type,
            errors=[]
        )
    
    def _log_summary(self, summary: BatchSummary):
        """Log batch processing summary."""
        logger.info("📊 Batch Processing Summary:")
        logger.info(f"   📁 Project: {summary.project_path}")
        logger.info(f"   🎯 Review Type: {summary.review_type}")
        logger.info(f"   📋 Total MRs: {summary.total_mrs}")
        logger.info(f"   ✅ Successful: {summary.successful_reviews}")
        logger.info(f"   ❌ Failed: {summary.failed_reviews}")
        logger.info(f"   📤 Posted: {summary.reviews_posted}")
        logger.info(f"   ⏱️ Total Time: {summary.total_processing_time:.2f}s")
        logger.info(f"   📊 Success Rate: {summary.success_rate():.1f}%")
        
        if summary.errors:
            logger.warning(f"   ⚠️ Errors: {len(summary.errors)}")
    
    def export_results(self, output_path: str, format: str = 'json'):
        """
        Export batch results to file.
        
        Args:
            output_path: Path to save results
            format: Export format ('json', 'csv')
        """
        if not self.results:
            logger.warning("No results to export")
            return
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        if format.lower() == 'json':
            with open(output_file, 'w') as f:
                json.dump([asdict(result) for result in self.results], f, indent=2)
        
        elif format.lower() == 'csv':
            with open(output_file, 'w', newline='') as f:
                if self.results:
                    writer = csv.DictWriter(f, fieldnames=asdict(self.results[0]).keys())
                    writer.writeheader()
                    for result in self.results:
                        writer.writerow(asdict(result))
        
        logger.info(f"📁 Results exported to {output_file}")
    
    def get_analytics(self) -> Dict[str, Any]:
        """Get detailed analytics from batch results."""
        if not self.results:
            return {}
        
        successful_results = [r for r in self.results if r.success]
        
        analytics = {
            'performance': {
                'total_processing_time': sum(r.processing_time for r in self.results),
                'average_processing_time': sum(r.processing_time for r in self.results) / len(self.results),
                'fastest_review': min(r.processing_time for r in self.results),
                'slowest_review': max(r.processing_time for r in self.results),
            },
            'quality': {
                'average_complexity_score': (
                    sum(r.complexity_score for r in successful_results) / len(successful_results)
                    if successful_results else 0
                ),
                'risk_distribution': self._get_risk_distribution(),
                'file_change_distribution': self._get_file_change_distribution(),
            },
            'success_metrics': {
                'success_rate': len(successful_results) / len(self.results) * 100,
                'reviews_posted_rate': sum(1 for r in self.results if r.review_posted) / len(self.results) * 100,
                'error_categories': self._categorize_errors(),
            }
        }
        
        return analytics
    
    def _get_risk_distribution(self) -> Dict[str, int]:
        """Get distribution of risk assessments."""
        risk_counts = {}
        for result in self.results:
            if result.success and result.risk_assessment:
                risk = result.risk_assessment
                risk_counts[risk] = risk_counts.get(risk, 0) + 1
        return risk_counts
    
    def _get_file_change_distribution(self) -> Dict[str, Any]:
        """Get distribution of file changes."""
        if not self.results:
            return {}
        
        successful_results = [r for r in self.results if r.success]
        if not successful_results:
            return {}
        
        file_counts = [r.file_count for r in successful_results]
        lines_added = [r.lines_added for r in successful_results]
        lines_removed = [r.lines_removed for r in successful_results]
        
        return {
            'files_changed': {
                'average': sum(file_counts) / len(file_counts),
                'max': max(file_counts),
                'min': min(file_counts),
            },
            'lines_added': {
                'total': sum(lines_added),
                'average': sum(lines_added) / len(lines_added),
                'max': max(lines_added),
            },
            'lines_removed': {
                'total': sum(lines_removed),
                'average': sum(lines_removed) / len(lines_removed),
                'max': max(lines_removed),
            }
        }
    
    def _categorize_errors(self) -> Dict[str, int]:
        """Categorize errors from failed results."""
        error_categories = {}
        
        for result in self.results:
            if not result.success and result.error:
                error = result.error.lower()
                
                if 'connection' in error or 'timeout' in error:
                    category = 'connection_issues'
                elif 'permission' in error or 'forbidden' in error:
                    category = 'permission_issues'
                elif 'not found' in error or '404' in error:
                    category = 'not_found'
                elif 'rate limit' in error:
                    category = 'rate_limiting'
                else:
                    category = 'other'
                
                error_categories[category] = error_categories.get(category, 0) + 1
        
        return error_categories