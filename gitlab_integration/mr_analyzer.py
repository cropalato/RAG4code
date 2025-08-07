#!/usr/bin/env python3
"""
Merge Request Analyzer for CodeRAG Integration

Analyzes GitLab merge request changes and generates context for review.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


class MRAnalyzer:
    """Analyzes merge request changes and extracts context."""
    
    def __init__(self, rag_system=None, max_file_size_mb: int = 5, max_files: int = 100):
        """
        Initialize MR analyzer with performance limits.
        
        Args:
            rag_system: CodeRAG system instance for context queries
            max_file_size_mb: Maximum file size to process (MB)
            max_files: Maximum number of files to process
        """
        self.rag_system = rag_system
        self.max_file_size = max_file_size_mb * 1024 * 1024  # Convert to bytes
        self.max_files = max_files
        
        # File extensions to analyze
        self.code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.vue',
            '.java', '.cpp', '.c', '.h', '.cs', '.php', 
            '.rb', '.go', '.rs', '.sql', '.json', '.yaml', '.yml'
        }
        
        # Patterns for extracting code elements
        self.function_patterns = {
            'python': r'def\s+(\w+)',
            'javascript': r'(?:function\s+(\w+)|(\w+)\s*=\s*(?:function|\(.*?\)\s*=>))',
            'typescript': r'(?:function\s+(\w+)|(\w+)\s*=\s*(?:function|\(.*?\)\s*=>))',
            'java': r'(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\(',
            'cpp': r'(?:\w+\s+)?(\w+)\s*\([^)]*\)\s*{',
            'go': r'func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(',
            'rust': r'fn\s+(\w+)\s*\(',
        }
        
        self.class_patterns = {
            'python': r'class\s+(\w+)',
            'javascript': r'class\s+(\w+)',
            'typescript': r'(?:class|interface)\s+(\w+)',
            'java': r'(?:public|private|protected)?\s*(?:abstract)?\s*class\s+(\w+)',
            'cpp': r'class\s+(\w+)',
            'go': r'type\s+(\w+)\s+struct',
            'rust': r'(?:struct|enum|trait)\s+(\w+)',
        }
    
    def analyze_mr_changes(self, mr_data: Dict[str, Any], changes_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze merge request changes comprehensively.
        
        Args:
            mr_data: GitLab MR data
            changes_data: GitLab MR changes data
            
        Returns:
            Analysis results dictionary
        """
        logger.info(f"🔍 Analyzing MR #{mr_data.get('iid', 'Unknown')}: {mr_data.get('title', 'No title')}")
        
        analysis = {
            'mr_info': self._extract_mr_info(mr_data),
            'file_changes': [],
            'code_changes': {
                'functions_modified': [],
                'classes_modified': [],
                'new_functions': [],
                'new_classes': [],
                'deleted_functions': [],
                'deleted_classes': []
            },
            'impact_analysis': {
                'files_count': 0,
                'lines_added': 0,
                'lines_removed': 0,
                'complexity_score': 0,
                'risk_factors': []
            },
            'review_context': []
        }
        
        changes = changes_data.get('changes', [])
        
        # Filter changes for performance (limit size and number)
        filtered_changes = self._filter_changes_for_performance(changes)
        analysis['impact_analysis']['files_count'] = len(filtered_changes)
        
        if len(changes) > len(filtered_changes):
            logger.warning(f"🔥 Filtered {len(changes) - len(filtered_changes)} files for performance "
                          f"(large files or too many files)")
        
        for change in filtered_changes:
            file_analysis = self._analyze_file_change(change)
            analysis['file_changes'].append(file_analysis)
            
            # Aggregate impact metrics
            analysis['impact_analysis']['lines_added'] += file_analysis['lines_added']
            analysis['impact_analysis']['lines_removed'] += file_analysis['lines_removed']
            
            # Extract code elements
            self._extract_code_elements(file_analysis, analysis['code_changes'])
        
        # Calculate complexity score
        analysis['impact_analysis']['complexity_score'] = self._calculate_complexity_score(analysis)
        
        # Identify risk factors
        analysis['impact_analysis']['risk_factors'] = self._identify_risk_factors(analysis)
        
        # Generate RAG context if available
        if self.rag_system:
            analysis['review_context'] = self._generate_rag_context(analysis)
        
        logger.info(f"📊 Analysis complete: {analysis['impact_analysis']['files_count']} files, "
                   f"+{analysis['impact_analysis']['lines_added']}/-{analysis['impact_analysis']['lines_removed']} lines")
        
        return analysis
    
    def _filter_changes_for_performance(self, changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter changes for performance optimization."""
        filtered_changes = []
        
        # Limit total number of files
        for change in changes[:self.max_files]:
            diff_content = change.get('diff', '')
            
            # Skip very large diffs to prevent memory issues
            if len(diff_content) > self.max_file_size:
                logger.warning(f"⚠️ Skipping large file: {change.get('new_path')} "
                              f"({len(diff_content)} bytes)")
                continue
            
            # Skip binary files
            if self._is_binary_file(change):
                continue
            
            filtered_changes.append(change)
        
        return filtered_changes
    
    def _is_binary_file(self, change: Dict[str, Any]) -> bool:
        """Check if file appears to be binary."""
        file_path = change.get('new_path') or change.get('old_path', '')
        
        # Check for binary file extensions
        binary_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', 
                            '.pdf', '.zip', '.tar', '.gz', '.exe', '.dll', '.so'}
        
        if any(file_path.lower().endswith(ext) for ext in binary_extensions):
            return True
        
        # Check for binary content indicators in diff
        diff_content = change.get('diff', '')
        if 'Binary files' in diff_content or '\x00' in diff_content:
            return True
        
        return False
    
    def _extract_mr_info(self, mr_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract basic MR information."""
        return {
            'iid': mr_data.get('iid'),
            'title': mr_data.get('title', ''),
            'description': mr_data.get('description', ''),
            'author': mr_data.get('author', {}).get('username', 'Unknown'),
            'source_branch': mr_data.get('source_branch', ''),
            'target_branch': mr_data.get('target_branch', ''),
            'state': mr_data.get('state', ''),
            'created_at': mr_data.get('created_at', ''),
            'updated_at': mr_data.get('updated_at', ''),
            'labels': [label.get('name', '') for label in mr_data.get('labels', [])],
            'milestone': mr_data.get('milestone', {}).get('title') if mr_data.get('milestone') else None
        }
    
    def _analyze_file_change(self, change: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze individual file change."""
        file_path = change.get('new_path') or change.get('old_path', '')
        diff_content = change.get('diff', '')
        
        file_analysis = {
            'file_path': file_path,
            'old_path': change.get('old_path'),
            'new_path': change.get('new_path'),
            'change_type': self._determine_change_type(change),
            'file_extension': Path(file_path).suffix.lower() if file_path else '',
            'language': self._detect_language(file_path),
            'lines_added': 0,
            'lines_removed': 0,
            'is_code_file': False,
            'diff_content': diff_content,
            'modified_lines': [],
            'context_lines': []
        }
        
        # Check if it's a code file
        file_analysis['is_code_file'] = file_analysis['file_extension'] in self.code_extensions
        
        # Parse diff
        if diff_content:
            self._parse_diff(diff_content, file_analysis)
        
        return file_analysis
    
    def _determine_change_type(self, change: Dict[str, Any]) -> str:
        """Determine the type of file change."""
        if change.get('new_file', False):
            return 'added'
        elif change.get('deleted_file', False):
            return 'deleted'
        elif change.get('renamed_file', False):
            return 'renamed'
        else:
            return 'modified'
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file path."""
        if not file_path:
            return 'unknown'
        
        extension = Path(file_path).suffix.lower()
        
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.vue': 'vue',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'cpp',
            '.h': 'cpp',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.sql': 'sql',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml'
        }
        
        return language_map.get(extension, 'unknown')
    
    def _parse_diff(self, diff_content: str, file_analysis: Dict[str, Any]) -> None:
        """Parse diff content to extract line changes."""
        lines = diff_content.split('\n')
        current_line_new = 0
        current_line_old = 0
        
        for line in lines:
            if line.startswith('@@'):
                # Parse hunk header
                match = re.search(r'@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@', line)
                if match:
                    current_line_old = int(match.group(1))
                    current_line_new = int(match.group(3))
                continue
            
            if line.startswith('+') and not line.startswith('+++'):
                file_analysis['lines_added'] += 1
                file_analysis['modified_lines'].append({
                    'type': 'added',
                    'line_number': current_line_new,
                    'content': line[1:]  # Remove + prefix
                })
                current_line_new += 1
            elif line.startswith('-') and not line.startswith('---'):
                file_analysis['lines_removed'] += 1
                file_analysis['modified_lines'].append({
                    'type': 'removed',
                    'line_number': current_line_old,
                    'content': line[1:]  # Remove - prefix
                })
                current_line_old += 1
            elif line.startswith(' '):
                # Context line
                file_analysis['context_lines'].append({
                    'line_number_old': current_line_old,
                    'line_number_new': current_line_new,
                    'content': line[1:]  # Remove space prefix
                })
                current_line_old += 1
                current_line_new += 1
    
    def _extract_code_elements(self, file_analysis: Dict[str, Any], code_changes: Dict[str, Any]) -> None:
        """Extract functions and classes from file changes."""
        if not file_analysis['is_code_file']:
            return
        
        language = file_analysis['language']
        
        # Extract from added/modified lines
        for line_info in file_analysis['modified_lines']:
            if line_info['type'] == 'added':
                content = line_info['content'].strip()
                
                # Extract functions
                functions = self._extract_functions_from_line(content, language)
                for func in functions:
                    code_changes['new_functions'].append({
                        'name': func,
                        'file_path': file_analysis['file_path'],
                        'line_number': line_info['line_number'],
                        'language': language
                    })
                
                # Extract classes
                classes = self._extract_classes_from_line(content, language)
                for cls in classes:
                    code_changes['new_classes'].append({
                        'name': cls,
                        'file_path': file_analysis['file_path'],
                        'line_number': line_info['line_number'],
                        'language': language
                    })
    
    def _extract_functions_from_line(self, line: str, language: str) -> List[str]:
        """Extract function names from a line of code."""
        functions = []
        pattern = self.function_patterns.get(language)
        
        if pattern:
            matches = re.findall(pattern, line)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle multiple groups
                    func_name = next((m for m in match if m), None)
                else:
                    func_name = match
                
                if func_name and func_name.isidentifier():
                    functions.append(func_name)
        
        return functions
    
    def _extract_classes_from_line(self, line: str, language: str) -> List[str]:
        """Extract class names from a line of code."""
        classes = []
        pattern = self.class_patterns.get(language)
        
        if pattern:
            matches = re.findall(pattern, line)
            for match in matches:
                if isinstance(match, str) and match.isidentifier():
                    classes.append(match)
        
        return classes
    
    def _calculate_complexity_score(self, analysis: Dict[str, Any]) -> int:
        """Calculate complexity score for the MR."""
        score = 0
        
        # File count factor
        files_count = analysis['impact_analysis']['files_count']
        score += min(files_count * 2, 20)  # Max 20 points
        
        # Lines changed factor
        lines_changed = analysis['impact_analysis']['lines_added'] + analysis['impact_analysis']['lines_removed']
        score += min(lines_changed // 10, 30)  # Max 30 points
        
        # Code elements factor
        code_changes = analysis['code_changes']
        new_elements = len(code_changes['new_functions']) + len(code_changes['new_classes'])
        score += min(new_elements * 3, 25)  # Max 25 points
        
        # File type diversity
        languages = set()
        for change in analysis['file_changes']:
            if change['language'] != 'unknown':
                languages.add(change['language'])
        score += min(len(languages) * 5, 25)  # Max 25 points
        
        return min(score, 100)  # Cap at 100
    
    def _identify_risk_factors(self, analysis: Dict[str, Any]) -> List[str]:
        """Identify potential risk factors in the MR."""
        risks = []
        
        # Large MR
        if analysis['impact_analysis']['files_count'] > 20:
            risks.append("Large number of files changed (>20)")
        
        if analysis['impact_analysis']['lines_added'] + analysis['impact_analysis']['lines_removed'] > 500:
            risks.append("Large number of lines changed (>500)")
        
        # High complexity
        if analysis['impact_analysis']['complexity_score'] > 75:
            risks.append("High complexity score")
        
        # Critical files
        critical_patterns = [
            r'.*\.sql$', r'.*migration.*', r'.*config.*', 
            r'.*security.*', r'.*auth.*', r'.*password.*'
        ]
        
        for change in analysis['file_changes']:
            file_path = change['file_path'].lower()
            for pattern in critical_patterns:
                if re.match(pattern, file_path):
                    risks.append(f"Critical file modified: {change['file_path']}")
                    break
        
        # Many new functions/classes
        code_changes = analysis['code_changes']
        new_elements = len(code_changes['new_functions']) + len(code_changes['new_classes'])
        if new_elements > 10:
            risks.append(f"Many new code elements ({new_elements})")
        
        return risks
    
    def _generate_rag_context(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate context using RAG system for review with detailed debug logging."""
        if not self.rag_system:
            logger.debug("🔍 No RAG system available, skipping context generation")
            return []
        
        logger.debug("🧠 Starting RAG context generation...")
        context_queries = []
        
        # Generate queries for new functions
        new_functions = analysis['code_changes']['new_functions']
        logger.debug(f"🔍 Found {len(new_functions)} new functions for RAG queries")
        
        for func in new_functions:
            query = f"functions similar to {func['name']} in {func['language']}"
            context_queries.append({
                'query': query,
                'type': 'function_similarity',
                'element': func
            })
            logger.debug(f"🔍 Added function query: {query}")
        
        # Generate queries for modified files
        code_files = [change for change in analysis['file_changes'] if change['is_code_file']]
        logger.debug(f"🔍 Found {len(code_files)} code files, analyzing first 5...")
        
        for change in code_files[:5]:  # Limit to first 5 files
            file_name = Path(change['file_path']).stem
            query = f"code patterns in {file_name} {change['language']}"
            context_queries.append({
                'query': query,
                'type': 'file_context',
                'element': change
            })
            logger.debug(f"🔍 Added file query: {query}")
        
        logger.debug(f"🔍 Generated {len(context_queries)} RAG queries, executing first 10...")
        
        # Execute queries and collect results
        results = []
        for i, query_info in enumerate(context_queries[:10]):  # Limit to 10 queries
            try:
                logger.debug(f"🔍 Executing RAG query {i+1}/10: {query_info['query']}")
                
                # Use the appropriate method based on RAG system type
                if hasattr(self.rag_system, 'search_code'):
                    rag_result = self.rag_system.search_code(query_info['query'], n_results=3)
                elif hasattr(self.rag_system, 'query_codebase'):
                    rag_result = self.rag_system.query_codebase(query_info['query'])
                else:
                    logger.warning(f"🔍 RAG system doesn't have expected search methods")
                    continue
                
                if rag_result and rag_result.get('hits'):
                    hits_count = len(rag_result['hits']['hits']) if 'hits' in rag_result.get('hits', {}) else len(rag_result.get('hits', []))
                    logger.debug(f"🔍 RAG query returned {hits_count} results")
                    
                    results.append({
                        'query': query_info['query'],
                        'type': query_info['type'],
                        'element': query_info['element'],
                        'rag_results': rag_result['hits']
                    })
                    
                    # Log first result for debugging
                    if hits_count > 0 and logger.level <= logging.DEBUG:
                        first_hit = rag_result['hits']['hits'][0] if 'hits' in rag_result.get('hits', {}) else rag_result['hits'][0]
                        source = first_hit.get('_source', {})
                        file_path = source.get('file_path', 'unknown')
                        logger.debug(f"🔍 First result from: {file_path}")
                else:
                    logger.debug(f"🔍 No results for query: {query_info['query']}")
                    
            except Exception as e:
                logger.warning(f"🔍 RAG query failed for '{query_info['query']}': {e}")
                logger.debug(f"🔍 RAG error details:", exc_info=True)
        
        logger.debug(f"🔍 RAG context generation complete. Found {len(results)} relevant contexts")
        return results
    
    def generate_analysis_summary(self, analysis: Dict[str, Any]) -> str:
        """Generate a human-readable summary of the analysis."""
        mr_info = analysis['mr_info']
        impact = analysis['impact_analysis']
        
        summary = f"""# MR Analysis Summary

## Basic Information
- **Title**: {mr_info['title']}
- **Author**: {mr_info['author']}
- **Source**: {mr_info['source_branch']} → {mr_info['target_branch']}

## Impact Analysis
- **Files Changed**: {impact['files_count']}
- **Lines Added**: {impact['lines_added']}
- **Lines Removed**: {impact['lines_removed']}
- **Complexity Score**: {impact['complexity_score']}/100

## Code Changes
- **New Functions**: {len(analysis['code_changes']['new_functions'])}
- **New Classes**: {len(analysis['code_changes']['new_classes'])}

## Risk Factors
"""
        
        if impact['risk_factors']:
            for risk in impact['risk_factors']:
                summary += f"- ⚠️ {risk}\n"
        else:
            summary += "- ✅ No significant risk factors identified\n"
        
        return summary