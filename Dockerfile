FROM python:3.9-slim-bullseye

WORKDIR /app

# Install system dependencies
RUN set -ex && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        default-libmysqlclient-dev \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir --upgrade pip setuptools wheel

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -m -u 1000 mcp

# Copy application files
COPY . .

# Set permissions
RUN chown -R mcp:mcp /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app:${PATH}"

# Switch to non-root user
USER mcp

# Make script executable
RUN chmod +x mcp_server.py

# Set the entrypoint
CMD ["python", "mcp_server.py"] 