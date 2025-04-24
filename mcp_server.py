#!/usr/bin/env python3
"""
MySQL MCP Server in Python

This MCP server provides access to MySQL databases using the Model Context Protocol (MCP).
It allows:
- Connecting to a MySQL database
- Listing tables in a database
- Describing table schemas
- Executing read-only SQL queries
"""

import json
import sys
import os
import signal
import time
import logging
import traceback
from datetime import datetime
import threading
import platform
from typing import Dict, List, Any, Optional, Union

# Set up logging
logging.basicConfig(
    level=logging.DEBUG if os.environ.get('DEBUG') else logging.INFO,
    format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    stream=sys.stderr
)
logger = logging.getLogger('mysql-mcp-server')

# Try to import MySQL connector
try:
    import mysql.connector
    from mysql.connector import Error, pooling
except ImportError:
    logger.error("MySQL Connector for Python is not installed. Please install it using: pip install mysql-connector-python")
    sys.exit(1)

# Global variables
running = True
initialized = False
last_activity_time = time.time()
KEEP_ALIVE_INTERVAL = 10  # seconds
TIMEOUT = 300  # seconds
connection_pool = None
row_limit = int(os.environ.get('ROW_LIMIT', 1000))
query_timeout = int(os.environ.get('QUERY_TIMEOUT', 10000)) / 1000  # Convert from ms to seconds

# Allowed SQL commands (read-only operations)
ALLOWED_COMMANDS = [
    'SELECT',
    'SHOW',
    'DESCRIBE',
    'DESC',
    'EXPLAIN',
]

# Disallowed SQL commands (write operations)
DISALLOWED_COMMANDS = [
    'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE',
    'RENAME', 'REPLACE', 'GRANT', 'REVOKE', 'LOCK', 'UNLOCK', 'CALL',
    'EXEC', 'EXECUTE', 'SET', 'START', 'BEGIN', 'COMMIT', 'ROLLBACK',
]

# Print startup information
logger.info(f"Starting MySQL MCP Server - Python {platform.python_version()} on {platform.platform()}")

def signal_handler(signum, frame):
    """Handle termination signals"""
    global running
    logger.info(f"Received signal {signum}, shutting down...")
    running = False
    cleanup()
    sys.exit(0)

def cleanup():
    """Clean up resources before shutdown"""
    global connection_pool
    if connection_pool:
        try:
            connection_pool.close()
            logger.info("Database connection pool closed")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")
    logger.info("Cleanup completed")

def keep_alive_thread_func():
    """Thread to send keep-alive messages"""
    global running, last_activity_time
    logger.info("Keep-alive thread started")
    
    while running:
        try:
            current_time = time.time()
            elapsed = current_time - last_activity_time
            
            if elapsed > KEEP_ALIVE_INTERVAL:
                logger.info(f"Sending keep-alive after {elapsed:.1f}s of inactivity")
                send_keep_alive()
                
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error in keep-alive thread: {e}")

def send_keep_alive():
    """Send keep-alive message to prevent timeout"""
    global last_activity_time
    last_activity_time = time.time()
    
    try:
        response = {
            "jsonrpc": "2.0",
            "method": "$/alive",
            "params": {"timestamp": datetime.utcnow().isoformat()}
        }
        print(json.dumps(response), flush=True)
    except Exception as e:
        logger.error(f"Error sending keep-alive: {e}")

def create_connection_pool(config: Dict[str, Any]) -> pooling.MySQLConnectionPool:
    """Create a MySQL connection pool"""
    logger.info(f"Creating MySQL connection pool to {config.get('host')}:{config.get('port', 3306)}")
    
    try:
        pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="mysql_pool",
            pool_size=10,
            **config
        )
        logger.info("Connection pool created successfully")
        return pool
    except Error as e:
        logger.error(f"Error creating connection pool: {e}")
        raise

def is_read_only_query(query: str) -> bool:
    """Check if a query is read-only"""
    # Normalize query
    normalized = query.replace('\n', ' ').strip().upper()
    
    # Check if query starts with allowed command
    starts_with_allowed = any(normalized.startswith(cmd + ' ') or normalized == cmd for cmd in ALLOWED_COMMANDS)
    
    # Check if query contains disallowed commands
    contains_disallowed = any(f" {cmd} " in f" {normalized} " for cmd in DISALLOWED_COMMANDS)
    
    # Check for multiple statements
    has_multiple_statements = ';' in normalized and not normalized.endswith(';')
    
    return starts_with_allowed and not contains_disallowed and not has_multiple_statements

def validate_query(query: str) -> None:
    """Validate that a query is safe to execute"""
    logger.info(f"Validating query: {query}")
    
    if not query or not isinstance(query, str):
        raise ValueError("Query must be a non-empty string")
    
    if not is_read_only_query(query):
        logger.warning(f"Rejected unsafe query: {query}")
        raise ValueError("Only read-only queries are allowed (SELECT, SHOW, DESCRIBE, EXPLAIN)")
    
    logger.info("Query validated as read-only")

