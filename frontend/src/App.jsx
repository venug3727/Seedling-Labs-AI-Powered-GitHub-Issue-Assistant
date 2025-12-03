/**
 * Main App Component
 *
 * GitHub Issue Assistant - AI-powered issue analysis tool.
 * Built for Seedling Labs Engineering Intern Craft Case.
 *
 * Features:
 * - Single Issue Analysis
 * - Issue Dependency Graph
 * - Duplicate Issue Detection
 * - Batch Analysis
 * - Cross-Repo Similar Issues
 */

import { useState } from "react";
import axios from "axios";
import {
  Sprout,
  Github,
  Sparkles,
  Target,
  Tags,
  BarChart3,
  GitBranch,
  Copy,
  Layers,
  Globe,
} from "lucide-react";

// Components
import InputForm from "./components/InputForm";
import AnalysisResult from "./components/AnalysisResult";
import Loader from "./components/Loader";
import ErrorDisplay from "./components/ErrorDisplay";
import DependencyGraph from "./components/DependencyGraph";
import DuplicateDetector from "./components/DuplicateDetector";
import BatchAnalysis from "./components/BatchAnalysis";
import CrossRepoSimilar from "./components/CrossRepoSimilar";
import LabelCreator from "./components/LabelCreator";

// API Configuration - Use relative URL for Vercel, or localhost for development
const API_BASE_URL = import.meta.env.VITE_API_URL || "";

