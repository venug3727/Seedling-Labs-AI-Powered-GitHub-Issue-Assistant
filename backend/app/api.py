"""
API Routes for the GitHub Issue Assistant.

Defines all HTTP endpoints:
- POST /api/analyze - Main analysis endpoint
- POST /api/dependencies - Issue dependency graph
- POST /api/duplicates - Find duplicate issues
- POST /api/create-labels - Create GitHub labels
- POST /api/batch-analyze - Analyze multiple issues
- POST /api/similar-cross-repo - Find similar issues across repos
- GET /api/health - Health check endpoint
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.models import IssueRequest, AnalysisResponse, HealthResponse
from app.services.github_service import get_github_service, GitHubService, GitHubServiceError
from app.services.llm_service import get_llm_service, LLMService
from app.services.advanced_features import get_advanced_features_service, AdvancedFeaturesService


# Request/Response models for new endpoints
class DependencyRequest(BaseModel):
    repo_url: str
    issue_number: int
    depth: int = Field(default=1, ge=1, le=3)


class DuplicateRequest(BaseModel):
    repo_url: str
    issue_number: int
    issue_title: str
    issue_body: Optional[str] = ""


class CreateLabelsRequest(BaseModel):
    repo_url: str
    labels: List[str]
    github_token: str


class BatchAnalyzeRequest(BaseModel):
    repo_url: str
    issue_numbers: List[int] = Field(..., min_length=1, max_length=10)


class CrossRepoRequest(BaseModel):
    issue_title: str
    issue_body: Optional[str] = ""
    exclude_repo: Optional[str] = ""

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api", tags=["Issue Analysis"])


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_issue(
    request: IssueRequest,
    github_service: GitHubService = Depends(get_github_service),
    llm_service: LLMService = Depends(get_llm_service)
) -> AnalysisResponse:
    """
    Analyze a GitHub issue using AI.
    
    This endpoint:
    1. Validates the input (repo URL and issue number)
    2. Fetches issue data from GitHub API
    3. Sends to LLM for analysis
    4. Returns structured analysis
    
    Args:
        request: IssueRequest with repo_url and issue_number
        
    Returns:
        AnalysisResponse with issue data and AI analysis
        
    Raises:
        HTTPException: For validation or processing errors
    """
    logger.info(f"Received analysis request for {request.repo_url} #{request.issue_number}")
    
    try:
        # Extract owner and repo from URL
        owner, repo = request.get_owner_repo()
        logger.info(f"Parsed repository: {owner}/{repo}")
        
        # Step 1: Fetch issue data from GitHub
        try:
            issue_data = await github_service.fetch_issue(owner, repo, request.issue_number)
            logger.info(f"Successfully fetched issue: {issue_data.title[:50]}...")
        except GitHubServiceError as e:
            logger.warning(f"GitHub API error: {e.message}")
            return AnalysisResponse(
                success=False,
                error=e.message
            )
        
        # Step 2: Analyze with LLM (with caching)
        try:
            analysis, was_cached = await llm_service.analyze_issue(
                issue_data, 
                repo_url=request.repo_url, 
                issue_number=request.issue_number
            )
            cache_status = "from cache" if was_cached else "fresh analysis"
            logger.info(f"Analysis complete ({cache_status}) - Priority: {analysis.priority_score}, Type: {analysis.type}")
        except ValueError as e:
            # LLM returned invalid JSON
            logger.error(f"LLM response parsing error: {e}")
            return AnalysisResponse(
                success=False,
                issue_data=issue_data,
                error=f"AI analysis failed to produce valid output. Please try again. Details: {str(e)}"
            )
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return AnalysisResponse(
                success=False,
                issue_data=issue_data,
                error=f"AI analysis failed: {str(e)}"
            )
        
        # Step 3: Return successful response
        return AnalysisResponse(
            success=True,
            issue_data=issue_data,
            analysis=analysis,
            cached=was_cached
        )
        
    except Exception as e:
        logger.error(f"Unexpected error during analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for monitoring.
    
    Returns:
        HealthResponse with service status
    """
    return HealthResponse(
        status="healthy",
        service="GitHub Issue Assistant API",
        version="1.0.0"
    )


