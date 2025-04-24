# MySQL MCP Server for Smithery (Python)

[![smithery badge](https://smithery.ai/badge/@aqaranewbiz/mcp-mysql-server)](https://smithery.ai/server/@aqaranewbiz/mcp-mysql-server)

A MySQL connector for Smithery that allows you to connect to your MySQL database directly from Smithery, built with Python.

## Features

- **Connect to MySQL Databases**: Configure and connect to MySQL databases
- **List Databases**: View all accessible databases
- **List Tables**: View all tables in a specified database
- **Describe Tables**: Get detailed schema information for tables
- **Execute Queries**: Run read-only SQL queries (SELECT, SHOW, DESCRIBE, EXPLAIN)
- **Security**: Built-in query validation ensures only read-only operations are allowed

## Installation in Smithery

After adding the MCP server in Smithery, you'll be able to enter your MySQL database credentials:

- **Host**: Database server hostname (default: localhost)
- **Port**: Database server port (default: 3306)
- **User**: Your MySQL username
- **Password**: Your MySQL password
- **Database**: (Optional) The specific database to connect to

## Installing via Smithery

To install MySQL Connector Server for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@aqaranewbiz/mcp-mysql-server):

```bash
npx -y @smithery/cli install @aqaranewbiz/mcp-mysql-server --client claude
```

## Manual Installation

1. Clone this repository:
```bash
git clone https://github.com/aqaralife/mysql-mcp-python-server.git
```

2. Install dependencies:
```bash
cd mysql-mcp-python-server
npm install
pip install -r requirements.txt
```

3. Make the scripts executable (Unix/Linux/Mac):
```bash
chmod +x mcp_server.py run.js
```

## Manual Usage

To start the server:
```bash
node run.js
```

Or, directly run the Python script:
```bash
python mcp_server.py
```

## Available Tools

### connect_db
Establishes a connection to a MySQL database.

**Parameters:**
- **host**: Database server hostname
- **port**: Database server port
- **user**: Database username
- **password**: Database password
- **database**: (Optional) Database name

### list_databases
Lists all accessible databases.

**Parameters:** None

### list_tables
Lists all tables in a database.

**Parameters:**
- **database**: (Optional) Database name, uses default if connected

### describe_table
Shows the schema for a table.

**Parameters:**
- **table**: Table name
- **database**: (Optional) Database name, uses default if connected

### execute_query
Executes a read-only SQL query.

**Parameters:**
- **query**: SQL query (only SELECT, SHOW, DESCRIBE, and EXPLAIN allowed)
- **database**: (Optional) Database name, uses default if connected

## Security

The server includes built-in validation to ensure only read-only operations are permitted:

- Only SELECT, SHOW, DESCRIBE, and EXPLAIN queries are allowed
- Queries containing SQL commands like INSERT, UPDATE, DELETE, DROP, etc. are automatically rejected
- Multiple statements in a single query (separated by semicolons) are not allowed

## Troubleshooting

If you encounter issues:

1. **Python Not Found**: The server will automatically detect `python3` or `python`. If neither works, ensure Python is installed and in your PATH.

2. **Missing Modules**: The server will attempt to install required packages automatically. If this fails, manually run:
   ```bash
   pip install mysql-connector-python>=8.0.0
   ```

3. **Connection Issues**: Verify your database credentials and ensure the MySQL server is running and accessible.

4. **Smithery Connection Issues**: Make sure the settings in Smithery are correctly configured with your database credentials.

5. **Server Unresponsive**: Check the log output in Smithery's console for errors.

## License

MIT

## Contact

If you have any questions, please create an issue. 