"""
Vercel Serverless Function for Batch Analysis.
Endpoint: POST /api/batch-analyze

Uses Hugging Face Inference API (Mistral-7B) for free, reliable analysis.
Includes smart caching for cost & latency optimization.
"""

import json
import os
import re
import hashlib
import time
import logging
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory cache
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

HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"

# =============================================================================
# SYSTEM PROMPT - Same as analyze.py
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
            logger.error(f"Hugging Face API error: {response.status_code} - {response.text[:200]}")
            return {}
        
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
            return {}


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
            issue_numbers = data.get("issue_numbers", [])[:10]  # Max 10

            api_key = os.getenv("HUGGINGFACE_API_KEY")
            if not api_key:
                self.wfile.write(json.dumps({"success": False, "error": "HUGGINGFACE_API_KEY not configured"}).encode())
                return

            match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?", repo_url)
            if not match:
                self.wfile.write(json.dumps({"success": False, "error": "Invalid GitHub URL"}).encode())
                return

            owner, repo = match.groups()
            github_token = os.getenv("GITHUB_TOKEN", "")
            headers = {"Accept": "application/vnd.github.v3+json"}
            if github_token:
                headers["Authorization"] = f"token {github_token}"

            results = []
            cache_hits = 0
            with httpx.Client(timeout=30) as client:
                for num in issue_numbers:
                    # Check cache for this specific issue analysis
                    issue_cache_key = generate_cache_key("batch_issue", repo_url, num)
                    cached_issue_result = cache_get(issue_cache_key)
                    if cached_issue_result:
                        cached_issue_result["cached"] = True
                        results.append(cached_issue_result)
                        cache_hits += 1
                        continue
                    
                    resp = client.get(f"https://api.github.com/repos/{owner}/{repo}/issues/{num}", headers=headers)
                    if resp.status_code != 200:
                        results.append({"issue_number": num, "success": False, "error": "Issue not found"})
                        continue
                    
                    issue = resp.json()
                    
                    # Build prompt same format as analyze.py (including comments)
                    body_text = issue.get("body") or "(No description provided)"
                    labels = [l.get('name', '') for l in issue.get('labels', [])] or ["(none)"]
                    
                    # Fetch comments for better analysis
                    comments_text = "(No comments)"
                    try:
                        comments_resp = client.get(
                            f"https://api.github.com/repos/{owner}/{repo}/issues/{num}/comments",
                            headers=headers
                        )
                        if comments_resp.status_code == 200:
                            comments_data = comments_resp.json()[:10]
                            if comments_data:
                                comments_text = "\n".join([
                                    f"- {c.get('user', {}).get('login', 'unknown')}: \"{c.get('body', '')[:500]}{'...' if len(c.get('body', '')) > 500 else ''}\""
                                    for c in comments_data
                                ])
                    except:
                        pass
                    
                    prompt = f"""Analyze this GitHub issue:

Title: {issue.get('title', '')}
Body: {body_text[:2000]}

Comments:
{comments_text}

Labels: {labels}
State: {issue.get('state', 'unknown')}
Author: {issue.get('user', {}).get('login', 'unknown')}
URL: {issue.get('html_url', '')}"""

                    analysis = call_huggingface_api(prompt, api_key)
                    
                    issue_result = {
                        "issue_number": num,
                        "title": issue.get("title", ""),
                        "state": issue.get("state", "open"),
                        "html_url": issue.get("html_url", ""),
                        "analysis": {
                            "summary": analysis.get("summary", ""),
                            "type": analysis.get("type", "unknown"),
                            "priority_score": analysis.get("priority_score", 0),
                            "priority_justification": analysis.get("priority_justification", ""),
                            "suggested_labels": analysis.get("suggested_labels", []),
                            "potential_impact": analysis.get("potential_impact", ""),
                            "confidence_score": analysis.get("confidence_score", 0.0),
                            "draft_response": analysis.get("draft_response", "")
                        },
                        "success": True,
                        "cached": False
                    }
                    
                    # Cache individual issue result
                    cache_set(issue_cache_key, issue_result)
                    results.append(issue_result)

            # Calculate aggregate statistics
            successful = [r for r in results if r.get("success")]
            
            type_counts = {}
            priority_sum = 0
            all_labels = []
            
            for r in successful:
                analysis = r.get("analysis", {})
                issue_type = analysis.get("type", "unknown")
                type_counts[issue_type] = type_counts.get(issue_type, 0) + 1
                priority_sum += analysis.get("priority_score", 0)
                all_labels.extend(analysis.get("suggested_labels", []))
            
            # Most common labels
            label_counts = {}
            for label in all_labels:
                label_counts[label] = label_counts.get(label, 0) + 1
            top_labels = sorted(label_counts.items(), key=lambda x: x[1], reverse=True)[:10]

            self.wfile.write(json.dumps({
                "success": True,
                "data": {
                    "issues": results,
                    "statistics": {
                        "total_analyzed": len(issue_numbers),
                        "successful": len(successful),
                        "failed": len(results) - len(successful),
                        "cache_hits": cache_hits,
                        "type_distribution": type_counts,
                        "average_priority": round(priority_sum / len(successful), 1) if successful else 0,
                        "top_labels": [{"label": l, "count": c} for l, c in top_labels]
                    }
                },
                "cached": cache_hits == len(issue_numbers)
            }).encode())

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())
