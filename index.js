#!/usr/bin/env node
/**
 * MySQL MCP Server Runner
 * 
 * This script launches the Python-based MySQL MCP server and handles communication
 * between Smithery and the Python process.
 */

const { spawn, exec } = require('child_process');
const fs = require('fs');
const path = require('path');

// Get the directory where this script is located
const scriptDir = path.dirname(__filename);
const mcp_server_path = path.join(scriptDir, 'mcp_server.py');
const requirements_path = path.join(scriptDir, 'requirements.txt');

// Create .local marker file for Smithery
const localMarkerFile = path.join(scriptDir, '.local');
if (!fs.existsSync(localMarkerFile)) {
  try {
    fs.writeFileSync(localMarkerFile, 'This is a local MCP server');
    console.error('Created .local marker file for Smithery');
  } catch (err) {
    console.error('Warning: Could not create .local marker file', err);
  }
}

// Log execution information
console.error(`Process ID: ${process.pid}`);
console.error(`Node version: ${process.version}`);
console.error(`Current directory: ${process.cwd()}`);
console.error(`Script path: ${__filename}`);
console.error(`Python script path: ${mcp_server_path}`);

// Function to detect Python command on system
function getPythonCommand() {
  return new Promise((resolve, reject) => {
    // Try python3 first (common on macOS and Linux)
    exec('python3 --version', (error) => {
      if (!error) {
        resolve('python3');
        return;
      }
      
      // Try python next (common on Windows)
      exec('python --version', (error) => {
        if (!error) {
          resolve('python');
          return;
        }
        
        // If neither worked, Python is not installed or not in PATH
        reject(new Error('Python is not installed or not in PATH. Please install Python 3.6 or later.'));
      });
    });
  });
}

// Function to install Python requirements
function installRequirements(pythonCmd) {
  return new Promise((resolve, reject) => {
    console.error('Installing Python requirements...');
    
    // Check if requirements.txt exists
    if (!fs.existsSync(requirements_path)) {
      console.error(`Error: requirements.txt not found at ${requirements_path}`);
      // Create a basic requirements file
      try {
        fs.writeFileSync(requirements_path, 'mysql-connector-python>=8.0.0\n');
        console.error('Created basic requirements.txt file');
      } catch (err) {
        console.error('Failed to create requirements.txt:', err);
        reject(new Error('Could not create requirements.txt'));
        return;
      }
    }
    
    const install = spawn(pythonCmd, ['-m', 'pip', 'install', '--user', 'mysql-connector-python>=8.0.0']);
    
    install.stdout.on('data', (data) => {
      console.error(`Pip: ${data}`);
    });
    
    install.stderr.on('data', (data) => {
      console.error(`Pip error: ${data}`);
    });
    
    install.on('close', (code) => {
      if (code !== 0) {
        console.error(`Warning: Pip exited with code ${code}`);
        // Continue anyway, as the user might have installed the packages manually
        resolve();
      } else {
        console.error('Python requirements installed successfully');
        resolve();
      }
    });
  });
}

// Function to start the Python MCP server
function startPythonServer(pythonCmd) {
  console.error('Starting MySQL MCP Server...');
  
  // Verify the Python script exists
  if (!fs.existsSync(mcp_server_path)) {
    console.error(`Error: MCP server script not found at ${mcp_server_path}`);
    process.exit(1);
  }
  
  // Make the script executable (Linux/macOS)
  try {
    fs.chmodSync(mcp_server_path, '755');
  } catch (err) {
    console.error('Warning: Could not make the Python script executable:', err);
  }
  
  // Set environment variables from Smithery settings
  const env = {
    ...process.env,
    MYSQL_HOST: process.env.SMITHERY_SETTING_HOST || 'localhost',
    MYSQL_PORT: process.env.SMITHERY_SETTING_PORT || '3306',
    MYSQL_USER: process.env.SMITHERY_SETTING_USER || '',
    MYSQL_PASSWORD: process.env.SMITHERY_SETTING_PASSWORD || '',
    MYSQL_DATABASE: process.env.SMITHERY_SETTING_DATABASE || '',
    PYTHONUNBUFFERED: '1',  // Ensure Python output is not buffered
  };
  
  // Log the configuration (masking sensitive data)
  console.error(`MySQL Configuration:
  - Host: ${env.MYSQL_HOST}
  - Port: ${env.MYSQL_PORT}
  - User: ${env.MYSQL_USER}
  - Database: ${env.MYSQL_DATABASE || '(none)'}
  - Password: ${env.MYSQL_PASSWORD ? '*****' : '(none)'}
`);
  
  // Launch the Python process
  const pythonProcess = spawn(pythonCmd, [mcp_server_path], { env });
  
  // Connect the Python process's stdout to Node's stdout (for MCP protocol messages)
  pythonProcess.stdout.pipe(process.stdout);
  
  // Log stderr but don't pipe it (for debugging)
  pythonProcess.stderr.on('data', (data) => {
    console.error(`Python: ${data}`);
  });
  
  // Handle process termination
  pythonProcess.on('close', (code) => {
    console.error(`Python process exited with code ${code}`);
    if (code !== 0) {
      console.error('Error: MCP server terminated abnormally');
    }
    process.exit(code);
  });
  
  // Handle unexpected errors
  pythonProcess.on('error', (err) => {
    console.error('Failed to start Python process:', err);
    process.exit(1);
  });
  
  // Handle Node.js process signals
  process.on('SIGINT', () => {
    console.error('Received SIGINT. Shutting down...');
    pythonProcess.kill('SIGINT');
  });
  
  process.on('SIGTERM', () => {
    console.error('Received SIGTERM. Shutting down...');
    pythonProcess.kill('SIGTERM');
  });
}

// Main function to run everything
async function main() {
  try {
    // Get the appropriate Python command
    const pythonCmd = await getPythonCommand();
    console.error(`Found Python command: ${pythonCmd}`);
    
    // Install requirements
    await installRequirements(pythonCmd);
    
    // Start the server
    startPythonServer(pythonCmd);
  } catch (error) {
    console.error(`Fatal error: ${error.message}`);
    process.exit(1);
  }
}

// Run the main function
main(); 