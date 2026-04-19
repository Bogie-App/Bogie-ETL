from config.connect import get_connection
from config.logger import logger


def _ensure_etl_metadata_table(conn) -> None:
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS etl_metadata (
                id          SERIAL PRIMARY KEY,
                key         VARCHAR(50) NOT NULL UNIQUE,
                value       TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def get_etl_metadata(key: str) -> str | None:
    conn = get_connection()
    if conn is None:
        logger.error("Connexion à la base de données échouée. Impossible de récupérer les métadonnées.")
        return None
    try:
        _ensure_etl_metadata_table(conn)
        with conn.cursor() as cursor:
            cursor.execute("SELECT value FROM etl_metadata WHERE key = %s", (key,))
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des métadonnées pour '{key}' : {e}")
        return None
    
def upsert_etl_metadata(key: str, value: str) -> None:
    conn = get_connection()
    if conn is None:
        logger.error("Connexion à la base de données échouée. Impossible de mettre à jour les métadonnées.")
        return
    try:
        _ensure_etl_metadata_table(conn)
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO etl_metadata (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (key, value))
            conn.commit()
            logger.info(f"Métadonnée '{key}' mise à jour avec succès.")
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour des métadonnées pour '{key}' : {e}")
        conn.rollback()

