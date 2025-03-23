# Base stage for shared dependencies
FROM node:20 as base

WORKDIR /app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Build stage
FROM base as build

# Copy all frontend files
COPY . .

# Build the app
RUN npm run build

# Production stage
FROM nginx:stable-alpine as production

# Copy built files from build stage to nginx serve directory
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]

# Development stage
FROM base as dev

# In dev mode, we'll mount the source code as a volume
# so we only need minimal setup here

# Expose development port
EXPOSE 3000

# Start development server with hot reloading
CMD ["npm", "start"]
