# 🌱 AI-Powered GitHub Issue Assistant

> **Seedling Labs Engineering Intern Craft Case**

An intelligent web application that analyzes GitHub issues using AI to provide structured summaries, priority scoring, and actionable insights for engineering teams.

![GitHub Issue Assistant Demo](https://img.shields.io/badge/Status-Production_Ready-green)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)

---

## 🚀 Quick Start (< 5 minutes)

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- [Google Gemini API Key](https://aistudio.google.com/app/apikey) (free tier available)

### Setup Instructions

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/seedling-issue-assistant.git
cd seedling-issue-assistant

# 2. Create environment file
cp .env.example .env

# 3. Add your Gemini API key to .env
# Edit .env and replace 'your_gemini_api_key_here' with your actual key

# 4. Build and run with Docker Compose
docker-compose up --build

# 5. Open your browser
# Frontend: http://localhost:5173
# API Docs: http://localhost:8000/docs
```

That's it! 🎉 The application is now running.

### Environment Variables Setup

Create a `.env` file in the root directory with the following variables:

```env
# ===========================================
# GitHub Issue Assistant - Environment Config
# ===========================================

# ✅ REQUIRED: Google Gemini API Key
# Get your free key at: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key_here

# ❌ OPTIONAL: GitHub Personal Access Token
# Increases rate limit from 60 to 5000 requests/hour
# Create at: https://github.com/settings/tokens
# Required scopes: public_repo (read-only)
GITHUB_TOKEN=your_github_token_here
```

#### How to Get Your API Keys:

**1. Gemini API Key (Required)**

- Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
- Sign in with your Google account
- Click "Create API Key"
- Copy the key and paste it in your `.env` file

**2. GitHub Token (Optional but Recommended)**

- Go to [GitHub Settings → Tokens](https://github.com/settings/tokens)
- Click "Generate new token (classic)"
- Give it a name like "Issue Assistant"
- Select scope: `public_repo`
- Generate and copy the token to your `.env` file

---

## 📋 Features

### Core Functionality

- ✅ **GitHub Issue Fetching**: Retrieves title, body, and comments from any public repository
- ✅ **AI-Powered Analysis**: Uses Google Gemini 1.5 Flash for intelligent issue analysis
- ✅ **Structured JSON Output**: Consistent, validated output format for easy integration

### AI Analysis Output

```json
{
    "summary": "One-sentence summary of the issue",
    "type": "bug | feature_request | documentation | question | other",
    "priority_score": 1-5,
    "priority_justification": "Reasoning for the priority score",
    "suggested_labels": ["relevant", "github", "labels"],
    "potential_impact": "Impact assessment for users"
}
```

### Extra Mile Features 🌟

- ✅ **Copy JSON Button**: One-click copy of analysis results to clipboard
- ✅ **Visual Priority Tags**: Color-coded priority badges (Critical=Red → Minimal=Gray)
- ✅ **Error Handling**: User-friendly error messages with helpful suggestions
- ✅ **Loading States**: Animated progress indicators during analysis
- ✅ **Quick Examples**: Pre-filled example repositories for easy testing

---

## 🏗️ Architecture

### Architecture Decision

> **"I chose a modular monolith to balance separation of concerns with ease of deployment (Docker Compose)."**

```
seedling-issue-assistant/
├── backend/                    # FastAPI Backend
│   ├── app/
│   │   ├── main.py            # Application entry point
│   │   ├── api.py             # API routes
│   │   ├── models.py          # Pydantic schemas
│   │   └── services/
│   │       ├── github_service.py   # GitHub API integration
│   │       └── llm_service.py      # Gemini AI integration
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                   # React + Vite Frontend
│   ├── src/
│   │   ├── App.jsx            # Main application
│   │   └── components/
│   │       ├── InputForm.jsx      # User input handling
│   │       ├── AnalysisResult.jsx # Results display
│   │       ├── Loader.jsx         # Loading animation
│   │       └── ErrorDisplay.jsx   # Error handling
│   ├── Dockerfile             # Multi-stage build
│   └── package.json
├── docker-compose.yml         # Container orchestration
└── README.md
```

### Tech Stack

| Layer           | Technology              | Purpose                           |
| --------------- | ----------------------- | --------------------------------- |
| **Frontend**    | React + Vite            | Fast, modern UI framework         |
| **Styling**     | TailwindCSS             | Utility-first CSS                 |
| **Icons**       | Lucide React            | Clean, consistent iconography     |
| **HTTP Client** | Axios                   | Promise-based HTTP requests       |
| **Backend**     | FastAPI                 | High-performance async Python API |
| **Validation**  | Pydantic                | Data validation and serialization |
| **AI**          | Google Gemini 2.0 Flash | Fast, cost-effective LLM          |
| **HTTP**        | HTTPX                   | Async HTTP client for GitHub API  |
| **Container**   | Docker                  | Production-ready deployment       |

---

## 🧠 Prompt Engineering Strategy

> **"Agentic Approach: I used a Product Manager persona for the LLM to ensure business-relevant prioritization."**

### 1. Persona-Based Prompting

The LLM is instructed to act as a **"Senior Technical Product Manager"** who:

- Understands business impact and user urgency
- Can classify issues based on technical and business criteria
- Provides actionable, structured feedback

### 2. Few-Shot Prompting

Two carefully crafted examples are included in every request:

**Example 1**: Critical bug (SSO crash affecting enterprise customers)

- Demonstrates priority 5 scoring
- Shows bug classification and impact assessment

**Example 2**: Feature request (dark mode)

- Demonstrates priority 2 scoring
- Shows feature_request classification

### 3. Strict JSON Schema Enforcement

- System prompt explicitly states: "You MUST respond with ONLY valid JSON"
- Pydantic models validate output on the backend
- Fallback parsing handles edge cases (markdown code blocks)

### 4. Priority Scoring Framework

```
5 (Critical): Production crashes, security vulnerabilities, data loss
4 (High): Major bugs affecting core functionality
3 (Medium): Non-critical bugs, moderate UX issues
2 (Low): Minor improvements, nice-to-haves
1 (Minimal): Typos, cosmetic issues, low-impact docs
```

---

## 🛡️ Edge Case Handling

| Scenario                         | Solution                                                                  |
| -------------------------------- | ------------------------------------------------------------------------- |
| **Private Repository**           | Returns clear error: "Access denied. This might be a private repository." |
| **Non-existent Issue (404)**     | User-friendly message with suggestions to check URL and issue number      |
| **Rate Limiting (429)**          | Detects GitHub rate limits, suggests waiting or adding GITHUB_TOKEN       |
| **Long Issue Body (>50k chars)** | Truncates content intelligently, preserves context, notifies user         |
| **Empty Issue Body**             | Handles gracefully, notes "(No description provided)"                     |
| **No Comments**                  | Works without comments, notes "(No comments)"                             |
| **LLM Invalid JSON**             | Parses common formats, extracts JSON from markdown blocks                 |
| **Network Timeouts**             | 30s timeout with clear error message                                      |

---

## 🔧 Configuration

### Environment Variables

| Variable         | Required | Description                                          |
| ---------------- | -------- | ---------------------------------------------------- |
| `GEMINI_API_KEY` | ✅ Yes   | Google Gemini API key                                |
| `GITHUB_TOKEN`   | ❌ No    | GitHub PAT for higher rate limits (60 → 5000 req/hr) |

### Ports

| Service            | Port | URL                         |
| ------------------ | ---- | --------------------------- |
| Frontend           | 3000 | http://localhost:5173       |
| Backend API        | 8000 | http://localhost:8000       |
| API Docs (Swagger) | 8000 | http://localhost:8000/docs  |
| API Docs (ReDoc)   | 8000 | http://localhost:8000/redoc |

---

## 📡 API Reference

### POST `/api/analyze`

Analyze a GitHub issue.

**Request Body:**

```json
{
  "repo_url": "https://github.com/facebook/react",
  "issue_number": 28850
}
```

**Response:**

```json
{
    "success": true,
    "issue_data": {
        "title": "Issue title",
        "body": "Issue description...",
        "state": "open",
        "labels": ["bug"],
        "comments": [...],
        "author": "username",
        "created_at": "2024-01-01T00:00:00Z",
        "html_url": "https://github.com/...",
        "comment_count": 5,
        "was_truncated": false
    },
    "analysis": {
        "summary": "...",
        "type": "bug",
        "priority_score": 4,
        "priority_justification": "...",
        "suggested_labels": ["bug", "high-priority"],
        "potential_impact": "..."
    }
}
```

### GET `/api/health`

Health check endpoint.

**Response:**

```json
{
  "status": "healthy",
  "service": "GitHub Issue Assistant API",
  "version": "1.0.0"
}
```

---

## 🧪 Development

### Running Locally (Without Docker)

**Backend:**

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
# Backend tests (if implemented)
cd backend
pytest

# Frontend tests (if implemented)
cd frontend
npm test
```

---

## ☁️ Deploy to Vercel

### One-Click Deploy

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/yourusername/seedling-issue-assistant)

### Manual Deployment Steps

**1. Install Vercel CLI**

```bash
npm install -g vercel
```

**2. Login to Vercel**

```bash
vercel login
```

**3. Deploy from project root**

```bash
cd seedling-issue-assistant
vercel
```

**4. Set Environment Variables in Vercel Dashboard**

- Go to your project settings in [Vercel Dashboard](https://vercel.com/dashboard)
- Navigate to **Settings → Environment Variables**
- Add the following variables:

| Name             | Value                        | Environment                      |
| ---------------- | ---------------------------- | -------------------------------- |
| `GEMINI_API_KEY` | Your Gemini API key          | Production, Preview, Development |
| `GITHUB_TOKEN`   | Your GitHub token (optional) | Production, Preview, Development |

**5. Redeploy**

```bash
vercel --prod
```

### Project Structure for Vercel

```
seedling-issue-assistant/
├── api/                        # Vercel Serverless Functions
│   ├── analyze.py              # POST /api/analyze endpoint
│   ├── health.py               # GET /api/health endpoint
│   └── requirements.txt        # Python dependencies
├── frontend/                   # React Frontend (built by Vercel)
│   ├── src/
│   └── package.json
├── vercel.json                 # Vercel configuration
└── README.md
```

### Environment Variables on Vercel

You can also use Vercel CLI to add secrets:

```bash
# Add Gemini API key
vercel env add GEMINI_API_KEY

# Add GitHub token (optional)
vercel env add GITHUB_TOKEN
```

---

---

## 🙏 Acknowledgments

- Built for [Seedling Labs](https://seedlinglabs.com) Engineering Intern Craft Case
- Powered by [Google Gemini](https://ai.google.dev/) AI
- UI components inspired by modern design systems

---

<div align="center">
  <strong>🌱 Dream. Sprout. Grow.</strong>
  <br>
  <em>Seedling Labs</em>
</div>
