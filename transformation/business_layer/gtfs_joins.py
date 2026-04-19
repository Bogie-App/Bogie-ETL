
# Ce que _build_metro_dataframe devrait déléguer à des méthodes focalisées
import pandas as pd


def _filter_metro_routes(df_routes, METRO_ROUTE_TYPE) -> pd.DataFrame:
    return df_routes[df_routes['route_type'].astype(str) == METRO_ROUTE_TYPE].copy()

def _join_trips_to_routes(df_trips, df_metro_routes) -> pd.DataFrame:
    return df_trips.merge(
        df_metro_routes[['route_id', 'route_short_name', 'route_long_name']],
        on='route_id',
        how='inner',
    )

def _join_stop_times_to_trips(df_stop_times, df_metro_trips) -> pd.DataFrame:
    return df_stop_times.merge(
        df_metro_trips[['trip_id', 'route_id', 'route_short_name', 'route_long_name', 'service_id', 'direction_id']],
        on='trip_id',
        how='inner',
    )

def _join_stop_info(df_times, df_stops) -> pd.DataFrame:
    return df_times.merge(
        df_stops[['stop_id', 'stop_name', 'stop_desc', 'stop_lat', 'stop_lon']],
        on='stop_id',       
        how='left',     
    )
