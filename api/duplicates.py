"""
Vercel Serverless Function for Duplicate Detection.
Endpoint: POST /api/duplicates

Uses same prompt as backend/app/services/advanced_features.py
Includes smart caching for cost & latency optimization.
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler
import httpx
from _cache import generate_cache_key, cache_get, cache_set

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Same prompt as backend advanced_features.py find_duplicate_issues()
DUPLICATE_PROMPT_TEMPLATE = """Compare these two GitHub issues and rate their semantic similarity from 0 to 100.

Issue 1:
Title: {source_title}
Body: {source_body}

Issue 2:
Title: {target_title}
Body: {target_body}

Consider:
- Are they reporting the same problem?
- Are they requesting the same feature?
- Do they have similar root causes?

Return ONLY a number from 0 to 100. No explanation."""


def call_gemini(prompt: str, api_key: str) -> str:
    """Call Gemini and return raw text response."""
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 50}
    }
    with httpx.Client(timeout=60) as client:
        resp = client.post(f"{GEMINI_API_URL}?key={api_key}", json=payload, headers={"Content-Type": "application/json"})
        if resp.status_code != 200:
            return ""
        data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except:
            return ""


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
            threshold = data.get("threshold", 0.5)  # Same default as backend (50%)

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

            with httpx.Client(timeout=30) as client:
                # Fetch source issue
                resp = client.get(f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}", headers=headers)
                if resp.status_code != 200:
                    self.wfile.write(json.dumps({"success": False, "error": "Issue not found"}).encode())
                    return
                source = resp.json()

                # Fetch recent issues (same limit=50 as backend)
                resp = client.get(f"https://api.github.com/repos/{owner}/{repo}/issues?state=all&per_page=50", headers=headers)
                issues = resp.json() if resp.status_code == 200 else []

            # Filter out current issue
            other_issues = [i for i in issues if i.get("number") != issue_number]

            if not other_issues:
                self.wfile.write(json.dumps({
                    "success": True,
                    "data": {"source_issue": {"number": issue_number, "title": source.get("title")}, "potential_duplicates": []},
                    "cached": False
                }).encode())
                return

            # Check cache first
            cache_key = generate_cache_key("duplicates", repo_url, issue_number, threshold)
            cached_result = cache_get(cache_key)
            
            if cached_result:
                self.wfile.write(json.dumps({
                    "success": True,
                    "data": cached_result,
                    "cached": True
                }).encode())
                return

            source_title = source.get("title", "")
            source_body = (source.get("body") or "")[:500]

            candidates = []
            
            # Compare with top 20 issues (same as backend)
            for issue in other_issues[:20]:
                target_title = issue.get("title", "")
                target_body = (issue.get("body") or "")[:500]
                
                # Use same prompt as backend
                prompt = DUPLICATE_PROMPT_TEMPLATE.format(
                    source_title=source_title,
                    source_body=source_body,
                    target_title=target_title,
                    target_body=target_body
                )
                
                score_text = call_gemini(prompt, api_key)
                
                # Extract number from response (same logic as backend)
                score_match = re.search(r'\d+', score_text)
                if score_match:
                    score = int(score_match.group()) / 100.0
                    if score >= threshold:  # Only include if above threshold
                        candidates.append({
                            "issue_number": issue.get("number"),
                            "title": target_title,
                            "similarity_score": round(score, 2),
                            "html_url": issue.get("html_url", ""),
                            "state": issue.get("state", "unknown")
                        })

            # Sort by similarity score (same as backend)
            candidates.sort(key=lambda x: x["similarity_score"], reverse=True)

            result_data = {
                "source_issue": {"number": issue_number, "title": source.get("title")},
                "potential_duplicates": candidates[:5]  # Return top 5 (same as backend)
            }
            
            # Store in cache
            cache_set(cache_key, result_data)

            self.wfile.write(json.dumps({
                "success": True,
                "data": result_data,
                "cached": False
            }).encode())

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())
