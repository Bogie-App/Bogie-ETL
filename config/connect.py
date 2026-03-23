import psycopg2
from .configuration import settings
from .logger import logger

def connect():
    try:
        conn = psycopg2.connect(**settings.db_config)
        logger.info('Connected to the PostgreSQL server.')
        return conn
    except (psycopg2.DatabaseError, Exception) as error:
        logger.error(f"Connection error: {error}")
        return None