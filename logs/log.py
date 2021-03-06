import logging
import os, sys
from logging.handlers import TimedRotatingFileHandler
from logging import StreamHandler


def setup_logging():
    """Set up logging file handler for both app and sqs consumer"""
    file_handler = TimedRotatingFileHandler('logs/autoscaling.log', 'D', 1, 10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    stream_handler = StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
    logger_instance = logging.getLogger('autoscaling')
    logger_instance.addHandler(file_handler)
    logger_instance.addHandler(stream_handler)
    level = os.environ['LOGGING_LEVEL'] if os.environ.get('LOGGING_LEVEL') else 'ERROR'
    logger_instance.setLevel(level)
    return logger_instance

logger = setup_logging()
