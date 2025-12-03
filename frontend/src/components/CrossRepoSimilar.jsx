/**
 * CrossRepoSimilar Component
 *
 * Finds similar issues across other GitHub repositories.
 * Uses GitHub Search API with semantic keywords.
 */

import { useState, useEffect, useCallback } from "react";
import {
  Globe,
  RefreshCw,
  AlertCircle,
  ExternalLink,
  Search,
  CheckCircle,
  XCircle,
  Github,
  Star,
} from "lucide-react";

const CrossRepoSimilar = ({ issueData, repoUrl }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);

  const API_BASE_URL = import.meta.env.VITE_API_URL || "";

  const getExcludeRepo = () => {
    if (!repoUrl) return "";
    // Extract owner/repo from URL
    const parts = repoUrl.replace("https://github.com/", "").split("/");
    return parts.slice(0, 2).join("/");
  };

  const findSimilar = useCallback(async () => {
    if (!issueData?.title) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/similar-cross-repo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          issue_title: issueData.title,
          issue_body: issueData.body || "",
          exclude_repo: getExcludeRepo(),
        }),
      });

      const data = await response.json();

      if (data.success) {
        setResults(data.data);
      } else {
        setError(data.error || "Failed to find similar issues");
      }
    } catch (err) {
      setError("Failed to connect to server");
    } finally {
      setLoading(false);
    }
  }, [issueData, repoUrl, API_BASE_URL]);

  useEffect(() => {
    if (issueData?.title) {
      findSimilar();
    }
  }, [issueData]);

  if (!issueData) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6 text-center">
        <Globe className="w-12 h-12 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500">
          Analyze an issue first to find similar issues across repositories
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-green-600 to-green-500 px-4 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Globe className="w-5 h-5 text-white" />
            <h3 className="font-semibold text-white text-sm sm:text-base">
              Cross-Repo Similar Issues
            </h3>
          </div>
          <button
            onClick={findSimilar}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/20 hover:bg-white/30 rounded-lg transition-colors text-white text-sm"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 sm:p-6">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <Search className="w-6 h-6 text-green-500 animate-pulse" />
            <span className="ml-2 text-gray-600">
              Searching across GitHub...
            </span>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && results && (
          <div className="space-y-4">
            {results.length > 0 ? (
              <>
                <p className="text-sm text-gray-600">
                  Found {results.length} similar issues in other repositories
                  that might have solutions.
                </p>

                <div className="space-y-3">
                  {results.map((item, idx) => (
                    <div
                      key={idx}
                      className="border border-gray-200 rounded-lg p-4 hover:border-green-300 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          {/* Repo Name */}
                          <div className="flex items-center gap-2 mb-2">
                            <Github className="w-4 h-4 text-gray-500" />
                            <span className="text-sm font-medium text-gray-700">
                              {item.repo_full_name}
                            </span>
                            <span className="text-xs text-gray-400">
                              #{item.issue_number}
                            </span>
                          </div>

                          {/* Issue Title */}
                          <p className="text-gray-800 text-sm line-clamp-2 mb-2">
                            {item.title}
                          </p>

                          {/* Meta Info */}
                          <div className="flex items-center gap-3 text-xs">
                            {item.state === "open" ? (
                              <span className="flex items-center gap-1 text-green-600">
                                <CheckCircle className="w-3 h-3" />
                                Open
                              </span>
                            ) : (
                              <span className="flex items-center gap-1 text-purple-600">
                                <XCircle className="w-3 h-3" />
                                Closed
                              </span>
                            )}
                            {item.relevance_score > 0 && (
                              <span className="flex items-center gap-1 text-gray-500">
                                <Star className="w-3 h-3" />
                                {Math.round(item.relevance_score * 100)}%
                                relevant
                              </span>
                            )}
                          </div>
                        </div>

                        <a
                          href={item.html_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-green-100 hover:bg-green-200 text-green-700 rounded-lg text-sm font-medium transition-colors flex-shrink-0"
                        >
                          <ExternalLink className="w-4 h-4" />
                          <span className="hidden sm:inline">View</span>
                        </a>
                      </div>

                      {/* Hint for closed issues */}
                      {item.state === "closed" && (
                        <div className="mt-3 p-2 bg-purple-50 rounded text-xs text-purple-700">
                          💡 This issue is closed - check for solutions in the
                          comments!
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="text-center py-8">
                <Globe className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-700 font-medium">
                  No Similar Issues Found
                </p>
                <p className="text-gray-500 text-sm mt-1">
                  This issue appears to be unique across GitHub
                </p>
              </div>
            )}
          </div>
        )}

        {/* Info */}
        <div className="mt-4 pt-4 border-t border-gray-100">
          <p className="text-xs text-gray-500">
            <Search className="w-3 h-3 inline mr-1" />
            Searches popular repositories for issues with similar keywords.
            Check closed issues for potential solutions!
          </p>
        </div>
      </div>
    </div>
  );
};

export default CrossRepoSimilar;
