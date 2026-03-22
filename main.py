import time
from ingestion.station_csv_loader import station_csv_loader
from repository.station_repository import insert_stations_batch, is_stations_table_empty
from transformation.station_normalize import station_normalize
from config.logger import logger

def main():
    logger.info("lancement du processus ETL...")

    while True:
        if not is_stations_table_empty():
            logger.info("La table stations contient déjà des données. ETL ignoré pour ce cycle.")
            
            # fonctionnalité par la suite ...

            logger.info("Cycle de traitement terminé. Attente de 60 secondes...")
            time.sleep(60)
            continue

        logger.info("Table stations vide. Lancement du cycle ETL.")

        logger.info("Phase d'extraction...")
        stations_brut = station_csv_loader()
        logger.info(f"{len(stations_brut)} stations extraites.")

        logger.info("Phase de transformation...")
        stations_cleaning = station_normalize(stations_brut)

        logger.info("Phase de chargement...")
        insert_stations_batch(stations_cleaning)
        logger.info("Processus ETL terminé.")

        # Cycle à préparer
        logger.info("Cycle de traitement terminé. Attente de 60 secondes...")
        time.sleep(60)

if __name__ == "__main__":
    main()