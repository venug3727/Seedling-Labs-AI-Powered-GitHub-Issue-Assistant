"""
Vercel Serverless Function for Batch Analysis.
Endpoint: POST /api/batch-analyze

Analyzes multiple GitHub issues at once.
"""

import json
import os
import re
import logging
import hashlib
from http.server import BaseHTTPRequestHandler

import httpx
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def fetch_issue(owner: str, repo: str, issue_number: int) -> dict:
    """Fetch a single issue from GitHub."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else "",
        "User-Agent": "Seedling-Issue-Assistant/1.0"
    }

    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"

    with httpx.Client(timeout=30) as client:
        response = client.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        return None


def analyze_issue(issue: dict, owner: str, repo: str) -> dict:
    """Analyze a single issue using Gemini."""
    title = issue.get("title", "")
    body = issue.get("body", "") or ""
    number = issue.get("number", 0)

    prompt = f"""Analyze this GitHub issue and provide a brief JSON response:

Issue #{number}:
Title: {title}
Body: {body[:1500]}

Return JSON with:
- priority: high/medium/low
- category: bug/feature/question/documentation/other
- effort: hours estimate
- key_points: 2-3 main points (array)
"""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json"
            )
        )

        result = json.loads(response.text)
        result["issue_number"] = number
        result["title"] = title
        result["url"] = issue.get("html_url", "")
        result["state"] = issue.get("state", "open")
        return result
    except Exception as e:
        logger.error(f"Analysis error for #{number}: {e}")
        return {
            "issue_number": number,
            "title": title,
            "priority": "unknown",
            "category": "unknown",
            "effort": "unknown",
            "key_points": [],
            "error": str(e)
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
            issue_numbers = data.get("issue_numbers", [])
            max_issues = min(len(issue_numbers), 10)  # Limit to 10

            if not GEMINI_API_KEY:
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": "Gemini API key not configured"
                }).encode())
                return

            match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?", repo_url)
            if not match:
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": "Invalid GitHub URL"
                }).encode())
                return

            owner, repo = match.groups()
            results = []

            for i in range(max_issues):
                issue_num = issue_numbers[i]
                issue = fetch_issue(owner, repo, issue_num)
                if issue:
                    analysis = analyze_issue(issue, owner, repo)
                    results.append(analysis)

            # Calculate summary stats
            summary = {
                "total_analyzed": len(results),
                "by_priority": {},
                "by_category": {}
            }

            for r in results:
                p = r.get("priority", "unknown")
                c = r.get("category", "unknown")
                summary["by_priority"][p] = summary["by_priority"].get(p, 0) + 1
                summary["by_category"][c] = summary["by_category"].get(c, 0) + 1

            self.wfile.write(json.dumps({
                "success": True,
                "data": {
                    "issues": results,
                    "summary": summary
                }
            }).encode())

        except Exception as e:
            logger.error(f"Error: {e}")
            self.wfile.write(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())
