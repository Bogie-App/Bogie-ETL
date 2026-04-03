import pandas as pd
from config.logger import logger
from models.station import Line, Station, StationLine, StationTiming


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
        df_trips_metro[['trip_id', 'route_id', 'route_short_name', 'route_long_name', 'service_id']],
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

        # trip representatif celui qui a le plus d'arrets surement à revoir pour une meilleure approche
        trip_counts = subset.groupby('trip_id', as_index=False)['stop_id'].count().rename(columns={'stop_id': 'nb_stops'})
        trip_id_ref = trip_counts.sort_values('nb_stops', ascending=False).iloc[0]['trip_id']

        trajet = subset[subset['trip_id'] == trip_id_ref].copy()
        trajet = trajet.sort_values('stop_sequence_num')
        trajet = trajet[['route_short_name', 'trip_id', 'stop_sequence_num', 'stop_id', 'stop_name', 'stop_desc', 'stop_lat', 'stop_lon']]
        trajet = trajet.drop_duplicates(subset=['stop_sequence_num', 'stop_id'])
        return trajet.reset_index(drop=True)

    trajet_m1 = trajet_ligne(df_metro, 'M1')
    trajet_m2 = trajet_ligne(df_metro, 'M2')

    logger.info(f"Trajet M1 : {len(trajet_m1)} arrêts")
    logger.info(f"Trajet M2 : {len(trajet_m2)} arrêts")

    station_lines: list[StationLine] = []

    for trajet in [trajet_m1, trajet_m2]:
        if trajet.empty:
            continue
        for _, row in trajet.iterrows():
            station_lines.append(StationLine(
                station=Station(
                    stop_id=row['stop_id'],
                    name=row['stop_name'],
                    description=row['stop_desc'] if row['stop_desc'] else None,
                    latitude=row['stop_lat'],
                    longitude=row['stop_lon'],
                ),
                line=Line(name=row['route_short_name']),
                stop_sequence=int(row['stop_sequence_num']),
            ))

    logger.info(f"{len(station_lines)} relations StationLine construites.")
    return station_lines, df_metro



def _normalize_gtfs_time(gtfs_time: str) -> str:
    """
    Normalise un horaire GTFS en temps PostgreSQL valide (HH:MM:SS)
    GTFS autorise des heures >= 24h pour les trajets après minuit (ex: 24:05:00 -> 00:05:00)
    """
    parts = gtfs_time.strip().split(':')
    hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
    hours = hours % 24
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


# A retravailler pour regrouper les mêmes horaires 
def station_timing_dataframe(df_metro: pd.DataFrame) -> list[StationTiming]:
    """
    Extrait les horaires depuis df_metro
    df_metro contient : stop_id, route_short_name, arrival_time, departure_time
    """
    logger.info("Transformation GTFS -> StationTiming...")

    df = df_metro[['stop_id', 'route_short_name', 'arrival_time', 'departure_time']].dropna()

    station_timings = [
        StationTiming(
            stop_id=row['stop_id'],
            line_name=row['route_short_name'],
            arrival_time=_normalize_gtfs_time(row['arrival_time']),
            departure_time=_normalize_gtfs_time(row['departure_time']),
        )
        for _, row in df.iterrows()
    ]

    logger.info(f"{len(station_timings)} horaires construits.")
    return station_timings


