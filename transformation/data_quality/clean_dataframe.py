import pandas as pd

## aligner la logique metier avec data quality
### Donnees de categorie statique (peuvent bouger a long terme)
# === df_stops ===
# stop_id => ne doit pas etre null / unique
# stop_name => ne doit pas etre null
# stop_desc => ne doit pas etre null
# stop_lat => ne doit pas etre null / doit etre dans la bbox de Lille
# stop_lon => ne doit pas etre null / doit etre dans la bbox de Lille

# === df_routes ===
# route_id => ne doit pas etre null / unique
# route_short_name => ne doit pas etre null
# route_long_name => ne doit pas etre null
# route_desc => ne doit pas etre null
# route_type => ne doit pas etre null

# === df_trips ===
# trip_id => ne doit pas etre null / unique
# route_id => ne doit pas etre null
# service_id => ne doit pas etre null
# direction_id => ne doit pas etre null (valeurs attendues: 0 ou 1)

### Donnees de categorie dynamique
# === df_stop_times ===
# trip_id => ne doit pas etre null
# arrival_time => ne doit pas etre null
# departure_time => ne doit pas etre null
# stop_id => ne doit pas etre null
# stop_sequence => ne doit pas etre null
# Contrainte d'unicite recommandee: (trip_id, stop_sequence)

# === df_calendars ===
# service_id => ne doit pas etre null
# date => ne doit pas etre null / format date conforme (YYYYMMDD)
# Contrainte d'unicite recommandee: (service_id, date)

# Classes de nettoyage spécifiques à chaque entité
class EntityCleaner:
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError("Méthode clean() doit être implémentée par les sous-classes.")

# Étapes de nettoyage génériques
class CleaningStep:
    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError("Méthode apply() doit être implémentée par les sous-classes.")

# remplissage des valeurs nulles
class FillNullStep(CleaningStep):
    def __init__(self, column: str, fill_value):
        self.column = column
        self.fill_value = fill_value
    
    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        #verifie que la colonne existe avant de tenter de remplir les nulls
        if(self.column in df.columns):
         df[self.column] = df[self.column].fillna(self.fill_value)
        return df


# convertit les chaines vides en valeurs nulles sur les colonnes cibles
class EmptyToNullStep(CleaningStep):
    def __init__(self, columns: list[str]):
        self.columns = columns

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for column in self.columns:
            if column in df.columns:
                series = df[column]
                if pd.api.types.is_string_dtype(series) or series.dtype == object:
                    series = series.astype(str).str.strip()
                df[column] = series.replace('', pd.NA)
        return df

# suppression des doublons
class DeduplicateStep(CleaningStep):
    def __init__(self, subset: list[str]):
        self.subset = subset

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.drop_duplicates(subset=self.subset)

# suppression des valeurs nulles
class DropNullStep(CleaningStep):
    def __init__(self, columns: list[str]):
        self.columns = columns

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.dropna(subset=self.columns)


# conserve uniquement les lignes dont la colonne appartient a une liste autorisee
class KeepAllowedValuesStep(CleaningStep):
    def __init__(self, column: str, allowed_values: set[str]):
        self.column = column
        self.allowed_values = {str(v).strip() for v in allowed_values}

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.column not in df.columns:
            return df

        filtered = df.copy()
        filtered[self.column] = filtered[self.column].astype(str).str.strip()
        return filtered[filtered[self.column].isin(self.allowed_values)]

# étapes de nettoyage
class DataFramePipeline:
    """Orchestre les étapes de nettoyage."""
    def __init__(self, steps: list[CleaningStep] | None = None):
        self.steps = steps or []

    def add_step(self, step: CleaningStep) -> 'DataFramePipeline':
        self.steps.append(step)
        return self
    
    def execute(self, df: pd.DataFrame) -> pd.DataFrame:
        for step in self.steps:
            df = step.apply(df)
        return df

# Cleaners spécifiques à chaque entité
# === df_stops ===
class StopCleaner(EntityCleaner):
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        return DataFramePipeline() \
            .add_step(EmptyToNullStep(['stop_id', 'stop_name', 'stop_desc', 'stop_lat', 'stop_lon'])) \
            .add_step(DropNullStep(['stop_id', 'stop_name', 'stop_desc', 'stop_lat', 'stop_lon'])) \
            .add_step(DeduplicateStep(subset=['stop_id'])) \
            .execute(df)

# === df_routes ===
class RouteCleaner(EntityCleaner):
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        return DataFramePipeline() \
            .add_step(EmptyToNullStep(['route_id', 'route_short_name', 'route_long_name', 'route_desc', 'route_type'])) \
            .add_step(DropNullStep(['route_id', 'route_short_name', 'route_long_name', 'route_desc', 'route_type'])) \
            .add_step(KeepAllowedValuesStep('route_type', {'0', '1'})) \
            .add_step(DeduplicateStep(subset=['route_id'])) \
            .execute(df)
    
# === df_trips ===
class TripCleaner(EntityCleaner):
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        return DataFramePipeline() \
            .add_step(EmptyToNullStep(['trip_id', 'route_id', 'service_id', 'direction_id'])) \
            .add_step(DropNullStep(['trip_id', 'route_id', 'service_id', 'direction_id'])) \
            .add_step(KeepAllowedValuesStep('direction_id', {'0', '1'})) \
            .add_step(DeduplicateStep(subset=['trip_id'])) \
            .execute(df)
    

### Donnees de categorie dynamique
# === df_stop_times ===
class StopTimeCleaner(EntityCleaner):
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        return DataFramePipeline() \
            .add_step(EmptyToNullStep(['trip_id', 'arrival_time', 'departure_time', 'stop_id', 'stop_sequence'])) \
            .add_step(DropNullStep(['trip_id', 'arrival_time', 'departure_time', 'stop_id', 'stop_sequence'])) \
            .add_step(DeduplicateStep(subset=['trip_id', 'stop_sequence'])) \
            .execute(df)
    
# === df_calendars ===
class CalendarCleaner(EntityCleaner):
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        return DataFramePipeline() \
            .add_step(EmptyToNullStep(['service_id', 'date'])) \
            .add_step(DropNullStep(['service_id', 'date'])) \
            .add_step(DeduplicateStep(subset=['service_id', 'date'])) \
            .execute(df) 
