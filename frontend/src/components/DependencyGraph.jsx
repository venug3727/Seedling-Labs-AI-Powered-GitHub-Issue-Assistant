/**
 * DependencyGraph Component
 *
 * Displays an interactive visualization of issue dependencies.
 * Shows how issues reference each other with #123, fixes #456 patterns.
 */

import { useState, useEffect, useCallback } from "react";
import {
  GitBranch,
  Circle,
  ArrowRight,
  RefreshCw,
  AlertCircle,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Link2,
  CheckCircle,
  XCircle,
} from "lucide-react";

const DependencyGraph = ({ repoUrl, issueNumber, issueData }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [graphData, setGraphData] = useState(null);
  const [expanded, setExpanded] = useState(true);
  const [depth, setDepth] = useState(1);

  const API_BASE_URL = import.meta.env.VITE_API_URL || "";

  const fetchDependencies = useCallback(async () => {
    if (!repoUrl || !issueNumber) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/dependencies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: repoUrl,
          issue_number: issueNumber,
          depth,
        }),
      });

      const data = await response.json();

      if (data.success) {
        setGraphData(data.data);
      } else {
        setError(data.error || "Failed to fetch dependencies");
      }
    } catch (err) {
      setError("Failed to connect to server");
    } finally {
      setLoading(false);
    }
  }, [repoUrl, issueNumber, depth, API_BASE_URL]);

  useEffect(() => {
    if (repoUrl && issueNumber) {
      fetchDependencies();
    }
  }, [repoUrl, issueNumber]);

  const getEdgeColor = (type) => {
    const colors = {
      fixes: "#22c55e",
      closes: "#22c55e",
      blocks: "#ef4444",
      blocked_by: "#f97316",
      mentions: "#6b7280",
    };
    return colors[type] || colors.mentions;
  };

  const getEdgeLabel = (type) => {
    const labels = {
      fixes: "fixes",
      closes: "closes",
      blocks: "blocks",
      blocked_by: "blocked by",
      mentions: "references",
    };
    return labels[type] || "references";
  };

  if (!repoUrl || !issueNumber) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-6 text-center">
        <GitBranch className="w-12 h-12 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500">
          Analyze an issue first to see its dependencies
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-600 to-purple-500 px-4 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitBranch className="w-5 h-5 text-white" />
            <h3 className="font-semibold text-white text-sm sm:text-base">
              Issue Dependencies
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
              className="text-xs sm:text-sm bg-white/20 text-white rounded px-2 py-1 border-0"
            >
              <option value={1} className="text-gray-800">
                Depth: 1
              </option>
              <option value={2} className="text-gray-800">
                Depth: 2
              </option>
              <option value={3} className="text-gray-800">
                Depth: 3
              </option>
            </select>
            <button
              onClick={fetchDependencies}
              disabled={loading}
              className="p-1.5 bg-white/20 hover:bg-white/30 rounded-lg transition-colors"
            >
              <RefreshCw
                className={`w-4 h-4 text-white ${
                  loading ? "animate-spin" : ""
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 sm:p-6">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="w-6 h-6 text-purple-500 animate-spin" />
            <span className="ml-2 text-gray-600">
              Analyzing dependencies...
            </span>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && graphData && (
          <div className="space-y-4">
            {/* Stats */}
            <div className="flex flex-wrap gap-4 text-sm">
              <div className="flex items-center gap-2">
                <Circle className="w-4 h-4 text-purple-500" />
                <span className="text-gray-600">
                  {graphData.total_nodes} issues found
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Link2 className="w-4 h-4 text-purple-500" />
                <span className="text-gray-600">
                  {graphData.total_edges} connections
                </span>
              </div>
            </div>

            {/* Graph Visualization */}
            {graphData.nodes.length > 0 ? (
              <div className="space-y-3">
                {/* Root Node */}
                {graphData.nodes
                  .filter((n) => n.is_root)
                  .map((node) => (
                    <div
                      key={node.id}
                      className="border-2 border-purple-500 rounded-lg p-4 bg-purple-50"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-bold text-purple-700">
                              #{node.issue_number}
                            </span>
                            <span
                              className={`px-2 py-0.5 text-xs rounded-full ${
                                node.state === "open"
                                  ? "bg-green-100 text-green-700"
                                  : "bg-gray-100 text-gray-600"
                              }`}
                            >
                              {node.state}
                            </span>
                            <span className="px-2 py-0.5 text-xs rounded-full bg-purple-200 text-purple-700">
                              Current Issue
                            </span>
                          </div>
                          <p className="text-gray-800 text-sm line-clamp-2">
                            {node.title}
                          </p>
                        </div>
                        <a
                          href={node.html_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1.5 hover:bg-purple-200 rounded transition-colors flex-shrink-0"
                        >
                          <ExternalLink className="w-4 h-4 text-purple-600" />
                        </a>
                      </div>
                    </div>
                  ))}

                {/* Edges and Connected Nodes */}
                {graphData.edges.length > 0 && (
                  <div className="pl-4 border-l-2 border-purple-200 space-y-2">
                    {graphData.edges.map((edge, idx) => {
                      const targetNode = graphData.nodes.find(
                        (n) => n.id === edge.target
                      );
                      if (!targetNode || targetNode.is_root) return null;

                      return (
                        <div key={idx} className="relative">
                          {/* Edge Label */}
                          <div className="flex items-center gap-2 mb-2">
                            <ArrowRight
                              className="w-4 h-4"
                              style={{ color: getEdgeColor(edge.type) }}
                            />
                            <span
                              className="text-xs font-medium px-2 py-0.5 rounded"
                              style={{
                                backgroundColor: `${getEdgeColor(edge.type)}20`,
                                color: getEdgeColor(edge.type),
                              }}
                            >
                              {getEdgeLabel(edge.type)}
                            </span>
                          </div>

                          {/* Target Node */}
                          <div className="border border-gray-200 rounded-lg p-3 bg-white hover:border-purple-300 transition-colors">
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="font-semibold text-gray-700">
                                    #{targetNode.issue_number}
                                  </span>
                                  {targetNode.state === "open" ? (
                                    <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                                  ) : (
                                    <XCircle className="w-3.5 h-3.5 text-gray-400" />
                                  )}
                                </div>
                                <p className="text-gray-600 text-sm line-clamp-2">
                                  {targetNode.title}
                                </p>
                                {edge.context && (
                                  <p className="text-xs text-gray-400 mt-1 italic line-clamp-1">
                                    {edge.context}
                                  </p>
                                )}
                              </div>
                              <a
                                href={targetNode.html_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="p-1 hover:bg-gray-100 rounded transition-colors flex-shrink-0"
                              >
                                <ExternalLink className="w-4 h-4 text-gray-500" />
                              </a>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {graphData.edges.length === 0 && (
                  <div className="text-center py-6 text-gray-500">
                    <Link2 className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                    <p>No issue references found in this issue</p>
                    <p className="text-xs mt-1">
                      The issue doesn't reference other issues with #123
                      patterns
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-6 text-gray-500">
                <GitBranch className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                <p>No dependency data available</p>
              </div>
            )}

            {/* Legend */}
            <div className="mt-4 pt-4 border-t border-gray-100">
              <p className="text-xs text-gray-500 mb-2">Reference Types:</p>
              <div className="flex flex-wrap gap-2">
                {["fixes", "blocks", "blocked_by", "mentions"].map((type) => (
                  <span
                    key={type}
                    className="text-xs px-2 py-1 rounded"
                    style={{
                      backgroundColor: `${getEdgeColor(type)}15`,
                      color: getEdgeColor(type),
                    }}
                  >
                    {getEdgeLabel(type)}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DependencyGraph;
