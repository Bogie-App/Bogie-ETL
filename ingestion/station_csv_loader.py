import pandas as pd
from config.configuration import Settings
from config.logger import logger

REQUIRED_STATIONS_COLUMNS = {"FID", "nom_statio", "commune", "insee", "ligne", "geom", "objectid"}

def station_csv_loader(settings: Settings | None = None) -> pd.DataFrame:
    """
    Charge les données des stations à partir d'un fichier CSV.
    Args:
        settings (Settings | None): Paramètres de configuration. Si None, les paramètres par défaut seront utilisés.
    Returns:
        pd.DataFrame: Un DataFrame contenant les données des stations.
    """

    if settings is None:
        logger.info("Aucun paramètre de configuration fourni")
        settings = Settings()

    stations_path = settings.input_dir / settings.stations_csv_filename

    if not stations_path.exists():
        raise FileNotFoundError(f"Fichier Stations introuvable : {stations_path}")

    df_stations = pd.read_csv(stations_path)

    # Validation des colonnes attendues
    missing_stations = REQUIRED_STATIONS_COLUMNS - set(df_stations.columns)
    if missing_stations:
        raise ValueError(f"Colonnes manquantes dans le fichier Stations : {missing_stations}")

    return df_stations
