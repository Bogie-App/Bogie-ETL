import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent

from ingestion.gtfs_loader import gtfs_loader
from repository.station_repository import insert_station_timings_batch, insert_stations_batch, purge_old_timings
from transformation.metro_station_dataframe import metro_station_dataframe, station_timing_dataframe
from config.logger import logger
from config.configuration import settings

def etl_job() -> None:
    """Job ETL : ingestion => transformation => insertion."""

    # Purge des horaires expirés avant ingestion
    purge_old_timings(settings.CALENDAR_DAYS_AHEAD)

    # Ingestion
    df_stops, df_routes, df_trips, df_stop_times, df_calendar = gtfs_loader(settings)

    # mettre une vérification de la qualité des données
    # Check()

    # Transformation
    station_lines, df_metro = metro_station_dataframe(df_stops, df_routes, df_trips, df_stop_times)
    # Insertion
    insert_stations_batch(station_lines)

    for chunk in station_timing_dataframe(df_metro, df_calendar, settings.CALENDAR_DAYS_AHEAD):
        insert_station_timings_batch(chunk)


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