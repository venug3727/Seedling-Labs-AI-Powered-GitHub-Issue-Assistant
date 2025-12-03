"""
API Routes for the GitHub Issue Assistant.

Defines all HTTP endpoints:
- POST /api/analyze - Main analysis endpoint
- GET /api/health - Health check endpoint
"""

import logging
from fastapi import APIRouter, HTTPException, Depends

from app.models import IssueRequest, AnalysisResponse, HealthResponse
from app.services.github_service import get_github_service, GitHubService, GitHubServiceError
from app.services.llm_service import get_llm_service, LLMService

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
        
        # Step 2: Analyze with LLM
        try:
            analysis = await llm_service.analyze_issue(issue_data)
            logger.info(f"Analysis complete - Priority: {analysis.priority_score}, Type: {analysis.type}")
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
            analysis=analysis
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
