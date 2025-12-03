"""
Vercel Serverless Function for Cross-Repo Similar Issues.
Endpoint: POST /api/similar-cross-repo

Uses same approach as backend/app/services/advanced_features.py
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler
import httpx

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

            source_repo_url = data.get("source_repo_url", "")
            source_issue_number = data.get("source_issue_number")
            target_repo_url = data.get("target_repo_url", "")

            source_match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?", source_repo_url)
            target_match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?", target_repo_url)
            
            if not source_match or not target_match:
                self.wfile.write(json.dumps({"success": False, "error": "Invalid GitHub URL"}).encode())
                return

            source_owner, source_repo = source_match.groups()
            target_owner, target_repo = target_match.groups()

            github_token = os.getenv("GITHUB_TOKEN", "")
            headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "Seedling-Issue-Assistant/1.0"}
            if github_token:
                headers["Authorization"] = f"token {github_token}"

            with httpx.Client(timeout=30) as client:
                # Fetch source issue
                resp = client.get(f"{GITHUB_API_BASE}/repos/{source_owner}/{source_repo}/issues/{source_issue_number}", headers=headers)
                if resp.status_code != 200:
                    self.wfile.write(json.dumps({"success": False, "error": "Source issue not found"}).encode())
                    return
                source = resp.json()

                source_title = source.get("title", "")
                source_body = (source.get("body") or "")[:200]
                
                # Extract keywords (same logic as backend find_similar_issues_cross_repo)
                text = f"{source_title} {source_body}"
                stop_words = {'the', 'a', 'an', 'is', 'it', 'to', 'in', 'for', 'on', 'with', 'as', 'by', 'at', 'from'}
                words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
                keywords = [w for w in words if w not in stop_words][:5]
                
                if not keywords:
                    self.wfile.write(json.dumps({
                        "success": True,
                        "data": {
                            "source_issue": {"number": source_issue_number, "title": source_title, "repo": f"{source_owner}/{source_repo}"},
                            "similar_issues": [],
                            "target_repo": f"{target_owner}/{target_repo}"
                        }
                    }).encode())
                    return
                
                # Search in target repo using GitHub Search API (same as backend)
                query = " ".join(keywords)
                search_url = f"{GITHUB_API_BASE}/search/issues?q={query}+is:issue+repo:{target_owner}/{target_repo}&sort=relevance&per_page=20"
                
                resp = client.get(search_url, headers=headers)
                
                if resp.status_code != 200 or "items" not in resp.json():
                    self.wfile.write(json.dumps({
                        "success": True,
                        "data": {
                            "source_issue": {"number": source_issue_number, "title": source_title, "repo": f"{source_owner}/{source_repo}"},
                            "similar_issues": [],
                            "target_repo": f"{target_owner}/{target_repo}"
                        }
                    }).encode())
                    return
                
                search_results = resp.json()

            results = []
            title_words = set(source_title.lower().split())
            
            for item in search_results.get("items", []):
                # Calculate relevance score (same logic as backend)
                other_title = item.get("title", "").lower()
                other_words = set(other_title.split())
                common_words = title_words.intersection(other_words)
                relevance = len(common_words) / max(len(title_words), 1)
                
                results.append({
                    "issue_number": item.get("number"),
                    "title": item.get("title", ""),
                    "html_url": item.get("html_url", ""),
                    "state": item.get("state", "unknown"),
                    "relevance_score": round(relevance, 2),
                    "created_at": item.get("created_at", "")
                })
            
            # Sort by relevance (same as backend)
            results.sort(key=lambda x: x["relevance_score"], reverse=True)

            self.wfile.write(json.dumps({
                "success": True,
                "data": {
                    "source_issue": {"number": source_issue_number, "title": source_title, "repo": f"{source_owner}/{source_repo}"},
                    "similar_issues": results[:10],  # Return top 10 (same as backend)
                    "target_repo": f"{target_owner}/{target_repo}"
                }
            }).encode())

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())
