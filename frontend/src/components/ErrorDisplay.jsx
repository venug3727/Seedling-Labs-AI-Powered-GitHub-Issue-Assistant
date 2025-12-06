/**
 * ErrorDisplay Component
 *
 * User-friendly error display with helpful suggestions.
 */

import { AlertCircle, RefreshCw, HelpCircle } from "lucide-react";

const ErrorDisplay = ({ error, onRetry }) => {
  // Determine error type and provide helpful message
  const getErrorDetails = (errorMessage) => {
    // Ensure errorMessage is a string
    const msg = (typeof errorMessage === 'string' ? errorMessage : String(errorMessage || 'Unknown error')).toLowerCase();

    if (msg.includes("not found") || msg.includes("404")) {
      return {
        title: "Issue Not Found",
        description: "The repository or issue could not be found.",
        suggestions: [
          "Check that the repository URL is correct",
          "Verify the issue number exists",
          "Make sure the repository is public",
        ],
      };
    }

    if (
      msg.includes("private") ||
      msg.includes("access denied") ||
      msg.includes("403")
    ) {
      return {
        title: "Access Denied",
        description: "Cannot access this repository.",
        suggestions: [
          "This might be a private repository",
          "Only public repositories are supported",
          "Check if the URL is correct",
        ],
      };
    }

    if (msg.includes("rate limit")) {
      return {
        title: "Rate Limit Exceeded",
        description: "Too many requests to GitHub API.",
        suggestions: [
          "Wait a few minutes and try again",
          "GitHub limits unauthenticated requests",
        ],
      };
    }

    if (msg.includes("timeout")) {
      return {
        title: "Request Timeout",
        description: "The request took too long to complete.",
        suggestions: [
          "Check your internet connection",
          "Try again in a moment",
          "The server might be busy",
        ],
      };
    }

    if (msg.includes("ai") || msg.includes("llm") || msg.includes("analysis")) {
      return {
        title: "Analysis Error",
        description: "The AI could not analyze this issue.",
        suggestions: [
          "Try again - sometimes AI responses vary",
          "The issue might have unusual formatting",
        ],
      };
    }

    return {
      title: "Something Went Wrong",
      description: errorMessage,
      suggestions: ["Please try again", "Check your inputs and try once more"],
    };
  };

  const { title, description, suggestions } = getErrorDetails(error);

  return (
    <div className="bg-white rounded-xl shadow-lg overflow-hidden">
      {/* Error Header */}
      <div className="bg-red-50 px-6 py-4 border-b border-red-100">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-red-100 rounded-lg">
            <AlertCircle className="w-6 h-6 text-red-600" />
          </div>
          <div>
            <h3 className="font-semibold text-red-800">{title}</h3>
            <p className="text-sm text-red-600">{description}</p>
          </div>
        </div>
      </div>

      {/* Suggestions */}
      <div className="p-6">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-500 mb-3">
          <HelpCircle className="w-4 h-4" />
          Suggestions
        </div>
        <ul className="space-y-2">
          {suggestions.map((suggestion, index) => (
            <li key={index} className="flex items-start gap-2 text-gray-700">
              <span className="text-gray-400 mt-1">•</span>
              <span>{suggestion}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Retry Button */}
      {onRetry && (
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-100">
          <button
            onClick={onRetry}
            className="flex items-center gap-2 px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </button>
        </div>
      )}
    </div>
  );
};

export default ErrorDisplay;
