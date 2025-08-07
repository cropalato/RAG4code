#!/usr/bin/env python3
"""
GitLab API Client for CodeRAG Integration

Handles authentication, MR fetching, and review posting to GitLab.
"""

import os
import logging
import requests
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse
import json

logger = logging.getLogger(__name__)


class GitLabClient:
    """GitLab API client for merge request operations."""
    
    def __init__(self, gitlab_url: str = None, token: str = None):
        """
        Initialize GitLab client.
        
        Args:
            gitlab_url: GitLab instance URL (e.g., https://gitlab.com)
            token: GitLab personal access token
        """
        self.gitlab_url = gitlab_url or os.getenv('GITLAB_URL', 'https://gitlab.com')
        self.token = token or os.getenv('GITLAB_TOKEN')
        
        if not self.token:
            raise ValueError("GitLab token is required. Set GITLAB_TOKEN environment variable or pass token parameter.")
        
        # Ensure URL has proper format
        if not self.gitlab_url.startswith(('http://', 'https://')):
            self.gitlab_url = f"https://{self.gitlab_url}"
        
        if not self.gitlab_url.endswith('/'):
            self.gitlab_url += '/'
            
        self.api_url = urljoin(self.gitlab_url, 'api/v4/')
        
        # Setup session
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'User-Agent': 'CodeRAG-GitLab-Integration/1.0.0'
        })
        
        logger.info(f"Initialized GitLab client for {self.gitlab_url}")
        
        # Validate connection
        self._validate_connection()
    
    def _validate_connection(self) -> bool:
        """Validate GitLab connection and token."""
        try:
            response = self.session.get(f"{self.api_url}user")
            response.raise_for_status()
            
            user_info = response.json()
            logger.info(f"✅ Connected to GitLab as user: {user_info.get('username', 'Unknown')}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to connect to GitLab: {e}")
            raise ConnectionError(f"Cannot connect to GitLab: {e}")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated request to GitLab API."""
        url = urljoin(self.api_url, endpoint)
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GitLab API request failed: {method} {endpoint} - {e}")
            raise
    
    def get_project(self, project_id: str) -> Dict[str, Any]:
        """
        Get project information.
        
        Args:
            project_id: Project ID or path (e.g., "group/project")
            
        Returns:
            Project information dictionary
        """
        # URL encode project path
        if '/' in project_id:
            project_id = project_id.replace('/', '%2F')
        
        response = self._make_request('GET', f"projects/{project_id}")
        return response.json()
    
    def get_merge_request(self, project_id: str, mr_iid: int) -> Dict[str, Any]:
        """
        Get merge request information.
        
        Args:
            project_id: Project ID or path
            mr_iid: Merge request IID (internal ID)
            
        Returns:
            Merge request information dictionary
        """
        if '/' in project_id:
            project_id = project_id.replace('/', '%2F')
        
        response = self._make_request('GET', f"projects/{project_id}/merge_requests/{mr_iid}")
        mr_data = response.json()
        
        logger.info(f"📋 Retrieved MR #{mr_iid}: {mr_data.get('title', 'No title')}")
        return mr_data
    
    def get_mr_changes(self, project_id: str, mr_iid: int) -> Dict[str, Any]:
        """
        Get merge request changes (diff information).
        
        Args:
            project_id: Project ID or path
            mr_iid: Merge request IID
            
        Returns:
            Changes information with diffs
        """
        if '/' in project_id:
            project_id = project_id.replace('/', '%2F')
        
        response = self._make_request('GET', f"projects/{project_id}/merge_requests/{mr_iid}/changes")
        changes_data = response.json()
        
        logger.info(f"📄 Retrieved changes for MR #{mr_iid}: {len(changes_data.get('changes', []))} files changed")
        return changes_data
    
    def get_mr_commits(self, project_id: str, mr_iid: int) -> List[Dict[str, Any]]:
        """
        Get merge request commits.
        
        Args:
            project_id: Project ID or path
            mr_iid: Merge request IID
            
        Returns:
            List of commit information
        """
        if '/' in project_id:
            project_id = project_id.replace('/', '%2F')
        
        response = self._make_request('GET', f"projects/{project_id}/merge_requests/{mr_iid}/commits")
        commits = response.json()
        
        logger.info(f"📝 Retrieved {len(commits)} commits for MR #{mr_iid}")
        return commits
    
    def get_mr_notes(self, project_id: str, mr_iid: int) -> List[Dict[str, Any]]:
        """
        Get merge request notes/comments.
        
        Args:
            project_id: Project ID or path
            mr_iid: Merge request IID
            
        Returns:
            List of notes/comments
        """
        if '/' in project_id:
            project_id = project_id.replace('/', '%2F')
        
        response = self._make_request('GET', f"projects/{project_id}/merge_requests/{mr_iid}/notes")
        notes = response.json()
        
        logger.info(f"💬 Retrieved {len(notes)} notes for MR #{mr_iid}")
        return notes
    
    def post_mr_note(self, project_id: str, mr_iid: int, body: str) -> Dict[str, Any]:
        """
        Post a note/comment to merge request.
        
        Args:
            project_id: Project ID or path
            mr_iid: Merge request IID
            body: Comment body (Markdown supported)
            
        Returns:
            Created note information
        """
        if '/' in project_id:
            project_id = project_id.replace('/', '%2F')
        
        data = {'body': body}
        response = self._make_request('POST', f"projects/{project_id}/merge_requests/{mr_iid}/notes", json=data)
        note = response.json()
        
        logger.info(f"✅ Posted note to MR #{mr_iid}")
        return note
    
    def post_mr_line_comment(self, project_id: str, mr_iid: int, file_path: str, 
                           line_number: int, body: str, line_type: str = "new") -> Dict[str, Any]:
        """
        Post a line-specific comment to merge request.
        
        Args:
            project_id: Project ID or path
            mr_iid: Merge request IID
            file_path: Path to the file
            line_number: Line number to comment on
            body: Comment body
            line_type: "new" or "old" line type
            
        Returns:
            Created note information
        """
        if '/' in project_id:
            project_id = project_id.replace('/', '%2F')
        
        # Get the latest commit SHA for positioning
        mr_info = self.get_merge_request(project_id.replace('%2F', '/'), mr_iid)
        base_sha = mr_info['diff_refs']['base_sha']
        head_sha = mr_info['diff_refs']['head_sha']
        start_sha = mr_info['diff_refs']['start_sha']
        
        data = {
            'body': body,
            'position': {
                'position_type': 'text',
                'base_sha': base_sha,
                'start_sha': start_sha,
                'head_sha': head_sha,
                'old_path': file_path,
                'new_path': file_path,
                f'{line_type}_line': line_number
            }
        }
        
        response = self._make_request('POST', f"projects/{project_id}/merge_requests/{mr_iid}/notes", json=data)
        note = response.json()
        
        logger.info(f"✅ Posted line comment to MR #{mr_iid} at {file_path}:{line_number}")
        return note
    
    def get_project_merge_requests(self, project_id: str, state: str = "opened", 
                                  per_page: int = 20) -> List[Dict[str, Any]]:
        """
        Get merge requests for a project.
        
        Args:
            project_id: Project ID or path
            state: MR state ("opened", "closed", "merged", "all")
            per_page: Number of results per page
            
        Returns:
            List of merge requests
        """
        if '/' in project_id:
            project_id = project_id.replace('/', '%2F')
        
        params = {
            'state': state,
            'per_page': per_page,
            'order_by': 'updated_at',
            'sort': 'desc'
        }
        
        response = self._make_request('GET', f"projects/{project_id}/merge_requests", params=params)
        mrs = response.json()
        
        logger.info(f"📋 Retrieved {len(mrs)} merge requests for project {project_id}")
        return mrs
    
    def parse_mr_url(self, mr_url: str) -> tuple[str, int]:
        """
        Parse GitLab MR URL to extract project and MR IID.
        
        Args:
            mr_url: GitLab merge request URL
            
        Returns:
            Tuple of (project_path, mr_iid)
        """
        try:
            parsed = urlparse(mr_url)
            path_parts = parsed.path.strip('/').split('/')
            
            # GitLab URL format: https://gitlab.com/group/project/-/merge_requests/123
            if len(path_parts) >= 4 and path_parts[-2] == 'merge_requests':
                mr_iid = int(path_parts[-1])
                # Find project path (everything before "/-/merge_requests")
                mr_index = path_parts.index('-')
                project_path = '/'.join(path_parts[:mr_index])
                
                return project_path, mr_iid
            else:
                raise ValueError("Invalid GitLab MR URL format")
                
        except (ValueError, IndexError) as e:
            raise ValueError(f"Cannot parse GitLab MR URL '{mr_url}': {e}")
    
    def get_mr_from_url(self, mr_url: str) -> Dict[str, Any]:
        """
        Get merge request data from GitLab URL.
        
        Args:
            mr_url: GitLab merge request URL
            
        Returns:
            Merge request data with additional metadata
        """
        project_path, mr_iid = self.parse_mr_url(mr_url)
        
        # Get MR data
        mr_data = self.get_merge_request(project_path, mr_iid)
        
        # Add parsed information
        mr_data['_gitlab_client_meta'] = {
            'project_path': project_path,
            'mr_iid': mr_iid,
            'original_url': mr_url
        }
        
        return mr_data