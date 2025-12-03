"""
Advanced Features Service - Additional AI-powered analysis features.

Features:
1. Issue Dependency Graph - Parse and visualize issue references
2. Duplicate Issue Detector - Find similar issues in the repo
3. Auto-Generate GitHub Labels - Create labels via API
4. Multi-Issue Batch Analysis - Analyze multiple issues at once
5. Cross-Repo Similar Issues - Find similar issues in other repos
"""

import re
import os
import logging
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass

import httpx
import google.generativeai as genai

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
REQUEST_TIMEOUT = 30.0


@dataclass
class IssueReference:
    """Represents a reference to another issue."""
    issue_number: int
    reference_type: str  # 'mentions', 'fixes', 'closes', 'blocks', 'blocked_by'
    context: str  # The text around the reference


@dataclass
class DependencyNode:
    """Node in the dependency graph."""
    issue_number: int
    title: str
    state: str
    references: List[IssueReference]
    html_url: str


@dataclass
class DuplicateCandidate:
    """A potential duplicate issue."""
    issue_number: int
    title: str
    similarity_score: float
    html_url: str
    state: str


@dataclass
class CrossRepoIssue:
    """Similar issue from another repository."""
    repo_full_name: str
    issue_number: int
    title: str
    html_url: str
    state: str
    relevance_score: float


