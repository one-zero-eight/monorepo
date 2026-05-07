# Copy logger from uvicorn
import logging

uvicorn_logger = logging.getLogger("uvicorn")

logging.basicConfig(level=logging.INFO)
logging.getLogger().handlers = uvicorn_logger.handlers
