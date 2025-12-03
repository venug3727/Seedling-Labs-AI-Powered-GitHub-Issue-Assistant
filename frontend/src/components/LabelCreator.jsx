/**
 * LabelCreator Component
 *
 * Create suggested labels on GitHub using user's Personal Access Token.
 * Shows a modal for token input and creates labels via API.
 */

import { useState } from "react";
import {
  Tag,
  Plus,
  Check,
  AlertCircle,
  X,
  Key,
  ExternalLink,
  RefreshCw,
  Lock,
  CheckCircle,
  XCircle,
} from "lucide-react";

const LabelCreator = ({ repoUrl, suggestedLabels, onClose }) => {
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [selectedLabels, setSelectedLabels] = useState(suggestedLabels || []);

  const API_BASE_URL = import.meta.env.VITE_API_URL || "";

  const toggleLabel = (label) => {
    setSelectedLabels((prev) =>
      prev.includes(label) ? prev.filter((l) => l !== label) : [...prev, label]
    );
  };

  const createLabels = async () => {
    if (!token.trim()) {
      setError("Please enter your GitHub Personal Access Token");
      return;
    }

    if (selectedLabels.length === 0) {
      setError("Please select at least one label to create");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/create-labels`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: repoUrl,
          labels: selectedLabels,
          github_token: token,
        }),
      });

      const data = await response.json();

      if (data.success) {
        setResults(data.data);
      } else {
        setError(data.error || "Failed to create labels");
      }
    } catch (err) {
      setError("Failed to connect to server");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-md w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="bg-gradient-to-r from-seedling-600 to-seedling-500 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Tag className="w-5 h-5 text-white" />
            <h3 className="font-semibold text-white">Create GitHub Labels</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-white" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {!results ? (
            <>
              {/* Warning */}
              <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-700 text-sm">
                <Lock className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium">Requires GitHub Access</p>
                  <p className="text-xs mt-1">
                    Your token is only used for this request and never stored.
                  </p>
                </div>
              </div>

              {/* Token Input */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  GitHub Personal Access Token
                </label>
                <input
                  type="password"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="ghp_xxxxxxxxxxxx"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-seedling-500 focus:border-seedling-500"
                />
                <a
                  href="https://github.com/settings/tokens/new?scopes=repo&description=Issue%20Assistant%20Label%20Creator"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-seedling-600 hover:underline mt-1"
                >
                  <ExternalLink className="w-3 h-3" />
                  Create a token with "repo" scope
                </a>
              </div>

              {/* Label Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select Labels to Create
                </label>
                <div className="flex flex-wrap gap-2">
                  {suggestedLabels?.map((label, idx) => (
                    <button
                      key={idx}
                      onClick={() => toggleLabel(label)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                        selectedLabels.includes(label)
                          ? "bg-seedling-100 text-seedling-700 border-2 border-seedling-500"
                          : "bg-gray-100 text-gray-600 border-2 border-transparent hover:bg-gray-200"
                      }`}
                    >
                      {selectedLabels.includes(label) ? (
                        <Check className="w-3.5 h-3.5" />
                      ) : (
                        <Plus className="w-3.5 h-3.5" />
                      )}
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Error */}
              {error && (
                <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {/* Create Button */}
              <button
                onClick={createLabels}
                disabled={
                  loading || !token.trim() || selectedLabels.length === 0
                }
                className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-all ${
                  loading || !token.trim() || selectedLabels.length === 0
                    ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                    : "bg-seedling-600 hover:bg-seedling-700 text-white"
                }`}
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Creating Labels...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    Create {selectedLabels.length} Label
                    {selectedLabels.length !== 1 ? "s" : ""}
                  </>
                )}
              </button>
            </>
          ) : (
            /* Results */
            <div className="space-y-4">
              <div className="text-center py-4">
                <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-2" />
                <h4 className="font-semibold text-gray-800">
                  Labels Processed
                </h4>
              </div>

              {/* Created */}
              {results.created?.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-green-700 mb-2">
                    ✅ Created ({results.created.length})
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {results.created.map((label, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs"
                      >
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Existing */}
              {results.existing?.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-blue-700 mb-2">
                    ℹ️ Already Exists ({results.existing.length})
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {results.existing.map((label, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs"
                      >
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Failed */}
              {results.failed?.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-red-700 mb-2">
                    ❌ Failed ({results.failed.length})
                  </p>
                  <div className="space-y-1">
                    {results.failed.map((item, idx) => (
                      <div key={idx} className="text-xs text-red-600">
                        {item.label}: {item.error}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <button
                onClick={onClose}
                className="w-full px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-medium transition-colors"
              >
                Close
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LabelCreator;
