/**
 * Loader Component
 *
 * Animated loading indicator with status messages.
 * Shows progress during issue analysis.
 */

import { Sprout, Github, Brain, CheckCircle } from "lucide-react";
import { useState, useEffect } from "react";

const Loader = () => {
  const [step, setStep] = useState(0);

  const steps = [
    {
      icon: Github,
      text: "Fetching issue from GitHub...",
      color: "text-gray-600",
    },
    {
      icon: Brain,
      text: "AI is analyzing the issue...",
      color: "text-purple-600",
    },
    {
      icon: CheckCircle,
      text: "Generating insights...",
      color: "text-seedling-600",
    },
  ];

  // Cycle through steps for visual feedback
  useEffect(() => {
    const interval = setInterval(() => {
      setStep((prev) => (prev + 1) % steps.length);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const CurrentIcon = steps[step].icon;

  return (
    <div className="bg-white rounded-xl shadow-lg p-8 text-center">
      {/* Main Animation */}
      <div className="relative w-24 h-24 mx-auto mb-6">
        {/* Outer ring */}
        <div className="absolute inset-0 border-4 border-seedling-100 rounded-full" />

        {/* Spinning ring */}
        <div className="absolute inset-0 border-4 border-transparent border-t-seedling-500 rounded-full animate-spin" />

        {/* Center icon */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div
            className={`p-3 bg-gray-50 rounded-full transition-all duration-300 ${steps[step].color}`}
          >
            <CurrentIcon className="w-8 h-8" />
          </div>
        </div>
      </div>

      {/* Status Text */}
      <div className="space-y-2">
        <p
          className={`text-lg font-medium transition-colors duration-300 ${steps[step].color}`}
        >
          {steps[step].text}
        </p>
        <p className="text-sm text-gray-400">This may take a few seconds...</p>
      </div>

      {/* Progress Dots */}
      <div className="flex justify-center gap-2 mt-6">
        {steps.map((_, index) => (
          <div
            key={index}
            className={`w-2 h-2 rounded-full transition-all duration-300 ${
              index === step
                ? "bg-seedling-500 w-4"
                : index < step
                ? "bg-seedling-300"
                : "bg-gray-200"
            }`}
          />
        ))}
      </div>

      {/* Seedling branding */}
      <div className="mt-8 pt-6 border-t border-gray-100 flex items-center justify-center gap-2 text-gray-400">
        <Sprout className="w-4 h-4" />
        <span className="text-xs">Powered by Seedling Labs AI</span>
      </div>
    </div>
  );
};

export default Loader;
