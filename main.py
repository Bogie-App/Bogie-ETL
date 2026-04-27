import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent

from ingestion.gtfs_loader import gtfs_loader
from repository.metadata_repository import upsert_etl_metadata
from transformation.data_quality.data_quality import DataQualityError, run_quality_checks, clean_dataset
from transformation.data_quality.clean_dataframe import (
    StopCleaner,
    RouteCleaner,
    TripCleaner,
    StopTimeCleaner,
    CalendarCleaner,
)
from repository.station_repository import (
    insert_stations_batch,
    insert_timing_staging_batch,
    swap_timing_staging,
)

from transformation.gtfs_station_pipeline import GTFSTransformer
from config.logger import logger
from config.configuration import settings
from config.config_datasets import PIPELINE_CONFIG

def etl_job() -> None:
    """Job ETL : ingestion => nettoyage => qualité => transformation => insertion atomique."""

    # Ingestion
    result = gtfs_loader(settings)
    if result is None:
        logger.info("Cycle ignoré : GTFS inchangé.")
        return

    (df_stops, df_routes, df_trips, df_stop_times, df_calendar), new_etag = result

    # Transform
    # ---------------
    cleaners = {
        'stops':      StopCleaner(),
        'routes':     RouteCleaner(),
        'trips':      TripCleaner(),
        'stop_times': StopTimeCleaner(),
        'calendar':   CalendarCleaner(),
    }
    cleaned_datasets = {
        name: cleaners[name].clean(clean_dataset(df, PIPELINE_CONFIG[name]))
        for name, df in {
            'stops': df_stops, 'routes': df_routes, 'trips': df_trips,
            'stop_times': df_stop_times, 'calendar': df_calendar,
        }.items()
    }

    # Qualité bloquant si données corrompues
    try:
        run_quality_checks(cleaned_datasets)
    except DataQualityError as e:
        logger.error(f"Cycle annulé — qualité insuffisante : {e}")
        return

    # Transformation
    transformer = GTFSTransformer(
        df_stops=cleaned_datasets['stops'],
        df_routes=cleaned_datasets['routes'],
        df_trips=cleaned_datasets['trips'],
        df_stop_times=cleaned_datasets['stop_times'],
    )
    # ---------------

    insert_stations_batch(transformer.station_lines())

    # Chargement des horaires en staging puis swap atomique
    for chunk in transformer.timing_chunks(cleaned_datasets['calendar'], horizon_days=settings.CALENDAR_DAYS_AHEAD):
        insert_timing_staging_batch(chunk)

    swap_timing_staging()

    # Persistance de l'ETag SEULEMENT après succès complet du pipeline
    # évite d'ignore un cycle à cause d'un crash 
    if new_etag:
        upsert_etl_metadata('source_gtfs_etag', new_etag)


def on_job_event(event: JobExecutionEvent) -> None:
    if event.exception:
        logger.error(f"Cycle ETL échoué : {event.exception}")
    else:
        logger.info("Cycle ETL terminé avec succès.")


def main() -> None:
    logger.info("Lancement du processus ETL...")

    scheduler = BlockingScheduler()
    scheduler.add_job(
        etl_job,
        trigger='interval',
        minutes=settings.CYCLE_INTERVAL_MINUTES,
        id='etl_job',
        next_run_time=datetime.datetime.now(),
        max_instances=1,
        misfire_grace_time=30,
    )
    scheduler.add_listener(on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    logger.info(f"Scheduler démarré cycle toutes les {settings.CYCLE_INTERVAL_MINUTES} minutes")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Arrêt du scheduler ETL")
        scheduler.shutdown()


if __name__ == "__main__":
    main()