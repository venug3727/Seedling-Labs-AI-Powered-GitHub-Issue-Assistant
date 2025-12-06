"""
Vercel Serverless Function for Cross-Repo Similar Issues.
Endpoint: POST /api/similar-cross-repo

Searches for similar issues across GitHub repositories using GitHub Search API.
Includes smart caching for cost & latency optimization.
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler
import httpx
from _cache import generate_cache_key, cache_get, cache_set

GITHUB_API_BASE = "https://api.github.com"


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

            # Get parameters from frontend
            issue_title = data.get("issue_title", "")
            issue_body = data.get("issue_body", "")
            exclude_repo = data.get("exclude_repo", "")

            if not issue_title:
                self.wfile.write(json.dumps({"success": False, "error": "Issue title is required"}).encode())
                return

            # Check cache first
            cache_key = generate_cache_key("cross_repo", issue_title, issue_body[:200] if issue_body else "", exclude_repo)
            cached_result = cache_get(cache_key)
            if cached_result:
                self.wfile.write(json.dumps({
                    "success": True,
                    "data": cached_result,
                    "cached": True
                }).encode())
                return

            github_token = os.getenv("GITHUB_TOKEN", "")
            headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "Seedling-Issue-Assistant/1.0"}
            if github_token:
                headers["Authorization"] = f"token {github_token}"

            # Extract keywords from title and body
            text = f"{issue_title} {issue_body[:200]}"
            stop_words = {'the', 'a', 'an', 'is', 'it', 'to', 'in', 'for', 'on', 'with', 'as', 'by', 'at', 'from', 'and', 'or', 'but', 'not', 'this', 'that', 'when', 'what', 'how', 'why', 'can', 'could', 'would', 'should', 'will', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'get', 'got', 'use', 'using', 'used'}
            words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
            keywords = [w for w in words if w not in stop_words][:5]

            if not keywords:
                self.wfile.write(json.dumps({
                    "success": True,
                    "data": []  # Return empty array for frontend compatibility
                }).encode())
                return

            # Build search query for GitHub Search API
            query = " ".join(keywords)
            search_url = f"{GITHUB_API_BASE}/search/issues?q={query}+is:issue&sort=relevance&per_page=20"

            with httpx.Client(timeout=30) as client:
                resp = client.get(search_url, headers=headers)

                if resp.status_code != 200:
                    self.wfile.write(json.dumps({
                        "success": False,
                        "error": f"GitHub Search API error: {resp.status_code}"
                    }).encode())
                    return

                search_data = resp.json()

            results = []
            title_words = set(issue_title.lower().split())

            for item in search_data.get("items", []):
                # Extract repo info from repository_url
                repo_url = item.get("repository_url", "")
                repo_full_name = repo_url.replace(f"{GITHUB_API_BASE}/repos/", "")

                # Skip if same repo as source
                if exclude_repo and repo_full_name.lower() == exclude_repo.lower():
                    continue

                # Calculate relevance score
                other_title = item.get("title", "").lower()
                other_words = set(other_title.split())
                common_words = title_words.intersection(other_words)
                relevance = len(common_words) / max(len(title_words), 1)

                results.append({
                    "repo_full_name": repo_full_name,
                    "issue_number": item.get("number"),
                    "title": item.get("title", ""),
                    "html_url": item.get("html_url", ""),
                    "state": item.get("state", "unknown"),
                    "relevance_score": round(relevance, 2),
                    "created_at": item.get("created_at", "")
                })

            # Sort by relevance
            results.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            # Cache top results
            result_data = results[:10]
            cache_set(cache_key, result_data)

            self.wfile.write(json.dumps({
                "success": True,
                "data": result_data,  # Return array directly for frontend compatibility
                "cached": False
            }).encode())

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())
