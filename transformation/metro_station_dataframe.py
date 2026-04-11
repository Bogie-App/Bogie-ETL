from collections.abc import Iterator
from datetime import datetime, timedelta

import pandas as pd
from config.logger import logger
from models.station import Line, Station, StationLine, StationTiming

# A refacto
def metro_station_dataframe(df_stops: pd.DataFrame,
                            df_routes: pd.DataFrame,
                            df_trips: pd.DataFrame,
                            df_stop_times: pd.DataFrame) -> tuple[list[StationLine], pd.DataFrame]:
    """
    Transforme les données GTFS en liste de StationLine
    Chaque objet représente une station sur une ligne avec son ordre
    """

    logger.info("Transformation des données GTFS en objets domaine...")

    # route_type == 1 => métro
    df_routes_metro = df_routes[df_routes['route_type'].astype(str) == '1'].copy()

    df_trips_metro = df_trips.merge(
        df_routes_metro[['route_id', 'route_short_name', 'route_long_name']],
        on='route_id',
        how='inner',
    )

    df_stop_times_metro = df_stop_times.merge(
        df_trips_metro[['trip_id', 'route_id', 'route_short_name', 'route_long_name', 'service_id', 'direction_id']],
        on='trip_id',
        how='inner',
    )

    df_metro = df_stop_times_metro.merge(
        df_stops[['stop_id', 'stop_name', 'stop_desc', 'stop_lat', 'stop_lon']],
        on='stop_id',
        how='left',
    )

    logger.info(f"Routes métro : {df_routes_metro['route_id'].nunique()}")
    logger.info(f"Trips métro  : {df_trips_metro['trip_id'].nunique()}")
    logger.info(f"Stop times métro : {len(df_stop_times_metro)}")

    lignes_metro = (
        df_routes_metro[['route_id', 'route_short_name', 'route_long_name']]
        .drop_duplicates()
        .sort_values(['route_short_name', 'route_id'])
    )
    logger.debug(f"Lignes métro disponibles :\n{lignes_metro.to_string(index=False)}")

    df_metro['stop_sequence_num'] = pd.to_numeric(df_metro['stop_sequence'], errors='coerce')

    def trajet_ligne(df: pd.DataFrame, line_name: str) -> pd.DataFrame:
        subset = df[df['route_short_name'].astype(str) == line_name].copy()
        if subset.empty:
            return pd.DataFrame()
        
        freq = (
            subset.groupby(['stop_sequence_num', 'stop_id'], as_index=False)
            .agg(count=('trip_id', 'count'))
        )
        canonical = (
            freq.sort_values('count', ascending=False)
            .drop_duplicates(subset=['stop_sequence_num'], keep='first')
            .sort_values('stop_sequence_num')
        )

        # Récupérer les infos de la station depuis le premier match
        stop_info = subset[['stop_id', 'stop_name', 'stop_desc', 'stop_lat', 'stop_lon']].drop_duplicates(subset=['stop_id'])
        trajet = canonical.merge(stop_info, on='stop_id', how='left')
        trajet['route_short_name'] = line_name
        trajet = trajet[['route_short_name', 'stop_sequence_num', 'stop_id', 'stop_name', 'stop_desc', 'stop_lat', 'stop_lon']]
        return trajet.reset_index(drop=True)

    # Découverte dynamique de toutes les lignes de métro
    line_names = sorted(df_routes_metro['route_short_name'].unique())
    logger.info(f"Lignes métro détectées : {line_names}")

    station_lines: list[StationLine] = []

    for line_name in line_names:
        trajet = trajet_ligne(df_metro, line_name)
        if trajet.empty:
            continue
        logger.info(f"Trajet {line_name} : {len(trajet)} arrêts")
        for row in trajet.itertuples(index=False):
            station_lines.append(StationLine(
                station=Station(
                    stop_id=row.stop_id,
                    name=row.stop_name,
                    description=row.stop_desc if row.stop_desc else None,
                    latitude=row.stop_lat,
                    longitude=row.stop_lon,
                ),
                line=Line(name=row.route_short_name),
                stop_sequence=int(row.stop_sequence_num),
            ))

    logger.info(f"{len(station_lines)} relations StationLine construites.")
    return station_lines, df_metro


def _normalize_gtfs_time(gtfs_time: str) -> str:
    """
    Normalise un horaire GTFS en temps PostgreSQL valide (HH:MM:SS).
    GTFS autorise des heures >= 24h pour les trajets après minuit (ex: 24:05:00 -> 00:05:00).
    """
    parts = gtfs_time.strip().split(':')
    hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
    return f"{hours % 24:02d}:{minutes:02d}:{seconds:02d}"


def _gtfs_day_offset(gtfs_time: str) -> int:
    """Retourne le décalage en jours pour un horaire GTFS (1 si après minuit, sinon 0)."""
    return int(gtfs_time.strip().split(':')[0]) // 24


def _shift_date(date_str: str, days: int) -> str:
    """Décale une date GTFS (YYYYMMDD) du nombre de jours donné."""
    if days == 0:
        return date_str
    return (datetime.strptime(date_str, '%Y%m%d') + timedelta(days=days)).strftime('%Y%m%d')

# A refacto
def station_timing_dataframe(
    df_metro: pd.DataFrame,
    df_calendars: pd.DataFrame,
    horizon_days: int = 14,
    chunk_size: int = 10_000,
) -> Iterator[list[StationTiming]]:
    """
    Génère des chunks de StationTiming sur une fenêtre glissante de horizon_days jours
    Yielde des listes de `chunk_siz objets pour éviter de tout charger en mémoire

    df_metro    : stop_id, route_short_name, arrival_time, departure_time, service_id, direction_id
    df_calendars: service_id, date (format YYYYMMDD)
    """
    logger.info(f"Transformation GTFS -> StationTiming (fenêtre {horizon_days}j, chunks {chunk_size})...")

    today = datetime.today().strftime('%Y%m%d')
    horizon = (datetime.today() + timedelta(days=horizon_days)).strftime('%Y%m%d')

    metro_service_ids = set(df_metro['service_id'].dropna().unique())
    df_cal_window = df_calendars[
        (df_calendars['date'] >= today) &
        (df_calendars['date'] <= horizon) &
        (df_calendars['service_id'].isin(metro_service_ids))
    ][['service_id', 'date']]
    logger.info(f"Dates calendrier retenues : {df_cal_window['date'].nunique()} ({today} → {horizon})")

    df = df_metro[['stop_id', 'route_short_name', 'arrival_time', 'departure_time', 'service_id', 'direction_id']].dropna()
    df = df.merge(df_cal_window, on='service_id', how='inner')

    logger.info(f"{len(df)} passages à traiter après filtre calendrier.")

    # Transformation vectorisée normaliser les horaires et dates en colonnes
    df = df.copy()
    df['day_offset'] = df['departure_time'].apply(_gtfs_day_offset)
    df['arrival_time_norm'] = df['arrival_time'].apply(_normalize_gtfs_time)
    df['departure_time_norm'] = df['departure_time'].apply(_normalize_gtfs_time)
    df['date_shifted'] = df.apply(lambda r: _shift_date(r['date'], r['day_offset']), axis=1)

    chunk: list[StationTiming] = []
    for row in df.itertuples(index=False):
        chunk.append(StationTiming(
            stop_id=row.stop_id,
            line_name=row.route_short_name,
            arrival_time=row.arrival_time_norm,
            departure_time=row.departure_time_norm,
            date=row.date_shifted,
            direction=int(row.direction_id),
        ))
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []

    if chunk:
        yield chunk
