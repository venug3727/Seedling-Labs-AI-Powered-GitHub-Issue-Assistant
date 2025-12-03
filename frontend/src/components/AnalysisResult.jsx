/**
 * AnalysisResult Component
 *
 * Displays the AI-generated analysis with:
 * - Visual priority tags (color-coded)
 * - Issue type badges
 * - Copy JSON button
 * - Export to PDF
 * - Expandable sections
 */

import { useState, useRef } from "react";
import {
  Copy,
  Check,
  ExternalLink,
  Tag,
  AlertTriangle,
  MessageSquare,
  User,
  Calendar,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Target,
  Lightbulb,
  AlertCircle,
  CircleDot,
  Bug,
  Zap,
  BookOpen,
  HelpCircle,
  FileText,
  Download,
} from "lucide-react";

/**
 * Priority Badge Component
 * Color-coded visual indicator for priority levels with icons
 */
const PriorityBadge = ({ score }) => {
  const config = {
    5: {
      label: "Critical",
      bg: "bg-red-100",
      text: "text-red-700",
      border: "border-red-200",
      dotColor: "bg-red-500",
    },
    4: {
      label: "High",
      bg: "bg-orange-100",
      text: "text-orange-700",
      border: "border-orange-200",
      dotColor: "bg-orange-500",
    },
    3: {
      label: "Medium",
      bg: "bg-yellow-100",
      text: "text-yellow-700",
      border: "border-yellow-200",
      dotColor: "bg-yellow-500",
    },
    2: {
      label: "Low",
      bg: "bg-blue-100",
      text: "text-blue-700",
      border: "border-blue-200",
      dotColor: "bg-blue-500",
    },
    1: {
      label: "Minimal",
      bg: "bg-gray-100",
      text: "text-gray-700",
      border: "border-gray-200",
      dotColor: "bg-gray-400",
    },
  };

  const { label, bg, text, border, dotColor } = config[score] || config[3];

  return (
    <div
      className={`inline-flex items-center gap-2 px-4 py-2 rounded-full ${bg} ${text} ${border} border font-medium`}
    >
      <span className={`w-3 h-3 rounded-full ${dotColor}`}></span>
      <span>Priority {score}/5</span>
      <span className="text-xs opacity-75">({label})</span>
    </div>
  );
};

/**
 * Issue Type Badge Component with Lucide icons
 */
const TypeBadge = ({ type }) => {
  const config = {
    bug: { bg: "bg-red-500", Icon: Bug },
    feature_request: { bg: "bg-purple-500", Icon: Zap },
    documentation: { bg: "bg-blue-500", Icon: BookOpen },
    question: { bg: "bg-green-500", Icon: HelpCircle },
    other: { bg: "bg-gray-500", Icon: FileText },
  };

  const { bg, Icon } = config[type] || config.other;
  const displayType = type.replace("_", " ");

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 ${bg} text-white text-sm font-medium rounded-full capitalize`}
    >
      <Icon className="w-3.5 h-3.5" />
      {displayType}
    </span>
  );
};

/**
 * Label Chip Component
 */
const LabelChip = ({ label }) => {
  // Generate consistent color based on label text
  const colors = [
    "bg-blue-100 text-blue-700",
    "bg-green-100 text-green-700",
    "bg-purple-100 text-purple-700",
    "bg-pink-100 text-pink-700",
    "bg-indigo-100 text-indigo-700",
    "bg-teal-100 text-teal-700",
  ];
  const colorIndex = label.length % colors.length;

  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-1 ${colors[colorIndex]} text-xs font-medium rounded-full`}
    >
      <Tag className="w-3 h-3" />
      {label}
    </span>
  );
};

