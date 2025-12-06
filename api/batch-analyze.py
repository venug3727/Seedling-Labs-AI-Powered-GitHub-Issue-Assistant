"""
Vercel Serverless Function for Batch Analysis.
Endpoint: POST /api/batch-analyze

Uses same prompts as backend llm_service.py for each issue.
Includes smart caching for cost & latency optimization.
Uses full few-shot prompting for consistent analysis quality.
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler
import httpx
from cache_utils import generate_cache_key, cache_get, cache_set

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# =============================================================================
# SYSTEM PROMPT - Agentic "Product Manager" Persona (Same as analyze.py)
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
# FEW-SHOT EXAMPLES (Same as analyze.py)
# =============================================================================
FEW_SHOT_EXAMPLE_1_USER = """Analyze this GitHub issue:

Title: App crashes on login when using SSO
Body: After the latest update (v2.3.1), clicking "Sign in with Google" causes the entire app to crash. This is happening on both iOS and Android. We have several enterprise customers who rely on SSO and they cannot access the app at all.

Comments:
- user_jane: "Same issue here. Our team of 50 people is completely blocked."
- user_mike: "Confirmed on iOS 17.1. Stack trace shows null pointer in AuthManager."
- maintainer_alex: "Looking into this urgently."

Labels: []
State: open"""

FEW_SHOT_EXAMPLE_1_RESPONSE = """{
    "summary": "Critical app crash occurs when users attempt to sign in using Google SSO, completely blocking enterprise customers from accessing the application.",
    "type": "bug",
    "priority_score": 5,
    "priority_justification": "Production crash affecting core authentication flow, blocking multiple enterprise customers and their teams from using the product entirely.",
    "suggested_labels": ["bug", "critical", "authentication", "SSO", "regression"],
    "potential_impact": "Severe - Enterprise customers with teams of 50+ users are completely unable to access the application, causing significant business disruption and potential churn risk.",
    "confidence_score": 0.95,
    "draft_response": "Hi @user, thank you for reporting this critical issue! We've confirmed the SSO crash affecting Google sign-in and have escalated this to our highest priority. Our team is actively investigating the null pointer in AuthManager. We'll provide updates here as we make progress and aim to have a fix deployed within 24 hours."
}"""

FEW_SHOT_EXAMPLE_2_USER = """Analyze this GitHub issue:

Title: Add dark mode support
Body: It would be great if the app supported dark mode. My eyes hurt when using the app at night.

Comments:
- user_bob: "+1, would love this feature"
- user_alice: "Yes please! iOS has had system-wide dark mode for years."

Labels: ["enhancement"]
State: open"""

FEW_SHOT_EXAMPLE_2_RESPONSE = """{
    "summary": "User requests dark mode support for the application to reduce eye strain during nighttime usage.",
    "type": "feature_request",
    "priority_score": 2,
    "priority_justification": "Quality of life improvement with user interest, but not blocking any core functionality. Common feature request but requires significant UI work.",
    "suggested_labels": ["enhancement", "UI/UX", "accessibility", "good-first-issue"],
    "potential_impact": "Low to moderate - Would improve user experience for night-time users and those with light sensitivity, but no functional impact on current users.",
    "confidence_score": 0.92,
    "draft_response": "Thanks for the suggestion! Dark mode is a popular request and we've added it to our feature backlog. While we can't commit to a specific timeline yet, we appreciate the feedback and will update this issue when we have more information on implementation plans."
}"""


def call_gemini(prompt: str, api_key: str) -> dict:
    """Call Gemini API with few-shot examples for consistent quality."""
    # Build conversation with few-shot examples (same as analyze.py)
    contents = [
        {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n" + FEW_SHOT_EXAMPLE_1_USER}]},
        {"role": "model", "parts": [{"text": FEW_SHOT_EXAMPLE_1_RESPONSE}]},
        {"role": "user", "parts": [{"text": FEW_SHOT_EXAMPLE_2_USER}]},
        {"role": "model", "parts": [{"text": FEW_SHOT_EXAMPLE_2_RESPONSE}]},
        {"role": "user", "parts": [{"text": prompt}]}
    ]
    
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
            "topP": 0.8,
            "topK": 40,
            "maxOutputTokens": 1500,
            "responseMimeType": "application/json"
        }
    }
    with httpx.Client(timeout=60) as client:
        resp = client.post(f"{GEMINI_API_URL}?key={api_key}", json=payload, headers={"Content-Type": "application/json"})
        if resp.status_code != 200:
            return {}
        data = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            return json.loads(text.strip())
        except:
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
            issue_numbers = data.get("issue_numbers", [])[:10]  # Max 10 (same as backend)

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                self.wfile.write(json.dumps({"success": False, "error": "GEMINI_API_KEY not configured"}).encode())
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

                    analysis = call_gemini(prompt, api_key)
                    
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

            # Calculate aggregate statistics (same as backend)
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
