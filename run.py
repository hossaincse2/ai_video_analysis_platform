#!/usr/bin/env python3
"""
Startup script for AI Video Analysis Platform
This script initializes the database and starts the FastAPI server
"""

import os
import sys
import json
import logging
import subprocess
import socket
from pathlib import Path
from datetime import datetime

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_port_availability(host, port):
    """Check if a port is available"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            return result != 0  # Port is available if connection fails
    except Exception as e:
        logger.warning(f"Error checking port {port}: {e}")
        return False


def find_available_port(host, start_port, max_port=None):
    """Find an available port starting from start_port"""
    if max_port is None:
        max_port = start_port + 100
    
    for port in range(start_port, max_port):
        if check_port_availability(host, port):
            return port
    return None


def kill_process_on_port(port):
    """Try to kill process using the specified port (Windows)"""
    try:
        import subprocess
        
        # Find process using the port
        result = subprocess.run([
            'netstat', '-ano', '|', 'findstr', f':{port}'
        ], capture_output=True, text=True, shell=True)
        
        if result.returncode == 0 and result.stdout:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        logger.info(f"Found process {pid} using port {port}")
                        
                        # Try to kill the process
                        kill_result = subprocess.run([
                            'taskkill', '/PID', pid, '/F'
                        ], capture_output=True, text=True)
                        
                        if kill_result.returncode == 0:
                            logger.info(f"Successfully killed process {pid}")
                            return True
                        else:
                            logger.warning(f"Failed to kill process {pid}")
            
    except Exception as e:
        logger.warning(f"Error trying to kill process on port {port}: {e}")
    
    return False


def check_dependencies():
    """Check if all required dependencies are installed with proper versions"""
    required_packages = [
        ('fastapi', 'FastAPI'),
        ('uvicorn', 'Uvicorn'),
        ('yt_dlp', 'yt-dlp'),
        ('pydantic', 'Pydantic'),
        ('dotenv', 'python-dotenv')
    ]

    missing_packages = []
    failed_imports = []
    
    for package, name in required_packages:
        try:
            # Use importlib for safer importing
            import importlib
            importlib.import_module(package.replace('-', '_'))
            logger.info(f"✅ {name} imported successfully")
        except ImportError as e:
            missing_packages.append(name)
            logger.warning(f"❌ Failed to import {name}: {e}")
        except Exception as e:
            failed_imports.append((name, str(e)))
            logger.error(f"❌ Error importing {name}: {e}")

    # Special handling for OpenAI - try to import without causing version conflicts
    try:
        # First check if we can install compatible versions
        fix_version_conflicts()
        import openai
        logger.info("✅ OpenAI imported successfully")
    except Exception as e:
        logger.warning(f"⚠️ OpenAI import failed: {e}")
        logger.info("Will attempt to use alternative AI service")

    if missing_packages:
        logger.error(f"Missing required packages: {', '.join(missing_packages)}")
        logger.error("Please install them using: pip install -r requirements.txt")
        return False

    if failed_imports:
        logger.error("Some packages failed to import due to version conflicts:")
        for package, error in failed_imports:
            logger.error(f"  {package}: {error}")
        logger.info("Attempting to fix version conflicts...")
        try:
            fix_version_conflicts()
            return True
        except Exception as e:
            logger.error(f"Failed to fix version conflicts: {e}")
            return False

    return True


def fix_version_conflicts():
    """Fix common version conflicts, especially typing_extensions and pydantic"""
    try:
        logger.info("Checking for version conflicts...")
        
        # Try to upgrade typing_extensions to a compatible version
        subprocess.run([
            sys.executable, "-m", "pip", "install", "--upgrade", 
            "typing_extensions>=4.8.0", "pydantic>=2.0.0"
        ], check=False, capture_output=True)
        
        logger.info("Updated typing_extensions and pydantic to compatible versions")
        
    except Exception as e:
        logger.warning(f"Could not automatically fix version conflicts: {e}")
        raise e


def check_environment():
    """Check if environment variables are properly set"""
    try:
        import importlib
        dotenv_module = importlib.import_module('dotenv')
        dotenv_module.load_dotenv()
        logger.info("✅ Environment variables loaded from .env file")
    except ImportError:
        logger.warning("python-dotenv not available, using system environment variables")
    except Exception as e:
        logger.warning(f"Error loading environment: {e}")

    # Make DATABASE_URL optional since we're using file-based storage
    logger.info("Using file-based storage instead of external database")
    return True


def create_directories():
    """Create necessary directories"""
    directories = ['downloads', 'uploads', 'logs', 'data']

    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        logger.info(f"Created directory: {directory}")


def initialize_database():
    """Initialize file-based database storage"""
    try:
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        # Create initial data files if they don't exist
        db_file = data_dir / "videos.json"
        if not db_file.exists():
            initial_data = {
                "videos": [],
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
            with open(db_file, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, indent=2, ensure_ascii=False)
            
        logger.info("File-based database initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False


def check_database_connection():
    """Check if the file-based database is accessible"""
    try:
        data_dir = Path("data")
        if not data_dir.exists():
            return False
            
        db_file = data_dir / "videos.json"
        if db_file.exists():
            # Try to read the file to ensure it's valid
            with open(db_file, 'r', encoding='utf-8') as f:
                json.load(f)
        
        logger.info("Database connection check passed")
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


def start_server():
    """Start the FastAPI server with automatic port handling"""
    try:
        import importlib
        uvicorn_module = importlib.import_module('uvicorn')
        
        try:
            dotenv_module = importlib.import_module('dotenv')
            dotenv_module.load_dotenv()
        except ImportError:
            pass

        host = os.getenv('HOST', '0.0.0.0')
        preferred_port = int(os.getenv('PORT', 8000))
        
        # Check if preferred port is available
        if check_port_availability(host, preferred_port):
            port = preferred_port
            logger.info(f"✅ Port {preferred_port} is available")
        else:
            logger.warning(f"⚠️ Port {preferred_port} is already in use")
            
            # Ask user if they want to kill the process using the port
            logger.info("Attempting to free up the port...")
            if kill_process_on_port(preferred_port):
                # Wait a moment and check again
                import time
                time.sleep(2)
                if check_port_availability(host, preferred_port):
                    port = preferred_port
                    logger.info(f"✅ Port {preferred_port} is now available")
                else:
                    # Find alternative port
                    port = find_available_port(host, preferred_port + 1)
            else:
                # Find alternative port
                port = find_available_port(host, preferred_port + 1)
            
            if port is None:
                logger.error(f"❌ Could not find an available port starting from {preferred_port}")
                return False
            elif port != preferred_port:
                logger.info(f"🔄 Using alternative port {port}")

        logger.info(f"🚀 Starting server on {host}:{port}")
        logger.info(f"📋 Access your application at: http://localhost:{port}")

        uvicorn_module.run(
            "main:app",
            host=host,
            port=port,
            reload=os.getenv('DEBUG', 'False').lower() == 'true',
            log_level=os.getenv('LOG_LEVEL', 'info').lower()
        )
        
        return True

    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        return False


def main():
    """Main startup function"""
    logger.info("🚀 Starting AI Video Analysis Platform")

    # Check dependencies
    if not check_dependencies():
        logger.error("❌ Dependency check failed")
        logger.info("💡 Try running: pip install --upgrade typing_extensions pydantic")
        sys.exit(1)

    logger.info("✅ Dependencies check passed")

    # Check environment
    if not check_environment():
        logger.error("❌ Environment check failed")
        sys.exit(1)

    logger.info("✅ Environment check passed")

    # Create directories
    create_directories()
    logger.info("✅ Directories created")

    # Initialize database
    if not initialize_database():
        logger.error("❌ Database initialization failed")
        sys.exit(1)

    # Check database connection
    if not check_database_connection():
        logger.error("❌ Database connection check failed")
        sys.exit(1)

    logger.info("✅ Database initialized")

    # Start server
    logger.info("🎬 All checks passed, starting server...")
    if not start_server():
        logger.error("❌ Failed to start server")
        sys.exit(1)


if __name__ == "__main__":
    main()