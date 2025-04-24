# Build stage
FROM python:3.9-slim as builder

WORKDIR /build

# Copy only requirements file first to leverage Docker cache
COPY requirements.txt .

# Install build dependencies and compile any necessary packages
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.9-slim

WORKDIR /app

# Copy only necessary files
COPY mcp_server.py .
COPY --from=builder /root/.local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages

# Create health check endpoint
RUN echo '#!/bin/sh\necho "HTTP/1.1 200 OK\n\nHealthy"' > health_check.sh && \
    chmod +x health_check.sh && \
    (nohup python3 -m http.server 14000 &)

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Make script executable
RUN chmod +x mcp_server.py

# Create .local marker file
RUN echo "This is a local MCP server" > .local

# Expose port for health checks
EXPOSE 14000

# Run the server
CMD ["python3", "mcp_server.py"] 