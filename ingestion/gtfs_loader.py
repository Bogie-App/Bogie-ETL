import io
import zipfile
import pandas as pd
from config.configuration import Settings
from config.logger import logger
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _build_session() -> requests.Session:
    """session HTTP avec retry et backoff"""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def gtfs_loader(settings: Settings) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Télécharge les données GTFS statiques d'ilevia
    Retourne (df_stops, df_routes, df_trips, df_stop_times, df_calendar)
    """

    session = _build_session()
    url = settings.GTFS_STATIC_ILEVIA_URL

    # par la suite vérifier si le fichier a changé (ETag / If-None-Match)
    logger.info(f"Téléchargement du GTFS depuis {url}...")
    response = session.get(url, timeout=60)
    response.raise_for_status()
    content = response.content
    logger.info(f"GTFS téléchargé ({len(content)} octets).")

    # Extraction des fichiers CSV
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        logger.debug(f"Fichiers GTFS disponibles : {z.namelist()}")
        with z.open('stops.txt') as f:
            df_stops = pd.read_csv(f, dtype=str, keep_default_na=False)
        with z.open('routes.txt') as f:
            df_routes = pd.read_csv(f, dtype=str, keep_default_na=False)
        with z.open('trips.txt') as f:
            df_trips = pd.read_csv(f, dtype=str, keep_default_na=False)
        with z.open('stop_times.txt') as f:
            df_stop_times = pd.read_csv(f, dtype=str, keep_default_na=False)
        with z.open('calendar_dates.txt') as f:
            df_calendar = pd.read_csv(f, dtype=str, keep_default_na=False)

    logger.info(f"stops={len(df_stops)} | routes={len(df_routes)} | trips={len(df_trips)} | stop_times={len(df_stop_times)} | calendar_dates={len(df_calendar)}")

    return df_stops, df_routes, df_trips, df_stop_times, df_calendar
