#!/usr/bin/env python3
"""
Review Generator for GitLab MR Integration

Generates intelligent code review comments using analysis and RAG context.
"""

import logging
from typing import Dict, List, Any
from pathlib import Path
import requests
import json
import time

logger = logging.getLogger(__name__)


class ReviewGenerator:
    """Generates intelligent code review comments."""
    
    def __init__(self, rag_system=None, ollama_host: str = None):
        """
        Initialize review generator.
        
        Args:
            rag_system: CodeRAG system instance
            ollama_host: Ollama server host for LLM generation
        """
        self.rag_system = rag_system
        self.ollama_host = ollama_host or "http://host.docker.internal:11434"
        
        # Review templates
        self.templates = {
            'general': self._load_template('general'),
            'security': self._load_template('security'),
            'performance': self._load_template('performance'),
            'python': self._load_template('python'),
            'javascript': self._load_template('javascript'),
            'typescript': self._load_template('javascript'),  # Use JS template for TS
            'java': self._load_template('general'),  # Fallback to general
            'go': self._load_template('general'),    # Fallback to general
            'rust': self._load_template('general')   # Fallback to general
        }
    
    def _load_template(self, template_name: str) -> str:
        """Load review template from file or use default."""
        try:
            template_path = Path(__file__).parent / 'templates' / f'{template_name}.md'
            if template_path.exists():
                with open(template_path, 'r') as f:
                    return f.read()
        except Exception as e:
            logger.warning(f"Could not load template {template_name}: {e}")
        
        # Return default template
        return self._get_default_template(template_name)
    
    def _get_default_template(self, template_name: str) -> str:
        """Get default template for review type."""
        templates = {
            'general': """You are an expert code reviewer analyzing a GitLab merge request.

## MR Information:
{mr_summary}

## Code Changes Analysis:
{analysis_summary}

## Related Code Context:
{rag_context}

## Review Instructions:
1. Analyze the code changes for:
   - Code quality and best practices
   - Potential bugs or issues
   - Architecture and design patterns
   - Maintainability and readability

2. Provide constructive feedback with:
   - Specific line-by-line comments when relevant
   - Suggestions for improvement
   - Praise for good practices
   - Questions for clarification if needed

3. Format your response as:
   - **Summary**: Overall assessment
   - **Detailed Comments**: Specific feedback
   - **Recommendations**: Actionable suggestions

Generate a thorough but concise code review:""",

            'security': """You are a security-focused code reviewer analyzing a GitLab merge request.

## MR Information:
{mr_summary}

## Code Changes Analysis:
{analysis_summary}

## Related Code Context:
{rag_context}

## Security Review Focus:
1. Look for security vulnerabilities:
   - SQL injection risks
   - XSS vulnerabilities
   - Authentication/authorization issues
   - Input validation problems
   - Sensitive data exposure

2. Check for security best practices:
   - Proper error handling
   - Secure configuration
   - Cryptographic implementations
   - Access control mechanisms

Generate a security-focused code review:""",

            'performance': """You are a performance-focused code reviewer analyzing a GitLab merge request.

## MR Information:
{mr_summary}

## Code Changes Analysis:
{analysis_summary}

## Related Code Context:
{rag_context}

## Performance Review Focus:
1. Identify performance issues:
   - Inefficient algorithms
   - Database query optimization
   - Memory usage patterns
   - CPU-intensive operations

2. Suggest improvements:
   - Caching strategies
   - Code optimization
   - Resource management
   - Scalability considerations

Generate a performance-focused code review:"""
        }
        
        return templates.get(template_name, templates['general'])
    
    def generate_review(self, analysis: Dict[str, Any], review_type: str = 'general', auto_detect_language: bool = True) -> Dict[str, Any]:
        """
        Generate comprehensive code review.
        
        Args:
            analysis: MR analysis results
            review_type: Type of review ('general', 'security', 'performance')
            auto_detect_language: If True, auto-detect primary language for specialized templates
            
        Returns:
            Generated review with summary and detailed comments
        """
        logger.info(f"🤖 Generating {review_type} review for MR #{analysis['mr_info']['iid']}")
        
        # Auto-detect primary language if enabled
        if auto_detect_language and review_type == 'general':
            primary_language = self._detect_primary_language(analysis)
            if primary_language and primary_language in self.templates:
                review_type = primary_language
                logger.info(f"🔍 Auto-detected primary language: {primary_language}")
        
        # Prepare context for LLM
        mr_summary = self._format_mr_summary(analysis['mr_info'])
        analysis_summary = self._format_analysis_summary(analysis)
        rag_context = self._format_rag_context(analysis.get('review_context', []))
        
        # Get template
        template = self.templates.get(review_type, self.templates['general'])
        
        # Format prompt
        prompt = template.format(
            mr_summary=mr_summary,
            analysis_summary=analysis_summary,
            rag_context=rag_context
        )
        
        try:
            # Generate review using LLM
            llm_response = self._call_llm(prompt)
            
            # Parse and structure the response
            review = self._parse_llm_response(llm_response, analysis)
            
            # Add metadata
            review['metadata'] = {
                'review_type': review_type,
                'mr_iid': analysis['mr_info']['iid'],
                'complexity_score': analysis['impact_analysis']['complexity_score'],
                'files_analyzed': analysis['impact_analysis']['files_count'],
                'generated_at': self._get_timestamp()
            }
            
            logger.info(f"✅ Review generated successfully")
            return review
            
        except Exception as e:
            logger.error(f"❌ Failed to generate review: {e}")
            return self._generate_fallback_review(analysis, review_type)
    
    def _format_mr_summary(self, mr_info: Dict[str, Any]) -> str:
        """Format MR information for LLM context."""
        return f"""
- **Title**: {mr_info['title']}
- **Author**: {mr_info['author']}
- **Branches**: {mr_info['source_branch']} → {mr_info['target_branch']}
- **Description**: {mr_info['description'][:500]}...
- **Labels**: {', '.join(mr_info['labels']) if mr_info['labels'] else 'None'}
"""
    
    def _format_analysis_summary(self, analysis: Dict[str, Any]) -> str:
        """Format analysis results for LLM context."""
        impact = analysis['impact_analysis']
        code_changes = analysis['code_changes']
        
        summary = f"""
- **Files Changed**: {impact['files_count']}
- **Lines**: +{impact['lines_added']} / -{impact['lines_removed']}
- **Complexity Score**: {impact['complexity_score']}/100
- **New Functions**: {len(code_changes['new_functions'])}
- **New Classes**: {len(code_changes['new_classes'])}
"""
        
        if impact['risk_factors']:
            summary += f"- **Risk Factors**: {'; '.join(impact['risk_factors'])}\n"
        
        # Add file details
        summary += "\n**Changed Files**:\n"
        for change in analysis['file_changes'][:10]:  # Limit to first 10 files
            summary += f"- {change['file_path']} ({change['change_type']}, {change['language']})\n"
        
        return summary
    
    def _format_rag_context(self, rag_context: List[Dict[str, Any]]) -> str:
        """Format RAG context for LLM."""
        if not rag_context:
            return "No related code context found."
        
        context_str = ""
        for ctx in rag_context[:5]:  # Limit to first 5 contexts
            context_str += f"\n**Query**: {ctx['query']}\n"
            context_str += f"**Type**: {ctx['type']}\n"
            
            for hit in ctx['rag_results'][:2]:  # Limit to 2 results per query
                source = hit['_source']
                context_str += f"- File: {source['file_path']}\n"
                if source.get('functions'):
                    context_str += f"  Functions: {', '.join(source['functions'])}\n"
                context_str += f"  Content: {source['content'][:200]}...\n"
        
        return context_str or "No specific code context available."
    
    def _call_llm(self, prompt: str) -> str:
        """Call Ollama LLM for review generation with detailed debug logging."""
        logger.debug("🤖 Starting LLM call to Ollama...")
        
        try:
            # Truncate prompt for performance if too long
            max_prompt_length = 4000
            original_length = len(prompt)
            
            if len(prompt) > max_prompt_length:
                prompt = prompt[:max_prompt_length] + "\n\n[... truncated for performance ...]"
                logger.debug(f"🔍 Prompt truncated from {original_length} to {len(prompt)} characters")
            else:
                logger.debug(f"🔍 Prompt length: {original_length} characters")
            
            # Log prompt details in debug mode
            if logger.level <= logging.DEBUG:
                logger.debug(f"🔍 Ollama host: {self.ollama_host}")
                logger.debug(f"🔍 Prompt preview (first 200 chars): {prompt[:200]}...")
            
            request_payload = {
                "model": "qwen2.5-coder",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "max_tokens": 1024,        # Reduced for faster generation
                    "num_predict": 1024,       # Match max_tokens
                    "num_ctx": 4096,          # Context window
                    "repeat_penalty": 1.1,    # Prevent repetition
                    "stop": ["```", "\n\n\n"] # Early stopping tokens
                }
            }
            
            logger.debug(f"🔍 Request options: {json.dumps(request_payload['options'], indent=2)}")
            logger.debug("🔍 Sending request to Ollama...")
            
            start_time = time.time()
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json=request_payload,
                timeout=60  # Reduced timeout for faster failure detection
            )
            
            request_time = time.time() - start_time
            logger.debug(f"🔍 Ollama response received in {request_time:.2f} seconds")
            logger.debug(f"🔍 Response status code: {response.status_code}")
            
            response.raise_for_status()
            result = response.json()
            
            generated_text = result.get('response', '')
            logger.debug(f"🔍 Generated text length: {len(generated_text)} characters")
            
            if logger.level <= logging.DEBUG and generated_text:
                logger.debug(f"🔍 Generated text preview (first 200 chars): {generated_text[:200]}...")
            
            if 'eval_count' in result:
                logger.debug(f"🔍 Tokens evaluated: {result.get('eval_count', 0)}")
            if 'eval_duration' in result:
                eval_duration = result.get('eval_duration', 0) / 1_000_000_000  # Convert to seconds
                logger.debug(f"🔍 Evaluation duration: {eval_duration:.2f} seconds")
            
            logger.debug("✅ LLM call completed successfully")
            return generated_text
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
    
    def _parse_llm_response(self, llm_response: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Parse LLM response into structured review."""
        # Try to extract structured sections
        sections = self._extract_sections(llm_response)
        
        # Generate line-specific comments
        line_comments = self._generate_line_comments(analysis, llm_response)
        
        return {
            'summary': sections.get('summary', llm_response[:500] + '...'),
            'detailed_comments': sections.get('detailed_comments', ''),
            'recommendations': sections.get('recommendations', ''),
            'line_comments': line_comments,
            'overall_assessment': self._assess_mr_risk(analysis),
            'full_response': llm_response
        }
    
    def _extract_sections(self, response: str) -> Dict[str, str]:
        """Extract structured sections from LLM response."""
        sections = {}
        current_section = None
        content = []
        
        for line in response.split('\n'):
            line = line.strip()
            
            # Look for section headers
            if line.startswith('**Summary**') or line.startswith('## Summary'):
                if current_section and content:
                    sections[current_section] = '\n'.join(content).strip()
                current_section = 'summary'
                content = []
            elif line.startswith('**Detailed Comments**') or line.startswith('## Detailed Comments'):
                if current_section and content:
                    sections[current_section] = '\n'.join(content).strip()
                current_section = 'detailed_comments'
                content = []
            elif line.startswith('**Recommendations**') or line.startswith('## Recommendations'):
                if current_section and content:
                    sections[current_section] = '\n'.join(content).strip()
                current_section = 'recommendations'
                content = []
            else:
                if current_section:
                    content.append(line)
        
        # Add final section
        if current_section and content:
            sections[current_section] = '\n'.join(content).strip()
        
        return sections
    
    def _generate_line_comments(self, analysis: Dict[str, Any], llm_response: str) -> List[Dict[str, Any]]:
        """Generate line-specific comments based on analysis."""
        line_comments = []
        
        # Focus on high-risk changes
        for change in analysis['file_changes']:
            if not change['is_code_file']:
                continue
            
            # Comment on large functions
            for line_info in change['modified_lines']:
                if line_info['type'] == 'added' and len(line_info['content']) > 100:
                    line_comments.append({
                        'file_path': change['file_path'],
                        'line_number': line_info['line_number'],
                        'comment': "Consider breaking down this long line for better readability.",
                        'type': 'suggestion'
                    })
        
        # Add comments for new functions (limit to first 5)
        for func in analysis['code_changes']['new_functions'][:5]:
            line_comments.append({
                'file_path': func['file_path'],
                'line_number': func['line_number'],
                'comment': f"New function `{func['name']}` - consider adding documentation and tests.",
                'type': 'suggestion'
            })
        
        return line_comments
    
    def _assess_mr_risk(self, analysis: Dict[str, Any]) -> str:
        """Assess overall MR risk level."""
        score = analysis['impact_analysis']['complexity_score']
        risk_count = len(analysis['impact_analysis']['risk_factors'])
        
        if score > 75 or risk_count > 3:
            return "HIGH_RISK"
        elif score > 50 or risk_count > 1:
            return "MEDIUM_RISK"
        else:
            return "LOW_RISK"
    
    def _generate_fallback_review(self, analysis: Dict[str, Any], review_type: str) -> Dict[str, Any]:
        """Generate fallback review when LLM fails."""
        mr_info = analysis['mr_info']
        impact = analysis['impact_analysis']
        
        summary = f"""
# Code Review for MR #{mr_info['iid']}

## Summary
This merge request modifies {impact['files_count']} files with {impact['lines_added']} additions and {impact['lines_removed']} deletions.

Complexity Score: {impact['complexity_score']}/100

## Key Points
- Changes span {len(set(change['language'] for change in analysis['file_changes']))} programming languages
- {len(analysis['code_changes']['new_functions'])} new functions added
- {len(analysis['code_changes']['new_classes'])} new classes added

## Recommendations
- Review for adherence to coding standards
- Ensure adequate test coverage
- Verify documentation is updated
"""
        
        if impact['risk_factors']:
            summary += "\n## Risk Factors\n"
            for risk in impact['risk_factors']:
                summary += f"- {risk}\n"
        
        return {
            'summary': summary,
            'detailed_comments': 'Detailed analysis unavailable - please review manually.',
            'recommendations': 'Standard code review practices apply.',
            'line_comments': [],
            'overall_assessment': self._assess_mr_risk(analysis),
            'full_response': summary,
            'metadata': {
                'review_type': review_type,
                'mr_iid': analysis['mr_info']['iid'],
                'fallback': True,
                'generated_at': self._get_timestamp()
            }
        }
    
    def _detect_primary_language(self, analysis: Dict[str, Any]) -> str:
        """Detect the primary programming language in the MR."""
        language_counts = {}
        
        # Count lines changed by language
        for change in analysis['file_changes']:
            language = change.get('language', 'unknown')
            if language != 'unknown':
                lines_changed = change.get('lines_added', 0) + change.get('lines_removed', 0)
                language_counts[language] = language_counts.get(language, 0) + lines_changed
        
        if not language_counts:
            return None
        
        # Return language with most changes
        primary_language = max(language_counts, key=language_counts.get)
        
        # Map to template names
        language_mapping = {
            'python': 'python',
            'javascript': 'javascript',
            'typescript': 'javascript',
            'java': 'java',
            'go': 'go',
            'rust': 'rust'
        }
        
        return language_mapping.get(primary_language)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def format_for_gitlab(self, review: Dict[str, Any]) -> str:
        """Format review for posting to GitLab."""
        mr_iid = review['metadata']['mr_iid']
        assessment = review['overall_assessment']
        
        # Choose emoji based on risk assessment
        risk_emoji = {
            'LOW_RISK': '✅',
            'MEDIUM_RISK': '⚠️',
            'HIGH_RISK': '🚨'
        }
        
        gitlab_review = f"""# 🤖 Automated Code Review {risk_emoji.get(assessment, '📋')}

## Summary
{review['summary']}

## Detailed Analysis
{review['detailed_comments']}

## Recommendations
{review['recommendations']}

---
*Generated by CodeRAG GitLab Integration - Review Type: {review['metadata']['review_type']}*
"""
        
        return gitlab_review