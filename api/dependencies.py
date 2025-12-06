"""
Vercel Serverless Function for Issue Dependencies.
Endpoint: POST /api/dependencies

Uses same reference parsing logic as backend/app/services/advanced_features.py
Includes smart caching for cost & latency optimization.
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler
import httpx
from _cache import generate_cache_key, cache_get, cache_set

GITHUB_API_BASE = "https://api.github.com"


def parse_issue_references(text):
    """
    Parse issue references from text.
    Same patterns as backend advanced_features.py parse_issue_references()
    """
    references = []
    
    # Same patterns as backend
    patterns = [
        # fixes #123, closes #123, resolves #123
        (r'(?:fix(?:es|ed)?|clos(?:es|ed)?|resolv(?:es|ed)?)\s+#(\d+)', 'fixes'),
        # blocked by #123, depends on #123
        (r'(?:blocked\s+by|depends\s+on)\s+#(\d+)', 'blocked_by'),
        # blocks #123
        (r'blocks?\s+#(\d+)', 'blocks'),
        # related to #123, see #123, ref #123
        (r'(?:related\s+to|see|ref(?:erence)?s?)\s+#(\d+)', 'mentions'),
        # plain #123 (lowest priority)
        (r'(?<![/\w])#(\d+)(?!\d)', 'mentions'),
    ]
    
    seen = set()
    if not text:
        return references
        
    for pattern, ref_type in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            issue_num = int(match.group(1))
            if issue_num not in seen:
                seen.add(issue_num)
                # Get context (surrounding text) - same as backend
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                
                references.append({
                    "issue_number": issue_num,
                    "reference_type": ref_type,
                    "context": f"...{context}..."
                })
    
    return references


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
            max_depth = min(data.get("max_depth", 1), 3)  # Same default=1 and max=3 as backend

            match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?", repo_url)
            if not match:
                self.wfile.write(json.dumps({"success": False, "error": "Invalid GitHub URL"}).encode())
                return

            owner, repo = match.groups()
            
            # Check cache first
            cache_key = generate_cache_key("dependencies", repo_url, issue_number, max_depth)
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

            nodes = []
            edges = []
            visited = set()

            def fetch_and_process(num, current_depth):
                """Recursively fetch issues and build graph (same logic as backend)."""
                if num in visited or current_depth > max_depth:
                    return
                visited.add(num)

                url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{num}"
                with httpx.Client(timeout=15) as client:
                    resp = client.get(url, headers=headers)
                    if resp.status_code != 200:
                        return
                    issue = resp.json()

                # Parse references from title and body (same as backend)
                text = f"{issue.get('title', '')} {issue.get('body', '') or ''}"
                references = parse_issue_references(text)

                # Add node (same structure as backend)
                nodes.append({
                    "id": str(num),
                    "issue_number": num,
                    "title": issue.get("title", ""),
                    "state": issue.get("state", "unknown"),
                    "html_url": issue.get("html_url", ""),
                    "is_root": num == issue_number
                })

                # Add edges and recursively process (same as backend)
                for ref in references:
                    edges.append({
                        "source": str(num),
                        "target": str(ref["issue_number"]),
                        "type": ref["reference_type"],
                        "context": ref["context"]
                    })
                    
                    if current_depth < max_depth:
                        fetch_and_process(ref["issue_number"], current_depth + 1)

            fetch_and_process(issue_number, 0)

            result_data = {
                "nodes": nodes,
                "edges": edges,
                "root_issue": issue_number,
                "total_nodes": len(nodes),
                "total_edges": len(edges)
            }
            
            # Cache the result
            cache_set(cache_key, result_data)

            self.wfile.write(json.dumps({
                "success": True,
                "data": result_data,
                "cached": False
            }).encode())

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())
