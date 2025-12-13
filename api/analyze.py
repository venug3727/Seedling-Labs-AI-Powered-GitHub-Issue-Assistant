"""
Vercel Serverless Function for GitHub Issue Analysis.
Endpoint: POST /api/analyze

Uses Hugging Face Inference API (Mistral-7B) for free, reliable analysis.
Same prompts as backend/app/services/llm_service.py
Includes smart caching for cost & latency optimization.
"""

import json
import os
import logging
import re
import hashlib
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler

import httpx

# In-memory cache (works in warm Vercel instances)
_cache = {}
_cache_ttl = timedelta(minutes=60)

def generate_cache_key(*args):
    raw_key = ":".join(str(arg) for arg in args)
    return hashlib.md5(raw_key.encode()).hexdigest()

def cache_get(key):
    if key in _cache:
        value, cached_at = _cache[key]
        if datetime.now() - cached_at < _cache_ttl:
            return value
        del _cache[key]
    return None

def cache_set(key, value):
    _cache[key] = (value, datetime.now())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"

# =============================================================================
# SYSTEM PROMPT - Agentic "Product Manager" Persona (Same as backend)
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
}"""

# =============================================================================
# FEW-SHOT EXAMPLES (Same as backend)
# =============================================================================
FEW_SHOT_EXAMPLE_1 = """Example 1:
Issue Title: App crashes on login when using SSO
Issue Body: After the latest update (v2.3.1), clicking "Sign in with Google" causes the entire app to crash.
Comments: user_jane: "Same issue here. Our team of 50 people is completely blocked."

Response:
{"summary": "Critical app crash occurs when users attempt to sign in using Google SSO.", "type": "bug", "priority_score": 5, "priority_justification": "Production crash affecting core authentication.", "suggested_labels": ["bug", "critical", "authentication"], "potential_impact": "Severe - Enterprise customers blocked.", "confidence_score": 0.95, "draft_response": "Thank you for reporting! We've escalated this to highest priority and aim to fix within 24 hours."}"""

FEW_SHOT_EXAMPLE_2 = """Example 2:
Issue Title: Add dark mode support
Issue Body: It would be great if the app supported dark mode. My eyes hurt when using the app at night.
Comments: user_bob: "+1, would love this feature"

Response:
{"summary": "User requests dark mode support to reduce eye strain.", "type": "feature_request", "priority_score": 2, "priority_justification": "Quality of life improvement, not blocking functionality.", "suggested_labels": ["enhancement", "UI/UX"], "potential_impact": "Low to moderate - UX improvement.", "confidence_score": 0.92, "draft_response": "Thanks for the suggestion! Dark mode is on our backlog. We'll update when we have more info."}"""


def call_huggingface_api(user_prompt: str, api_key: str) -> dict:
    """Call Hugging Face Inference API with Mistral-7B."""
    
    full_prompt = f"""<s>[INST] {SYSTEM_PROMPT}

{FEW_SHOT_EXAMPLE_1}

{FEW_SHOT_EXAMPLE_2}

Now analyze this issue and respond with ONLY valid JSON:

{user_prompt}

