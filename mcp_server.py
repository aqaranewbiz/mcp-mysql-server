#!/usr/bin/env python3

import json
import sys
import os
import logging
import signal
from typing import Dict, Any, List, Optional
from mysql.connector import connect, Error, pooling
from pythonjsonlogger import jsonlogger

# Configure logging
logger = logging.getLogger()
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# Global variables
connection_pool = None
initialized = False

# Allowed SQL commands for read-only operations
ALLOWED_COMMANDS = {
    'SELECT', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN'
}

def create_connection_pool() -> None:
    """Create MySQL connection pool using environment variables"""
    global connection_pool
    
    try:
        config = {
            'host': os.environ['MYSQL_HOST'],
            'port': int(os.environ.get('MYSQL_PORT', 3306)),
            'user': os.environ['MYSQL_USER'],
            'password': os.environ['MYSQL_PASSWORD'],
            'database': os.environ.get('MYSQL_DATABASE', ''),
        }
        
        connection_pool = pooling.MySQLConnectionPool(
            pool_name="mypool",
            pool_size=5,
            **config
        )
        logger.info("MySQL connection pool created successfully")
    except Error as e:
        logger.error(f"Error creating connection pool: {e}")
        raise

def is_read_only_query(query: str) -> bool:
    """Check if the query is read-only"""
    first_word = query.strip().split()[0].upper()
    return first_word in ALLOWED_COMMANDS

def validate_query(query: str) -> None:
    """Validate if the query is allowed"""
    if not is_read_only_query(query):
        raise ValueError(f"Only read-only queries are allowed. Allowed commands: {', '.join(ALLOWED_COMMANDS)}")

def execute_query(query: str, params: List[Any] = None, database: str = None) -> Dict[str, Any]:
    """Execute a SQL query and return results"""
    if not connection_pool:
        return {"success": False, "error": "Database connection not initialized"}
    
    try:
        connection = connection_pool.get_connection()
        if database:
            connection.cmd_init_db(database)
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, params or ())
        
        results = cursor.fetchall()
        return {
            "success": True,
            "results": results,
            "rowCount": len(results)
        }
    except Error as e:
        logger.error(f"Database error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

def list_databases() -> Dict[str, Any]:
    """List all accessible databases"""
    return execute_query("SHOW DATABASES")

def list_tables(database: str = None) -> Dict[str, Any]:
    """List all tables in a database"""
    return execute_query("SHOW FULL TABLES", database=database)

def describe_table(table: str, database: str = None) -> Dict[str, Any]:
    """Describe a table schema"""
    return execute_query(f"DESCRIBE `{table}`", database=database)

def handle_request(request: str) -> Dict:
    """Handle JSON-RPC request"""
    try:
        request_obj = json.loads(request)
        method = request_obj.get("method")
        params = request_obj.get("params", {})
        request_id = request_obj.get("id")
        
        logger.info(f"Received request: method={method}, id={request_id}")
        
        # Handle initialization
        if method == "initialize":
            global initialized
            initialized = True
            create_connection_pool()
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "capabilities": {
                        "textDocumentSync": 1
                    },
                    "serverInfo": {
                        "name": "mysql-mcp-server",
                        "version": "1.0.0"
                    }
                }
            }
        
        # Handle shutdown
        elif method == "shutdown":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": None
            }
        
        # Handle exit
        elif method == "exit":
            logger.info("Received exit notification")
            sys.exit(0)
        
        # Handle tool listing
        elif method == "MCP/listTools":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": {
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
                                        "description": "Database name"
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
                                        "description": "Database name"
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
                                        "description": "SQL query (SELECT, SHOW, DESCRIBE only)"
                                    },
                                    "database": {
                                        "type": "string",
                                        "description": "Database name"
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
            tool_name = params.get("tool")
            tool_params = params.get("parameters", {})
            
            if not initialized:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32002,
                        "message": "Server not initialized"
                    }
                }
            
            result = None
            if tool_name == "list_databases":
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
                    try:
                        validate_query(query)
                        result = execute_query(
                            query=query,
                            database=tool_params.get("database")
                        )
                    except ValueError as e:
                        result = {"success": False, "error": str(e)}
            else:
                result = {"success": False, "error": f"Unknown tool: {tool_name}"}
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
        
        # Handle unknown method
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": "Parse error"
            }
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": str(e)
            }
        }

def main():
    """Main entry point"""
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
                
            response = handle_request(line.strip())
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main() 