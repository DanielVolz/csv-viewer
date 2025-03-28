# Base stage for shared dependencies
FROM node:20 AS base

WORKDIR /app

# Copy package files first (for better caching)
COPY package.json package-lock.json ./

# Install dependencies with --legacy-peer-deps flag (required)
RUN npm install --legacy-peer-deps

# Build stage
FROM base AS build

# Copy only necessary files for build
COPY public/ ./public/
COPY src/ ./src/
COPY babel.config.js ./
COPY jest.config.js ./

# Build the app
RUN npm run build

# Production stage
FROM nginx:stable-alpine AS production

# Copy built files from build stage to nginx serve directory
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]

# Development stage
FROM base AS dev

# In dev mode, we'll mount the source code as a volume
# so we only need minimal setup here

# Expose development port
EXPOSE 3000

# Start development server with hot reloading
CMD ["npm", "start"]