Response: [/INST]"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    with httpx.Client(timeout=60) as client:
        response = client.post(
            HUGGINGFACE_API_URL,
            headers=headers,
            json={
                "inputs": full_prompt,
                "parameters": {
                    "max_new_tokens": 800,
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "do_sample": True,
                    "return_full_text": False
                }
            }
        )
        
        if response.status_code == 503:
            # Model is loading, wait and retry
            time.sleep(20)
            response = client.post(
                HUGGINGFACE_API_URL,
                headers=headers,
                json={
                    "inputs": full_prompt,
                    "parameters": {
                        "max_new_tokens": 800,
                        "temperature": 0.3,
                        "top_p": 0.9,
                        "do_sample": True,
                        "return_full_text": False
                    }
                }
            )
        
        if response.status_code != 200:
            return {"error": f"Hugging Face API error: {response.status_code} - {response.text[:200]}"}
        
        result = response.json()
        
        # Extract generated text
        if isinstance(result, list) and len(result) > 0:
            generated_text = result[0].get("generated_text", "")
        else:
            generated_text = str(result)
        
        # Find JSON in response
        text = generated_text.strip()
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            text = text[start_idx:end_idx + 1]
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response: {e}")
            # Return default response
            return {
                "summary": "Analysis completed with limited context",
                "type": "other",
                "priority_score": 3,
                "priority_justification": "Unable to fully parse issue details",
                "suggested_labels": ["needs-triage"],
                "potential_impact": "Unknown - requires manual review",
                "confidence_score": 0.3,
                "draft_response": "Thank you for submitting this issue. Our team will review it shortly."
            }


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            repo_url = data.get("repo_url", "")
            issue_number = data.get("issue_number")

            if not repo_url or not issue_number:
                self.wfile.write(json.dumps({"success": False, "error": "Missing repo_url or issue_number"}).encode())
                return

            match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?", repo_url)
            if not match:
                self.wfile.write(json.dumps({"success": False, "error": "Invalid GitHub URL"}).encode())
                return

            owner, repo = match.groups()
            issue_data = self._fetch_github_issue(owner, repo, issue_number)
            
            if "error" in issue_data:
                self.wfile.write(json.dumps({"success": False, "error": issue_data["error"]}).encode())
                return

            # Check cache first
            cache_key = generate_cache_key("analyze", repo_url, issue_number, issue_data.get("created_at", ""))
            cached_analysis = cache_get(cache_key)
            
            if cached_analysis:
                logger.info(f"Cache HIT for {repo_url} #{issue_number}")
                self.wfile.write(json.dumps({"success": True, "issue_data": issue_data, "analysis": cached_analysis, "cached": True}).encode())
                return

            api_key = os.getenv("HUGGINGFACE_API_KEY")
            if not api_key:
                self.wfile.write(json.dumps({"success": False, "error": "HUGGINGFACE_API_KEY not configured"}).encode())
                return

            prompt = self._build_prompt(issue_data)
            analysis = call_huggingface_api(prompt, api_key)
            
            if "error" in analysis:
                self.wfile.write(json.dumps({"success": False, "issue_data": issue_data, "error": analysis["error"]}).encode())
                return

            # Store in cache
            cache_set(cache_key, analysis)
            logger.info(f"Cache SET for {repo_url} #{issue_number}")

            self.wfile.write(json.dumps({"success": True, "issue_data": issue_data, "analysis": analysis, "cached": False}).encode())

        except Exception as e:
            logger.error(f"Error: {e}")
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())

    def _fetch_github_issue(self, owner: str, repo: str, issue_number: int) -> dict:
        github_token = os.getenv("GITHUB_TOKEN")
        headers = {"Accept": "application/vnd.github.v3+json"}
        if github_token:
            headers["Authorization"] = f"token {github_token}"

        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}", headers=headers)

                if response.status_code == 404:
                    return {"error": "Issue not found. Please check the repository URL and issue number."}
                elif response.status_code == 403:
                    return {"error": "Access denied. This might be a private repository or rate limit exceeded."}
                elif response.status_code != 200:
                    return {"error": f"GitHub API error: {response.status_code}"}

                issue = response.json()

                comments_response = client.get(f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments", headers=headers)
                comments_data = comments_response.json() if comments_response.status_code == 200 else []

            comments = [{"author": c.get("user", {}).get("login", "unknown"), "body": c.get("body", "")[:500]} for c in comments_data[:10]]
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

    def _build_prompt(self, issue_data: dict) -> str:
        """Format issue for analysis (same format as backend)."""
        body = issue_data.get("body") or "(No description provided)"
        
        if issue_data.get("comments"):
            comments_text = " | ".join([
                f"{c['author']}: \"{c['body'][:200]}{'...' if len(c['body']) > 200 else ''}\""
                for c in issue_data.get("comments", [])[:5]
            ])
        else:
            comments_text = "(No comments)"
        
        labels = issue_data.get("labels") if issue_data.get("labels") else ["(none)"]
        
        return f"""Issue Title: {issue_data['title']}
Issue Body: {body[:1500]}
Comments: {comments_text}
Labels: {labels}
State: {issue_data.get('state', 'unknown')}"""
