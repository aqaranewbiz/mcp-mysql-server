# Build stage for Node.js dependencies
FROM node:lts-alpine AS node-builder

WORKDIR /build
COPY package*.json ./
RUN npm install --ignore-scripts

# Build stage for Python dependencies
FROM python:3.9-alpine AS python-builder

WORKDIR /build
COPY requirements.txt ./
RUN apk add --no-cache --virtual .build-deps gcc musl-dev && \
    pip install --no-cache-dir --user -r requirements.txt && \
    apk del .build-deps

# Final stage
FROM node:lts-alpine

# Install Python and required runtime dependencies
RUN apk add --no-cache python3 py3-pip

WORKDIR /app

# Copy Node.js dependencies
COPY --from=node-builder /build/node_modules ./node_modules

# Copy Python dependencies
COPY --from=python-builder /root/.local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages

# Copy application files
COPY mcp_server.py run.js ./

# Make scripts executable
RUN chmod +x mcp_server.py run.js

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production

# Set the entrypoint command
CMD ["node", "run.js"] 