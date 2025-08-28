#!/usr/bin/python3
"""
HashWrap WSGI Application
Production WSGI interface for Apache mod_wsgi deployment
"""

import sys
import os
import logging
from pathlib import Path

# Add the application directory to Python path
app_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(app_dir))

# Set up production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('/var/log/hashwrap/hashwrap.log'),
        logging.StreamHandler()
    ]
)

# Import the Flask application
try:
    from app_fixed import app as application
    
    # Production configuration overrides
    application.config.update(
        DEBUG=False,
        TESTING=False,
        ENV='production'
    )
    
    # Log successful startup
    application.logger.info("HashWrap WSGI application loaded successfully")
    
except Exception as e:
    # Log startup errors
    logging.error(f"Failed to load HashWrap application: {e}")
    raise

if __name__ == "__main__":
    # This won't run under WSGI, but useful for testing
    application.run(debug=False)