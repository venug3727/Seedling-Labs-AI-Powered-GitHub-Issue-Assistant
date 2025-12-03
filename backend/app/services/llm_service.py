"""
LLM Service - The "Brain" of the Issue Assistant.

Uses an Agentic approach with:
- Persona: Senior Technical Product Manager
- Few-shot prompting: 2 examples for reliable JSON output
- Strict JSON schema enforcement
- Smart caching for latency & cost optimization
- Confidence scoring for AI transparency
- Draft response generation for agentic assistance
- Gemini 2.0 Flash for fast, cost-effective analysis
"""

import json
import os
import logging
import hashlib
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta

import google.generativeai as genai

from app.models import GitHubIssueData, IssueAnalysis

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# SMART CACHE - Cost & Latency Optimization
# ============================================================================
class AnalysisCache:
    """
    In-memory cache for issue analysis results.
    Saves API costs and reduces latency for repeated analyses.
    """
    def __init__(self, ttl_minutes: int = 60):
        self._cache: Dict[str, Tuple[IssueAnalysis, datetime]] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
    
    def _generate_key(self, repo_url: str, issue_number: int, issue_updated: str) -> str:
        """Generate a unique cache key including issue update time for freshness."""
        raw_key = f"{repo_url}:{issue_number}:{issue_updated}"
        return hashlib.md5(raw_key.encode()).hexdigest()
    
    def get(self, repo_url: str, issue_number: int, issue_updated: str) -> Optional[IssueAnalysis]:
        """Retrieve cached analysis if available and not expired."""
        key = self._generate_key(repo_url, issue_number, issue_updated)
        if key in self._cache:
            analysis, cached_at = self._cache[key]
            if datetime.now() - cached_at < self._ttl:
                logger.info(f"Cache HIT for {repo_url} #{issue_number}")
                return analysis
            else:
                # Expired, remove from cache
                del self._cache[key]
                logger.info(f"Cache EXPIRED for {repo_url} #{issue_number}")
        return None
    
    def set(self, repo_url: str, issue_number: int, issue_updated: str, analysis: IssueAnalysis):
        """Store analysis result in cache."""
        key = self._generate_key(repo_url, issue_number, issue_updated)
        self._cache[key] = (analysis, datetime.now())
        logger.info(f"Cache SET for {repo_url} #{issue_number}")
    
    def clear(self):
        """Clear all cached entries."""
        self._cache.clear()
        logger.info("Cache cleared")


# Global cache instance
_analysis_cache = AnalysisCache(ttl_minutes=60)


# ============================================================================
# SYSTEM PROMPT - Agentic "Product Manager" Persona
# ============================================================================
SYSTEM_PROMPT = """You are a Senior Technical Product Manager at a fast-paced tech startup.

Your role is to analyze GitHub issues and provide structured, actionable insights that help engineering teams prioritize their backlog effectively.

## Your Analysis Framework:

### Priority Scoring (1-5):
- **5 (Critical)**: Production crashes, security vulnerabilities, data loss, blocking issues affecting many users
- **4 (High)**: Major bugs affecting core functionality, significant performance degradation, high user impact
- **3 (Medium)**: Non-critical bugs, moderate UX issues, features with clear business value
- **2 (Low)**: Minor improvements, nice-to-haves, edge cases affecting few users
- **1 (Minimal)**: Typos, cosmetic issues, documentation fixes with low impact

### Issue Type Classification:
- **bug**: Something is broken or not working as expected
- **feature_request**: New functionality or enhancement request
- **documentation**: Docs improvements, typos, clarifications
- **question**: User seeking help or clarification
- **other**: Anything that doesn't fit above categories

### Confidence Scoring (0.0-1.0):
Rate your confidence in this analysis:
- **0.9-1.0**: Very clear issue with obvious classification and priority
- **0.7-0.89**: Reasonably confident, but some ambiguity exists
- **0.5-0.69**: Moderate uncertainty, limited context available
- **Below 0.5**: Low confidence, issue is vague or conflicting information

### Draft Response Guidelines:
Write a professional, empathetic response that:
- Thanks the user for reporting
- Acknowledges the issue briefly
- Indicates next steps or timeline expectations
- Maintains a helpful, supportive tone
- Is concise (2-4 sentences)

## Output Requirements:
You MUST respond with ONLY valid JSON. No markdown, no explanations, just the JSON object.

## JSON Schema:
{
    "summary": "string - One clear sentence summarizing the issue",
    "type": "string - One of: bug, feature_request, documentation, question, other",
    "priority_score": "integer - 1 to 5",
    "priority_justification": "string - Brief reasoning for the score",
    "suggested_labels": ["array", "of", "2-5", "labels"],
    "potential_impact": "string - Impact on users, especially for bugs",
    "confidence_score": "float - 0.0 to 1.0, your confidence in this analysis",
    "draft_response": "string - A polite, professional response to post on GitHub"
}
"""

