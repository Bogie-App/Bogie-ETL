from config.connect import get_connection, release_connection
from config.logger import logger
from models.station import StationLine, StationTiming
from psycopg2.extras import execute_values

### Décorateur de connexion
def with_connection(func):
    def wrapper(*args, **kwargs):
        conn = get_connection()
        if conn is None:
            raise ConnectionError("Connexion à la base de données échouée. Swap staging annulé.")
        try:
            with conn.cursor() as cursor:
                result = func(cursor, *args, **kwargs)  # exécute la fonction décorée

            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur swap staging : {e}")
            raise
        finally:
            release_connection(conn)
    return wrapper

# helper pour récupérer les id en base à partir de valeurs uniques (ex: stop_id, line name)
def get_id_map(cursor, table: str, key_col:str, values: list[str]) -> dict:
    query = f"SELECT id, {key_col} FROM {table} WHERE {key_col} = ANY(%s)"
    cursor.execute(query, ( values,))
    return {key: id_ for id_, key in cursor.fetchall()}

@with_connection
def insert_stations_batch(cursor, station_lines: list[StationLine]) -> None:

    if not station_lines:
        logger.info("Aucune donnée à insérer pour les stations.")
        return
    # --- 1 Lignes ---
    line_names = list({sl.line.name for sl in station_lines})
    execute_values(
        cursor,
        "INSERT INTO lines (name) VALUES %s ON CONFLICT (name) DO NOTHING",
        [(n,) for n in line_names],
    )

    line_map = get_id_map(cursor, 'lines', 'name', line_names)
    logger.info(f"{len(line_map)} lignes en base.")

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

    station_map = get_id_map(cursor, 'stations', 'stop_id', stop_ids)
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

    logger.info("Insertion terminée avec succès.")

@with_connection
def insert_timing_staging_batch(cursor,timings: list[StationTiming]) -> None:
    """Insère un chunk dans la table de staging"""

    if not timings:
        logger.info("Aucune donnée à insérer pour les horaires.")
        return
    
    stop_ids = list({t.stop_id for t in timings})
    line_names = list({t.line_name for t in timings})

    station_map = get_id_map(cursor, 'stations', 'stop_id', stop_ids)
    line_map = get_id_map(cursor, 'lines', 'name', line_names)

    timing_data = [
        (station_map[t.stop_id], line_map[t.line_name], t.arrival_time, t.departure_time, t.date, t.direction)
        for t in timings
        if t.stop_id in station_map and t.line_name in line_map
    ]

    execute_values(
        cursor,
        "INSERT INTO station_timing_staging (station_id, line_id, arrival_time, departure_time, date, direction) VALUES %s",
        timing_data,
    )

@with_connection
def swap_timing_staging(cursor) -> int: 
    cursor.execute("TRUNCATE TABLE station_timing")

    cursor.execute("""
        INSERT INTO station_timing (station_id, line_id, arrival_time, departure_time, date, direction)
        SELECT DISTINCT station_id, line_id, arrival_time, departure_time, date, direction
        FROM station_timing_staging
    """)
    inserted = cursor.rowcount

    cursor.execute("TRUNCATE TABLE station_timing_staging")

    logger.info(f"Swap staging : {inserted} horaires insérés.")
    return inserted