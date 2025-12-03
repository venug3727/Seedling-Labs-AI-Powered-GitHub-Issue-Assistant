"""
Vercel Serverless Function for Issue Dependencies.
Endpoint: POST /api/dependencies

Parses issue references (#123, fixes #456) and builds dependency graph.
"""

import json
import os
import re
import logging
from http.server import BaseHTTPRequestHandler

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


def parse_issue_references(text: str) -> list:
    """Parse issue references from text."""
    references = []
    patterns = [
        (r'(?:fix(?:es|ed)?|clos(?:es|ed)?|resolv(?:es|ed)?)\s+#(\d+)', 'fixes'),
        (r'(?:blocked\s+by|depends\s+on)\s+#(\d+)', 'blocked_by'),
        (r'blocks?\s+#(\d+)', 'blocks'),
        (r'(?:related\s+to|see|ref(?:erence)?s?)\s+#(\d+)', 'mentions'),
        (r'(?<![/\w])#(\d+)(?!\d)', 'mentions'),
    ]
    
    seen = set()
    for pattern, ref_type in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            issue_num = int(match.group(1))
            if issue_num not in seen:
                seen.add(issue_num)
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                references.append({
                    "issue_number": issue_num,
                    "reference_type": ref_type,
                    "context": f"...{context}..."
                })
    
    return references


def fetch_github_issue(owner: str, repo: str, issue_number: int, headers: dict) -> dict:
    """Fetch a single issue from GitHub."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}"
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch issue #{issue_number}: {e}")
    return None


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
            depth = min(data.get("depth", 1), 3)

            match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?", repo_url)
            if not match:
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": "Invalid GitHub URL"
                }).encode())
                return

            owner, repo = match.groups()

            github_token = os.getenv("GITHUB_TOKEN")
            headers = {"Accept": "application/vnd.github.v3+json"}
            if github_token:
                headers["Authorization"] = f"token {github_token}"

            nodes = []
            edges = []
            visited = set()

            def process_issue(num: int, current_depth: int):
                if num in visited or current_depth > depth:
                    return
                visited.add(num)

                issue = fetch_github_issue(owner, repo, num, headers)
                if not issue:
                    return

                text = f"{issue.get('title', '')} {issue.get('body', '') or ''}"
                references = parse_issue_references(text)

                nodes.append({
                    "id": str(num),
                    "issue_number": num,
                    "title": issue.get("title", ""),
                    "state": issue.get("state", "unknown"),
                    "html_url": issue.get("html_url", ""),
                    "is_root": num == issue_number
                })

                for ref in references:
                    edges.append({
                        "source": str(num),
                        "target": str(ref["issue_number"]),
                        "type": ref["reference_type"],
                        "context": ref["context"]
                    })

                    if current_depth < depth:
                        process_issue(ref["issue_number"], current_depth + 1)

            process_issue(issue_number, 0)

            self.wfile.write(json.dumps({
                "success": True,
                "data": {
                    "nodes": nodes,
                    "edges": edges,
                    "root_issue": issue_number,
                    "total_nodes": len(nodes),
                    "total_edges": len(edges)
                }
            }).encode())

        except Exception as e:
            logger.error(f"Error: {e}")
            self.wfile.write(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())
