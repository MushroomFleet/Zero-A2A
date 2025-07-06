"""
Main entry point for Zero-A2A Protocol server
"""

import uvicorn
import structlog
import logging
from pythonjsonlogger import jsonlogger

from src.core.config import settings


def setup_logging():
    """Configure structured logging for the application"""
    
    # Configure standard logging
    logHandler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(name)s %(levelname)s %(message)s'
    )
    logHandler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.addHandler(logHandler)
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def main():
    """Main function to run the Zero-A2A server"""
    
    # Setup logging
    setup_logging()
    logger = structlog.get_logger()
    
    logger.info(
        "Starting Zero-A2A Protocol server",
        version=settings.app_version,
        host=settings.host,
        port=settings.port,
        debug=settings.debug
    )
    
    # Import the FastAPI app
    from src.server.app import app
    
    # Run the server
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=settings.debug,
        access_log=True,
        server_header=False,
        date_header=False
    )


if __name__ == "__main__":
    main()
