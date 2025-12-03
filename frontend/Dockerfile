# Frontend Dockerfile for GitHub Issue Assistant
# Simple development/production setup using Vite

FROM node:20-alpine

WORKDIR /app

# Copy package files first for better caching
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Expose port
EXPOSE 5173

# Run Vite dev server (works for demo/intern assignment)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
