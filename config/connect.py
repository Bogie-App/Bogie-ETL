import psycopg2
import psycopg2.pool
from .configuration import settings
from .logger import logger

_pool: psycopg2.pool.SimpleConnectionPool | None = None


def get_pool() -> psycopg2.pool.SimpleConnectionPool:
    """Retourne le pool de connexions (singleton). Créé au premier appel."""
    global _pool
    if _pool is None or _pool.closed:
        _pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            **settings.db_config,
        )
        logger.info("Pool de connexions PostgreSQL initialisé (1-5 connexions).")
    return _pool


def get_connection():
    """Récupère une connexion depuis le pool."""
    try:
        pool = get_pool()
        conn = pool.getconn()
        return conn
    except (psycopg2.DatabaseError, Exception) as error:
        logger.error(f"Connection error: {error}")
        return None


def release_connection(conn):
    """Remet une connexion dans le pool."""
    try:
        pool = get_pool()
        pool.putconn(conn)
    except Exception as error:
        logger.error(f"Erreur lors du retour de connexion au pool: {error}")
