"""
GitHub Service - Fetches issue data from GitHub API.

Features:
- Async HTTP calls using HTTPX for performance
- Comprehensive edge case handling:
  - Private repositories (403)
  - Non-existent issues (404)
  - Rate limiting (429)
  - Long content truncation (>50k chars)
- Optional GitHub token for higher rate limits
"""

import os
import logging
from typing import Optional, List

import httpx

from app.models import GitHubIssueData, GitHubComment

# Configure logging
logger = logging.getLogger(__name__)

# Constants
GITHUB_API_BASE = "https://api.github.com"
MAX_CONTENT_LENGTH = 50000  # 50k character limit for LLM context
REQUEST_TIMEOUT = 30.0  # 30 seconds timeout


class GitHubServiceError(Exception):
    """Custom exception for GitHub service errors."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class GitHubService:
    """
    Service for interacting with the GitHub API.
    Handles issue fetching with comprehensive error handling.
    """

    def __init__(self):
        """Initialize the GitHub service with optional authentication."""
        self.token = os.getenv("GITHUB_TOKEN")  # Optional: for higher rate limits
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Seedling-Issue-Assistant/1.0"
        }
        
        # Add auth header if token is provided
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
            logger.info("GitHub Service initialized with authentication")
        else:
            logger.info("GitHub Service initialized without authentication (rate limits apply)")

    async def _make_request(self, url: str) -> dict:
        """
        Make an async HTTP request to the GitHub API.
        
        Args:
            url: Full API URL
            
        Returns:
            dict: JSON response data
            
        Raises:
            GitHubServiceError: For various API errors
        """
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            try:
                response = await client.get(url, headers=self.headers)
                
                # Handle specific error codes
                if response.status_code == 404:
                    raise GitHubServiceError(
                        "Repository or issue not found. Please check the URL and issue number.",
                        status_code=404
                    )
                elif response.status_code == 403:
                    # Could be rate limit or private repo
                    if "rate limit" in response.text.lower():
                        raise GitHubServiceError(
                            "GitHub API rate limit exceeded. Please try again later or add a GITHUB_TOKEN.",
                            status_code=403
                        )
                    else:
                        raise GitHubServiceError(
                            "Access denied. This might be a private repository.",
                            status_code=403
                        )
                elif response.status_code == 429:
                    raise GitHubServiceError(
                        "Too many requests. Please wait a moment and try again.",
                        status_code=429
                    )
                elif response.status_code != 200:
                    raise GitHubServiceError(
                        f"GitHub API error: {response.status_code}",
                        status_code=response.status_code
                    )
                
                return response.json()
                
            except httpx.TimeoutException:
                raise GitHubServiceError(
                    "Request to GitHub timed out. Please try again.",
                    status_code=408
                )
            except httpx.RequestError as e:
                raise GitHubServiceError(
                    f"Network error when connecting to GitHub: {str(e)}",
                    status_code=500
                )

    def _truncate_content(self, content: str, max_length: int = MAX_CONTENT_LENGTH) -> tuple[str, bool]:
        """
        Truncate content if it exceeds maximum length.
        
        Args:
            content: The content to potentially truncate
            max_length: Maximum allowed length
            
        Returns:
            tuple: (truncated_content, was_truncated)
        """
        if len(content) <= max_length:
            return content, False
        
        # Truncate and add indicator
        truncated = content[:max_length - 100]  # Leave room for truncation message
        truncated += "\n\n[... Content truncated due to length ...]"
        return truncated, True

    async def _fetch_comments(self, owner: str, repo: str, issue_number: int) -> List[GitHubComment]:
        """
        Fetch comments for a specific issue.
        
        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            
        Returns:
            List[GitHubComment]: List of comments
        """
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        
        try:
            comments_data = await self._make_request(url)
            
            comments = []
            for comment in comments_data[:20]:  # Limit to 20 comments
                comments.append(GitHubComment(
                    author=comment.get("user", {}).get("login", "unknown"),
                    body=comment.get("body", ""),
                    created_at=comment.get("created_at", "")
                ))
            
            return comments
            
        except GitHubServiceError as e:
            # Log but don't fail if comments can't be fetched
            logger.warning(f"Could not fetch comments: {e.message}")
            return []

    async def fetch_issue(self, owner: str, repo: str, issue_number: int) -> GitHubIssueData:
        """
        Fetch a GitHub issue with its comments.
        
        Args:
            owner: Repository owner (e.g., "facebook")
            repo: Repository name (e.g., "react")
            issue_number: Issue number
            
        Returns:
            GitHubIssueData: Structured issue data
            
        Raises:
            GitHubServiceError: For API errors
        """
        logger.info(f"Fetching issue #{issue_number} from {owner}/{repo}")
        
        # Fetch the issue
        issue_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}"
        issue_data = await self._make_request(issue_url)
        
        # Check if this is actually a pull request
        if "pull_request" in issue_data:
            logger.info("Note: This issue is actually a pull request")
        
        # Fetch comments
        comments = await self._fetch_comments(owner, repo, issue_number)
        
        # Extract and process data
        title = issue_data.get("title", "")
        body = issue_data.get("body") or ""
        
        # Calculate total content length for truncation check
        total_content = title + body + " ".join([c.body for c in comments])
        was_truncated = len(total_content) > MAX_CONTENT_LENGTH
        
        # Truncate body if necessary
        if was_truncated:
            body, _ = self._truncate_content(body, MAX_CONTENT_LENGTH // 2)
            # Also limit comments
            remaining_length = MAX_CONTENT_LENGTH - len(title) - len(body)
            truncated_comments = []
            current_length = 0
            
            for comment in comments:
                if current_length + len(comment.body) > remaining_length:
                    # Truncate this comment and stop
                    truncated_body = comment.body[:remaining_length - current_length - 50]
                    truncated_comments.append(GitHubComment(
                        author=comment.author,
                        body=truncated_body + "...",
                        created_at=comment.created_at
                    ))
                    break
                truncated_comments.append(comment)
                current_length += len(comment.body)
            
            comments = truncated_comments
            logger.info(f"Content truncated from {len(total_content)} to ~{MAX_CONTENT_LENGTH} chars")
        
        # Extract labels
        labels = [label.get("name", "") for label in issue_data.get("labels", [])]
        
        return GitHubIssueData(
            title=title,
            body=body if body else None,
            state=issue_data.get("state", "unknown"),
            labels=labels,
            comments=comments,
            author=issue_data.get("user", {}).get("login", "unknown"),
            created_at=issue_data.get("created_at", ""),
            html_url=issue_data.get("html_url", ""),
            comment_count=issue_data.get("comments", 0),
            was_truncated=was_truncated
        )

    async def health_check(self) -> bool:
        """
        Verify GitHub API connectivity.
        
        Returns:
            bool: True if API is accessible
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{GITHUB_API_BASE}/rate_limit",
                    headers=self.headers
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"GitHub health check failed: {e}")
            return False


# Singleton instance
_github_service: Optional[GitHubService] = None


def get_github_service() -> GitHubService:
    """
    Get or create the GitHub service singleton.
    """
    global _github_service
    if _github_service is None:
        _github_service = GitHubService()
    return _github_service
