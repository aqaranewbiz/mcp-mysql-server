# MySQL MCP Server

A Model Context Protocol (MCP) server that enables secure interaction with MySQL databases. This server allows AI assistants to list tables, read data, and execute read-only SQL queries through a controlled interface.

## Features

- Read-only access to MySQL databases
- Connection pooling for efficient resource management
- Secure query validation
- JSON-RPC 2.0 protocol support
- Comprehensive logging
- Docker support

## Available Tools

1. `list_databases`: List all accessible databases
2. `list_tables`: List all tables in a database
3. `describe_table`: Show the schema for a table
4. `execute_query`: Execute read-only SQL queries (SELECT, SHOW, DESCRIBE only)

## Configuration

The server requires the following environment variables:

- `MYSQL_HOST`: MySQL server hostname
- `MYSQL_PORT`: MySQL server port (default: 3306)
- `MYSQL_USER`: MySQL username
- `MYSQL_PASSWORD`: MySQL user password
- `MYSQL_DATABASE`: (Optional) Default database name

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python mcp_server.py
```

## Docker Usage

Build the image:
```bash
docker build -t mysql-mcp-server .
```

Run the container:
```bash
docker run -e MYSQL_HOST=host.docker.internal \
           -e MYSQL_PORT=3306 \
           -e MYSQL_USER=your_user \
           -e MYSQL_PASSWORD=your_password \
           -e MYSQL_DATABASE=your_database \
           mysql-mcp-server
```

## Security

- Only read-only SQL commands are allowed (SELECT, SHOW, DESCRIBE, EXPLAIN)
- All queries are validated before execution
- Connection pooling prevents resource exhaustion
- Sensitive information is handled securely

## License

MIT License 