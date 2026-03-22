from config.configuration import Settings
from config.connect import connect
from config.logger import logger
from psycopg2.extras import execute_values


def is_stations_table_empty() -> bool:
    """Retourne True si la table stations est vide."""
    connection = connect()
    if connection is None:
        logger.error("Connexion à la base de données échouée. Contrôle annulé.")
        return False

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT NOT EXISTS (SELECT 1 FROM stations LIMIT 1);")
            result = cursor.fetchone()
            return bool(result[0]) if result else False
    except Exception as e:
        logger.error(f"Erreur lors du contrôle de la table stations : {e}")
        return False
    finally:
        connection.close()


def insert_stations_batch(stations):
    print("Insertion dans la base de données...")
    """Insère des données table stations.
    Args:
    """
    if not stations:
        logger.info("Aucune station à insérer.")
        return

    connection = connect()
    if connection is None:
        logger.error("Connexion à la base de données échouée. Insertion annulée.")
        return

    try:
        with connection.cursor() as cursor:
            
            # create_at, update_at automatiquement gérés par la base de données avec des valeurs par défaut
            insert_query = """
                INSERT INTO stations (name, address, line, latitude, longitude)
                VALUES %s
            """
            station_data = [
                (
                    station.name,
                    station.address,
                    station.line,
                    station.latitude,
                    station.longitude
                )
                for station in stations
            ]

            execute_values(cursor, insert_query, station_data)
            connection.commit()
            logger.info(f"{len(stations)} stations insérées dans la base de données.")
    except Exception as e:
        connection.rollback()
        logger.error(f"Erreur lors de l'insertion batch : {e}")
    finally:
        connection.close()

    
    print("Données insérées avec succès.")