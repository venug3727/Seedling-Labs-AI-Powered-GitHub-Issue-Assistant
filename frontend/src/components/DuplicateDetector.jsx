/**
 * DuplicateDetector Component
 *
 * Finds and displays potential duplicate issues in the repository.
 * Uses semantic similarity to identify duplicates.
 */

import { useState, useEffect, useCallback } from "react";
import {
  Copy,
  RefreshCw,
  AlertCircle,
  ExternalLink,
  Search,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Percent,
} from "lucide-react";

const DuplicateDetector = ({ repoUrl, issueNumber, issueData }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [duplicates, setDuplicates] = useState(null);

  const API_BASE_URL = import.meta.env.VITE_API_URL || "";

  const findDuplicates = useCallback(async () => {
    if (!repoUrl || !issueNumber || !issueData) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/duplicates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: repoUrl,
          issue_number: issueNumber,
          issue_title: issueData.title,
          issue_body: issueData.body || "",
        }),
      });

      const data = await response.json();

      if (data.success) {
        setDuplicates(data.data);
      } else {
        setError(data.error || "Failed to find duplicates");
      }
    } catch (err) {
      setError("Failed to connect to server");
    } finally {
      setLoading(false);
    }
  }, [repoUrl, issueNumber, issueData, API_BASE_URL]);

  useEffect(() => {
    if (repoUrl && issueNumber && issueData) {
      findDuplicates();
    }
  }, [repoUrl, issueNumber, issueData]);

  const getSimilarityColor = (score) => {
    if (score >= 0.85)
      return {
        bg: "bg-red-100",
        text: "text-red-700",
        label: "Very Likely Duplicate",
      };
    if (score >= 0.7)
      return {
        bg: "bg-orange-100",
        text: "text-orange-700",
        label: "Likely Duplicate",
      };
    if (score >= 0.5)
      return {
        bg: "bg-yellow-100",
        text: "text-yellow-700",
        label: "Possibly Related",
      };
    return {
      bg: "bg-gray-100",
      text: "text-gray-600",
      label: "Low Similarity",
    };
  };

  if (!repoUrl || !issueNumber || !issueData) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6 text-center">
        <Copy className="w-12 h-12 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500">
          Analyze an issue first to find duplicates
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-orange-600 to-orange-500 px-4 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Copy className="w-5 h-5 text-white" />
            <h3 className="font-semibold text-white text-sm sm:text-base">
              Duplicate Detector
            </h3>
          </div>
          <button
            onClick={findDuplicates}
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
            <Search className="w-6 h-6 text-orange-500 animate-pulse" />
            <span className="ml-2 text-gray-600">
              Scanning for duplicates...
            </span>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && duplicates && (
          <div className="space-y-4">
            {duplicates.length > 0 ? (
              <>
                <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-700 text-sm">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                  <span>
                    Found {duplicates.length} potential duplicate(s). Review
                    before taking action.
                  </span>
                </div>

                <div className="space-y-3">
                  {duplicates.map((dup, idx) => {
                    const similarity = getSimilarityColor(dup.similarity_score);

                    return (
                      <div
                        key={idx}
                        className="border border-gray-200 rounded-lg p-4 hover:border-orange-300 transition-colors"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-2 flex-wrap">
                              <span className="font-semibold text-gray-800">
                                #{dup.issue_number}
                              </span>
                              {dup.state === "open" ? (
                                <span className="flex items-center gap-1 text-xs text-green-600">
                                  <CheckCircle className="w-3 h-3" />
                                  Open
                                </span>
                              ) : (
                                <span className="flex items-center gap-1 text-xs text-gray-500">
                                  <XCircle className="w-3 h-3" />
                                  Closed
                                </span>
                              )}
                              <span
                                className={`px-2 py-0.5 text-xs rounded-full ${similarity.bg} ${similarity.text}`}
                              >
                                {Math.round(dup.similarity_score * 100)}% match
                              </span>
                            </div>

                            <p className="text-gray-700 text-sm line-clamp-2 mb-2">
                              {dup.title}
                            </p>

                            <span className={`text-xs ${similarity.text}`}>
                              {similarity.label}
                            </span>
                          </div>

                          <a
                            href={dup.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-700 text-sm transition-colors flex-shrink-0"
                          >
                            <ExternalLink className="w-4 h-4" />
                            <span className="hidden sm:inline">View</span>
                          </a>
                        </div>

                        {/* Similarity Bar */}
                        <div className="mt-3">
                          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div
                              className={`h-full transition-all ${
                                dup.similarity_score >= 0.85
                                  ? "bg-red-500"
                                  : dup.similarity_score >= 0.7
                                  ? "bg-orange-500"
                                  : dup.similarity_score >= 0.5
                                  ? "bg-yellow-500"
                                  : "bg-gray-400"
                              }`}
                              style={{
                                width: `${dup.similarity_score * 100}%`,
                              }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <div className="text-center py-8">
                <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
                <p className="text-gray-700 font-medium">No Duplicates Found</p>
                <p className="text-gray-500 text-sm mt-1">
                  This issue appears to be unique in the repository
                </p>
              </div>
            )}
          </div>
        )}

        {/* Info */}
        <div className="mt-4 pt-4 border-t border-gray-100">
          <p className="text-xs text-gray-500">
            <Percent className="w-3 h-3 inline mr-1" />
            Similarity is calculated using AI semantic analysis of issue titles
            and descriptions.
          </p>
        </div>
      </div>
    </div>
  );
};

export default DuplicateDetector;
