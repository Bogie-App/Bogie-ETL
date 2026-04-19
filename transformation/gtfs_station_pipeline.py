from collections.abc import Iterator
import pandas as pd
from config.logger import logger
from models.station import StationLine, StationTiming
from transformation.business_layer.service import _canonical_route, _build_timing_dataframe
from transformation.business_layer.gtfs_joins import (
    _filter_metro_routes,
    _join_trips_to_routes,
    _join_stop_times_to_trips,
    _join_stop_info,
)
from transformation.persistence.metro_data_frame_query import MetroDataFrameView
from transformation.mappers.station_line_mapper import _to_domain , _to_timing_chunks

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
        self._station_repo = MetroDataFrameView(self._df_metro)

    # Use Case 
    def station_lines(self) -> list[StationLine]:

        """Retourne la liste des relations station-ligne avec leur ordre sur le trajet."""
        
        line_names = self._station_repo.list_line_names() # repo
        
        logger.info(f"Lignes métro détectées : {line_names}")

        result: list[StationLine] = []

        for line_name in line_names:
            rows = self._station_repo.get_line_stop_rows(line_name) # repo
            canonical = _canonical_route(rows, line_name) # service
            if canonical.empty:
                continue
            logger.info(f"Trajet {line_name} : {len(canonical)} arrêts")

            result.extend(_to_domain(canonical)) # presentation

        logger.info(f"{len(result)} relations StationLine construites.")

        return result
    
  # Use Case 
    def timing_chunks(
        self,
        df_calendars: pd.DataFrame,
        horizon_days: int = 14,
        chunk_size: int = 10_000,
    ) -> Iterator[list[StationTiming]]:
        """
        Génère des chunks de StationTiming sur une fenêtre glissante de `horizon_days` jours.
        Yields des listes de `chunk_size` objets pour éviter de tout charger en mémoire.

        df_calendars : service_id, date (format YYYYMMDD)
        """

        # logic metier : validation d'entrée
        if horizon_days <= 0:
         raise ValueError(f"horizon_days doit être positif, reçu : {horizon_days}") # validation d'entrée

        logger.info(f"Transformation GTFS -> StationTiming (fenêtre {horizon_days}j, chunks {chunk_size})...")
        
        df = _build_timing_dataframe(
            _df_metro=self._df_metro,
            df_calendars=df_calendars,
            horizon_days=horizon_days,
        ) # service
        logger.info(f"{len(df)} passages à traiter après filtre calendrier.")

        return _to_timing_chunks(df, chunk_size) # presentation

    # logic et travaille trop lourd 
    def _build_metro_dataframe(
        self,
        df_stops: pd.DataFrame,
        df_routes: pd.DataFrame,
        df_trips: pd.DataFrame,
        df_stop_times: pd.DataFrame,
    ) -> pd.DataFrame:
        """Construit le DataFrame central métro en filtrant et croisant les sources GTFS."""
        logger.info("Transformation des données GTFS en objets domaine...")

        df_routes_metro = _filter_metro_routes(df_routes, self.METRO_ROUTE_TYPE)
        df_trips_metro = _join_trips_to_routes(df_trips, df_routes_metro)
        df_stop_times_metro = _join_stop_times_to_trips(df_stop_times, df_trips_metro)
        df_metro = _join_stop_info(df_stop_times_metro, df_stops)

        df_metro['stop_sequence_num'] = pd.to_numeric(df_metro['stop_sequence'], errors='coerce')

        logger.info(f"Routes métro : {df_routes_metro['route_id'].nunique()}")
        logger.info(f"Trips métro  : {df_trips_metro['trip_id'].nunique()}")
        logger.info(f"Stop times métro : {len(df_stop_times_metro)}")
        logger.debug(
            f"Lignes métro disponibles :\n"
            f"{df_routes_metro[['route_id','route_short_name','route_long_name']].drop_duplicates().sort_values('route_short_name').to_string(index=False)}"
        )

        return df_metro