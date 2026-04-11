from config.connect import get_connection, release_connection
from config.logger import logger
from models.station import StationLine, StationTiming
from psycopg2.extras import execute_values


def purge_old_timings(retention_days: int = 14) -> int:
    """Supprime les horaires dont la date est antérieure à la fenêtre de rétention.
    Retourne le nombre de lignes supprimées."""
    conn = get_connection()
    if conn is None:
        logger.error("Connexion échouée. Purge annulée.")
        return 0

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM station_timing WHERE date < CURRENT_DATE - %s * INTERVAL '1 day'",
                (retention_days,),
            )
            deleted = cursor.rowcount
        conn.commit()
        if deleted:
            logger.info(f"Purge : {deleted} anciens horaires supprimés (rétention {retention_days}j).")
        else:
            logger.info("Purge : aucun ancien horaire à supprimer.")
        return deleted
    except Exception as e:
        conn.rollback()
        logger.error(f"Erreur lors de la purge des anciens timings : {e}")
        return 0
    finally:
        release_connection(conn)

def is_stations_table_empty() -> bool:
    """Retourne True si la table stations est vide"""
    conn = get_connection()
    if conn is None:
        logger.error("Connexion à la base de données échouée. Contrôle annulé.")
        return False

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT NOT EXISTS (SELECT 1 FROM stations LIMIT 1);")
            result = cursor.fetchone()
            return bool(result[0]) if result else False
    except Exception as e:
        logger.error(f"Erreur lors du contrôle de la table stations : {e}")
        return False
    finally:
        release_connection(conn)


def insert_stations_batch(station_lines: list[StationLine]) -> None:
    """
    Insère les données en 3 étapes :
      1. Upsert dans lines
      2. Upsert dans stations
      3. Upsert dans station_line (avec stop_sequence)
    """
    if not station_lines:
        logger.info("Aucune donnée à insérer.")
        return

    conn = get_connection()
    if conn is None:
        logger.error("Connexion à la base de données échouée. Insertion annulée.")
        return

    try:
        with conn.cursor() as cursor:

            # --- 1 Lignes ---
            line_names = list({sl.line.name for sl in station_lines})
            execute_values(
                cursor,
                "INSERT INTO lines (name) VALUES %s ON CONFLICT (name) DO NOTHING",
                [(n,) for n in line_names],
            )
            cursor.execute("SELECT id, name FROM lines WHERE name = ANY(%s)", (line_names,))
            line_map: dict[str, int] = {name: id_ for id_, name in cursor.fetchall()}
            logger.info(f"Lignes en base : {line_map}")

            # --- 2 Stations ---
            seen_stop_ids: set[str] = set()
            station_data = []
            for sl in station_lines:
                s = sl.station
                if s.stop_id not in seen_stop_ids:
                    seen_stop_ids.add(s.stop_id)
                    station_data.append((s.stop_id, s.name, s.description, s.latitude, s.longitude))

            execute_values(
                cursor,
                """
                INSERT INTO stations (stop_id, name, description, latitude, longitude)
                VALUES %s
                ON CONFLICT (stop_id) DO UPDATE SET
                    name        = EXCLUDED.name,
                    description = EXCLUDED.description,
                    latitude    = EXCLUDED.latitude,
                    longitude   = EXCLUDED.longitude,
                    updated_at  = CURRENT_TIMESTAMP
                """,
                station_data,
            )
            stop_ids = list(seen_stop_ids)
            cursor.execute("SELECT id, stop_id FROM stations WHERE stop_id = ANY(%s)", (stop_ids,))
            station_map: dict[str, int] = {stop_id: id_ for id_, stop_id in cursor.fetchall()}
            logger.info(f"{len(station_map)} stations en base.")

            # --- 3 station_line ---
            station_line_data = [
                (station_map[sl.station.stop_id], line_map[sl.line.name], sl.stop_sequence)
                for sl in station_lines
                if sl.station.stop_id in station_map and sl.line.name in line_map
            ]
            execute_values(
                cursor,
                """
                INSERT INTO station_line (station_id, line_id, stop_sequence)
                VALUES %s
                ON CONFLICT (station_id, line_id) DO UPDATE SET
                    stop_sequence = EXCLUDED.stop_sequence
                """,
                station_line_data,
            )
            logger.info(f"{len(station_line_data)} relations station-ligne insérées.")

        conn.commit()
        logger.info("Insertion terminée avec succès.")

    except Exception as e:
        conn.rollback()
        logger.error(f"Erreur lors de l'insertion : {e}")
    finally:
        release_connection(conn)


def insert_station_timings_batch(timings: list[StationTiming]) -> None:
    if not timings:
        return

    conn = get_connection()
    if conn is None:
        logger.error("Connexion échouée. Insertion timing annulée.")
        return

    try:
        with conn.cursor() as cursor:
            # Récupère les ID depuis ce qui existe déjà en base
            stop_ids = list({t.stop_id for t in timings})
            line_names = list({t.line_name for t in timings})

            cursor.execute("SELECT id, stop_id FROM stations WHERE stop_id = ANY(%s)", (stop_ids,))
            station_map = {stop_id: id_ for id_, stop_id in cursor.fetchall()}

            cursor.execute("SELECT id, name FROM lines WHERE name = ANY(%s)", (line_names,))
            line_map = {name: id_ for id_, name in cursor.fetchall()}

            timing_data = [
                (station_map[t.stop_id], line_map[t.line_name], t.arrival_time, t.departure_time, t.date, t.direction)
                for t in timings
                if t.stop_id in station_map and t.line_name in line_map
            ]

            execute_values(
                cursor,
                """
                INSERT INTO station_timing (station_id, line_id, arrival_time, departure_time, date, direction)
                VALUES %s
                ON CONFLICT (station_id, line_id, arrival_time, departure_time, date, direction) DO NOTHING
                """,
                timing_data,
            )
            logger.info(f"{len(timing_data)} horaires insérés.")

        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Erreur insertion timings : {e}")
    finally:
        release_connection(conn)