const AnalysisResult = ({ data }) => {
  const [copied, setCopied] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);
  const [showIssueDetails, setShowIssueDetails] = useState(false);
  const [exporting, setExporting] = useState(false);
  const resultRef = useRef(null);

  const { issue_data, analysis } = data;

  // Copy JSON to clipboard
  const copyToClipboard = async () => {
    const jsonOutput = JSON.stringify(analysis, null, 2);
    try {
      await navigator.clipboard.writeText(jsonOutput);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  // Export to PDF
  const exportToPDF = async () => {
    setExporting(true);

    try {
      // Create a printable version
      const printContent = `
        <!DOCTYPE html>
        <html>
        <head>
          <title>Issue Analysis - ${issue_data.title}</title>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; max-width: 800px; margin: 0 auto; color: #1f2937; }
            h1 { color: #059669; font-size: 24px; margin-bottom: 8px; }
            h2 { color: #374151; font-size: 18px; margin-top: 24px; margin-bottom: 12px; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; }
            .header { background: linear-gradient(135deg, #059669, #10b981); color: white; padding: 24px; border-radius: 12px; margin-bottom: 24px; }
            .header h1 { color: white; margin: 0; }
            .header p { color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 14px; }
            .meta { display: flex; gap: 24px; margin-top: 16px; font-size: 13px; color: rgba(255,255,255,0.8); }
            .badge { display: inline-block; padding: 6px 16px; border-radius: 20px; font-weight: 600; font-size: 14px; margin-right: 8px; }
            .priority-5 { background: #fef2f2; color: #b91c1c; }
            .priority-4 { background: #fff7ed; color: #c2410c; }
            .priority-3 { background: #fefce8; color: #a16207; }
            .priority-2 { background: #eff6ff; color: #1d4ed8; }
            .priority-1 { background: #f3f4f6; color: #374151; }
            .type-bug { background: #ef4444; color: white; }
            .type-feature_request { background: #8b5cf6; color: white; }
            .type-documentation { background: #3b82f6; color: white; }
            .type-question { background: #22c55e; color: white; }
            .type-other { background: #6b7280; color: white; }
            .section { background: #f9fafb; padding: 16px; border-radius: 8px; margin-bottom: 16px; }
            .section-title { font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; color: #6b7280; margin-bottom: 8px; font-weight: 600; }
            .labels { display: flex; flex-wrap: wrap; gap: 8px; }
            .label { background: #e0f2fe; color: #0369a1; padding: 4px 12px; border-radius: 12px; font-size: 12px; }
            .footer { margin-top: 32px; padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #9ca3af; text-align: center; }
            @media print { body { padding: 20px; } .header { break-inside: avoid; } }
          </style>
        </head>
        <body>
          <div class="header">
            <h1>${issue_data.title}</h1>
            <p>Issue #${issue_data.html_url.split("/").pop()} • ${
        issue_data.state
      }</p>
            <div class="meta">
              <span>Author: ${issue_data.author}</span>
              <span>Created: ${new Date(
                issue_data.created_at
              ).toLocaleDateString()}</span>
              <span>Comments: ${issue_data.comment_count}</span>
            </div>
          </div>

          <div style="margin-bottom: 24px;">
            <span class="badge type-${analysis.type}">${analysis.type
        .replace("_", " ")
        .toUpperCase()}</span>
            <span class="badge priority-${analysis.priority_score}">PRIORITY ${
        analysis.priority_score
      }/5</span>
          </div>

          <h2>Summary</h2>
          <div class="section">
            <p style="margin: 0; line-height: 1.6;">${analysis.summary}</p>
          </div>

          <h2>Priority Justification</h2>
          <div class="section">
            <p style="margin: 0; line-height: 1.6;">${
              analysis.priority_justification
            }</p>
          </div>

          <h2>Potential Impact</h2>
          <div class="section">
            <p style="margin: 0; line-height: 1.6;">${
              analysis.potential_impact
            }</p>
          </div>

          <h2>Suggested Labels</h2>
          <div class="labels">
            ${analysis.suggested_labels
              .map((label) => `<span class="label">${label}</span>`)
              .join("")}
          </div>

          <div class="footer">
            <p>Generated by Seedling Labs GitHub Issue Assistant</p>
            <p>Analysis Date: ${new Date().toLocaleString()}</p>
            <p>Source: ${issue_data.html_url}</p>
          </div>
        </body>
        </html>
      `;

      // Open print dialog
      const printWindow = window.open("", "_blank");
      printWindow.document.write(printContent);
      printWindow.document.close();
      printWindow.focus();

      // Wait for content to load then print
      setTimeout(() => {
        printWindow.print();
        printWindow.close();
      }, 250);
    } catch (err) {
      console.error("Failed to export PDF:", err);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header with Issue Info */}
      <div className="bg-white rounded-xl shadow-lg overflow-hidden">
        {/* Title Bar */}
        <div className="bg-gradient-to-r from-seedling-600 to-seedling-500 px-6 py-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 text-seedling-100 text-sm mb-1">
                <span>Issue #{issue_data.html_url.split("/").pop()}</span>
                <span>•</span>
                <span className="capitalize">{issue_data.state}</span>
              </div>
              <h2 className="text-xl font-semibold text-white truncate">
                {issue_data.title}
              </h2>
            </div>
            <a
              href={issue_data.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white text-sm rounded-lg transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              View on GitHub
            </a>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-100 flex flex-wrap gap-4 text-sm text-gray-600">
          <div className="flex items-center gap-1.5">
            <User className="w-4 h-4" />
            <span>{issue_data.author}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Calendar className="w-4 h-4" />
            <span>{new Date(issue_data.created_at).toLocaleDateString()}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <MessageSquare className="w-4 h-4" />
            <span>{issue_data.comment_count} comments</span>
          </div>
          {issue_data.was_truncated && (
            <div className="flex items-center gap-1.5 text-amber-600">
              <AlertTriangle className="w-4 h-4" />
              <span>Content truncated</span>
            </div>
          )}
        </div>

        {/* Expandable Issue Details */}
        <div className="px-6">
          <button
            onClick={() => setShowIssueDetails(!showIssueDetails)}
            className="w-full py-3 flex items-center justify-between text-sm text-gray-500 hover:text-gray-700 transition-colors"
          >
            <span>Issue Details</span>
            {showIssueDetails ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>

          {showIssueDetails && (
            <div className="pb-4 space-y-3">
              {issue_data.body && (
                <div className="p-3 bg-gray-50 rounded-lg text-sm text-gray-700 whitespace-pre-wrap max-h-48 overflow-y-auto">
                  {issue_data.body}
                </div>
              )}
              {issue_data.labels.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  <span className="text-xs text-gray-500">
                    Existing labels:
                  </span>
                  {issue_data.labels.map((label, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 bg-gray-200 text-gray-700 text-xs rounded"
                    >
                      {label}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* AI Analysis Card */}
      <div className="bg-white rounded-xl shadow-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-seedling-500" />
            <h3 className="font-semibold text-gray-900">AI Analysis</h3>
          </div>
          <div className="flex items-center gap-2">
            <TypeBadge type={analysis.type} />
            <PriorityBadge score={analysis.priority_score} />
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Summary */}
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-gray-500 mb-2">
              <Target className="w-4 h-4" />
              Summary
            </div>
            <p className="text-gray-800 leading-relaxed">{analysis.summary}</p>
          </div>

          {/* Priority Justification */}
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-gray-500 mb-2">
              <AlertTriangle className="w-4 h-4" />
              Priority Justification
            </div>
            <p className="text-gray-700">{analysis.priority_justification}</p>
          </div>

          {/* Potential Impact */}
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-gray-500 mb-2">
              <Lightbulb className="w-4 h-4" />
              Potential Impact
            </div>
            <p className="text-gray-700">{analysis.potential_impact}</p>
          </div>

          {/* Suggested Labels */}
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-gray-500 mb-3">
              <Tag className="w-4 h-4" />
              Suggested Labels
            </div>
            <div className="flex flex-wrap gap-2">
              {analysis.suggested_labels.map((label, index) => (
                <LabelChip key={index} label={label} />
              ))}
            </div>
          </div>
        </div>

        {/* Actions Footer */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex flex-wrap items-center justify-between gap-3">
          <button
            onClick={() => setShowRawJson(!showRawJson)}
            className="text-sm text-gray-600 hover:text-gray-800 transition-colors"
          >
            {showRawJson ? "Hide" : "Show"} Raw JSON
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={exportToPDF}
              disabled={exporting}
              className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50"
            >
              <Download className="w-4 h-4" />
              {exporting ? "Exporting..." : "Export PDF"}
            </button>

            <button
              onClick={copyToClipboard}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                copied
                  ? "bg-green-100 text-green-700"
                  : "bg-seedling-100 text-seedling-700 hover:bg-seedling-200"
              }`}
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  Copy JSON
                </>
              )}
            </button>
          </div>
        </div>

        {/* Raw JSON Display */}
        {showRawJson && (
          <div className="px-6 pb-6">
            <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto text-sm">
              {JSON.stringify(analysis, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};

export default AnalysisResult;