class AdvancedFeaturesService:
    """Service for advanced analysis features."""

    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Seedling-Issue-Assistant/1.0"
        }
        if self.github_token:
            self.headers["Authorization"] = f"token {self.github_token}"
        
        # Initialize Gemini for similarity analysis
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash")
        else:
            self.model = None

    async def _make_github_request(self, url: str) -> Optional[dict]:
        """Make a request to GitHub API."""
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            try:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"GitHub API returned {response.status_code} for {url}")
                    return None
            except Exception as e:
                logger.error(f"GitHub request error: {e}")
                return None

    # ==================== 1. DEPENDENCY GRAPH ====================
    
    def parse_issue_references(self, text: str, current_repo: str = "") -> List[IssueReference]:
        """
        Parse issue references from text.
        Finds patterns like #123, fixes #456, closes owner/repo#789
        """
        references = []
        
        # Pattern for issue references
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
        for pattern, ref_type in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                issue_num = int(match.group(1))
                if issue_num not in seen:
                    seen.add(issue_num)
                    # Get context (surrounding text)
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    context = text[start:end].strip()
                    
                    references.append(IssueReference(
                        issue_number=issue_num,
                        reference_type=ref_type,
                        context=f"...{context}..."
                    ))
        
        return references

    async def build_dependency_graph(
        self, 
        owner: str, 
        repo: str, 
        issue_number: int,
        depth: int = 1
    ) -> Dict:
        """
        Build a dependency graph for an issue.
        
        Returns:
            Dict with nodes and edges for visualization
        """
        nodes = []
        edges = []
        visited = set()
        
        async def process_issue(num: int, current_depth: int):
            if num in visited or current_depth > depth:
                return
            visited.add(num)
            
            # Fetch issue data
            url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{num}"
            data = await self._make_github_request(url)
            
            if not data:
                return
            
            # Parse references from title and body
            text = f"{data.get('title', '')} {data.get('body', '') or ''}"
            references = self.parse_issue_references(text, f"{owner}/{repo}")
            
            # Add node
            nodes.append({
                "id": str(num),
                "issue_number": num,
                "title": data.get("title", ""),
                "state": data.get("state", "unknown"),
                "html_url": data.get("html_url", ""),
                "is_root": num == issue_number
            })
            
            # Add edges and process referenced issues
            for ref in references:
                edges.append({
                    "source": str(num),
                    "target": str(ref.issue_number),
                    "type": ref.reference_type,
                    "context": ref.context
                })
                
                # Recursively process referenced issues
                if current_depth < depth:
                    await process_issue(ref.issue_number, current_depth + 1)
        
        await process_issue(issue_number, 0)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "root_issue": issue_number,
            "total_nodes": len(nodes),
            "total_edges": len(edges)
        }

    # ==================== 2. DUPLICATE DETECTOR ====================
    
    async def find_duplicate_issues(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        issue_title: str,
        issue_body: str,
        limit: int = 50
    ) -> List[Dict]:
        """
        Find potential duplicate issues in the repository.
        Uses semantic similarity via Gemini.
        """
        # Fetch recent issues
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues?state=all&per_page={limit}"
        issues = await self._make_github_request(url)
        
        if not issues:
            return []
        
        # Filter out the current issue
        other_issues = [i for i in issues if i.get("number") != issue_number]
        
        if not other_issues or not self.model:
            return []
        
        # Prepare issue summaries for comparison
        current_summary = f"Title: {issue_title}\nBody: {(issue_body or '')[:500]}"
        
        candidates = []
        for issue in other_issues[:20]:  # Limit to 20 for API efficiency
            other_title = issue.get("title", "")
            other_body = (issue.get("body") or "")[:500]
            other_summary = f"Title: {other_title}\nBody: {other_body}"
            
            # Use Gemini to compute similarity
            prompt = f"""Compare these two GitHub issues and rate their semantic similarity from 0 to 100.
            
Issue 1:
{current_summary}

Issue 2:
{other_summary}

Consider:
- Are they reporting the same problem?
- Are they requesting the same feature?
- Do they have similar root causes?

Return ONLY a number from 0 to 100. No explanation."""
            
            try:
                response = self.model.generate_content(prompt)
                score_text = response.text.strip()
                # Extract number from response
                score_match = re.search(r'\d+', score_text)
                if score_match:
                    score = int(score_match.group()) / 100.0
                    if score >= 0.5:  # Only include if 50%+ similar
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
        
        # Sort by similarity score
        candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        return candidates[:5]  # Return top 5

    # ==================== 3. AUTO-GENERATE LABELS ====================
    
    async def create_github_labels(
        self,
        owner: str,
        repo: str,
        labels: List[str],
        github_token: str
    ) -> Dict:
        """
        Create labels on GitHub repository.
        
        Args:
            owner: Repo owner
            repo: Repo name
            labels: List of label names to create
            github_token: User's GitHub PAT
            
        Returns:
            Dict with created/existing/failed labels
        """
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {github_token}",
            "User-Agent": "Seedling-Issue-Assistant/1.0"
        }
        
        results = {
            "created": [],
            "existing": [],
            "failed": []
        }
        
        # Predefined colors for different label types
        label_colors = {
            "bug": "d73a4a",
            "feature": "a2eeef",
            "enhancement": "a2eeef",
            "documentation": "0075ca",
            "question": "d876e3",
            "help wanted": "008672",
            "good first issue": "7057ff",
            "priority": "fbca04",
            "critical": "b60205",
            "high": "d93f0b",
            "medium": "fbca04",
            "low": "0e8a16",
            "default": "ededed"
        }
        
        def get_color(label_name: str) -> str:
            """Get appropriate color for a label."""
            label_lower = label_name.lower()
            for key, color in label_colors.items():
                if key in label_lower:
                    return color
            return label_colors["default"]
        
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            for label in labels:
                url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/labels"
                payload = {
                    "name": label,
                    "color": get_color(label),
                    "description": f"Auto-generated by Issue Assistant"
                }
                
                try:
                    response = await client.post(url, json=payload, headers=headers)
                    
                    if response.status_code == 201:
                        results["created"].append(label)
                    elif response.status_code == 422:
                        # Label already exists
                        results["existing"].append(label)
                    else:
                        results["failed"].append({
                            "label": label,
                            "error": response.text
                        })
                except Exception as e:
                    results["failed"].append({
                        "label": label,
                        "error": str(e)
                    })
        
        return results

    # ==================== 4. BATCH ANALYSIS ====================
    
    async def batch_analyze_issues(
        self,
        owner: str,
        repo: str,
        issue_numbers: List[int],
        llm_service
    ) -> Dict:
        """
        Analyze multiple issues at once.
        
        Returns:
            Dict with individual analyses and aggregate stats
        """
        from app.services.github_service import GitHubService
        
        github_service = GitHubService()
        results = []
        
        for issue_num in issue_numbers[:10]:  # Limit to 10 issues
            try:
                # Fetch issue
                issue_data = await github_service.fetch_issue(owner, repo, issue_num)
                
                # Analyze with LLM
                analysis, was_cached = await llm_service.analyze_issue(
                    issue_data,
                    repo_url=f"https://github.com/{owner}/{repo}",
                    issue_number=issue_num
                )
                
                results.append({
                    "issue_number": issue_num,
                    "title": issue_data.title,
                    "state": issue_data.state,
                    "html_url": issue_data.html_url,
                    "analysis": {
                        "summary": analysis.summary,
                        "type": analysis.type,
                        "priority_score": analysis.priority_score,
                        "priority_justification": analysis.priority_justification,
                        "suggested_labels": analysis.suggested_labels,
                        "potential_impact": analysis.potential_impact,
                        "confidence_score": analysis.confidence_score
                    },
                    "cached": was_cached,
                    "success": True
                })
            except Exception as e:
                logger.error(f"Failed to analyze issue #{issue_num}: {e}")
                results.append({
                    "issue_number": issue_num,
                    "success": False,
                    "error": str(e)
                })
        
        # Calculate aggregate statistics
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
        
        return {
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

    # ==================== 5. CROSS-REPO SIMILAR ISSUES ====================
    
    async def find_similar_issues_cross_repo(
        self,
        issue_title: str,
        issue_body: str,
        exclude_repo: str = ""
    ) -> List[Dict]:
        """
        Search for similar issues across popular GitHub repositories.
        
        Uses GitHub Search API to find related issues.
        """
        # Extract keywords from title and body
        text = f"{issue_title} {(issue_body or '')[:200]}"
        
        # Remove common words and special characters
        stop_words = {'the', 'a', 'an', 'is', 'it', 'to', 'in', 'for', 'on', 'with', 'as', 'by', 'at', 'from'}
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        keywords = [w for w in words if w not in stop_words][:5]
        
        if not keywords:
            return []
        
        # Build search query
        query = " ".join(keywords)
        search_url = f"{GITHUB_API_BASE}/search/issues?q={query}+is:issue&sort=relevance&per_page=20"
        
        response = await self._make_github_request(search_url)
        
        if not response or "items" not in response:
            return []
        
        results = []
        for item in response["items"]:
            repo_url = item.get("repository_url", "")
            repo_full_name = repo_url.replace(f"{GITHUB_API_BASE}/repos/", "")
            
            # Skip if same repo
            if exclude_repo and repo_full_name.lower() == exclude_repo.lower():
                continue
            
            # Calculate simple relevance score based on title similarity
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
        
        # Sort by relevance
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return results[:10]


# Singleton
_advanced_service: Optional[AdvancedFeaturesService] = None


def get_advanced_features_service() -> AdvancedFeaturesService:
    """Get or create the advanced features service singleton."""
    global _advanced_service
    if _advanced_service is None:
        _advanced_service = AdvancedFeaturesService()
    return _advanced_service