# ============================================================================
# FEW-SHOT EXAMPLES - Teaching the LLM expected behavior
# ============================================================================
FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": """Analyze this GitHub issue:

Title: App crashes on login when using SSO
Body: After the latest update (v2.3.1), clicking "Sign in with Google" causes the entire app to crash. This is happening on both iOS and Android. We have several enterprise customers who rely on SSO and they cannot access the app at all.

Comments:
- user_jane: "Same issue here. Our team of 50 people is completely blocked."
- user_mike: "Confirmed on iOS 17.1. Stack trace shows null pointer in AuthManager."
- maintainer_alex: "Looking into this urgently."

Labels: []
State: open"""
    },
    {
        "role": "model",
        "content": """{
    "summary": "Critical app crash occurs when users attempt to sign in using Google SSO, completely blocking enterprise customers from accessing the application.",
    "type": "bug",
    "priority_score": 5,
    "priority_justification": "Production crash affecting core authentication flow, blocking multiple enterprise customers and their teams from using the product entirely.",
    "suggested_labels": ["bug", "critical", "authentication", "SSO", "regression"],
    "potential_impact": "Severe - Enterprise customers with teams of 50+ users are completely unable to access the application, causing significant business disruption and potential churn risk.",
    "confidence_score": 0.95,
    "draft_response": "Hi @user, thank you for reporting this critical issue! We've confirmed the SSO crash affecting Google sign-in and have escalated this to our highest priority. Our team is actively investigating the null pointer in AuthManager. We'll provide updates here as we make progress and aim to have a fix deployed within 24 hours."
}"""
    },
    {
        "role": "user",
        "content": """Analyze this GitHub issue:

Title: Add dark mode support
Body: It would be great if the app supported dark mode. My eyes hurt when using the app at night.

Comments:
- user_bob: "+1, would love this feature"
- user_alice: "Yes please! iOS has had system-wide dark mode for years."

Labels: ["enhancement"]
State: open"""
    },
    {
        "role": "model",
        "content": """{
    "summary": "User requests dark mode support for the application to reduce eye strain during nighttime usage.",
    "type": "feature_request",
    "priority_score": 2,
    "priority_justification": "Quality of life improvement with user interest, but not blocking any core functionality. Common feature request but requires significant UI work.",
    "suggested_labels": ["enhancement", "UI/UX", "accessibility", "good-first-issue"],
    "potential_impact": "Low to moderate - Would improve user experience for night-time users and those with light sensitivity, but no functional impact on current users.",
    "confidence_score": 0.92,
    "draft_response": "Thanks for the suggestion! Dark mode is a popular request and we've added it to our feature backlog. While we can't commit to a specific timeline yet, we appreciate the feedback and will update this issue when we have more information on implementation plans."
}"""
    }
]


class LLMService:
    """
    Service class for interacting with Google's Gemini LLM.
    Implements agentic prompt engineering for reliable issue analysis.
    Includes smart caching for cost & latency optimization.
    """

    def __init__(self):
        """Initialize the Gemini client with API key from environment."""
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is not set. "
                "Please set it in your .env file."
            )
        
        # Configure the Gemini API
        genai.configure(api_key=self.api_key)
        
        # Use Gemini 2.0 Flash - the latest fast model
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={
                "temperature": 0.3,  # Lower temperature for more consistent output
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 1500,  # Increased for draft_response
            },
            system_instruction=SYSTEM_PROMPT
        )
        
        # Reference to global cache
        self.cache = _analysis_cache
        
        logger.info("LLM Service initialized with Gemini 2.0 Flash + Smart Caching")

    def _format_issue_for_analysis(self, issue_data: GitHubIssueData) -> str:
        """
        Format GitHub issue data into a prompt-friendly string.
        Handles edge cases like empty body or no comments.
        """
        # Build the issue description
        body = issue_data.body or "(No description provided)"
        
        # Format comments
        if issue_data.comments:
            comments_text = "\n".join([
                f"- {c.author}: \"{c.body[:500]}{'...' if len(c.body) > 500 else ''}\""
                for c in issue_data.comments[:10]  # Limit to first 10 comments
            ])
        else:
            comments_text = "(No comments)"
        
        # Format existing labels
        labels = issue_data.labels if issue_data.labels else ["(none)"]
        
        # Note if content was truncated
        truncation_note = ""
        if issue_data.was_truncated:
            truncation_note = "\n\n[Note: Issue content was truncated due to length]"
        
        return f"""Analyze this GitHub issue:

