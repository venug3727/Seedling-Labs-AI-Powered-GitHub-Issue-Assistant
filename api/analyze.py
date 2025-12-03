"""
Vercel Serverless Function for GitHub Issue Analysis.
Endpoint: POST /api/analyze

Features:
- Smart caching for cost & latency optimization
- Confidence scoring for AI transparency
- Draft response generation for agentic assistance
"""

import json
import os
import logging
import re
import hashlib
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional

import google.generativeai as genai
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# SMART CACHE - Cost & Latency Optimization
# =============================================================================
class AnalysisCache:
    """In-memory cache for issue analysis results."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache: Dict[str, Tuple[dict, datetime]] = {}
            cls._instance._ttl = timedelta(minutes=60)
        return cls._instance
    
    def _generate_key(self, repo_url: str, issue_number: int, issue_updated: str) -> str:
        raw_key = f"{repo_url}:{issue_number}:{issue_updated}"
        return hashlib.md5(raw_key.encode()).hexdigest()
    
    def get(self, repo_url: str, issue_number: int, issue_updated: str) -> Optional[dict]:
        key = self._generate_key(repo_url, issue_number, issue_updated)
        if key in self._cache:
            analysis, cached_at = self._cache[key]
            if datetime.now() - cached_at < self._ttl:
                logger.info(f"Cache HIT for {repo_url} #{issue_number}")
                return analysis
            else:
                del self._cache[key]
        return None
    
    def set(self, repo_url: str, issue_number: int, issue_updated: str, analysis: dict):
        key = self._generate_key(repo_url, issue_number, issue_updated)
        self._cache[key] = (analysis, datetime.now())
        logger.info(f"Cache SET for {repo_url} #{issue_number}")


# Global cache instance
analysis_cache = AnalysisCache()

# =============================================================================
# SYSTEM PROMPT - Agentic "Product Manager" Persona
# =============================================================================
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

# Few-shot examples
FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": """Analyze this GitHub issue:

Title: App crashes on login when using SSO
Body: After the latest update (v2.3.1), clicking "Sign in with Google" causes the entire app to crash. This is happening on both iOS and Android. We have several enterprise customers who rely on SSO and they cannot access the app at all.

Comments:
- user_jane: "Same issue here. Our team of 50 people is completely blocked."
- user_mike: "Confirmed on iOS 17.1. Stack trace shows null pointer in AuthManager."

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


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_POST(self):
        """Handle POST request for issue analysis."""
        # CORS headers
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

        try:
            # Parse request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            repo_url = data.get("repo_url", "")
            issue_number = data.get("issue_number")

            if not repo_url or not issue_number:
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": "Missing repo_url or issue_number"
                }).encode())
                return

            # Extract owner/repo from URL
            match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?", repo_url)
            if not match:
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": "Invalid GitHub URL format"
                }).encode())
                return

            owner, repo = match.groups()

            # Fetch issue from GitHub
            issue_data = self._fetch_github_issue(owner, repo, issue_number)
            if "error" in issue_data:
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": issue_data["error"]
                }).encode())
                return

            # Check cache first
            cached_analysis = analysis_cache.get(repo_url, issue_number, issue_data.get("created_at", ""))
            if cached_analysis:
                self.wfile.write(json.dumps({
                    "success": True,
                    "issue_data": issue_data,
                    "analysis": cached_analysis,
                    "cached": True
                }).encode())
                return

            # Analyze with Gemini (cache miss)
            analysis = self._analyze_with_gemini(issue_data)
            if "error" in analysis:
                self.wfile.write(json.dumps({
                    "success": False,
                    "issue_data": issue_data,
                    "error": analysis["error"]
                }).encode())
                return

            # Store in cache
            analysis_cache.set(repo_url, issue_number, issue_data.get("created_at", ""), analysis)

            # Return success response
            self.wfile.write(json.dumps({
                "success": True,
                "issue_data": issue_data,
                "analysis": analysis,
                "cached": False
            }).encode())

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            self.wfile.write(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())

    def _fetch_github_issue(self, owner: str, repo: str, issue_number: int) -> dict:
        """Fetch issue data from GitHub API."""
        github_token = os.getenv("GITHUB_TOKEN")
        headers = {"Accept": "application/vnd.github.v3+json"}
        if github_token:
            headers["Authorization"] = f"token {github_token}"

        try:
            # Fetch issue
            issue_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
            with httpx.Client(timeout=30) as client:
                response = client.get(issue_url, headers=headers)

                if response.status_code == 404:
                    return {"error": "Issue not found. Please check the repository URL and issue number."}
                elif response.status_code == 403:
                    return {"error": "Access denied. This might be a private repository or rate limit exceeded."}
                elif response.status_code != 200:
                    return {"error": f"GitHub API error: {response.status_code}"}

                issue = response.json()

                # Fetch comments
                comments_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
                comments_response = client.get(comments_url, headers=headers)
                comments_data = comments_response.json() if comments_response.status_code == 200 else []

            # Format comments
            comments = [
                {"author": c.get("user", {}).get("login", "unknown"), "body": c.get("body", "")[:500]}
                for c in comments_data[:10]
            ]

            # Check for truncation
            body = issue.get("body") or ""
            was_truncated = len(body) > 50000
            if was_truncated:
                body = body[:50000] + "... [truncated]"

            return {
                "title": issue.get("title", ""),
                "body": body,
                "state": issue.get("state", "unknown"),
                "labels": [l.get("name", "") for l in issue.get("labels", [])],
                "comments": comments,
                "author": issue.get("user", {}).get("login", "unknown"),
                "created_at": issue.get("created_at", ""),
                "html_url": issue.get("html_url", ""),
                "comment_count": issue.get("comments", 0),
                "was_truncated": was_truncated
            }

        except httpx.TimeoutException:
            return {"error": "Request to GitHub timed out. Please try again."}
        except Exception as e:
            return {"error": f"Failed to fetch issue: {str(e)}"}

    def _analyze_with_gemini(self, issue_data: dict) -> dict:
        """Analyze issue with Google Gemini."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"error": "GEMINI_API_KEY not configured"}

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 1500,  # Increased for draft_response
                },
                system_instruction=SYSTEM_PROMPT
            )

            # Format issue for prompt
            comments_text = "\n".join([
                f"- {c['author']}: \"{c['body'][:300]}{'...' if len(c['body']) > 300 else ''}\""
                for c in issue_data.get("comments", [])[:5]
            ]) or "(No comments)"

            user_prompt = f"""Analyze this GitHub issue:

Title: {issue_data['title']}
Body: {issue_data.get('body') or '(No description provided)'}

Comments:
{comments_text}

Labels: {issue_data.get('labels', [])}
State: {issue_data.get('state', 'unknown')}
Author: {issue_data.get('author', 'unknown')}
URL: {issue_data.get('html_url', '')}"""

            # Build chat with few-shot examples
            chat_history = []
            for example in FEW_SHOT_EXAMPLES:
                chat_history.append({
                    "role": example["role"],
                    "parts": [example["content"]]
                })

            chat = model.start_chat(history=chat_history)
            response = chat.send_message(user_prompt)

            # Parse response
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            return json.loads(text)

        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse AI response: {str(e)}"}
        except Exception as e:
            return {"error": f"AI analysis failed: {str(e)}"}