// Tab definitions
const TABS = [
  {
    id: "analysis",
    label: "Analysis",
    icon: Sparkles,
    description: "AI-powered issue analysis",
  },
  {
    id: "dependencies",
    label: "Dependencies",
    icon: GitBranch,
    description: "Issue reference graph",
  },
  {
    id: "duplicates",
    label: "Duplicates",
    icon: Copy,
    description: "Find similar issues",
  },
  {
    id: "batch",
    label: "Batch",
    icon: Layers,
    description: "Analyze multiple issues",
  },
  {
    id: "cross-repo",
    label: "Cross-Repo",
    icon: Globe,
    description: "Search other repos",
  },
];

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("analysis");
  const [currentRepoUrl, setCurrentRepoUrl] = useState("");
  const [currentIssueNumber, setCurrentIssueNumber] = useState(null);
  const [showLabelCreator, setShowLabelCreator] = useState(false);

  /**
   * Handle form submission - analyze a GitHub issue
   */
  const handleAnalyze = async (formData) => {
    setIsLoading(true);
    setResult(null);
    setError(null);
    setCurrentRepoUrl(formData.repo_url);
    setCurrentIssueNumber(formData.issue_number);

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/analyze`,
        formData,
        {
          headers: {
            "Content-Type": "application/json",
          },
          timeout: 60000, // 60 second timeout for LLM processing
        }
      );

      const data = response.data;

      if (data.success) {
        setResult(data);
      } else {
        setError(data.error || "Analysis failed. Please try again.");
      }
    } catch (err) {
      console.error("Analysis error:", err);

      if (err.code === "ECONNABORTED") {
        setError(
          "Request timeout. The analysis is taking too long. Please try again."
        );
      } else if (err.response) {
        // Server responded with error
        setError(
          err.response.data?.detail ||
            err.response.data?.error ||
            "Server error. Please try again."
        );
      } else if (err.request) {
        // No response received
        setError(
          "Could not connect to the server. Please ensure the backend is running."
        );
      } else {
        setError("An unexpected error occurred. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Clear results and start fresh
   */
  const handleReset = () => {
    setResult(null);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-3 sm:px-6 lg:px-8 py-3 sm:py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="p-1.5 sm:p-2 bg-seedling-100 rounded-lg flex-shrink-0">
                <Sprout className="w-5 h-5 sm:w-6 sm:h-6 text-seedling-600" />
              </div>
              <div className="min-w-0">
                <h1 className="text-base sm:text-xl font-bold text-gray-900 truncate">
                  GitHub Issue Assistant
                </h1>
                <p className="text-xs sm:text-sm text-gray-500 hidden xs:block">
                  AI-Powered Analysis by Seedling Labs
                </p>
              </div>
            </div>
            <div className="hidden sm:flex items-center gap-2 text-sm text-gray-500">
              <Sparkles className="w-4 h-4 text-seedling-500" />
              <span>Powered by Gemini AI</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-8">
        {/* Hero Section - Only show when no results */}
        {!result && !isLoading && !error && (
          <div className="text-center mb-6 sm:mb-8">
            <div className="inline-flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-1.5 sm:py-2 bg-seedling-100 text-seedling-700 rounded-full text-xs sm:text-sm font-medium mb-3 sm:mb-4">
              <Github className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              Public Repositories Only
            </div>
            <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-900 mb-2 sm:mb-3 px-2">
              Analyze Any GitHub Issue with AI
            </h2>
            <p className="text-sm sm:text-base md:text-lg text-gray-600 max-w-2xl mx-auto px-2">
              Get instant insights, priority scoring, and smart label
              suggestions for any public GitHub issue.
            </p>
          </div>
        )}

        {/* Input Form - Always visible unless loading */}
        {!isLoading && (
          <div className="mb-6">
            <InputForm onSubmit={handleAnalyze} isLoading={isLoading} />
          </div>
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="mb-8">
            <Loader />
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="mb-8">
            <ErrorDisplay error={error} onRetry={handleReset} />
          </div>
        )}

        {/* Tab Navigation - Only show after analysis is complete */}
        {result && (
          <div className="mb-6">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-1.5">
              <div className="flex overflow-x-auto gap-1 scrollbar-hide">
                {TABS.map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-2 sm:py-2.5 rounded-lg font-medium text-xs sm:text-sm whitespace-nowrap transition-all ${
                        isActive
                          ? "bg-seedling-100 text-seedling-700"
                          : "text-gray-600 hover:bg-gray-100"
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      <span>{tab.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-2 text-center">
              {TABS.find((t) => t.id === activeTab)?.description}
            </p>
          </div>
        )}

        {/* Tab Content - Only show after analysis */}
        {result && (
          <div className="space-y-6">
            {/* Analysis Tab */}
            {activeTab === "analysis" && (
              <div className="mb-8">
                <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                  <h2 className="text-lg font-semibold text-gray-800">
                    Analysis Results
                  </h2>
                  <div className="flex items-center gap-2">
                    {result.analysis?.suggested_labels && (
                      <button
                        onClick={() => setShowLabelCreator(true)}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-seedling-100 hover:bg-seedling-200 text-seedling-700 rounded-lg text-sm font-medium transition-colors"
                      >
                        <Tags className="w-4 h-4" />
                        <span className="hidden sm:inline">
                          Create Labels on GitHub
                        </span>
                        <span className="sm:hidden">Create Labels</span>
                      </button>
                    )}
                    <button
                      onClick={handleReset}
                      className="text-sm text-seedling-600 hover:text-seedling-700 font-medium"
                    >
                      ← New Analysis
                    </button>
                  </div>
                </div>
                <AnalysisResult data={result} />
              </div>
            )}

            {/* Dependencies Tab */}
            {activeTab === "dependencies" && (
              <DependencyGraph
                repoUrl={currentRepoUrl}
                issueNumber={currentIssueNumber}
                issueData={result?.issue_data}
              />
            )}

            {/* Duplicates Tab */}
            {activeTab === "duplicates" && (
              <DuplicateDetector
                repoUrl={currentRepoUrl}
                issueNumber={currentIssueNumber}
                issueData={result?.issue_data}
              />
            )}

            {/* Batch Tab */}
            {activeTab === "batch" && (
              <BatchAnalysis repoUrl={currentRepoUrl} />
            )}

            {/* Cross-Repo Tab */}
            {activeTab === "cross-repo" && (
              <CrossRepoSimilar
                issueData={result?.issue_data}
                repoUrl={currentRepoUrl}
              />
            )}
          </div>
        )}

        {/* Features Section - Only show on initial state (no result, no loading, no error) */}
        {!result && !isLoading && !error && (
          <div className="mt-8 sm:mt-12 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 sm:gap-6">
            <FeatureCard
              icon={Target}
              title="Priority Scoring"
              description="AI assigns a priority score (1-5) based on business impact and user urgency."
            />
            <FeatureCard
              icon={Tags}
              title="Smart Labels"
              description="Get intelligent label suggestions to organize your issues effectively."
            />
            <FeatureCard
              icon={BarChart3}
              title="Impact Analysis"
              description="Understand the potential impact on users to make informed decisions."
            />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white mt-auto">
        <div className="max-w-6xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6">
          <div className="flex flex-col items-center justify-center gap-2 sm:gap-4 text-center">
            <div className="flex items-center gap-2 text-gray-500 text-xs sm:text-sm">
              <Sprout className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-seedling-500" />
              <span>Seedling Labs Engineering Craft Case</span>
            </div>
            <div className="text-xs sm:text-sm text-gray-400">
              Built with React, FastAPI, and Gemini AI
            </div>
          </div>
        </div>
      </footer>

      {/* Label Creator Modal */}
      {showLabelCreator && result?.analysis?.suggested_labels && (
        <LabelCreator
          repoUrl={currentRepoUrl}
          suggestedLabels={result.analysis.suggested_labels}
          onClose={() => setShowLabelCreator(false)}
        />
      )}
    </div>
  );
}

/**
 * Feature Card Component
 */
const FeatureCard = ({ icon: Icon, title, description }) => (
  <div className="bg-white rounded-xl p-4 sm:p-6 shadow-md hover:shadow-lg transition-shadow">
    <div className="p-2 sm:p-3 bg-seedling-100 rounded-lg w-fit mb-2 sm:mb-3">
      <Icon className="w-5 h-5 sm:w-6 sm:h-6 text-seedling-600" />
    </div>
    <h3 className="font-semibold text-gray-900 mb-1 sm:mb-2 text-sm sm:text-base">
      {title}
    </h3>
    <p className="text-xs sm:text-sm text-gray-600">{description}</p>
  </div>
);

export default App;
