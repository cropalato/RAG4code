#!/usr/bin/env python3
"""
GitLab Merge Request Review CLI

Command-line interface for analyzing and reviewing GitLab merge requests
using CodeRAG integration.
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Optional, Dict, Any
import time
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Configure detailed logging
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

from gitlab_integration import GitLabClient, MRAnalyzer, ReviewGenerator
from gitlab_integration.batch_processor import BatchProcessor
from gitlab_integration.ci_integration import GitLabCIIntegration
from code_rag import DockerCodeRAGSystem


class GitLabReviewCLI:
    """Main CLI class for GitLab MR review."""
    
    def __init__(self, verbose: bool = False, debug_file: str = None):
        """Initialize CLI with debug capabilities."""
        self.logger = setup_logging(verbose, debug_file)
        self.verbose = verbose
        
        # Initialize components
        self.gitlab_client = None
        self.rag_system = None
        self.mr_analyzer = None
        self.review_generator = None
        
        self.logger.info("🚀 GitLab Review CLI initialized")
        if verbose:
            self.logger.debug("🔍 Debug mode enabled - detailed logging active")
    
    
    def initialize_components(self, config: Optional[Dict[str, Any]] = None):
        """Initialize GitLab client and RAG system with detailed debug logging."""
        try:
            self.logger.info("🔧 Starting component initialization...")
            
            # Debug configuration
            if self.verbose and config:
                self.logger.debug(f"🔍 Configuration received: {json.dumps({k: '***' if 'token' in k.lower() else v for k, v in config.items()}, indent=2)}")
            
            # Initialize GitLab client
            self.logger.info("🔌 Connecting to GitLab...")
            gitlab_url = config.get('gitlab_url') if config else os.getenv('GITLAB_URL')
            gitlab_token = config.get('gitlab_token') if config else os.getenv('GITLAB_TOKEN')
            
            if self.verbose:
                self.logger.debug(f"🔍 GitLab URL: {gitlab_url}")
                self.logger.debug(f"🔍 GitLab Token: {'***' if gitlab_token else 'Not provided'}")
            
            self.gitlab_client = GitLabClient(gitlab_url, gitlab_token)
            self.logger.info("✅ GitLab client initialized")
            
            # Initialize RAG system
            self.logger.info("🧠 Initializing CodeRAG system...")
            rag_config = {
                'ollama_host': config.get('ollama_host') if config else os.getenv('OLLAMA_HOST', 'http://host.docker.internal:11434'),
                'api_url': config.get('rag_api_url') if config else os.getenv('RAG_API_URL', 'http://localhost:8000')
            }
            
            if self.verbose:
                self.logger.debug(f"🔍 RAG configuration: {json.dumps(rag_config, indent=2)}")
            
            self.rag_system = DockerCodeRAGSystem()
            self.logger.info("✅ CodeRAG system initialized")
            
            # Initialize analyzer and review generator
            self.logger.info("🔍 Initializing MR analyzer...")
            self.mr_analyzer = MRAnalyzer(self.rag_system)
            self.logger.debug("✅ MR analyzer ready")
            
            self.logger.info("🤖 Initializing review generator...")
            ollama_host = rag_config['ollama_host']
            self.review_generator = ReviewGenerator(self.rag_system, ollama_host)
            
            if self.verbose:
                self.logger.debug(f"🔍 Review generator using Ollama at: {ollama_host}")
            
            self.logger.debug("✅ Review generator ready")
            
            # Initialize batch processor
            self.logger.debug("📦 Initializing batch processor...")
            self.batch_processor = BatchProcessor(
                self.gitlab_client, 
                self.mr_analyzer, 
                self.review_generator
            )
            self.logger.debug("✅ Batch processor ready")
            
            # Initialize CI integration
            self.logger.debug("🔄 Initializing CI integration...")
            self.ci_integration = GitLabCIIntegration(
                self.gitlab_client,
                self.mr_analyzer,
                self.review_generator
            )
            self.logger.debug("✅ CI integration ready")
            
            self.logger.info("✅ All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize components: {e}")
            if self.verbose:
                self.logger.debug(f"🔍 Full error details:", exc_info=True)
            raise
    
    def review_mr_from_url(self, mr_url: str, review_type: str = 'general', 
                          post_review: bool = False, project_filter: str = None) -> Dict[str, Any]:
        """
        Review merge request from GitLab URL.
        
        Args:
            mr_url: GitLab merge request URL
            review_type: Type of review ('general', 'security', 'performance')
            post_review: Whether to post review to GitLab
            project_filter: Filter RAG queries by project
            
        Returns:
            Review results dictionary
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"🔍 Starting review of MR: {mr_url}")
            if self.verbose:
                self.logger.debug(f"🔍 Review parameters - Type: {review_type}, Post: {post_review}, Project filter: {project_filter}")
            
            # Parse URL and get MR data
            self.logger.debug("🔗 Parsing MR URL...")
            project_path, mr_iid = self.gitlab_client.parse_mr_url(mr_url)
            self.logger.info(f"📋 Project: {project_path}, MR IID: {mr_iid}")
            
            # Fetch MR data
            self.logger.debug("📥 Fetching MR data from GitLab...")
            mr_data = self.gitlab_client.get_merge_request(project_path, mr_iid)
            
            if self.verbose:
                self.logger.debug(f"🔍 MR data received - Title: {mr_data.get('title', 'N/A')}")
                self.logger.debug(f"🔍 MR author: {mr_data.get('author', {}).get('username', 'N/A')}")
                self.logger.debug(f"🔍 MR state: {mr_data.get('state', 'N/A')}")
            
            self.logger.debug("📥 Fetching MR changes from GitLab...")
            changes_data = self.gitlab_client.get_mr_changes(project_path, mr_iid)
            
            if self.verbose:
                files_count = len(changes_data.get('changes', []))
                self.logger.debug(f"🔍 Changes data received - Files changed: {files_count}")
                
                # Log first few changed files for debugging
                for i, change in enumerate(changes_data.get('changes', [])[:3]):
                    file_path = change.get('new_path') or change.get('old_path', 'unknown')
                    self.logger.debug(f"🔍 File {i+1}: {file_path}")
            
            # Set project filter if not specified
            if not project_filter and self.rag_system:
                # Try to infer project name from GitLab project
                project_filter = mr_data.get('path_with_namespace', '').split('/')[-1]
                self.logger.info(f"🎯 Using inferred project filter: {project_filter}")
            
            # Update RAG system with project filter
            if project_filter and hasattr(self.mr_analyzer, 'project_filter'):
                self.mr_analyzer.project_filter = project_filter
                if self.verbose:
                    self.logger.debug(f"🔍 Set project filter on MR analyzer: {project_filter}")
            
            # Analyze MR
            self.logger.info("🔬 Analyzing merge request changes...")
            if self.verbose:
                self.logger.debug("🔍 Starting MR analysis with RAG context...")
            
            analysis = self.mr_analyzer.analyze_mr_changes(mr_data, changes_data)
            
            if self.verbose:
                impact = analysis.get('impact_analysis', {})
                self.logger.debug(f"🔍 Analysis complete - Complexity: {impact.get('complexity_score', 0)}/100")
                self.logger.debug(f"🔍 Files analyzed: {impact.get('files_count', 0)}")
                self.logger.debug(f"🔍 Lines added: {impact.get('lines_added', 0)}")
                self.logger.debug(f"🔍 Lines removed: {impact.get('lines_removed', 0)}")
                
                # Log RAG context found
                rag_context = analysis.get('review_context', [])
                self.logger.debug(f"🔍 RAG context entries found: {len(rag_context)}")
                for i, context in enumerate(rag_context[:3]):  # Log first 3 contexts
                    self.logger.debug(f"🔍 RAG context {i+1}: {context.get('type', 'unknown')} - {context.get('query', '')[:100]}...")
            
            # Generate review
            self.logger.info(f"🤖 Generating {review_type} review...")
            if self.verbose:
                self.logger.debug(f"🔍 Sending analysis to review generator...")
                self.logger.debug(f"🔍 Review will be generated using Ollama...")
            
            review = self.review_generator.generate_review(analysis, review_type)
            
            if self.verbose:
                self.logger.debug(f"🔍 Review generated successfully")
                self.logger.debug(f"🔍 Review type used: {review.get('metadata', {}).get('review_type', review_type)}")
                self.logger.debug(f"🔍 Risk assessment: {review.get('overall_assessment', 'N/A')}")
                summary_length = len(review.get('summary', ''))
                self.logger.debug(f"🔍 Review summary length: {summary_length} characters")
            
            # Post review if requested
            if post_review:
                self.logger.info("📤 Posting review to GitLab...")
                gitlab_comment = self.review_generator.format_for_gitlab(review)
                
                note = self.gitlab_client.post_mr_note(project_path, mr_iid, gitlab_comment)
                review['posted_note_id'] = note.get('id')
                self.logger.info(f"✅ Review posted successfully (Note ID: {note.get('id')})")
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            result = {
                'success': True,
                'mr_url': mr_url,
                'project_path': project_path,
                'mr_iid': mr_iid,
                'analysis': analysis,
                'review': review,
                'processing_time': processing_time,
                'posted': post_review
            }
            
            self.logger.info(f"🎉 Review completed in {processing_time:.2f} seconds")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Review failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'mr_url': mr_url,
                'processing_time': time.time() - start_time
            }
    
    def review_mr_by_id(self, project_path: str, mr_iid: int, **kwargs) -> Dict[str, Any]:
        """Review MR by project path and IID."""
        # Construct URL and use existing method
        gitlab_url = self.gitlab_client.gitlab_url.rstrip('/')
        mr_url = f"{gitlab_url}/{project_path}/-/merge_requests/{mr_iid}"
        
        return self.review_mr_from_url(mr_url, **kwargs)
    
    def list_project_mrs(self, project_path: str, state: str = 'opened') -> List[Dict[str, Any]]:
        """List merge requests for a project."""
        try:
            mrs = self.gitlab_client.get_project_merge_requests(project_path, state)
            
            # Format for display
            formatted_mrs = []
            for mr in mrs:
                formatted_mrs.append({
                    'iid': mr['iid'],
                    'title': mr['title'],
                    'author': mr['author']['username'],
                    'state': mr['state'],
                    'created_at': mr['created_at'],
                    'updated_at': mr['updated_at'],
                    'source_branch': mr['source_branch'],
                    'target_branch': mr['target_branch'],
                    'url': mr['web_url']
                })
            
            return formatted_mrs
            
        except Exception as e:
            self.logger.error(f"Failed to list MRs: {e}")
            return []
    
    def batch_review_mrs(self, project_path: str, state: str = 'opened', 
                        max_reviews: int = 5, parallel_workers: int = 1, 
                        export_results: str = None, **review_kwargs) -> Dict[str, Any]:
        """Enhanced batch review with progress tracking and analytics."""
        self.logger.info(f"📦 Starting enhanced batch review for project: {project_path}")
        
        # Setup progress callback
        def progress_callback(current: int, total: int, message: str):
            if total > 0:
                percentage = (current / total) * 100
                self.logger.info(f"🔄 [{current}/{total}] ({percentage:.1f}%) {message}")
            else:
                self.logger.info(f"🔄 {message}")
        
        self.batch_processor.set_progress_callback(progress_callback)
        
        # Configure batch processing
        filters = {}
        if 'author_filter' in review_kwargs:
            filters['author'] = review_kwargs.pop('author_filter')
        if 'label_filter' in review_kwargs:
            filters['labels'] = review_kwargs.pop('label_filter')
        
        # Run batch processing
        summary = self.batch_processor.process_project_mrs(
            project_path=project_path,
            review_type=review_kwargs.get('review_type', 'general'),
            mr_state=state,
            max_reviews=max_reviews,
            post_reviews=review_kwargs.get('post_review', False),
            parallel_workers=parallel_workers,
            delay_between_reviews=review_kwargs.get('delay', 1.0),
            filters=filters if filters else None
        )
        
        # Export results if requested
        if export_results:
            self.batch_processor.export_results(
                export_results, 
                format='json' if export_results.endswith('.json') else 'csv'
            )
        
        # Get analytics
        analytics = self.batch_processor.get_analytics()
        
        return {
            'summary': summary,
            'results': self.batch_processor.results,
            'analytics': analytics
        }
    
    def run_ci_mode(self) -> Dict[str, Any]:
        """Run in CI mode for automated reviews."""
        self.logger.info("🤖 Running in CI mode")
        
        try:
            result = self.ci_integration.run_ci_review()
            
            if result.get('skipped'):
                self.logger.info(f"⏭️ Review skipped: {result['reason']}")
            else:
                self.logger.info("✅ CI review completed successfully")
                
                # Log key metrics
                analysis = result.get('analysis', {})
                review = result.get('review', {})
                
                self.logger.info(f"📊 Complexity: {analysis.get('complexity_score', 0)}")
                self.logger.info(f"🎯 Risk: {review.get('risk_assessment', 'UNKNOWN')}")
                self.logger.info(f"📤 Posted: {review.get('posted', False)}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ CI review failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'ci_env': self.ci_integration.ci_env
            }
    
    def show_config(self):
        """Show current configuration."""
        config_info = {
            'GitLab URL': getattr(self.gitlab_client, 'gitlab_url', 'Not initialized'),
            'RAG System': 'Initialized' if self.rag_system else 'Not initialized',
            'Ollama Host': getattr(self.review_generator, 'ollama_host', 'Not initialized'),
            'Log Level': logging.getLogger().getEffectiveLevel()
        }
        
        print("📋 Current Configuration:")
        for key, value in config_info.items():
            print(f"  {key}: {value}")
    
    def print_results(self, results: Dict[str, Any], output_format: str = 'text'):
        """Print review results in enhanced format."""
        if output_format == 'json':
            # Remove non-serializable objects for JSON output
            clean_results = self._clean_for_json(results)
            print(json.dumps(clean_results, indent=2))
            return
        
        # Enhanced text format with better visual structure
        if not results['success']:
            print(f"\n{'=' * 60}")
            print(f"❌ REVIEW FAILED")
            print(f"{'=' * 60}")
            print(f"Error: {results['error']}")
            print(f"MR URL: {results.get('mr_url', 'N/A')}")
            print(f"{'=' * 60}")
            return
        
        review = results['review']
        analysis = results['analysis']
        
        # Header section
        print(f"\n{'=' * 60}")
        print(f"🎉 MERGE REQUEST REVIEW COMPLETE")
        print(f"{'=' * 60}")
        
        # Basic info section
        print(f"📋 MR #{results['mr_iid']}: {analysis['mr_info']['title']}")
        print(f"👤 Author: {analysis['mr_info']['author']}")
        print(f"🌿 {analysis['mr_info']['source_branch']} → {analysis['mr_info']['target_branch']}")
        
        # Metrics section
        print(f"\n{'─' * 40}")
        print(f"📊 ANALYSIS METRICS")
        print(f"{'─' * 40}")
        
        # Color-coded complexity score
        complexity = analysis['impact_analysis']['complexity_score']
        if complexity >= 75:
            complexity_color = "🔴"
        elif complexity >= 50:
            complexity_color = "🟡"
        else:
            complexity_color = "🟢"
        
        print(f"⏱️  Processing time: {results['processing_time']:.2f} seconds")
        print(f"{complexity_color} Complexity score: {complexity}/100")
        print(f"📁 Files changed: {analysis['impact_analysis']['files_count']}")
        print(f"📈 Lines: +{analysis['impact_analysis']['lines_added']} / -{analysis['impact_analysis']['lines_removed']}")
        
        # Risk assessment with emoji
        risk = review['overall_assessment']
        risk_emoji = {"LOW_RISK": "🟢", "MEDIUM_RISK": "🟡", "HIGH_RISK": "🔴"}.get(risk, "⚪")
        print(f"{risk_emoji} Risk level: {risk.replace('_', ' ').title()}")
        
        # Posting status
        if results.get('posted'):
            print(f"📤 Review posted to GitLab (Note ID: {review.get('posted_note_id')})")
        else:
            print(f"💾 Review generated (not posted)")
        
        # Review content section
        print(f"\n{'─' * 40}")
        print(f"📝 REVIEW SUMMARY")
        print(f"{'─' * 40}")
        print(self._format_text_block(review['summary']))
        
        if review.get('detailed_comments'):
            print(f"\n{'─' * 40}")
            print(f"🔍 DETAILED ANALYSIS") 
            print(f"{'─' * 40}")
            print(self._format_text_block(review['detailed_comments']))
        
        if review.get('recommendations'):
            print(f"\n{'─' * 40}")
            print(f"💡 RECOMMENDATIONS")
            print(f"{'─' * 40}")
            print(self._format_text_block(review['recommendations']))
        
        # Footer
        print(f"\n{'=' * 60}")
        review_type = review['metadata'].get('review_type', 'general')
        print(f"🤖 Generated by CodeRAG • Review type: {review_type}")
        print(f"{'=' * 60}")
    
    def _format_text_block(self, text: str, indent: str = "  ") -> str:
        """Format text block with proper indentation and line breaks."""
        if not text:
            return f"{indent}(No content)"
        
        # Clean up the text and add indentation
        lines = text.strip().split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                formatted_lines.append(f"{indent}{line}")
            else:
                formatted_lines.append("")  # Preserve empty lines
        
        return '\n'.join(formatted_lines)
    
    def _clean_for_json(self, obj: Any) -> Any:
        """Clean object for JSON serialization."""
        if isinstance(obj, dict):
            return {k: self._clean_for_json(v) for k, v in obj.items() 
                   if k not in ['rag_system', 'gitlab_client']}
        elif isinstance(obj, list):
            return [self._clean_for_json(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            return str(obj)
        else:
            return obj


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        description="GitLab Merge Request Review using CodeRAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Review specific MR
  %(prog)s --mr https://gitlab.com/group/project/-/merge_requests/123
  
  # Review with security focus and post to GitLab
  %(prog)s --mr https://gitlab.com/group/project/-/merge_requests/123 --type security --post
  
  # Review by project and MR ID
  %(prog)s --project group/project --mr-id 123
  
  # Batch review open MRs
  %(prog)s --project group/project --batch --max-reviews 3
  
  # List MRs for project
  %(prog)s --project group/project --list
        """
    )
    
    # Main commands
    parser.add_argument('--mr', help='GitLab merge request URL')
    parser.add_argument('--project', help='GitLab project path (group/project)')
    parser.add_argument('--mr-id', type=int, help='Merge request IID')
    
    # Actions
    parser.add_argument('--list', action='store_true', help='List merge requests')
    parser.add_argument('--batch', action='store_true', help='Batch review multiple MRs')
    parser.add_argument('--config', action='store_true', help='Show configuration')
    parser.add_argument('--ci-mode', action='store_true', help='Run in CI/CD mode for automated reviews')
    parser.add_argument('--generate-ci-config', action='store_true',
                       help='Generate GitLab CI configuration template')
    parser.add_argument('--generate-project-config', action='store_true',
                       help='Generate project configuration template')
    
    # Options
    parser.add_argument('--type', choices=['general', 'security', 'performance'], 
                       default='general', help='Review type (default: general)')
    parser.add_argument('--post', action='store_true', help='Post review to GitLab')
    parser.add_argument('--project-filter', help='Filter RAG queries by project name')
    parser.add_argument('--max-reviews', type=int, default=5, 
                       help='Maximum reviews in batch mode (default: 5)')
    parser.add_argument('--state', choices=['opened', 'closed', 'merged', 'all'], 
                       default='opened', help='MR state for listing (default: opened)')
    parser.add_argument('--parallel-workers', type=int, default=1,
                       help='Number of parallel workers for batch processing (default: 1)')
    parser.add_argument('--delay', type=float, default=1.0,
                       help='Delay between reviews in seconds (default: 1.0)')
    parser.add_argument('--export-results', 
                       help='Export batch results to file (JSON or CSV based on extension)')
    parser.add_argument('--author-filter',
                       help='Filter MRs by author username')
    parser.add_argument('--label-filter', nargs='+',
                       help='Filter MRs by labels (space-separated)')
    parser.add_argument('--analytics', action='store_true',
                       help='Show detailed analytics for batch processing')
    
    # Output
    parser.add_argument('--output', choices=['text', 'json'], default='text',
                       help='Output format (default: text)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose debug output')
    parser.add_argument('--debug-file', help='Save debug logs to specific file')
    
    return parser


def main():
    """Main CLI entry point with debug support."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Initialize CLI with debug capabilities
    debug_file = getattr(args, 'debug_file', None)
    cli = GitLabReviewCLI(verbose=args.verbose, debug_file=debug_file)
    
    try:
        # Handle template generation (no initialization needed)
        if args.generate_ci_config:
            from gitlab_integration.ci_integration import GitLabCIIntegration
            integration = GitLabCIIntegration(None, None, None)
            print(integration.generate_ci_config_template())
            return
        
        if args.generate_project_config:
            from gitlab_integration.ci_integration import GitLabCIIntegration
            integration = GitLabCIIntegration(None, None, None)
            print(integration.generate_project_config_template())
            return
        
        # Show config if requested
        if args.config:
            cli.initialize_components()
            cli.show_config()
            return
        
        # Handle CI mode
        if args.ci_mode:
            cli.initialize_components()
            result = cli.run_ci_mode()
            
            if args.output == 'json':
                clean_result = cli._clean_for_json(result)
                print(json.dumps(clean_result, indent=2))
            else:
                if result.get('success', True):
                    print("✅ CI review completed successfully")
                else:
                    print(f"❌ CI review failed: {result.get('error')}")
                    sys.exit(1)
            return
        
        # Validate arguments
        if not any([args.mr, args.project, args.list, args.config, args.ci_mode]):
            print("❌ Error: Must specify --mr, --project, --list, --config, or --ci-mode")
            parser.print_help()
            sys.exit(1)
        
        # Initialize components
        cli.initialize_components()
        
        # Handle different commands
        if args.list:
            if not args.project:
                print("❌ Error: --project required for --list")
                sys.exit(1)
            
            mrs = cli.list_project_mrs(args.project, args.state)
            if args.output == 'json':
                print(json.dumps(mrs, indent=2))
            else:
                print(f"📋 Found {len(mrs)} {args.state} merge requests:")
                for mr in mrs:
                    print(f"  #{mr['iid']}: {mr['title']} ({mr['author']})")
        
        elif args.batch:
            if not args.project:
                print("❌ Error: --project required for --batch")
                sys.exit(1)
            
            batch_results = cli.batch_review_mrs(
                args.project, 
                state=args.state,
                max_reviews=args.max_reviews,
                parallel_workers=args.parallel_workers,
                export_results=args.export_results,
                review_type=args.type,
                post_review=args.post,
                project_filter=args.project_filter,
                delay=args.delay,
                author_filter=args.author_filter,
                label_filter=args.label_filter
            )
            
            summary = batch_results['summary']
            results = batch_results['results']
            analytics = batch_results['analytics']
            
            if args.output == 'json':
                clean_results = cli._clean_for_json(batch_results)
                print(json.dumps(clean_results, indent=2))
            else:
                # Enhanced batch output with better formatting
                print(f"\n{'=' * 60}")
                print(f"🎉 BATCH REVIEW COMPLETE")
                print(f"{'=' * 60}")
                print(f"📁 Project: {args.project}")
                print(f"🎯 Review Type: {args.type}")
                print(f"⚙️  Workers: {args.parallel_workers}")
                
                print(f"\n{'─' * 40}")
                print(f"📊 RESULTS SUMMARY")
                print(f"{'─' * 40}")
                
                # Color-coded success rate
                success_rate = summary.success_rate()
                if success_rate >= 90:
                    rate_emoji = "🟢"
                elif success_rate >= 70:
                    rate_emoji = "🟡"
                else:
                    rate_emoji = "🔴"
                
                print(f"{rate_emoji} Success Rate: {success_rate:.1f}% ({summary.successful_reviews}/{summary.total_mrs})")
                print(f"⏱️  Total Time: {summary.total_processing_time:.2f}s")
                print(f"⚡ Avg Time/Review: {summary.average_processing_time:.2f}s")
                print(f"📤 Reviews Posted: {summary.reviews_posted}")
                
                if args.analytics and analytics:
                    print(f"\n{'─' * 40}")
                    print(f"📈 DETAILED ANALYTICS")
                    print(f"{'─' * 40}")
                    
                    perf = analytics.get('performance', {})
                    print(f"⚡ Performance:")
                    print(f"  • Average processing: {perf.get('average_processing_time', 0):.2f}s")
                    print(f"  • Fastest review: {perf.get('fastest_review', 0):.2f}s")
                    print(f"  • Slowest review: {perf.get('slowest_review', 0):.2f}s")
                    
                    quality = analytics.get('quality', {})
                    print(f"\n🎯 Quality Metrics:")
                    print(f"  • Average complexity: {quality.get('average_complexity_score', 0):.1f}/100")
                    
                    risk_dist = quality.get('risk_distribution', {})
                    if risk_dist:
                        print(f"  • Risk distribution:")
                        for risk_level, count in risk_dist.items():
                            risk_emoji = {"LOW_RISK": "🟢", "MEDIUM_RISK": "🟡", "HIGH_RISK": "🔴"}.get(risk_level, "⚪")
                            print(f"    {risk_emoji} {risk_level.replace('_', ' ').title()}: {count}")
                
                print(f"\n{'─' * 40}")
                print(f"📋 INDIVIDUAL RESULTS")
                print(f"{'─' * 40}")
                
                for result in results:
                    if result.success:
                        risk_emoji = {"LOW_RISK": "🟢", "MEDIUM_RISK": "🟡", "HIGH_RISK": "🔴"}.get(result.risk_assessment, "⚪")
                        print(f"  ✅ MR #{result.mr_iid}: {risk_emoji} {result.risk_assessment.replace('_', ' ').title()} "
                              f"(complexity: {result.complexity_score}/100, {result.processing_time:.1f}s)")
                    else:
                        print(f"  ❌ MR #{result.mr_iid}: {result.error}")
                
                if args.export_results:
                    print(f"\n{'─' * 40}")
                    print(f"📁 Results exported to: {args.export_results}")
                
                print(f"\n{'=' * 60}")
                print(f"🤖 Batch processing powered by CodeRAG")
                print(f"{'=' * 60}")
        
        elif args.mr:
            result = cli.review_mr_from_url(
                args.mr,
                review_type=args.type,
                post_review=args.post,
                project_filter=args.project_filter
            )
            cli.print_results(result, args.output)
        
        elif args.project and args.mr_id:
            result = cli.review_mr_by_id(
                args.project,
                args.mr_id,
                review_type=args.type,
                post_review=args.post,
                project_filter=args.project_filter
            )
            cli.print_results(result, args.output)
        
        else:
            print("❌ Error: Invalid command combination")
            parser.print_help()
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n⏹️ Review interrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.getLogger(__name__).error(f"❌ Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()