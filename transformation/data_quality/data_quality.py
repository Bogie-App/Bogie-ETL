import re
import pandas as pd
from config.logger import logger
## aligner la logique metier avec clean_dataframe
# Bounding box approximative de la métropole lilloise
_LILLE_LAT = (50.4, 50.8)
_LILLE_LON = (2.8, 3.3)

# Regex horaire GTFS : heures peuvent dépasser 23
_TIME_RE = re.compile(r'^\d{1,3}:[0-5]\d:[0-5]\d$')


class DataQualityError(ValueError):
    """Vérification bloquante échoue."""


def check_stops(df: pd.DataFrame) -> None:
    """Vérifie la qualité du dataset stops."""
    _check_no_null(df, ['stop_id', 'stop_name', 'stop_lat', 'stop_lon'], 'stops')

    lats = pd.to_numeric(df['stop_lat'], errors='coerce')
    lons = pd.to_numeric(df['stop_lon'], errors='coerce')
    out_of_bbox = (
        lats.isna() | lons.isna() |
        ~lats.between(*_LILLE_LAT) |
        ~lons.between(*_LILLE_LON)
    ).sum()
    if out_of_bbox:
        raise DataQualityError(f"[stops] qualité insuffisante : {out_of_bbox} arrêt(s) hors bbox ou coordonnées invalides.")

def check_routes(df: pd.DataFrame) -> None:
    """Vérifie la qualité du dataset routes."""
    _check_no_null(df, ['route_id', 'route_type'], 'routes')

    valid_types = {'0', '1'}
    invalid = ~df['route_type'].astype(str).isin(valid_types)
    if invalid.any():
        logger.warning(f"[routes] {invalid.sum()} route(s) avec route_type invalide : {df.loc[invalid, 'route_type'].unique().tolist()}")


def check_trips(df: pd.DataFrame) -> None:
    """Vérifie la qualité du dataset trips."""
    _check_no_null(df, ['route_id', 'service_id', 'trip_id', 'direction_id'], 'trips')

    invalid_dir = ~df['direction_id'].astype(str).isin({'0', '1'})
    if invalid_dir.any():
        raise DataQualityError(f"[trips] direction_id hors {{0,1}} sur {invalid_dir.sum()} ligne(s).")


def check_stop_times(df: pd.DataFrame) -> None:
    """Vérifie la qualité du dataset stop_times."""
    _check_no_null(df, ['trip_id', 'arrival_time', 'departure_time', 'stop_id', 'stop_sequence'], 'stop_times')

    # Détecter les horaires malformés
    bad_arr = ~df['arrival_time'].str.match(_TIME_RE)
    bad_dep = ~df['departure_time'].str.match(_TIME_RE)
    if bad_arr.any() or bad_dep.any():
        raise DataQualityError(
            f"[stop_times] horaires malformés — arrival: {bad_arr.sum()}, departure: {bad_dep.sum()}."
        )

    # Doublons (trip_id, stop_sequence) cassent la séquence canonique
    dupes = df.duplicated(subset=['trip_id', 'stop_sequence']).sum()
    if dupes:
        logger.warning(f"[stop_times] {dupes} doublon(s) (trip_id, stop_sequence) détectés.")

    # Seuil minimal absolu si le GTFS est corrompu il aura peu de lignes
    if len(df) < 1_000:
        raise DataQualityError(f"[stop_times] volume anormalement faible : {len(df)} lignes (attendu > 1 000).")


def check_calendar(df: pd.DataFrame) -> None:
    """Vérifie la qualité du dataset calendar_dates."""
    _check_no_null(df, ['service_id', 'date'], 'calendar')

    bad_dates = ~df['date'].str.match(r'^\d{8}$')
    if bad_dates.any():
        raise DataQualityError(f"[calendar] {bad_dates.sum()} date(s) au format invalide (attendu YYYYMMDD).")


QUALITY_CHECKS = {
    'stops': check_stops,
    'routes': check_routes,
    'trips': check_trips,
    'stop_times': check_stop_times,
    'calendar': check_calendar,
}


def run_quality_checks(datasets: dict[str, pd.DataFrame]) -> None:
    """Exécute tous les checks de qualité. DataQualityError si bloquant."""
    for name, df in datasets.items():
        check_fn = QUALITY_CHECKS.get(name)
        if check_fn is None:
            continue
        logger.info(f"[quality] Vérification '{name}' ({len(df)} lignes)...")
        check_fn(df)
    logger.info("[quality] Tous les checks passés.")

def clean_dataset(df: pd.DataFrame, expected_columns: list[str]) -> pd.DataFrame:
    """Projette le DataFrame sur les colonnes attendues et lève une erreur si l'une manque."""
    missing = [col for col in expected_columns if col not in df.columns]
    if missing:
        raise DataQualityError(f"Colonnes manquantes dans la source : {missing}")
    return df[expected_columns].copy()

def _check_no_null(df: pd.DataFrame, cols: list[str], name: str) -> None:
    for col in cols:
        nulls = df[col].isnull().sum()
        if nulls:
            logger.warning(f"[{name}] {nulls} valeur(s) nulle(s) dans '{col}'.")
