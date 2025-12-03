"""
Vercel Serverless Function for Cross-Repo Similar Issues.
Endpoint: POST /api/similar-cross-repo

Searches GitHub for similar issues in other repositories.
"""

import json
import os
import re
import logging
from http.server import BaseHTTPRequestHandler

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

            issue_title = data.get("issue_title", "")
            issue_body = data.get("issue_body", "")
            exclude_repo = data.get("exclude_repo", "").lower()

            # Extract keywords
            text = f"{issue_title} {issue_body[:200]}"
            stop_words = {'the', 'a', 'an', 'is', 'it', 'to', 'in', 'for', 'on', 'with', 'as', 'by', 'at', 'from'}
            words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
            keywords = [w for w in words if w not in stop_words][:5]

            if not keywords:
                self.wfile.write(json.dumps({
                    "success": True,
                    "data": []
                }).encode())
                return

            # Search GitHub
            query = " ".join(keywords)
            search_url = f"https://api.github.com/search/issues?q={query}+is:issue&sort=relevance&per_page=20"

            github_token = os.getenv("GITHUB_TOKEN")
            headers = {"Accept": "application/vnd.github.v3+json"}
            if github_token:
                headers["Authorization"] = f"token {github_token}"

            with httpx.Client(timeout=30) as client:
                response = client.get(search_url, headers=headers)
                if response.status_code != 200:
                    self.wfile.write(json.dumps({
                        "success": False,
                        "error": "GitHub search failed"
                    }).encode())
                    return
                
                search_data = response.json()

            results = []
            for item in search_data.get("items", []):
                repo_url = item.get("repository_url", "")
                repo_full_name = repo_url.replace("https://api.github.com/repos/", "")

                if exclude_repo and repo_full_name.lower() == exclude_repo:
                    continue

                # Calculate relevance
                other_title = item.get("title", "").lower()
                title_words = set(issue_title.lower().split())
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

            results.sort(key=lambda x: x["relevance_score"], reverse=True)

            self.wfile.write(json.dumps({
                "success": True,
                "data": results[:10]
            }).encode())

        except Exception as e:
            logger.error(f"Error: {e}")
            self.wfile.write(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())
