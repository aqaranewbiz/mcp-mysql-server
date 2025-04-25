FROM python:3.9-slim

WORKDIR /app

# Install build dependencies and MySQL client
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Make script executable
RUN chmod +x mcp_server.py

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set the entrypoint command
CMD ["python", "mcp_server.py"] 