from collections.abc import Iterator
from datetime import datetime, timedelta

import pandas as pd

from config.logger import logger
from models.station import Line, Station, StationLine, StationTiming


class GTFSTransformer:
    """
    Transforme les DataFrames GTFS bruts en objets domaine (StationLine, StationTiming).

    Usage :
        transformer = GTFSTransformer(df_stops, df_routes, df_trips, df_stop_times)
        insert_stations_batch(transformer.station_lines())
        for chunk in transformer.timing_chunks(df_calendars, horizon_days=14):
            insert_station_timings_batch(chunk)
    """

    METRO_ROUTE_TYPE = '1'

    def __init__(
        self,
        df_stops: pd.DataFrame,
        df_routes: pd.DataFrame,
        df_trips: pd.DataFrame,
        df_stop_times: pd.DataFrame,
    ) -> None:
        self._df_metro = self._build_metro_dataframe(df_stops, df_routes, df_trips, df_stop_times)

    def station_lines(self) -> list[StationLine]:
        """Retourne la liste des relations station-ligne avec leur ordre sur le trajet."""
        df_routes_metro = self._df_metro[['route_short_name']].drop_duplicates()
        line_names = sorted(df_routes_metro['route_short_name'].unique())
        logger.info(f"Lignes métro détectées : {line_names}")

        result: list[StationLine] = []
        for line_name in line_names:
            canonical = self._canonical_route(line_name)
            if canonical.empty:
                continue
            logger.info(f"Trajet {line_name} : {len(canonical)} arrêts")
            for row in canonical.itertuples(index=False):
                result.append(StationLine(
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

        logger.info(f"{len(result)} relations StationLine construites.")
        return result

    def timing_chunks(
        self,
        df_calendars: pd.DataFrame,
        horizon_days: int = 14,
        chunk_size: int = 10_000,
    ) -> Iterator[list[StationTiming]]:
        """
        Génère des chunks de StationTiming sur une fenêtre glissante de `horizon_days` jours.
        Yielde des listes de `chunk_size` objets pour éviter de tout charger en mémoire.

        df_calendars : service_id, date (format YYYYMMDD)
        """
        if horizon_days <= 0:
         raise ValueError(f"horizon_days doit être positif, reçu : {horizon_days}")

        logger.info(f"Transformation GTFS -> StationTiming (fenêtre {horizon_days}j, chunks {chunk_size})...")

        df = self._build_timing_dataframe(df_calendars, horizon_days)
        logger.info(f"{len(df)} passages à traiter après filtre calendrier.")

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

    def _build_metro_dataframe(
        self,
        df_stops: pd.DataFrame,
        df_routes: pd.DataFrame,
        df_trips: pd.DataFrame,
        df_stop_times: pd.DataFrame,
    ) -> pd.DataFrame:
        """Construit le DataFrame central métro en filtrant et croisant les sources GTFS."""
        logger.info("Transformation des données GTFS en objets domaine...")

        df_routes_metro = df_routes[
            df_routes['route_type'].astype(str) == self.METRO_ROUTE_TYPE
        ].copy()

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
        df_metro['stop_sequence_num'] = pd.to_numeric(df_metro['stop_sequence'], errors='coerce')

        logger.info(f"Routes métro : {df_routes_metro['route_id'].nunique()}")
        logger.info(f"Trips métro  : {df_trips_metro['trip_id'].nunique()}")
        logger.info(f"Stop times métro : {len(df_stop_times_metro)}")
        logger.debug(
            f"Lignes métro disponibles :\n"
            f"{df_routes_metro[['route_id','route_short_name','route_long_name']].drop_duplicates().sort_values('route_short_name').to_string(index=False)}"
        )

        return df_metro

    def _canonical_route(self, line_name: str) -> pd.DataFrame:
        """
        Construit la séquence canonique d'arrêts pour une ligne.
        Pour chaque stop_sequence, retient le stop_id le plus fréquent
        parmi tous les trips — approche robuste face aux services partiels.
        """
        subset = self._df_metro[
            self._df_metro['route_short_name'].astype(str) == line_name
        ].copy()
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

        stop_info = subset[['stop_id', 'stop_name', 'stop_desc', 'stop_lat', 'stop_lon']].drop_duplicates(subset=['stop_id'])
        trajet = canonical.merge(stop_info, on='stop_id', how='left')
        trajet['route_short_name'] = line_name
        return trajet[['route_short_name', 'stop_sequence_num', 'stop_id', 'stop_name', 'stop_desc', 'stop_lat', 'stop_lon']].reset_index(drop=True)

    def _build_timing_dataframe(
        self,
        df_calendars: pd.DataFrame,
        horizon_days: int,
    ) -> pd.DataFrame:
        """Filtre et normalise le DataFrame des horaires sur la fenêtre glissante."""
        today = datetime.today().strftime('%Y%m%d')
        horizon = (datetime.today() + timedelta(days=horizon_days)).strftime('%Y%m%d')

        metro_service_ids = set(self._df_metro['service_id'].dropna().unique())
        df_cal_window = df_calendars[
            (df_calendars['date'] >= today) &
            (df_calendars['date'] <= horizon) &
            (df_calendars['service_id'].isin(metro_service_ids))
        ][['service_id', 'date']]
        logger.info(f"Dates calendrier retenues : {df_cal_window['date'].nunique()} ({today} → {horizon})")

        df = (
            self._df_metro[['stop_id', 'route_short_name', 'arrival_time', 'departure_time', 'service_id', 'direction_id']]
            .dropna()
            .merge(df_cal_window, on='service_id', how='inner')
            .copy()
        )

        # Normalisation vectorisée
        for col, out in [('arrival_time', 'arrival_time_norm'), ('departure_time', 'departure_time_norm')]:
            parts = df[col].str.strip().str.split(':', expand=True).astype(int)
            df[out] = (
                (parts[0] % 24).astype(str).str.zfill(2) + ':' +
                parts[1].astype(str).str.zfill(2) + ':' +
                parts[2].astype(str).str.zfill(2)
            )

        # day_offset basé sur arrival_time
        arrival_hours = df['arrival_time'].str.strip().str.split(':', expand=True)[0].astype(int)
        df['day_offset'] = arrival_hours // 24

        # Décalage de date vectorisé via pandas Timedelta
        df['date_shifted'] = (
            pd.to_datetime(df['date'], format='%Y%m%d') +
            pd.to_timedelta(df['day_offset'], unit='d')
        ).dt.strftime('%Y%m%d')

        return df