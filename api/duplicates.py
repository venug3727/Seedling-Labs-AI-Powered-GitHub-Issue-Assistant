"""
Vercel Serverless Function for Duplicate Detection.
Endpoint: POST /api/duplicates

Finds potential duplicate issues using semantic similarity.
"""

import json
import os
import re
import logging
from http.server import BaseHTTPRequestHandler

import httpx
import google.generativeai as genai

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

            repo_url = data.get("repo_url", "")
            issue_number = data.get("issue_number")
            issue_title = data.get("issue_title", "")
            issue_body = data.get("issue_body", "")

            match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?", repo_url)
            if not match:
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": "Invalid GitHub URL"
                }).encode())
                return

            owner, repo = match.groups()

            # Fetch recent issues
            github_token = os.getenv("GITHUB_TOKEN")
            headers = {"Accept": "application/vnd.github.v3+json"}
            if github_token:
                headers["Authorization"] = f"token {github_token}"

            url = f"https://api.github.com/repos/{owner}/{repo}/issues?state=all&per_page=50"
            
            with httpx.Client(timeout=30) as client:
                response = client.get(url, headers=headers)
                if response.status_code != 200:
                    self.wfile.write(json.dumps({
                        "success": False,
                        "error": "Failed to fetch issues"
                    }).encode())
                    return
                
                issues = response.json()

            # Filter out current issue
            other_issues = [i for i in issues if i.get("number") != issue_number][:20]

            if not other_issues:
                self.wfile.write(json.dumps({
                    "success": True,
                    "data": []
                }).encode())
                return

            # Setup Gemini
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": "GEMINI_API_KEY not configured"
                }).encode())
                return

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")

            current_summary = f"Title: {issue_title}\nBody: {issue_body[:500]}"
            candidates = []

            for issue in other_issues:
                other_title = issue.get("title", "")
                other_body = (issue.get("body") or "")[:500]
                other_summary = f"Title: {other_title}\nBody: {other_body}"

                prompt = f"""Compare these two GitHub issues and rate their semantic similarity from 0 to 100.

Issue 1:
{current_summary}

Issue 2:
{other_summary}

Consider: Are they reporting the same problem? Are they requesting the same feature?
Return ONLY a number from 0 to 100. No explanation."""

                try:
                    response = model.generate_content(prompt)
                    score_text = response.text.strip()
                    score_match = re.search(r'\d+', score_text)
                    if score_match:
                        score = int(score_match.group()) / 100.0
                        if score >= 0.5:
                            candidates.append({
                                "issue_number": issue.get("number"),
                                "title": other_title,
                                "similarity_score": round(score, 2),
                                "html_url": issue.get("html_url", ""),
                                "state": issue.get("state", "unknown")
                            })
                except Exception as e:
                    logger.warning(f"Similarity check failed: {e}")
                    continue

            candidates.sort(key=lambda x: x["similarity_score"], reverse=True)

            self.wfile.write(json.dumps({
                "success": True,
                "data": candidates[:5]
            }).encode())

        except Exception as e:
            logger.error(f"Error: {e}")
            self.wfile.write(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())
