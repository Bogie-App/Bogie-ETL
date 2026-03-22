import pandas as pd
from config.logger import logger
from models.station import Station


def _extract_coordinates(geom_value) -> tuple[float | None, float | None]:
    if isinstance(geom_value, dict) and "coordinates" in geom_value:
        coordinates = geom_value.get("coordinates", [])
        if isinstance(coordinates, (list, tuple)) and len(coordinates) >= 2:
            return float(coordinates[1]), float(coordinates[0])

    if isinstance(geom_value, str):
        text = geom_value.strip()
        if text.startswith("POINT") and "(" in text and ")" in text:
            coords = text[text.find("(") + 1:text.rfind(")")].strip().split()
            if len(coords) >= 2:
                return float(coords[0]), float(coords[1])

    return None, None

def station_normalize(df_stations: pd.DataFrame) -> list[Station]:
    """
    Normalise les données des stations pour les rendre compatibles avec la structure de la base de données.
    Args:
        df_stations (pd.DataFrame): DataFrame contenant les données brutes des stations.
    Returns:
        list[Station]: Une liste d'objets Station normalisés prêts à être insérés dans la base de données.
    """
    ####
    # split les transformations par la suite
    ####

    # garder que les colonnes nécessaires pour la base de données
    # objectifid non concluante : a revoir
    df_selection = df_stations[["nom_statio", "commune", "ligne", "geom"]].copy()

    # Séparer les coordonnées géographiques en latitude et longitude
    df_selection[["latitude", "longitude"]] = df_selection["geom"].apply(
        lambda value: pd.Series(_extract_coordinates(value))
    )

    # retirer la colonne geom qui n'est plus nécessaire
    df_selection.drop(columns=["geom"], inplace=True)

    # Renommer les colonnes pour un usage interne propre
    df_cleaning = df_selection.rename(columns={
        "nom_statio": "name",
        "commune": "address",
        "ligne": "line",
    })

    all_stations = [
        Station(**row.to_dict())
        for _, row in df_cleaning.iterrows()
        if pd.notna(row["latitude"]) and pd.notna(row["longitude"])
    ]

    logger.info(f"{len(all_stations)} stations normalisées prêtes pour l'insertion.")

    return all_stations