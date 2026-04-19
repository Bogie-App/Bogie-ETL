from datetime import datetime, timedelta

import pandas as pd

# Le stop canonique = le plus fréquent par séquence
def _canonical_route(df_metro, line_name) -> pd.DataFrame:
    """
    Construit la séquence canonique d'arrêts pour une ligne.
    Pour chaque stop_sequence, retient le stop_id le plus fréquent
    parmi tous les trips — approche robuste face aux services partiels.
    """
    subset = df_metro[
        df_metro['route_short_name'].astype(str) == line_name
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
    _df_metro: pd.DataFrame,
    df_calendars: pd.DataFrame,
    horizon_days: int,
) -> pd.DataFrame:
    """Filtre et normalise le DataFrame des horaires sur la fenêtre glissante."""
    today = datetime.today().strftime('%Y%m%d')
    horizon = (datetime.today() + timedelta(days=horizon_days)).strftime('%Y%m%d')

    metro_service_ids = set(_df_metro['service_id'].dropna().unique())

    # logic metier
    df_cal_window = df_calendars[
        (df_calendars['date'] >= today) &
        (df_calendars['date'] <= horizon) &
        (df_calendars['service_id'].isin(metro_service_ids))
    ][['service_id', 'date']]

    df_filter = (
        _df_metro[['stop_id', 'route_short_name', 'arrival_time', 'departure_time', 'service_id', 'direction_id']]
        .dropna()
        .merge(df_cal_window, on='service_id', how='inner')
        .copy()
    )

    df_normalze = _normalize_gtfs_times(df_filter)
    df = _compute_day_offset(df_normalze)

    return df
# Une heure GTFS de 25:00 = 01:00 le lendemain
def _normalize_gtfs_times(df) -> pd.DataFrame:
        # Normalisation vectorisée
    for col, out in [('arrival_time', 'arrival_time_norm'), ('departure_time', 'departure_time_norm')]:
        parts = df[col].str.strip().str.split(':', expand=True).astype(int)
        df[out] = (
            (parts[0] % 24).astype(str).str.zfill(2) + ':' +
            parts[1].astype(str).str.zfill(2) + ':' +
            parts[2].astype(str).str.zfill(2)
        )
    arrival_hours = df['arrival_time'].str.strip().str.split(':', expand=True)[0].astype(int)
    df['day_offset'] = arrival_hours // 24
    return df

# La fenêtre glissante = aujourd'hui + 14 jours
def _compute_day_offset(df) -> pd.DataFrame:
    df['date_shifted'] = (
        pd.to_datetime(df['date'], format='%Y%m%d') +
        pd.to_timedelta(df['day_offset'], unit='d')
    ).dt.strftime('%Y%m%d')

    return df
