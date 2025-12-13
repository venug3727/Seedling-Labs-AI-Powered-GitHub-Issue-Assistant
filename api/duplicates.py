"""
Vercel Serverless Function for Duplicate Detection.
Endpoint: POST /api/duplicates

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

# Same prompt as backend advanced_features.py find_duplicate_issues()
DUPLICATE_PROMPT_TEMPLATE = """<s>[INST] Compare these two GitHub issues and rate their semantic similarity from 0 to 100.

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

Return ONLY a number from 0 to 100. No explanation. [/INST]"""


def call_huggingface_similarity(prompt: str, api_key: str) -> str:
    """Call Hugging Face API and return raw text response for similarity score."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    with httpx.Client(timeout=60) as client:
        response = client.post(
            HUGGINGFACE_API_URL,
            headers=headers,
            json={
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 20,
                    "temperature": 0.1,
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
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens": 20,
                        "temperature": 0.1,
                        "top_p": 0.9,
                        "do_sample": True,
                        "return_full_text": False
                    }
                }
            )
        
        if response.status_code != 200:
            logger.error(f"Hugging Face API error: {response.status_code}")
            return ""
        
        result = response.json()
        
        # Extract generated text
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("generated_text", "").strip()
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
                
                score_text = call_huggingface_similarity(prompt, api_key)
                
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
