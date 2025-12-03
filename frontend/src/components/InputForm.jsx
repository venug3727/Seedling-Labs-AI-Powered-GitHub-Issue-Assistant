/**
 * InputForm Component
 * 
 * Handles user input for GitHub repository URL and issue number.
 * Features:
 * - Real-time URL validation
 * - Loading state during analysis
 * - Error display
 */

import { useState } from 'react';
import { Github, Search, AlertCircle, HelpCircle } from 'lucide-react';

const InputForm = ({ onSubmit, isLoading }) => {
  const [repoUrl, setRepoUrl] = useState('');
  const [issueNumber, setIssueNumber] = useState('');
  const [validationError, setValidationError] = useState('');

  // Validate GitHub URL format
  const validateUrl = (url) => {
    const pattern = /^https?:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/;
    return pattern.test(url.trim());
  };

  // Handle form submission
  const handleSubmit = (e) => {
    e.preventDefault();
    setValidationError('');

    // Validate inputs
    if (!repoUrl.trim()) {
      setValidationError('Please enter a GitHub repository URL');
      return;
    }

    if (!validateUrl(repoUrl)) {
      setValidationError('Invalid URL format. Example: https://github.com/facebook/react');
      return;
    }

    const issueNum = parseInt(issueNumber, 10);
    if (!issueNumber || isNaN(issueNum) || issueNum <= 0) {
      setValidationError('Please enter a valid issue number (positive integer)');
      return;
    }

    // Submit form
    onSubmit({
      repo_url: repoUrl.trim(),
      issue_number: issueNum
    });
  };

  // Example repos for quick testing
  const exampleRepos = [
    { url: 'https://github.com/facebook/react', issue: 28850 },
    { url: 'https://github.com/microsoft/vscode', issue: 100 },
    { url: 'https://github.com/vercel/next.js', issue: 50000 },
  ];

  const fillExample = (example) => {
    setRepoUrl(example.url);
    setIssueNumber(example.issue.toString());
    setValidationError('');
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-6 md:p-8">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-seedling-100 rounded-lg">
          <Github className="w-6 h-6 text-seedling-600" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Analyze GitHub Issue</h2>
          <p className="text-sm text-gray-500">Enter a public repository URL and issue number</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Repository URL Input */}
        <div>
          <label htmlFor="repoUrl" className="block text-sm font-medium text-gray-700 mb-1">
            Repository URL
          </label>
          <div className="relative">
            <input
              type="text"
              id="repoUrl"
              value={repoUrl}
              onChange={(e) => {
                setRepoUrl(e.target.value);
                setValidationError('');
              }}
              placeholder="https://github.com/owner/repo"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-seedling-500 focus:border-seedling-500 transition-colors"
              disabled={isLoading}
            />
          </div>
        </div>

        {/* Issue Number Input */}
        <div>
          <label htmlFor="issueNumber" className="block text-sm font-medium text-gray-700 mb-1">
            Issue Number
          </label>
          <input
            type="number"
            id="issueNumber"
            value={issueNumber}
            onChange={(e) => {
              setIssueNumber(e.target.value);
              setValidationError('');
            }}
            placeholder="12345"
            min="1"
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-seedling-500 focus:border-seedling-500 transition-colors"
            disabled={isLoading}
          />
        </div>

        {/* Validation Error */}
        {validationError && (
          <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 p-3 rounded-lg">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{validationError}</span>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isLoading}
          className={`w-full flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-medium transition-all
            ${isLoading 
              ? 'bg-gray-400 cursor-not-allowed' 
              : 'bg-seedling-600 hover:bg-seedling-700 active:bg-seedling-800 text-white shadow-md hover:shadow-lg'
            }`}
        >
          {isLoading ? (
            <>
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Analyzing...
            </>
          ) : (
            <>
              <Search className="w-5 h-5" />
              Analyze Issue
            </>
          )}
        </button>
      </form>

      {/* Quick Examples */}
      <div className="mt-6 pt-6 border-t border-gray-100">
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-3">
          <HelpCircle className="w-4 h-4" />
          <span>Try an example:</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {exampleRepos.map((example, index) => (
            <button
              key={index}
              onClick={() => fillExample(example)}
              disabled={isLoading}
              className="text-xs px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-full transition-colors disabled:opacity-50"
            >
              {example.url.replace('https://github.com/', '')} #{example.issue}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default InputForm;
