/**
 * BatchAnalysis Component
 *
 * Analyze multiple issues at once with aggregate statistics.
 * Supports CSV export for project management.
 */

import { useState } from "react";
import {
  Layers,
  RefreshCw,
  AlertCircle,
  ExternalLink,
  Download,
  ChevronDown,
  ChevronUp,
  BarChart3,
  CheckCircle,
  XCircle,
  Sparkles,
  Tag,
} from "lucide-react";

const BatchAnalysis = ({ repoUrl }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [issueInput, setIssueInput] = useState("");
  const [expandedIssues, setExpandedIssues] = useState({});

  const API_BASE_URL = import.meta.env.VITE_API_URL || "";

  const parseIssueNumbers = (input) => {
    // Support formats: "1,2,3" or "1-5" or "1, 2, 3" or "1-3, 5, 7-9"
    const numbers = new Set();

    const parts = input.split(",").map((p) => p.trim());
    for (const part of parts) {
      if (part.includes("-")) {
        const [start, end] = part.split("-").map((n) => parseInt(n.trim()));
        if (!isNaN(start) && !isNaN(end)) {
          for (let i = start; i <= Math.min(end, start + 9); i++) {
            numbers.add(i);
          }
        }
      } else {
        const num = parseInt(part);
        if (!isNaN(num)) numbers.add(num);
      }
    }

    return Array.from(numbers).slice(0, 10); // Max 10 issues
  };

  const analyzeBatch = async () => {
    const issueNumbers = parseIssueNumbers(issueInput);

    if (issueNumbers.length === 0) {
      setError('Please enter valid issue numbers (e.g., "1,2,3" or "1-5")');
      return;
    }

    if (!repoUrl) {
      setError("Please enter a repository URL first");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/batch-analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: repoUrl,
          issue_numbers: issueNumbers,
        }),
      });

      const data = await response.json();

      if (data.success) {
        setResults(data.data);
      } else {
        setError(data.error || "Batch analysis failed");
      }
    } catch (err) {
      setError("Failed to connect to server");
    } finally {
      setLoading(false);
    }
  };

  const exportToCSV = () => {
    if (!results?.issues) return;

    const headers = [
      "Issue #",
      "Title",
      "State",
      "Type",
      "Priority",
      "Summary",
      "Labels",
      "Impact",
      "URL",
    ];
    const rows = results.issues
      .filter((i) => i.success)
      .map((issue) => [
        issue.issue_number,
        `"${issue.title.replace(/"/g, '""')}"`,
        issue.state,
        issue.analysis.type,
        issue.analysis.priority_score,
        `"${issue.analysis.summary.replace(/"/g, '""')}"`,
        `"${issue.analysis.suggested_labels.join(", ")}"`,
        `"${issue.analysis.potential_impact.replace(/"/g, '""')}"`,
        issue.html_url,
      ]);

    const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `issue-analysis-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const toggleExpand = (num) => {
    setExpandedIssues((prev) => ({ ...prev, [num]: !prev[num] }));
  };

  const getPriorityColor = (score) => {
    const colors = {
      5: "bg-red-100 text-red-700",
      4: "bg-orange-100 text-orange-700",
      3: "bg-yellow-100 text-yellow-700",
      2: "bg-blue-100 text-blue-700",
      1: "bg-gray-100 text-gray-600",
    };
    return colors[score] || colors[3];
  };

  return (
    <div className="bg-white rounded-xl shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-500 px-4 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-white" />
          <h3 className="font-semibold text-white text-sm sm:text-base">
            Batch Analysis
          </h3>
        </div>
      </div>

      {/* Input Section */}
      <div className="p-4 sm:p-6 border-b border-gray-100">
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Issue Numbers
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={issueInput}
                onChange={(e) => setIssueInput(e.target.value)}
                placeholder="1-5, 10, 15-20"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                disabled={loading}
              />
              <button
                onClick={analyzeBatch}
                disabled={loading || !issueInput.trim()}
                className={`px-4 py-2 rounded-lg font-medium text-sm transition-all flex items-center gap-2 ${
                  loading || !issueInput.trim()
                    ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                    : "bg-blue-600 hover:bg-blue-700 text-white"
                }`}
              >
                {loading ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4" />
                )}
                <span className="hidden sm:inline">Analyze</span>
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Enter issue numbers separated by commas or ranges (max 10).
              Example: 1-5, 10, 15
            </p>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 mx-4 mt-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center gap-2 text-red-700 text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="p-8 text-center">
          <RefreshCw className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-3" />
          <p className="text-gray-600">Analyzing issues...</p>
          <p className="text-gray-400 text-sm">This may take a minute</p>
        </div>
      )}

      {/* Results */}
      {!loading && results && (
        <div className="p-4 sm:p-6 space-y-6">
          {/* Statistics Dashboard */}
          <div className="bg-gradient-to-r from-gray-50 to-blue-50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-blue-600" />
                <h4 className="font-semibold text-gray-800">
                  Analysis Summary
                </h4>
              </div>
              <button
                onClick={exportToCSV}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-lg text-sm font-medium transition-colors"
              >
                <Download className="w-4 h-4" />
                Export CSV
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-white rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {results.statistics.total_analyzed}
                </div>
                <div className="text-xs text-gray-500">Total Issues</div>
              </div>
              <div className="bg-white rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-green-600">
                  {results.statistics.successful}
                </div>
                <div className="text-xs text-gray-500">Analyzed</div>
              </div>
              <div className="bg-white rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-orange-600">
                  {results.statistics.average_priority}
                </div>
                <div className="text-xs text-gray-500">Avg Priority</div>
              </div>
              <div className="bg-white rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-red-600">
                  {results.statistics.failed}
                </div>
                <div className="text-xs text-gray-500">Failed</div>
              </div>
            </div>

            {/* Type Distribution */}
            {Object.keys(results.statistics.type_distribution).length > 0 && (
              <div className="mt-4">
                <p className="text-xs text-gray-500 mb-2">Issue Types:</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(results.statistics.type_distribution).map(
                    ([type, count]) => (
                      <span
                        key={type}
                        className="px-2 py-1 bg-white rounded text-xs font-medium text-gray-700"
                      >
                        {type.replace("_", " ")}: {count}
                      </span>
                    )
                  )}
                </div>
              </div>
            )}

            {/* Top Labels */}
            {results.statistics.top_labels?.length > 0 && (
              <div className="mt-4">
                <p className="text-xs text-gray-500 mb-2">
                  Most Common Labels:
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {results.statistics.top_labels
                    .slice(0, 6)
                    .map((item, idx) => (
                      <span
                        key={idx}
                        className="flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs"
                      >
                        <Tag className="w-3 h-3" />
                        {item.label} ({item.count})
                      </span>
                    ))}
                </div>
              </div>
            )}
          </div>

          {/* Issue List */}
          <div className="space-y-2">
            <h4 className="font-semibold text-gray-800">Individual Results</h4>
            {results.issues.map((issue, idx) => (
              <div
                key={idx}
                className={`border rounded-lg transition-colors ${
                  issue.success
                    ? "border-gray-200 hover:border-blue-300"
                    : "border-red-200 bg-red-50"
                }`}
              >
                {/* Issue Header */}
                <div
                  className="p-3 cursor-pointer flex items-center justify-between"
                  onClick={() =>
                    issue.success && toggleExpand(issue.issue_number)
                  }
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <span className="font-semibold text-gray-700">
                      #{issue.issue_number}
                    </span>
                    {issue.success ? (
                      <>
                        <span
                          className={`px-2 py-0.5 text-xs rounded-full ${getPriorityColor(
                            issue.analysis.priority_score
                          )}`}
                        >
                          P{issue.analysis.priority_score}
                        </span>
                        <span className="text-sm text-gray-600 truncate hidden sm:inline">
                          {issue.title}
                        </span>
                      </>
                    ) : (
                      <span className="text-sm text-red-600">
                        Failed: {issue.error}
                      </span>
                    )}
                  </div>
                  {issue.success &&
                    (expandedIssues[issue.issue_number] ? (
                      <ChevronUp className="w-4 h-4 text-gray-400" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-gray-400" />
                    ))}
                </div>

                {/* Expanded Details */}
                {issue.success && expandedIssues[issue.issue_number] && (
                  <div className="px-3 pb-3 border-t border-gray-100 pt-3 space-y-2">
                    <p className="text-sm text-gray-700">
                      {issue.analysis.summary}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <span className="text-xs text-gray-500">
                        Type: {issue.analysis.type}
                      </span>
                      <span className="text-xs text-gray-500">
                        State: {issue.state}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {issue.analysis.suggested_labels.map((label, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs"
                        >
                          {label}
                        </span>
                      ))}
                    </div>
                    <a
                      href={issue.html_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
                    >
                      <ExternalLink className="w-3 h-3" />
                      View on GitHub
                    </a>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && !results && !error && (
        <div className="p-8 text-center">
          <Layers className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500">
            Enter issue numbers above to analyze multiple issues at once
          </p>
        </div>
      )}
    </div>
  );
};

export default BatchAnalysis;