@router.get("/health/detailed")
async def detailed_health_check(
    github_service: GitHubService = Depends(get_github_service)
) -> dict:
    """
    Detailed health check including external service connectivity.
    
    Returns:
        dict with status of each component
    """
    github_healthy = await github_service.health_check()
    
    # Check if LLM service can be initialized (API key present)
    llm_initialized = False
    try:
        llm_service = get_llm_service()
        llm_initialized = True
    except ValueError:
        pass
    
    all_healthy = github_healthy and llm_initialized
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": {
            "api": "healthy",
            "github_api": "healthy" if github_healthy else "unhealthy",
            "llm_service": "healthy" if llm_initialized else "unhealthy (check GEMINI_API_KEY)"
        }
    }


# ==================== ADVANCED FEATURES ENDPOINTS ====================

def _parse_repo_url(repo_url: str) -> tuple[str, str]:
    """Extract owner and repo from URL."""
    parts = repo_url.strip().rstrip("/").split("/")
    return parts[-2], parts[-1]


@router.post("/dependencies")
async def get_issue_dependencies(
    request: DependencyRequest,
    advanced_service: AdvancedFeaturesService = Depends(get_advanced_features_service)
) -> dict:
    """
    Get dependency graph for an issue.
    Parses issue references (#123, fixes #456, etc.) and builds a graph.
    """
    logger.info(f"Building dependency graph for {request.repo_url} #{request.issue_number}")
    
    try:
        owner, repo = _parse_repo_url(request.repo_url)
        graph = await advanced_service.build_dependency_graph(
            owner, repo, request.issue_number, request.depth
        )
        # graph already includes 'cached' field from the service
        return {"success": True, "data": graph, "cached": graph.get("cached", False)}
    except Exception as e:
        logger.error(f"Dependency graph error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/duplicates")
async def find_duplicates(
    request: DuplicateRequest,
    advanced_service: AdvancedFeaturesService = Depends(get_advanced_features_service)
) -> dict:
    """
    Find potential duplicate issues in the repository.
    Uses semantic similarity to identify duplicates.
    """
    logger.info(f"Finding duplicates for {request.repo_url} #{request.issue_number}")
    
    try:
        owner, repo = _parse_repo_url(request.repo_url)
        duplicates, was_cached = await advanced_service.find_duplicate_issues(
            owner, repo, request.issue_number,
            request.issue_title, request.issue_body or ""
        )
        return {"success": True, "data": duplicates, "cached": was_cached}
    except Exception as e:
        logger.error(f"Duplicate detection error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/create-labels")
async def create_labels(
    request: CreateLabelsRequest,
    advanced_service: AdvancedFeaturesService = Depends(get_advanced_features_service)
) -> dict:
    """
    Create labels on GitHub repository.
    Requires user's GitHub Personal Access Token.
    """
    logger.info(f"Creating labels for {request.repo_url}")
    
    try:
        owner, repo = _parse_repo_url(request.repo_url)
        results = await advanced_service.create_github_labels(
            owner, repo, request.labels, request.github_token
        )
        return {"success": True, "data": results}
    except Exception as e:
        logger.error(f"Label creation error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/batch-analyze")
async def batch_analyze(
    request: BatchAnalyzeRequest,
    advanced_service: AdvancedFeaturesService = Depends(get_advanced_features_service),
    llm_service: LLMService = Depends(get_llm_service)
) -> dict:
    """
    Analyze multiple issues at once.
    Returns individual analyses and aggregate statistics.
    """
    logger.info(f"Batch analyzing {len(request.issue_numbers)} issues from {request.repo_url}")
    
    try:
        owner, repo = _parse_repo_url(request.repo_url)
        results = await advanced_service.batch_analyze_issues(
            owner, repo, request.issue_numbers, llm_service
        )
        return {"success": True, "data": results}
    except Exception as e:
        logger.error(f"Batch analysis error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/similar-cross-repo")
async def find_similar_cross_repo(
    request: CrossRepoRequest,
    advanced_service: AdvancedFeaturesService = Depends(get_advanced_features_service)
) -> dict:
    """
    Find similar issues across other GitHub repositories.
    Uses GitHub Search API with semantic keywords.
    """
    logger.info(f"Finding similar issues across repos for: {request.issue_title[:50]}...")
    
    try:
        results, was_cached = await advanced_service.find_similar_issues_cross_repo(
            request.issue_title,
            request.issue_body or "",
            request.exclude_repo or ""
        )
        return {"success": True, "data": results, "cached": was_cached}
    except Exception as e:
        logger.error(f"Cross-repo search error: {e}")
        return {"success": False, "error": str(e)}
