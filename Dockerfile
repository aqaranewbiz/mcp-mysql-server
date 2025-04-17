FROM python:3.9-slim

WORKDIR /app

# Copy application files
COPY . .

# Install Node.js
RUN apt-get update && \
    apt-get install -y nodejs npm && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir mysql-connector-python>=8.0.0

# Make scripts executable
RUN chmod +x mcp_server.py run.js

# Create .local marker file
RUN echo "This is a local MCP server" > .local

# Set environment variables
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1

# Expose port if needed for health checks
EXPOSE 14000

# Run the server
CMD ["node", "run.js"] 