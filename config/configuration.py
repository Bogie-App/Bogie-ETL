from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import HttpUrl

PROJECT_ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    
    print("Loading configuration settings started...")
    
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
    def input_dir(self) -> Path:
        """Retourne le répertoire des fichiers d'entrée."""
        inputs_dir = PROJECT_ROOT / "Inputs"
        return inputs_dir
    
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