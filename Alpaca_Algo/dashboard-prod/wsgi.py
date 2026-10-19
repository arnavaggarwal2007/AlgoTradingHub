"""
wsgi.py — WSGI Entry Point for Production Deployment

This module is the entry point for Gunicorn and other WSGI servers.
Use: gunicorn wsgi:app -c gunicorn_config.py

It:
- Loads environment variables from .env
- Initializes the Dash app
- Configures logging
- Sets up error handling
- Returns the WSGI application object
"""
import os
import sys
import logging
from pathlib import Path

# Add app directory to path
APP_DIR = Path(__file__).parent
sys.path.insert(0, str(APP_DIR))

# Load environment variables before app initialization
from dotenv import load_dotenv
load_dotenv(APP_DIR / ".env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_app():
    """
    Factory function to create and configure the Dash app.
    
    Returns:
        Dash app instance (with .server property for WSGI)
    """
    # Import here to allow for proper environment setup
    from app.app import app as dash_app
    
    logger.info("Pre-Swing Dashboard initialized")
    logger.info(f"Environment: {os.getenv('FLASK_ENV', 'development')}")
    logger.info(f"Debug mode: {os.getenv('DEBUG', 'false').lower() == 'true'}")
    
    return dash_app


# Create the app instance
app = create_app()

# Expose Flask server for WSGI servers (Gunicorn, etc.)
# Gunicorn looks for "application" variable by default, but we use "app"
application = app.server if hasattr(app, 'server') else app

if __name__ == "__main__":
    # Development: python wsgi.py
    logger.warning("Running in development mode. Use 'gunicorn wsgi:app' for production.")
    app.run_server(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8050)),
        debug=os.getenv("DEBUG", "false").lower() == "true"
    )