def execute_query(sql: str, params: List[Any] = None, database: str = None) -> Dict[str, Any]:
    """Execute a SQL query with error handling"""
    global connection_pool
    
    if not connection_pool:
        raise ValueError("Not connected to MySQL. Use connect_db first.")
    
    connection = None
    try:
        # Get connection from pool
        connection = connection_pool.get_connection()
        
        # Use specified database if provided
        if database:
            logger.info(f"Using database: {database}")
            connection.cmd_query(f"USE `{database}`")
        
        # Create cursor
        cursor = connection.cursor(dictionary=True)
        
        # Execute query
        start_time = time.time()
        cursor.execute(sql, params or [])
        
        # Fetch results
        if cursor.with_rows:
            rows = cursor.fetchall()
            # Apply row limit
            if len(rows) > row_limit:
                logger.info(f"Limiting results from {len(rows)} to {row_limit} rows")
                rows = rows[:row_limit]
        else:
            rows = []
        
        # Log execution time
        execution_time = time.time() - start_time
        logger.info(f"Query executed in {execution_time:.3f}s, returned {len(rows)} rows")
        
        return {
            "success": True,
            "rows": rows,
            "rowCount": len(rows),
            "fields": [desc[0] for desc in cursor.description] if cursor.description else []
        }
    except Error as e:
        logger.error(f"Error executing query: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if connection:
            connection.close()

def connect_db(host: str, port: int = 3306, user: str = None, password: str = None, database: str = None) -> Dict[str, Any]:
    """Connect to a MySQL database"""
    global connection_pool
    
    if not user or not password:
        return {"success": False, "error": "Username and password are required"}
    
    logger.info(f"Connecting to MySQL database at {host}:{port}")
    
    try:
        config = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
        }
        
        if database:
            config["database"] = database
            
        # Close existing pool if it exists
        if connection_pool:
            connection_pool.close()
            
        # Create new pool
        connection_pool = create_connection_pool(config)
        
        # Test connection
        connection = connection_pool.get_connection()
        connection.cmd_query("SELECT 1")
        connection.close()
        
        logger.info("Connected to MySQL database successfully")
        return {"success": True, "message": f"Connected to MySQL at {host}:{port} successfully"}
    except Error as e:
        logger.error(f"Error connecting to database: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"success": False, "error": str(e)}

def list_databases() -> Dict[str, Any]:
    """List all accessible databases"""
    logger.info("Listing databases")
    return execute_query("SHOW DATABASES")

def list_tables(database: str = None) -> Dict[str, Any]:
    """List all tables in a database"""
    logger.info(f"Listing tables in database: {database or 'default'}")
    return execute_query("SHOW FULL TABLES", database=database)

def describe_table(table: str, database: str = None) -> Dict[str, Any]:
    """Describe a table schema"""
    logger.info(f"Describing table {table} in {database or 'default'} database")
    return execute_query(f"DESCRIBE `{table}`", database=database)

def execute_sql_query(query: str, database: str = None) -> Dict[str, Any]:
    """Execute a read-only SQL query"""
    logger.info(f"Executing query in {database or 'default'} database")
    
    try:
        validate_query(query)
        return execute_query(query, database=database)
    except ValueError as e:
        return {"success": False, "error": str(e)}

def handle_request(request: str) -> Dict:
    """Handle JSON-RPC request"""
    global last_activity_time, initialized
    
    # Update last activity time
    last_activity_time = time.time()
    
    try:
        # Parse the request
        request_obj = json.loads(request)
        method = request_obj.get("method")
        params = request_obj.get("params", {})
        request_id = request_obj.get("id")
        
        logger.info(f"Received request: method={method}, id={request_id}")
        
        # Handle initialization
        if method == "initialize":
            logger.info("Processing initialize request")
            initialized = True
            
            # Return server capabilities
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "capabilities": {
                        "textDocumentSync": 1,
                        "completionProvider": {
                            "resolveProvider": True,
                            "triggerCharacters": ["."]
                        },
                        "hoverProvider": True
                    },
                    "serverInfo": {
                        "name": "mysql-mcp-server",
                        "version": "1.0.0"
                    }
                }
            }
            
        # Handle shutdown
        elif method == "shutdown":
            logger.info("Processing shutdown request")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": None
            }
            
        # Handle exit
        elif method == "exit":
            logger.info("Received exit notification, shutting down...")
            cleanup()
            sys.exit(0)
            
        # Handle tool listing
        elif method == "MCP/listTools":
            logger.info("Processing MCP/listTools request")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": {
                        "connect_db": {
                            "description": "Connect to a MySQL database",
                            "parameters": {
                                "properties": {
                                    "host": {
                                        "type": "string",
                                        "description": "MySQL server hostname or IP address",
                                        "default": "localhost"
                                    },
                                    "port": {
                                        "type": "integer",
                                        "description": "MySQL server port",
                                        "default": 3306
                                    },
                                    "user": {
                                        "type": "string",
                                        "description": "MySQL username"
                                    },
                                    "password": {
                                        "type": "string",
                                        "description": "MySQL password",
                                        "format": "password"
                                    },
                                    "database": {
                                        "type": "string",
                                        "description": "Database name (optional)"
                                    }
                                },
                                "required": ["host", "user", "password"]
                            }
                        },
                        "list_databases": {
                            "description": "List all accessible databases",
                            "parameters": {
                                "properties": {}
                            }
                        },
                        "list_tables": {
                            "description": "List all tables in a database",
                            "parameters": {
                                "properties": {
                                    "database": {
                                        "type": "string",
                                        "description": "Database name (optional, uses default if connected)"
                                    }
                                }
                            }
                        },
                        "describe_table": {
                            "description": "Show the schema for a table",
                            "parameters": {
                                "properties": {
                                    "table": {
                                        "type": "string",
                                        "description": "Table name"
                                    },
                                    "database": {
                                        "type": "string",
                                        "description": "Database name (optional, uses default if connected)"
                                    }
                                },
                                "required": ["table"]
                            }
                        },
                        "execute_query": {
                            "description": "Execute a read-only SQL query",
                            "parameters": {
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "SQL query (only SELECT, SHOW, DESCRIBE, and EXPLAIN allowed)"
                                    },
                                    "database": {
                                        "type": "string",
                                        "description": "Database name (optional, uses default if connected)"
                                    }
                                },
                                "required": ["query"]
                            }
                        }
                    }
                }
            }
            
        # Handle tool calls
        elif method == "MCP/callTool":
            logger.info(f"Processing MCP/callTool request: {params}")
            
            tool_name = params.get("tool")
            tool_params = params.get("parameters", {})
            
            # Execute the appropriate tool
            result = None
            if tool_name == "connect_db":
                result = connect_db(
                    host=tool_params.get("host", "localhost"),
                    port=int(tool_params.get("port", 3306)),
                    user=tool_params.get("user"),
                    password=tool_params.get("password"),
                    database=tool_params.get("database")
                )
            elif tool_name == "list_databases":
                result = list_databases()
            elif tool_name == "list_tables":
                result = list_tables(database=tool_params.get("database"))
            elif tool_name == "describe_table":
                table = tool_params.get("table")
                if not table:
                    result = {"success": False, "error": "Table name is required"}
                else:
                    result = describe_table(
                        table=table,
                        database=tool_params.get("database")
                    )
            elif tool_name == "execute_query":
                query = tool_params.get("query")
                if not query:
                    result = {"success": False, "error": "Query is required"}
                else:
                    result = execute_sql_query(
                        query=query,
                        database=tool_params.get("database")
                    )
            else:
                result = {"success": False, "error": f"Unknown tool: {tool_name}"}
                
            logger.info(f"Tool {tool_name} execution completed with success={result.get('success', False)}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
            
        # Handle unknown method
        else:
            error_msg = f"Unknown method: {method}"
            logger.error(error_msg)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": error_msg
                }
            }
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": f"Parse error: {str(e)}"
            }
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        traceback.print_exc()
        return {
            "jsonrpc": "2.0",
            "id": request_id if "request_id" in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

def main():
    """Main entry point"""
    global running, initialized
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start keep-alive thread
    keep_alive_thread = threading.Thread(target=keep_alive_thread_func)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()
    
    # Get database connection info from environment variables
    host = os.environ.get('MYSQL_HOST')
    user = os.environ.get('MYSQL_USER')
    password = os.environ.get('MYSQL_PASSWORD')
    database = os.environ.get('MYSQL_DATABASE')
    port = int(os.environ.get('MYSQL_PORT', '3306'))
    
    if not all([host, user, password]):
        logger.error("Required environment variables MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD not set")
        sys.exit(1)
    
    try:
        # Connect to database
        result = connect_db(host=host, port=port, user=user, password=password, database=database)
        if not result.get('success'):
            logger.error(f"Failed to connect to database: {result.get('error')}")
            sys.exit(1)
        initialized = True
        
        # Main loop
        while running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                    
                request = json.loads(line)
                response = handle_request(request)
                
                if response:
                    print(json.dumps(response), flush=True)
                    
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
            except Exception as e:
                logger.error(f"Error processing request: {e}\n{traceback.format_exc()}")
                
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        cleanup()

if __name__ == "__main__":
    main() 