Title: {issue_data.title}
Body: {body}

Comments:
{comments_text}

Labels: {labels}
State: {issue_data.state}
Author: {issue_data.author}
URL: {issue_data.html_url}{truncation_note}"""

    def _parse_llm_response(self, response_text: str) -> dict:
        """
        Parse the LLM response, handling potential formatting issues.
        Extracts JSON even if wrapped in markdown code blocks.
        """
        text = response_text.strip()
        
        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        
        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
        
        # Parse JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response was: {response_text[:500]}")
            raise ValueError(f"LLM did not return valid JSON: {e}")

    async def analyze_issue(self, issue_data: GitHubIssueData, repo_url: str = "", issue_number: int = 0) -> Tuple[IssueAnalysis, bool]:
        """
        Analyze a GitHub issue using the LLM with agentic prompting.
        Includes smart caching for cost & latency optimization.
        
        Args:
            issue_data: Structured GitHub issue data
            repo_url: Repository URL for cache key
            issue_number: Issue number for cache key
            
        Returns:
            Tuple[IssueAnalysis, bool]: (analysis result, was_cached)
            
        Raises:
            ValueError: If LLM response cannot be parsed
            Exception: For API errors
        """
        # Check cache first
        cached_result = self.cache.get(repo_url, issue_number, issue_data.created_at)
        if cached_result:
            return cached_result, True
        
        logger.info(f"Analyzing issue: {issue_data.title[:50]}... (cache miss)")
        
        # Format the issue for the LLM
        user_prompt = self._format_issue_for_analysis(issue_data)
        
        # Build conversation with few-shot examples
        chat_history = []
        
        # Add few-shot examples
        for example in FEW_SHOT_EXAMPLES:
            chat_history.append({
                "role": example["role"],
                "parts": [example["content"]]
            })
        
        try:
            # Start chat with few-shot examples (system_instruction is set in model config)
            chat = self.model.start_chat(history=chat_history)
            
            # Send the actual issue for analysis
            response = await chat.send_message_async(user_prompt)
            
            # Parse the response
            analysis_dict = self._parse_llm_response(response.text)
            
            # Validate against Pydantic model
            analysis = IssueAnalysis(**analysis_dict)
            
            # Store in cache
            self.cache.set(repo_url, issue_number, issue_data.created_at, analysis)
            
            logger.info(f"Analysis complete. Priority: {analysis.priority_score}, Type: {analysis.type}, Confidence: {analysis.confidence_score}")
            return analysis, False
            
        except Exception as e:
            logger.error(f"Error during LLM analysis: {e}")
            raise

    async def health_check(self) -> bool:
        """
        Verify the LLM service is operational.
        
        Returns:
            bool: True if service is healthy
        """
        try:
            # Simple test to verify API connectivity
            response = self.model.generate_content("Reply with 'OK' if you can read this.")
            return "OK" in response.text or len(response.text) > 0
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return False


# Singleton instance for dependency injection
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """
    Get or create the LLM service singleton.
    Implements lazy initialization pattern.
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
