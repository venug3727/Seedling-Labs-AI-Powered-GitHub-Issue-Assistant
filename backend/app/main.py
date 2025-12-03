"""
FastAPI Application Entry Point.

This is the main entry point for the GitHub Issue Assistant API.
Configures CORS, logging, and mounts all routes.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.api import router

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Runs startup and shutdown logic.
    """
    # Startup
    logger.info("🚀 Starting GitHub Issue Assistant API...")
    
    # Validate required environment variables
    if not os.getenv("GEMINI_API_KEY"):
        logger.warning("⚠️  GEMINI_API_KEY not set - LLM analysis will fail!")
    else:
        logger.info("✅ GEMINI_API_KEY configured")
    
    if os.getenv("GITHUB_TOKEN"):
        logger.info("✅ GITHUB_TOKEN configured (higher rate limits)")
    else:
        logger.info("ℹ️  GITHUB_TOKEN not set (using unauthenticated rate limits)")
    
    logger.info("✅ API ready to accept requests")
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down GitHub Issue Assistant API...")


# Create FastAPI application
app = FastAPI(
    title="GitHub Issue Assistant API",
    description="""
    AI-powered GitHub issue analysis service.
    
    ## Features
    - Fetches GitHub issue data (title, body, comments)
    - AI-powered analysis using Google Gemini
    - Structured JSON output with priority scoring
    
    ## Endpoints
    - `POST /api/analyze` - Analyze a GitHub issue
    - `GET /api/health` - Health check
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
# In production, you would restrict this to specific origins
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "GitHub Issue Assistant API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or default to 8000
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # Enable auto-reload for development
        log_level="info"
    )
