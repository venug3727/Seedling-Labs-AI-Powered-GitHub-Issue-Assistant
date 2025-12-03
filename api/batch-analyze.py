"""
Vercel Serverless Function for Batch Analysis.
Endpoint: POST /api/batch-analyze

Uses same prompts as backend llm_service.py for each issue.
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler
import httpx

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Same system prompt as backend llm_service.py
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

## Output Requirements:
You MUST respond with ONLY valid JSON. No markdown, no explanations, just the JSON object.

## JSON Schema:
{
    "summary": "string - One clear sentence summarizing the issue",
    "type": "string - One of: bug, feature_request, documentation, question, other",
    "priority_score": "integer - 1 to 5",
    "priority_justification": "string - Brief reasoning for the score",
    "suggested_labels": ["array", "of", "2-5", "labels"],
    "potential_impact": "string - Impact on users"
}"""


def call_gemini(prompt: str, api_key: str) -> dict:
    payload = {
        "contents": [{"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n" + prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "topP": 0.8,
            "topK": 40,
            "maxOutputTokens": 800,
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
            with httpx.Client(timeout=30) as client:
                for num in issue_numbers:
                    resp = client.get(f"https://api.github.com/repos/{owner}/{repo}/issues/{num}", headers=headers)
                    if resp.status_code != 200:
                        results.append({"issue_number": num, "success": False, "error": "Issue not found"})
                        continue
                    
                    issue = resp.json()
                    
                    # Build prompt same format as backend
                    body_text = issue.get("body") or "(No description provided)"
                    prompt = f"""Analyze this GitHub issue:

Title: {issue.get('title', '')}
Body: {body_text[:2000]}

Labels: {[l.get('name', '') for l in issue.get('labels', [])]}
State: {issue.get('state', 'unknown')}"""

                    analysis = call_gemini(prompt, api_key)
                    
                    results.append({
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
                            "potential_impact": analysis.get("potential_impact", "")
                        },
                        "success": True
                    })

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
                        "type_distribution": type_counts,
                        "average_priority": round(priority_sum / len(successful), 1) if successful else 0,
                        "top_labels": [{"label": l, "count": c} for l, c in top_labels]
                    }
                }
            }).encode())

        except Exception as e:
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())
