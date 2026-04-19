import io
import zipfile
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config.configuration import Settings
from config.logger import logger
from repository.metadata_repository import get_etl_metadata

GTFSBundle = tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]
GTFSResult = tuple[GTFSBundle, str | None]


def _build_session() -> requests.Session:
    """Session HTTP avec retry et backoff"""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def gtfs_loader(settings: Settings) -> GTFSResult | None:
    """
    Télécharge les données GTFS statiques si elles ont été modifiées (ETag).
    Retourne (DataFrames, nouvel ETag) ou None si GTFS inchangé (HTTP 304).
    L'ETag n'est PAS persisté ici — le caller le commit après succès du pipeline.
    """
    session = _build_session()
    url = settings.GTFS_STATIC_ILEVIA_URL
    last_etag = get_etl_metadata('source_gtfs_etag')

    req_headers = {}
    if last_etag:
        req_headers['If-None-Match'] = last_etag
        logger.info(f"Vérification de mise à jour avec l'ETag : {last_etag}")

    logger.info(f"Appel de {url}...")
    response = session.get(url, headers=req_headers, timeout=60)

    if response.status_code == 304:
        logger.info("HTTP 304 : GTFS inchangé depuis la dernière ingestion, prenons un petit café ☕ !")
        return None

    response.raise_for_status()

    new_etag = response.headers.get('ETag')
    content = response.content
    logger.info(f"Nouveau GTFS téléchargé ({len(content)} octets). Nouvel ETag récupéré : {new_etag}")

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

    dataframes = (df_stops, df_routes, df_trips, df_stop_times, df_calendar)
    return dataframes, new_etag
