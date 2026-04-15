from pathlib import Path
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):

    # GTFS
    GTFS_STATIC_ILEVIA_URL: str = 'https://media.ilevia.fr/opendata/gtfs.zip'
    CYCLE_INTERVAL_MINUTES: int = 1440
    CALENDAR_DAYS_AHEAD: int = 14
    
    # PostgreSQL
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: int

    @property
    def base_dir(self) -> Path:
        """Retourne le répertoire racine du projet."""
        return PROJECT_ROOT

    @property
    def db_config(self) -> dict:
        return {
            "host": self.postgres_host,
            "port": self.postgres_port,
            "dbname": self.postgres_db,
            "user": self.postgres_user,
            "password": self.postgres_password,
        }

settings = Settings()