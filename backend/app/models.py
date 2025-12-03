"""
Pydantic models for request/response validation.
Ensures strict type checking and automatic API documentation.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import re


class IssueRequest(BaseModel):
    """
    Request model for analyzing a GitHub issue.
    Validates repository URL format and issue number.
    """
    repo_url: str = Field(
        ...,
        description="GitHub repository URL (e.g., https://github.com/facebook/react)",
        examples=["https://github.com/facebook/react"]
    )
    issue_number: int = Field(
        ...,
        gt=0,
        description="GitHub issue number (must be positive integer)",
        examples=[1234]
    )

    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        """Validate that the URL is a valid GitHub repository URL."""
        # Clean up the URL
        v = v.strip().rstrip("/")
        
        # Pattern to match GitHub repo URLs
        pattern = r"^https?://github\.com/[\w.-]+/[\w.-]+$"
        if not re.match(pattern, v):
            raise ValueError(
                "Invalid GitHub URL. Expected format: https://github.com/owner/repo"
            )
        return v

    def get_owner_repo(self) -> tuple[str, str]:
        """Extract owner and repo name from the URL."""
        parts = self.repo_url.rstrip("/").split("/")
        return parts[-2], parts[-1]


class GitHubComment(BaseModel):
    """Model for a GitHub issue comment."""
    author: str = Field(..., description="Comment author username")
    body: str = Field(..., description="Comment body text")
    created_at: str = Field(..., description="Comment creation timestamp")


class GitHubIssueData(BaseModel):
    """
    Structured data fetched from GitHub API.
    Contains all information needed for LLM analysis.
    """
    title: str = Field(..., description="Issue title")
    body: Optional[str] = Field(None, description="Issue body/description")
    state: str = Field(..., description="Issue state (open/closed)")
    labels: List[str] = Field(default_factory=list, description="Existing labels on the issue")
    comments: List[GitHubComment] = Field(default_factory=list, description="Issue comments")
    author: str = Field(..., description="Issue author username")
    created_at: str = Field(..., description="Issue creation timestamp")
    html_url: str = Field(..., description="URL to the issue on GitHub")
    comment_count: int = Field(0, description="Total number of comments")
    was_truncated: bool = Field(False, description="Whether content was truncated due to length")


class IssueAnalysis(BaseModel):
    """
    LLM-generated analysis output.
    This is the core output format required by the assignment.
    """
    summary: str = Field(
        ...,
        description="A one-sentence summary of the user's problem or request"
    )
    type: str = Field(
        ...,
        description="Issue classification: bug, feature_request, documentation, question, or other"
    )
    priority_score: int = Field(
        ...,
        ge=1,
        le=5,
        description="Priority score from 1 (low) to 5 (critical)"
    )
    priority_justification: str = Field(
        ...,
        description="Brief justification for the priority score"
    )
    suggested_labels: List[str] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="Array of 2-5 relevant GitHub labels"
    )
    potential_impact: str = Field(
        ...,
        description="Brief sentence on potential impact on users (especially for bugs)"
    )


class AnalysisResponse(BaseModel):
    """
    Complete API response including GitHub data and LLM analysis.
    """
    success: bool = Field(..., description="Whether the analysis was successful")
    issue_data: Optional[GitHubIssueData] = Field(None, description="Fetched GitHub issue data")
    analysis: Optional[IssueAnalysis] = Field(None, description="LLM-generated analysis")
    error: Optional[str] = Field(None, description="Error message if analysis failed")


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="API version")
